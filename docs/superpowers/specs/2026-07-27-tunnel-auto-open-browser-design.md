# SSH 隧道启动成功后自动打开浏览器设计

日期：2026-07-27
状态：已批准

## 背景与目标

`scripts/tunnel.bat`（模板 `scripts/tunnel.bat.sample`，见 `2026-07-21-private-access-ssh-tunnel-design.md`）双击后建立 SSH 隧道，用户需自己再开浏览器输入地址。

目标：隧道**确认建立成功后**自动打开 `http://127.0.0.1:5000/`。

核心难点：脚本末尾的 `wsl -d Ubuntu sshpass -e ssh -N ...` 是阻塞前台进程，永不返回，因此「启动成功」这个时点无法靠命令返回码获得，必须靠旁路探测本地 5000 端口。

## 方案选择

- **方案 A（采用）**：独立 helper `scripts/wait_and_open.ps1` 承载轮询逻辑，tunnel.bat 用 `start` 把它甩到后台，前台照旧跑阻塞 ssh。轮询逻辑可读、可单测，helper 不含凭据可入库。
- 方案 B（否决）：把 PowerShell 轮询单行内嵌进 tunnel.bat。保住单文件自包含，但要同时满足 bat 转义（`%`→`%%`）与 PowerShell 语法，改起来极易出错且不可单测。
- 方案 C（否决）：ssh 加 `-f` 后台化，bat 自己探活。隧道脱离窗口生存，关窗口不再断隧道，残留 ssh 进程需手动 kill，与现有「窗口开着 = 隧道在」的心智模型冲突。

## 设计

### 1. 组件划分

**新增 `scripts/wait_and_open.ps1`**（入库，不含任何凭据）。单一职责：轮询一个 URL 直到可访问，然后用默认浏览器打开它，超时则静默退出。

参数：

| 参数 | 默认值 | 说明 |
|---|---|---|
| `-Url` | `http://127.0.0.1:5000/` | 探活与最终打开的地址 |
| `-TimeoutSeconds` | `60` | 总等待上限，超时退出码 1 |
| `-IntervalMs` | `500` | 两次探活间隔 |

**改 `scripts/tunnel.bat.sample` 与 `scripts/tunnel.bat`**。后者是用户本地实文件（含真实凭据，已在 `.gitignore`），同步改但不入库。两处新增：

1. 起 ssh **之前**做端口预检，5000 已被监听则报错 + `pause` + `exit /b 1`
2. 预检通过后把 helper 甩到后台：

```bat
start "" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0wait_and_open.ps1"
```

`%~dp0` 保证从任意工作目录双击都能定位 helper。`-ExecutionPolicy Bypass` 免除 MOTW 意外（本机 CurrentUser 策略为 `RemoteSigned`，git 检出的本地文件本可直接跑，此处只是加固）。

### 2. 成功判定语义

`Invoke-WebRequest -UseBasicParsing -TimeoutSec 3` 请求目标 URL：

- **2xx** → 判定通，打开浏览器，退出码 0
- **4xx/5xx**（PowerShell 5.1 抛 `WebException`，但 `$_.Exception.Response` 非空）→ 同样判定通并打开。理由：隧道通不通与远端 Flask 返回什么状态码是两件事，只要拿到 HTTP 响应就说明转发链路已建立
- **连接被拒 / 超时**（`$_.Exception.Response` 为 null）→ 隧道尚未就绪，等 `IntervalMs` 重试
- **超过 `TimeoutSeconds` 仍无响应** → 退出码 1，静默结束，不弹窗。前台 ssh 窗口自身的报错即诊断入口

选择 HTTP 探活而非 TCP 连通性探测：ssh 认证成功绑定本地端口后 TCP 立即可连，但此时远端 Flask 未必在跑，会打开一个连接被重置的页面。

### 3. 端口预检

```bat
netstat -ano | findstr /R /C:":5000 .*LISTENING"
```

匹配到即说明本机已有进程占用 5000。模式中 `:5000` 后的空格保证 `:50000` 不误命中。

命中时打印提示（占用者可能是本机 `python run.py`，或上一个未关闭的 tunnel 窗口），附 `netstat -ano | findstr :5000` 供用户自查 PID，然后 `pause` 退出，**不起 ssh、不开浏览器**。

此预检杜绝的失败模式：端口被占时 ssh 的 `-L` 绑定失败，但浏览器照旧打开并连上本机服务，用户误以为在看云端数据。

### 4. 失败模式

| 情况 | 表现 |
|---|---|
| 端口已被占用 | 预检拦下，提示 + pause 退出，不开浏览器 |
| ssh 认证失败 | 前台窗口显示 ssh 报错；后台探活超时静默退出，不开浏览器 |
| 隧道通但服务器 Flask 未运行 | ssh 接受 TCP 后 channel 失败 → 无 HTTP 响应 → 判定未通 → 超时不开 |
| 隧道正常 | 通常 1-3 秒探到，浏览器自动打开 |
| 用户关闭 tunnel 窗口 | 后台 powershell 为独立进程，最多再存活 `TimeoutSeconds` 后自行退出，无残留 |

### 5. 文档同步

- `tunnel.bat.sample` 头部注释第 4 步由「keep the window open, then browse http://localhost:5000」改为说明浏览器会自动打开
- `2026-07-21-private-access-ssh-tunnel-design.md` 补一节指向本设计

## 风险与取舍

- helper 与 bat 分离后本地隧道脚本不再纯自包含，依赖同目录的 `wait_and_open.ps1`。两者同在 `scripts/`，`%~dp0` 定位可靠；helper 缺失时 `start` 本身成功拉起 `powershell.exe`，是 powershell 因 `-File` 路径不存在而报错退出，`-WindowStyle Hidden` 使该报错不可见——净行为仍是隧道正常工作，仅退化为不自动开浏览器
- 60 秒超时为固定值，跨网认证极慢时可能错过。可通过 `-TimeoutSeconds` 参数调整，不改代码

## 验收标准

1. `python -m http.server 5000` 起临时服务后运行 `wait_and_open.ps1`，浏览器打开且退出码 0
2. 无任何服务时以 `-TimeoutSeconds 3` 运行，退出码 1 且不打开浏览器
3. 临时服务占用 5000 时运行 tunnel.bat，预检拦截并退出，不起 ssh
4. `git status` 确认 `scripts/tunnel.bat` 仍未被 git 跟踪
