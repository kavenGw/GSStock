# 开发环境与工作流

> **何时读**：跑脚本/查 DB、提 commit、改或跑 `.bat`/`.ps1`、踩 Windows 编码/heredoc/管道坑、git 协议（并行 session）、分支策略、测试布局

## Windows 坑点

- **编码**：`python -c` 打印含中文/emoji 需 `PYTHONIOENCODING=utf-8`；它只管 stdout/stderr，`open()`/`write_text()` 必须显式 `encoding='utf-8'`。
- **env 前缀在 `rtk` 之前**：`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python ...`，反过来 rtk 会把 env 当程序名。
- **`.bat`/`.ps1` 纯 ASCII**（铁律）：系统 ACP 是 950，UTF-8 中文会错乱行边界。`.bat` 满屏 not recognized；`.ps1` **静默吞掉注释的下一行且 ParseErrors=0**，更危险。改完用 `python -c "d=open(p,'rb').read(); print(sum(1 for b in d if b>127))"` 校验为 0；选纯 ASCII 不加 BOM。判 `.ps1` 语句是否存在用 Parser AST（`[System.Management.Automation.Language.Parser]::ParseFile`）而非「能跑」。
- **别执行非 `.bat`/`.cmd` 后缀的批处理**（如 `.bat.sample`）：cmd 走 ShellExecute 当文档打开，拉起 VS Code 并阻塞。要跑先复制成 `.bat`。从 Bash 调 cmd 会被 MSYS 改写 `/c` 等 token，改用 PowerShell `& cmd /c "$path"`。
- **`cmd /c "cmd1 & echo %errorlevel%"` 读到的是旧值**（整行预展开）。取退出码分离命令或用 PowerShell `$LASTEXITCODE`。
- **管道吞 stdout**：`| grep` / `Select-String` 可能吞掉 python 输出；验证脚本改为写文件再 Read。后台任务的 stderr（429 重试 / apscheduler）会把 `2>&1 | tail` 填满；crawl4ai 进度条走 **stdout**，`2>/dev/null` 挡不住。跑测试看结果：`pytest ... > 文件 2>&1; grep -E "passed|failed" 文件`。
- **heredoc / 多行嵌套引号易失配**：改用 `Write → scripts/_xxx.py → python scripts/_xxx.py`，跑完 `rm`。脚本内 import `app` 需 `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))`。
- **`wc -l` 对含中文 md 不可靠**，用 `python -c "print(sum(1 for _ in open(p, encoding='utf-8')))"`。
- **Bash cwd 跨调用持久**：不裸 `cd`，一律绝对路径。

## create_app 与 DB

- `create_app()` 即便 `SCHEDULER_ENABLED=0` 仍会启调度器（17 任务）+ OCR + crawl4ai + LLM。只测路由/配置层用 `Flask() + register_blueprint(<bp>)`；渲染 HTML 的路由因 base.html 跨 blueprint `url_for` 必须走 `create_app()`。
- 只读巡检直接 sqlite3：`PYTHONIOENCODING=utf-8 python -c "import sqlite3; c=sqlite3.connect('data/stock.db').cursor(); ..."`。
- 表名先查 `sqlite_master`（`Stock`→`stock`，`StockCategory`→`stock_categories`，不可从类名推）。

## 分支与测试

- **投研写档在 main，功能开 worktree**：`stock-research` / `buffett` / `analyze-category` / `portfolio-rebalance` / `liquidation-strategy` 等往 `docs/stock-analytics/` 写档的 skill 在 main 跑（跨档 `related_docs` 对称与 lint 依赖同一工作树）；改 `app/` 代码先开独立 worktree。
- 单测平铺 `tests/test_*.py`，不建子目录。
- 一次性脚本（`scripts/_xxx.py`、`verify_*`）任务结束 `rm`，不入库；产物可留 `.omc/artifacts/`。
- 新增/修改环境变量同步 `CLAUDE.md`、`README.md`、`.env.sample`。装第三方仓库后同步 `GITHUB_RELEASE_REPOS`（见 news-and-research.md）。

## Git 协议（并行 session）

- **`git add` 与 `git commit` 同一条命令链**：`git add <精确路径...> && git commit -F .git/MSG.txt`（中文 message 走文件）。跨工具调用分开会被另一 session 的 `reset`/`add` 清空暂存区。删除用 `git rm -q --ignore-unmatch <path>` 同链。
- **同链只 add 会入库的路径**：混入 gitignore 路径（`.superpowers/`、`.omc/`）会让 `git add` 报错，链在 commit 前中止、提交静默没落地。
- **别用 `git commit -- <pathspec>`**：它绕过 index 直接取工作区，会裹挟并行 session 在写改动。
- **`valuations.yaml` 等单文件聚合无法按条目分离暂存**：连带提交对方条目并在 message 注明即可，勿回退对方内容。提交后 `git show HEAD:<file>` 复核自己那条真的落库，sync 脚本自报不可信。
- **amend 前 `git rev-parse HEAD` 核对**，HEAD 已变则改新建 commit。
- **验证 commit 没脱链用 `git merge-base --is-ancestor <SHA> HEAD`**，别信 `git log -N` 短列表。
- **删路由/服务模块前全仓 grep importer**：`grep -rn "from app.routes.<mod> import\|app.services.<mod>"`，service 常函数级惰性 import 且在 `try` 外，漏删会静默 500。删后跑全量 pytest 并补 smoke 测试。
