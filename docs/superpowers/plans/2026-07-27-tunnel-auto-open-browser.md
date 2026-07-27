# SSH 隧道启动成功后自动打开浏览器 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 双击 `scripts/tunnel.bat` 建立 SSH 隧道后，确认隧道真的通了再自动用默认浏览器打开 `http://127.0.0.1:5000/`。

**Architecture:** 隧道命令 `wsl ... ssh -N` 是永不返回的阻塞前台进程，因此「启动成功」只能靠旁路探测。新增独立 helper `scripts/wait_and_open.ps1` 承载 HTTP 轮询逻辑，由 bat 用 `start` 甩到后台运行；bat 前台照旧跑阻塞 ssh。起 ssh 之前先做 5000 端口预检，占用则报错退出，避免浏览器打开的其实是本机服务。

**Tech Stack:** Windows batch (cmd)、Windows PowerShell 5.1（`Invoke-WebRequest` / `Start-Process`）、`netstat` + `findstr`。无新增第三方依赖。

设计文档：`docs/superpowers/specs/2026-07-27-tunnel-auto-open-browser-design.md`

## Global Constraints

- 响应中文；不写多余注释（只保留关键流程注释）；不留 backup 文件
- 所有 git 命令前加 `rtk`（链式 `&&` 中也要）
- **`git add` 与 `git commit` 必须放进同一条 Bash 命令链**，切勿跨工具调用分开（并行 session 会抢 git index，实测 staged 文件下一条命令就消失）
- `scripts/tunnel.bat` 与 `scripts/tunnel.local.bat` 均在 `.gitignore` 内，含真实服务器凭据，**绝不 `git add`**；只有 `scripts/tunnel.bat.sample` 入库
- 目标 URL 固定为 `http://127.0.0.1:5000/`（不用 `localhost`）
- 探活默认参数：超时 60 秒、间隔 500ms
- PowerShell 目标版本为 Windows PowerShell 5.1，**不可使用 PS 6+ 专有参数**（如 `Invoke-WebRequest -NoProxy`、`-SkipHttpErrorCheck`）
- 本机 PowerShell CurrentUser 执行策略为 `RemoteSigned`；调用 helper 一律带 `-ExecutionPolicy Bypass`

## File Structure

| 文件 | 动作 | 职责 |
|---|---|---|
| `scripts/wait_and_open.ps1` | 新建（入库） | 唯一职责：轮询一个 URL 直到可访问，成功即用默认浏览器打开并 exit 0，超时 exit 1。不含任何凭据、不感知 ssh |
| `scripts/tunnel.bat.sample` | 修改（入库） | 隧道脚本模板。新增端口预检 + 后台拉起 helper；ssh 调用本身不变 |
| `scripts/tunnel.bat` | 修改（**不入库**） | 用户本地实文件，含真实凭据。与 sample 同步同样两处改动，凭据行保持原样 |
| `docs/superpowers/specs/2026-07-21-private-access-ssh-tunnel-design.md` | 修改（入库） | 原隧道设计文档，补一节指向本次设计 |

---

### Task 1: 探活 helper `scripts/wait_and_open.ps1`

**Files:**
- Create: `scripts/wait_and_open.ps1`

**Interfaces:**
- Consumes: 无
- Produces: 命令行契约，Task 2 依赖此契约调用
  - 调用形式：`powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "<path>\wait_and_open.ps1"`
  - 参数：`-Url <string>`（默认 `http://127.0.0.1:5000/`）、`-TimeoutSeconds <int>`（默认 `60`）、`-IntervalMs <int>`（默认 `500`）
  - 退出码：`0` = 探到并已打开浏览器；`1` = 超时未探到，未打开浏览器
  - stdout：成功打印 `Tunnel is up, opening <url>`；超时打印 `Timed out after <n> s, <url> never responded`

- [ ] **Step 1: 先写失败验证（超时路径）**

helper 还不存在，先确认调用它会失败——这就是本任务的「失败的测试」。

Run（在仓库根目录 `D:\Git\stock`）：

```bash
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/wait_and_open.ps1 -Url http://127.0.0.1:5999/ -TimeoutSeconds 3; echo "EXIT=$?"
```

Expected: PowerShell 报 `The argument ... does not exist` / `无法找到路径`，`EXIT=1`（文件不存在导致的失败，不是超时逻辑生效）。

- [ ] **Step 2: 写 helper**

创建 `scripts/wait_and_open.ps1`，内容完整如下：

