# 云服务器私有访问（gunicorn 本机监听 + SSH 隧道）实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让云服务器上的应用公网不可见，仅用户本机经 SSH 隧道访问。

**Architecture:** gunicorn 监听地址从 `0.0.0.0:5000` 收敛到 `127.0.0.1:5000`（服务器唯一改动）；本机侧提供 `scripts/tunnel.bat.sample` 模板（WSL Ubuntu 内 sshpass 建 SSH 隧道），用户复制为 `scripts/tunnel.local.bat` 填真实凭据，该文件 gitignore 不入库。

**Tech Stack:** gunicorn 配置、Windows batch、WSL Ubuntu + sshpass + OpenSSH、pytest。

**Spec:** `docs/superpowers/specs/2026-07-21-private-access-ssh-tunnel-design.md`

## Global Constraints

- 所有 git/pytest 命令前加 `rtk`；env 赋值必须在 `rtk` 之前（`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python ...`）
- `git add` 与 `git commit` 必须放同一条 Bash 命令链；中文多行 commit message 写入 `.git/MSG.txt` 后 `git commit -F`，不用 heredoc
- commit message 末尾加 `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`
- 单测平铺 `tests/test_*.py`，不建子目录
- `.bat` 文件内注释只用 ASCII/英文（中文注释在 cp936 控制台下会乱码甚至解析异常）
- 不改 `app/` 代码；本计划共 3 个小文件（1 行配置 + 1 个模板 + 1 行 gitignore），默认在 main 直接执行；如有并行 session 在跑，改为开独立 worktree

---

### Task 1: gunicorn 只监听本机

**Files:**
- Modify: `gunicorn.conf.py:3`
- Test: `tests/test_gunicorn_conf.py`（新建）

**Interfaces:**
- Consumes: 无
- Produces: `gunicorn.conf.py` 中 `bind = "127.0.0.1:5000"`；回归测试锁定该值，防止未来误改回公网监听

- [ ] **Step 1: 写失败测试**

新建 `tests/test_gunicorn_conf.py`：

```python
import importlib.util
from pathlib import Path


def test_gunicorn_binds_localhost_only():
    conf_path = Path(__file__).resolve().parent.parent / "gunicorn.conf.py"
    spec = importlib.util.spec_from_file_location("gunicorn_conf", conf_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.bind == "127.0.0.1:5000"
```

说明：`exec_module` 会执行配置文件里的 `os.makedirs(logs)`，`logs/` 已在 `.gitignore`，无副作用。

- [ ] **Step 2: 运行确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_gunicorn_conf.py -v`
Expected: FAIL，`AssertionError: assert '0.0.0.0:5000' == '127.0.0.1:5000'`

- [ ] **Step 3: 改配置**

`gunicorn.conf.py` 第 3 行：

```python
bind = "127.0.0.1:5000"
```

- [ ] **Step 4: 运行确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_gunicorn_conf.py -v`
Expected: PASS（1 passed）

- [ ] **Step 5: 提交**

```bash
printf 'feat(deploy): gunicorn 只监听 127.0.0.1，应用公网不可见\n\n配套回归测试锁定 bind 值，防误改回 0.0.0.0\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>\n' > .git/MSG.txt && rtk git add gunicorn.conf.py tests/test_gunicorn_conf.py && rtk git commit -F .git/MSG.txt && rtk git show --stat HEAD
```

确认 `git show --stat` 只含这 2 个文件。

---

### Task 2: 隧道脚本模板 + gitignore

**Files:**
- Create: `scripts/tunnel.bat.sample`
- Modify: `.gitignore`（`scripts/_*.txt` 行附近追加一行）

**Interfaces:**
- Consumes: 无（模板独立于 Task 1）
- Produces: 用户复制 `scripts/tunnel.bat.sample` → `scripts/tunnel.local.bat` 填真实凭据后双击建隧道；`scripts/tunnel.local.bat` 被 git 忽略

- [ ] **Step 1: 写模板文件**

新建 `scripts/tunnel.bat.sample`（ASCII 注释；Write 工具默认 UTF-8，纯 ASCII 内容无编码问题）：

```bat
@echo off
REM SSH tunnel to cloud server (see docs/superpowers/specs/2026-07-21-private-access-ssh-tunnel-design.md)
REM Usage:
REM   1. Copy this file to tunnel.local.bat (gitignored, NEVER commit it)
REM   2. Fill in the three values below
REM   3. One-time in WSL Ubuntu: sudo apt install sshpass
REM   4. Double-click tunnel.local.bat; keep the window open, then browse http://localhost:5000
REM Note: avoid passwords containing " or % (breaks batch/wsl quoting); change password if needed

set SERVER_USER=your_user
set SERVER_HOST=your.server.ip
set SERVER_PASS=your_password

wsl -d Ubuntu sshpass -p "%SERVER_PASS%" ssh -N -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=60 -L 5000:127.0.0.1:5000 %SERVER_USER%@%SERVER_HOST%
pause
```

- [ ] **Step 2: .gitignore 追加**

在 `.gitignore` 的 `scripts/_*.txt` 行后追加：

```
scripts/tunnel.local.bat
```

- [ ] **Step 3: 验证 ignore 生效**

```bash
touch scripts/tunnel.local.bat && rtk git check-ignore -v scripts/tunnel.local.bat; rm scripts/tunnel.local.bat
```

Expected: 输出 `.gitignore:<行号>:scripts/tunnel.local.bat`（check-ignore exit 0 = 被忽略）

- [ ] **Step 4: 提交**

```bash
printf 'feat(deploy): SSH 隧道脚本模板（WSL sshpass），tunnel.local.bat 不入库\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>\n' > .git/MSG.txt && rtk git add scripts/tunnel.bat.sample .gitignore && rtk git commit -F .git/MSG.txt && rtk git show --stat HEAD
```

确认只含这 2 个文件。

---

### Task 3: 全量回归 + 服务器端部署验收（手工）

**Files:** 无代码改动

- [ ] **Step 1: 全量单测无回归**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ > .omc/pytest_out.txt 2>&1; grep -E "passed|failed|error" .omc/pytest_out.txt | tail -3
```

Expected: 全 passed，无新增 failed（crawl4ai 进度条走 stdout，必须重定向到文件再 grep，不能用管道 tail）

- [ ] **Step 2: push**

```bash
rtk git push
```

- [ ] **Step 3: 服务器端更新重启（用户/SSH 手工执行）**

服务器上：

```bash
./update_and_run.sh
```

- [ ] **Step 4: 验收——公网不可达**

本机（未开隧道时）：

```bash
curl -m 5 http://服务器IP:5000/ ; echo "exit=$?"
```

Expected: 连接拒绝或超时（exit 7 或 28），不返回 HTTP 200

服务器上确认监听地址已收敛：

```bash
ss -tlnp | grep 5000
```

Expected: `127.0.0.1:5000`，无 `0.0.0.0:5000`

- [ ] **Step 5: 验收——隧道可用**

本机：WSL Ubuntu 内 `sudo apt install sshpass`（一次性）→ 复制 `scripts/tunnel.bat.sample` 为 `scripts/tunnel.local.bat` 填入真实凭据 → 双击运行 → 浏览器打开 `http://localhost:5000` 应正常显示应用。

- [ ] **Step 6: 可选加固（云控制台手工）**

云厂商安全组删除 5000 端口入站规则。
