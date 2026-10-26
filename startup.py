"""跨平台启动、就绪验证及失败清理。"""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, build_opener

ROOT = Path(__file__).resolve().parent
_reports = []


def report(module, status='PASS', detail=''):
    print(f'[{status}] {module}: {detail}', flush=True)
    state = {'module': module, 'status': status, 'detail': detail}
    _reports.append(state)
    path = os.environ.get('GS_STARTUP_STATUS')
    if path and Path(path).parent.exists():
        target = Path(path)
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps(dict(state, reports=_reports)), encoding='utf-8')
        temporary.replace(target)


def wait_ready(url, timeout, process=None, token=None, status_path=None, watched=()):
    deadline = time.monotonic() + timeout
    opener = build_opener(ProxyHandler({}))
    last = '未响应'
    current_module = ''
    seen = 0
    while time.monotonic() < deadline:
        if status_path and Path(status_path).exists():
            state = json.loads(Path(status_path).read_text(encoding='utf-8'))
            last = f"{state['module']}: {state['detail']}"
            current_module = last
            records = state.get('reports', [])
            for record in records[seen:]:
                print(f"[{record['status']}] {record['module']}: {record['detail']}", flush=True)
            seen = len(records)
            if state['status'] == 'FAIL':
                raise RuntimeError(last)
        for child in ([process] if process is not None else []) + list(watched):
            if child.poll() is not None:
                raise RuntimeError(f'进程提前退出，退出码 {child.returncode}; {last}')
        try:
            with opener.open(url, timeout=min(1, max(.01, deadline - time.monotonic()))) as response:
                data = json.load(response)
                if token is None:
                    if data.get('status') == 'ok':
                        return
                elif data.get('token') == token and data.get('ready') is True:
                    return
                else:
                    raise RuntimeError('端口响应来自其他进程或应用未就绪')
        except HTTPError as exc:
            if exc.code != 503:
                raise RuntimeError(f'健康检查 HTTP {exc.code}') from exc
            last = '服务仍在初始化 (503)'
        except (URLError, TimeoutError, ConnectionError) as exc:
            last = str(exc)
        time.sleep(min(.2, max(0, deadline - time.monotonic())))
    raise TimeoutError(f'等待 {timeout:g} 秒仍未就绪: {current_module}; {last}')


def stop_process(process):
    if os.name == 'nt':
        if process.poll() is None:
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
    process.wait(timeout=10)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--detach', action='store_true')
    args = parser.parse_args()
    if args.detach and os.name == 'nt':
        parser.error('--detach 仅用于 Linux 服务')
    def interrupted(signum, frame):
        raise KeyboardInterrupt(f'收到信号 {signum}')
    signal.signal(signal.SIGTERM, interrupted)
    os.chdir(ROOT)
    children = []
    detached = False
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / '.env')
        timeout = float(os.environ.get('STARTUP_TIMEOUT', '120'))
        llama_timeout = float(os.environ.get('LLAMA_STARTUP_TIMEOUT', '300'))
        if not 0 < timeout < float('inf') or not 0 < llama_timeout < float('inf'):
            raise ValueError('启动超时必须是正数')
        with socket.socket() as probe:
            probe.bind(('127.0.0.1', 5000))
        logs = ROOT / 'logs'
        logs.mkdir(exist_ok=True)

        def launch(command, logfile, env=None):
            with (logs / logfile).open('ab') as output:
                process = subprocess.Popen(command, cwd=ROOT, env=env,
                                           stdin=subprocess.DEVNULL,
                                           stdout=output, stderr=subprocess.STDOUT,
                                           start_new_session=os.name != 'nt',
                                           creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            children.append(process)
            return process

        if os.environ.get('LLAMA_SERVER_ENABLED', 'false').lower() == 'true':
            url = os.environ.get('LLAMA_SERVER_URL', 'http://127.0.0.1:8080').rstrip('/')
            llama = None
            if os.name == 'nt' and url in ('http://127.0.0.1:8080', 'http://localhost:8080'):
                with socket.socket() as probe:
                    occupied = probe.connect_ex(('127.0.0.1', 8080)) == 0
                if not occupied:
                    model = Path(os.environ.get('LLAMA_MODEL_PATH', r'D:\Models\Qwen_Qwen3.5-9B-Q4_K_M.gguf'))
                    if not model.is_file():
                        raise FileNotFoundError(f'llama-server 模型不存在: {model}')
                    llama = launch(['llama-server', '-m', str(model), '-ngl', '99',
                                    '-c', '4096', '--port', '8080'], 'llama-startup.log')
            report('llama-server', 'WAIT', url)
            wait_ready(url + '/health', llama_timeout, llama)
            report('llama-server')
        else:
            report('llama-server', 'SKIP', '未启用')

        with tempfile.TemporaryDirectory(prefix='gsstock-startup-') as directory:
            token = uuid.uuid4().hex
            status_path = str(Path(directory) / 'status.json')
            env = dict(os.environ, GS_STARTUP_TOKEN=token, GS_STARTUP_STATUS=status_path,
                       PYTHONUNBUFFERED='1', PYTHONUTF8='1')
            command = [sys.executable, 'run.py'] if os.name == 'nt' else [
                sys.executable, '-m', 'gunicorn', '-c', 'gunicorn.conf.py',
                '--timeout', str(int(timeout) + 10), 'run:app']
            app_process = launch(command, 'startup.log', env)
            report('Web / 模块初始化', 'WAIT', 'logs/startup.log')
            wait_ready('http://127.0.0.1:5000/_startup/ready', timeout,
                       app_process, token, status_path, children[:-1])
            if any(child.poll() is not None for child in children):
                raise RuntimeError('启动的进程已退出')
        report('GSStock', detail='所有启用模块验证通过，http://127.0.0.1:5000；明细 logs/startup.log')
        if args.detach:
            (ROOT / 'gsstock.pid').write_text(str(app_process.pid), encoding='ascii')
            detached = True
            return 0
        return app_process.wait()
    except (Exception, KeyboardInterrupt) as exc:
        print(f'[FAIL] 启动失败: {exc}\n日志: {ROOT / "logs"} (startup.log / error.log / llama-startup.log)',
              file=sys.stderr, flush=True)
        return 1
    finally:
        if not detached:
            for child in reversed(children):
                try:
                    stop_process(child)
                except (OSError, subprocess.TimeoutExpired) as exc:
                    print(f'[FAIL] 清理进程 {child.pid} 失败: {exc}', file=sys.stderr)


if __name__ == '__main__':
    sys.exit(main())