```powershell
<#
轮询 URL 直到可访问，成功后用默认浏览器打开。由 tunnel.bat 后台调用。
退出码：0 = 已打开；1 = 超时未探到。
#>
param(
    [string]$Url = 'http://127.0.0.1:5000/',
    [int]$TimeoutSeconds = 60,
    [int]$IntervalMs = 500
)

# 全局代理（Clash/v2ray 等）可能截走 127.0.0.1 请求，显式禁用
[System.Net.WebRequest]::DefaultWebProxy = $null

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)

while ((Get-Date) -lt $deadline) {
    $reachable = $false
    try {
        Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3 | Out-Null
        $reachable = $true
    } catch {
        # 拿到 HTTP 响应（含 4xx/5xx）即说明转发链路已建立；连接被拒时 Response 为 null
        if ($_.Exception.Response) { $reachable = $true }
    }

    if ($reachable) {
        Write-Host "Tunnel is up, opening $Url"
        Start-Process $Url
        exit 0
    }

    Start-Sleep -Milliseconds $IntervalMs
}

Write-Host "Timed out after $TimeoutSeconds s, $Url never responded"
exit 1
```

写文件时必须显式 `encoding='utf-8'`（Windows 下默认 cp950 会对注释里的中文抛 `UnicodeEncodeError`）。

- [ ] **Step 3: 验证超时路径**

5999 端口上没有任何服务，脚本应轮询 3 秒后放弃、不开浏览器。

Run:

```bash
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/wait_and_open.ps1 -Url http://127.0.0.1:5999/ -TimeoutSeconds 3; echo "EXIT=$?"
```

Expected: 输出 `Timed out after 3 s, http://127.0.0.1:5999/ never responded`，`EXIT=1`，**没有浏览器窗口弹出**。

- [ ] **Step 4: 起临时服务，验证成功路径**

先用 Bash 工具的 `run_in_background` 起临时 HTTP 服务（用 5999 避开可能在跑的本机 Flask）：

```bash
python -m http.server 5999
```

然后前台跑：

```bash
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/wait_and_open.ps1 -Url http://127.0.0.1:5999/ -TimeoutSeconds 10; echo "EXIT=$?"
```

Expected: 输出 `Tunnel is up, opening http://127.0.0.1:5999/`，`EXIT=0`，**默认浏览器弹出一个目录列表页**（这是预期的，验证完手动关掉即可）。

若浏览器没弹出但 `EXIT=0`，说明 `Start-Process` 没生效，需排查系统默认浏览器关联，不要放过。

- [ ] **Step 5: 验证 4xx 也判定为通**

临时服务仍在跑，请求一个不存在的路径（返回 404）：

```bash
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/wait_and_open.ps1 -Url http://127.0.0.1:5999/nope -TimeoutSeconds 5; echo "EXIT=$?"
```

Expected: `EXIT=0` 并打开浏览器（页面显示 404）。这证明「拿到 HTTP 响应即算隧道通」的分支生效，不会因远端返回错误码而误判未通。

验证完停掉后台的 `python -m http.server 5999`。

- [ ] **Step 6: 提交**

```bash
rtk git add scripts/wait_and_open.ps1 && rtk git commit -m "feat(tunnel): 新增隧道探活 helper wait_and_open.ps1

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

提交后 `rtk git show --stat HEAD` 确认只含 `scripts/wait_and_open.ps1` 一个文件，未裹挟并行 session 的在写档。

---

### Task 2: `tunnel.bat.sample` 端口预检 + 后台拉起 helper

**Files:**
- Modify: `scripts/tunnel.bat.sample`（当前 20 行，改注释第 7 行 + 在 `set WSLENV=SSHPASS` 之前插入两段）
- Modify: `docs/superpowers/specs/2026-07-21-private-access-ssh-tunnel-design.md`（文末追加一节）

**Interfaces:**
- Consumes: Task 1 的 `scripts/wait_and_open.ps1` 命令行契约（`-File` 调用、默认参数即目标行为，故不传任何参数）
- Produces: `scripts/tunnel.bat.sample` 的最终形态，Task 3 逐行复制其中两段改动到本地 `scripts/tunnel.bat`

- [ ] **Step 1: 确认改动前的工作区状态**

`git status` 开局显示 `scripts/tunnel.bat.sample` 已被标记为 modified，但 `git diff` 输出为空（疑似行尾符差异）。动手前先确认清楚，避免把无关改动裹挟进提交。

Run:

```bash
rtk git status --porcelain scripts/ && rtk git diff --stat scripts/tunnel.bat.sample
```

记录输出。若 diff 确为空（仅索引态差异），照常继续；若有实质内容改动，先看清是什么再决定是否一并提交。

- [ ] **Step 2: 写失败验证——占用 5000 时当前脚本毫无反应**

用 Bash 工具 `run_in_background` 起临时服务占住 5000：

```bash
python -m http.server 5000
```

然后确认「检测语句」此刻还不存在于脚本里：

```bash
grep -c "netstat" scripts/tunnel.bat.sample
```

Expected: 输出 `0`（脚本尚无任何端口预检）。这就是本任务要修复的缺口：此时双击脚本，ssh 的 `-L` 绑定会失败，而浏览器仍会打开并连上本机的临时服务。

保持临时服务继续运行，Step 4 要用。

- [ ] **Step 3: 改 `scripts/tunnel.bat.sample`**

改动一，注释第 7 行（原文 `REM   4. Double-click tunnel.local.bat; keep the window open, then browse http://localhost:5000`）替换为两行：

