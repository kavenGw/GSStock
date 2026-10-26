import json
import os
from pathlib import Path
import shutil
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import subprocess
import sys
import threading
from types import SimpleNamespace

import pytest

import startup


@pytest.fixture
def health_server():
    state = {'status': 200, 'body': {'ready': True, 'token': 'current'}}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(state['status'])
            self.end_headers()
            self.wfile.write(json.dumps(state['body']).encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{server.server_port}', state
    server.shutdown()
    server.server_close()
    thread.join()


def test_ready_requires_current_instance(health_server):
    url, state = health_server
    startup.wait_ready(url, 1, token='current')
    with pytest.raises(RuntimeError, match='其他进程'):
        startup.wait_ready(url, 1, token='old')


def test_loading_times_out(health_server):
    url, state = health_server
    state['status'] = 503
    with pytest.raises(TimeoutError, match='仍未就绪'):
        startup.wait_ready(url, .1)


def test_dead_process_fails_without_waiting():
    process = subprocess.Popen([sys.executable, '-c', 'raise SystemExit(7)'])
    process.wait()
    with pytest.raises(RuntimeError, match='退出码 7'):
        startup.wait_ready('http://127.0.0.1:1', 120, process)


def test_module_failure_preempts_live_process(tmp_path, monkeypatch):
    path = tmp_path / 'status.json'
    monkeypatch.setenv('GS_STARTUP_STATUS', str(path))
    startup.report('OCR', 'FAIL', '模型损坏')
    with pytest.raises(RuntimeError, match='OCR: 模型损坏'):
        startup.wait_ready('http://127.0.0.1:1', 120, status_path=path)


def test_cleanup_terminates_child():
    process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'],
                               start_new_session=sys.platform != 'win32')
    startup.stop_process(process)
    assert process.poll() is not None


def test_missing_scheduled_job_is_fatal(monkeypatch):
    from app.services.startup_checks import validate_scheduler
    from app.strategies.registry import registry
    monkeypatch.setattr(registry, '_strategies', {})
    scheduler = SimpleNamespace(running=True, get_jobs=lambda: [])
    with pytest.raises(RuntimeError, match='news_poll'):
        validate_scheduler(SimpleNamespace(scheduler=scheduler))


def test_strategy_import_failure_is_fatal(monkeypatch):
    import importlib
    module = importlib.import_module('app.strategies.registry')
    def fail(name):
        raise ImportError('broken dependency')
    monkeypatch.setattr(module.importlib, 'import_module', fail)
    monkeypatch.setattr(module.registry, '_strategies', {})
    with pytest.raises(RuntimeError, match='broken dependency'):
        module.registry.discover()


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows 批处理入口')
def test_batch_propagates_failure():
    env = dict(os.environ, STARTUP_TIMEOUT='invalid', PYTHONUTF8='1')
    result = subprocess.run(['cmd', '/c', str(startup.ROOT / 'start.bat')],
                            env=env, capture_output=True, timeout=15)
    assert result.returncode != 0
    assert b'[FAIL]' in result.stderr


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows 启动器真实子进程')
@pytest.mark.parametrize('mode', ['ready', 'failed', 'timeout'])
def test_launcher_with_real_child(tmp_path, monkeypatch, mode):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(startup, 'ROOT', tmp_path)
    monkeypatch.setenv('LLAMA_SERVER_ENABLED', 'false')
    monkeypatch.setenv('STARTUP_TIMEOUT', '.8' if mode == 'timeout' else '5')
    monkeypatch.setenv('LLAMA_STARTUP_TIMEOUT', '1')
    monkeypatch.setattr(sys, 'argv', ['startup.py'])
    if mode == 'ready':
        source = '''
import json, os, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(json.dumps({'ready': True, 'token': os.environ['GS_STARTUP_TOKEN']}).encode())
server = HTTPServer(('127.0.0.1', 5000), Handler)
threading.Timer(1.5, server.shutdown).start()
server.serve_forever()
server.server_close()
'''
    elif mode == 'failed':
        source = '''
import json, os, time
from pathlib import Path
Path(os.environ['GS_STARTUP_STATUS']).write_text(json.dumps({'module': 'OCR', 'status': 'FAIL', 'detail': 'broken'}))
time.sleep(60)
'''
    else:
        source = 'import time; time.sleep(60)'
    (tmp_path / 'run.py').write_text(source, encoding='utf-8')
    stopped = []
    original_stop = startup.stop_process
    def stop(process):
        original_stop(process)
        stopped.append(process)
    monkeypatch.setattr(startup, 'stop_process', stop)
    assert startup.main() == (0 if mode == 'ready' else 1)
    assert stopped and all(process.poll() is not None for process in stopped)


def test_scheduler_recovery_failure_stops_scheduler(monkeypatch):
    from flask import Flask
    from app.scheduler.engine import SchedulerEngine
    from app.strategies.registry import registry
    monkeypatch.setattr(registry, '_strategies', {})
    engine = SchedulerEngine()
    monkeypatch.setattr(engine, '_check_daily_push_catchup', lambda app: None)
    def fail(app):
        raise RuntimeError('recovery failed')
    monkeypatch.setattr(engine, '_recover_esports_monitors', fail)
    with pytest.raises(RuntimeError, match='recovery failed'):
        engine.init_app(Flask(__name__))
    assert not engine.scheduler.running


def bash_executable():
    candidate = Path(r'C:\Program Files\Git\bin\bash.exe')
    if sys.platform == 'win32':
        if candidate.exists():
            return str(candidate)
        pytest.skip('未安装 Git Bash')
    executable = shutil.which('bash')
    if not executable:
        pytest.skip('未安装 Bash')
    return executable


def test_linux_start_propagates_failure(tmp_path):
    shutil.copyfile(startup.ROOT / 'gsstock', tmp_path / 'gsstock')
    interpreter = tmp_path / 'venv' / 'bin' / 'python'
    interpreter.parent.mkdir(parents=True)
    interpreter.write_text('#!/bin/bash\nexit 7\n', encoding='utf-8')
    interpreter.chmod(0o755)
    result = subprocess.run([bash_executable(), 'gsstock', 'start'],
                            cwd=tmp_path, capture_output=True, timeout=10)
    assert result.returncode == 7


def test_update_stops_on_dependency_failure(tmp_path):
    shutil.copyfile(startup.ROOT / 'update_and_run.sh', tmp_path / 'update_and_run.sh')
    files = {
        'gsstock': '#!/bin/bash\necho "$1" >> calls.txt\n',
        'mock_bin/git': '#!/bin/bash\nexit 0\n',
        'venv/bin/pip': '#!/bin/bash\nexit 9\n',
    }
    for name, content in files.items():
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')
        target.chmod(0o755)
    result = subprocess.run([bash_executable(), '-c',
                             'export PATH="$PWD/mock_bin:$PATH"; exec bash update_and_run.sh'],
                            cwd=tmp_path, capture_output=True, timeout=10)
    assert result.returncode == 9
    assert b'[FAIL]' in result.stderr
    assert (tmp_path / 'calls.txt').read_text().splitlines() == ['stop']