```bat
REM   4. Double-click tunnel.local.bat; the browser opens http://127.0.0.1:5000/ by itself
REM      once the tunnel is up. Keep the window open -- closing it drops the tunnel.
```

改动二，在 `set "SSHPASS=your_password"` 之后、`set WSLENV=SSHPASS` 之前，插入以下内容（注意保留空行分隔）：

```bat
REM 5000 必须空闲，否则 ssh -L 绑定失败而浏览器仍会打开、指向本机服务造成误判
netstat -ano -p TCP | findstr /R /C:":5000 .*LISTENING" >nul
if %errorlevel% equ 0 (
    echo [ERROR] Local port 5000 is already in use -- maybe a local "python run.py"
    echo         or an earlier tunnel window is still running.
    echo         Run "netstat -ano ^| findstr :5000" to find the owning PID.
    pause
    exit /b 1
)

start "" /min powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0wait_and_open.ps1"
```

要点，改的时候别写错：

- `findstr` 模式里 `:5000` 后面那个空格是必需的，否则 `:50000` 会误命中
- `%errorlevel% equ 0` 表示 findstr 找到了匹配（findstr 命中返回 0），即端口**已被占用**
- `echo` 里的管道符必须写成 `^|`，否则 cmd 会当成真管道
- `%~dp0` 自带结尾反斜杠，所以是 `"%~dp0wait_and_open.ps1"` 而非 `"%~dp0\wait_and_open.ps1"`
- helper 不传任何参数，走默认值（`http://127.0.0.1:5000/` / 60 秒 / 500ms）

- [ ] **Step 4: 验证预检拦截（端口被占）**

Step 2 起的临时服务仍占着 5000。直接跑改完的 sample——它会在 ssh 之前就退出，所以用占位凭据跑是安全的（`< /dev/null` 让 `pause` 立刻返回）：

```bash
cmd /c "scripts\\tunnel.bat.sample" < /dev/null; echo "EXIT=$?"
```

Expected:
- 打印 `[ERROR] Local port 5000 is already in use ...` 三行提示
- `EXIT=1`
- **没有** `wsl` / `ssh` 相关输出（说明确实在 ssh 之前就退出了）
- **没有**浏览器弹出

- [ ] **Step 5: 验证端口空闲时预检放行**

停掉后台的 `python -m http.server 5000`，然后只验证预检语句本身（不能整脚本跑，占位凭据会让 ssh 卡住）：

```bash
cmd /c "netstat -ano -p TCP | findstr /R /C:\":5000 .*LISTENING\" >nul"; echo "EXIT=$?"
```

Expected: `EXIT=1`（findstr 未命中 = 端口空闲），对应脚本里 `%errorlevel% equ 0` 不成立、不进 ERROR 分支、继续往下走。

- [ ] **Step 6: 补原设计文档的交叉引用**

在 `docs/superpowers/specs/2026-07-21-private-access-ssh-tunnel-design.md` 文末追加：

```markdown

## 后续演进

- 2026-07-27：隧道建立成功后自动打开浏览器（端口预检 + HTTP 探活），见 `2026-07-27-tunnel-auto-open-browser-design.md`
```

写文件显式 `encoding='utf-8'`。

- [ ] **Step 7: 提交**

```bash
rtk git add scripts/tunnel.bat.sample docs/superpowers/specs/2026-07-21-private-access-ssh-tunnel-design.md && rtk git commit -m "feat(tunnel): tunnel.bat 端口预检 + 后台探活自动开浏览器

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

提交后 `rtk git show --stat HEAD` 确认恰好两个文件，且 `scripts/tunnel.bat` **不在**其中。

---

### Task 3: 同步本地 `scripts/tunnel.bat` 并端到端验证

`scripts/tunnel.bat` 是用户真正双击的文件，含真实服务器 IP / 密码，已被 `.gitignore` 忽略。它与 sample 是同一脚本的两个副本，前两个任务的改动必须手工同步过去，否则改了等于没改。

**Files:**
- Modify: `scripts/tunnel.bat`（**不入库**，全程不得出现在任何 `git add` 中）

**Interfaces:**
- Consumes: Task 2 定稿的 `scripts/tunnel.bat.sample`（逐行对照复制两处改动）
- Produces: 无（终点任务）

- [ ] **Step 1: 确认 tunnel.bat 确实被 git 忽略**

动手前先确认，防止后续误提交凭据。

Run:

```bash
rtk git check-ignore -v scripts/tunnel.bat; echo "EXIT=$?"
```

Expected: 输出 `.gitignore:35:scripts/tunnel.bat  scripts/tunnel.bat`，`EXIT=0`。若 `EXIT=1`（未被忽略），**立即停手**并报告，不要继续改这个文件。

- [ ] **Step 2: 同步两处改动**

把 Task 2 Step 3 的**两处改动原样**应用到 `scripts/tunnel.bat`：注释第 7 行替换成两行，以及在 `set "SSHPASS=..."` 之后、`set WSLENV=SSHPASS` 之前插入端口预检块 + `start ... wait_and_open.ps1` 那行。

**第 13-15 行的三行凭据（`SERVER_USER` / `SERVER_HOST` / `SSHPASS`）保持原样不动**，不要替换成 sample 的占位符。用 Edit 工具做精确替换，不要整文件覆写。

- [ ] **Step 3: 验证两文件仅凭据行不同**

```bash
diff scripts/tunnel.bat scripts/tunnel.bat.sample
```

Expected: diff 只报第 13-15 行三行（`SERVER_USER` / `SERVER_HOST` / `SSHPASS`）不同，其余完全一致。若还报别的行不同，说明同步漏了，回 Step 2 补齐。

- [ ] **Step 4: 端到端实跑**

确认 5000 端口空闲后，请用户双击 `scripts\tunnel.bat`（或在终端 `cmd /c scripts\tunnel.bat`）。

Expected:
- 窗口保持打开，显示 ssh 无输出（`-N` 静默转发）
- 数秒内默认浏览器自动打开 `http://127.0.0.1:5000/`，显示应用首页
- 关闭窗口后隧道断开，页面刷新不可用

这一步需要真实服务器可达，属人工验收。若用户当前无法连服务器，跳过并明确说明「端到端未验证」，不得声称已验证。

- [ ] **Step 5: 收尾确认无凭据泄漏**

```bash
rtk git status --porcelain scripts/
```

Expected: 输出中**不含** `scripts/tunnel.bat`（被忽略故不显示）。若它以 `??` 或 `M` 出现，说明 `.gitignore` 失效，立即停手报告。

本任务无提交（唯一改动的文件不入库）。

---

## Self-Review

**Spec coverage：** 设计文档 6 节全部落到任务——第 1 节组件划分 → Task 1 + Task 2 Step 3；第 2 节成功判定语义（2xx / 4xx-5xx / 连接被拒 / 超时四分支）→ Task 1 Step 2 代码 + Step 3/4/5 分别验证超时、2xx、4xx 三条路径；第 3 节端口预检 → Task 2 Step 3-5；第 4 节失败模式 → 预检拦截（Task 2 Step 4）、超时不开（Task 1 Step 3）已实测，ssh 认证失败与远端 Flask 未起两行归入 Task 3 Step 4 人工验收；第 5 节文档同步 → Task 2 Step 3（注释）+ Step 6（交叉引用）；第 6 节验收标准 4 条 → 分别对应 Task 1 Step 4、Task 1 Step 3、Task 2 Step 4、Task 3 Step 5。

**新增于设计之外的一处实现细节：** helper 顶部 `[System.Net.WebRequest]::DefaultWebProxy = $null`。设计文档未提及，但全局模式代理会截走 `127.0.0.1` 请求导致探活恒失败，与「探测本地端口」的设计意图一致，一行成本，予以保留。

**类型/契约一致性：** helper 文件名 `wait_and_open.ps1` 在 Task 1 Interfaces、Task 1 Step 2/3/4/5、Task 1 Step 6 提交、Task 2 Step 3 调用行、Task 2 Interfaces 中拼写一致；参数名 `-Url` / `-TimeoutSeconds` / `-IntervalMs` 与 param 块一致；退出码语义（0=已开，1=超时）在 Interfaces 与各验证步骤 Expected 中一致。

**端口选择：** Task 1 用 5999 做临时服务（避开可能在跑的本机 Flask），Task 2 必须用 5000（预检写死 5000），两者不冲突且各自 Expected 已写明。
