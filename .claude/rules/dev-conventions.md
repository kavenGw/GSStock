# 开发规范与项目元信息

> **何时读**：改 schema、加测试、提 commit、安装第三方仓库（同步 GITHUB_RELEASE_REPOS）、配置环境变量、踩 Windows 编码 / heredoc / 管道吞 stdout / create_app 副作用 等坑
> **不必读**：纯业务逻辑实现（除非需要 commit）

## 技术栈

Flask + SQLAlchemy + SQLite + RapidOCR(ONNX) + Bootstrap5 + 原生 JS。数据：akshare（A股）+ yfinance（美股/港股/期货）+ Twelve Data + Polygon。LLM：智谱 GLM（LITE 免费 glm-4-flash）+ Google Gemini（FLASH/PREMIUM 主力）。调度：APScheduler。可选 PyTorch（`app/ml/` AI 走势预测，未安装自动跳过）。

## 股票代码配置

期货、指数代码配置在 `app/config/stock_codes.py`，股票代码从数据库 `Stock` 和 `StockCategory` 表获取。

**配置项**：期货 / 指数 / 分类代码常量见 `app/config/stock_codes.py`（`FUTURES_CODES` / `INDEX_CODES` / `CATEGORY_CODES` / `CATEGORY_NAMES`）。

**股票代码管理**：
- 股票代码存储在 `Stock` 表，可通过界面编辑
- 股票分类存储在 `StockCategory` 表，关联 `Category` 表

## 数据存储

- 数据库：`data/stock.db`（公共：股票池 / 新闻 / 缓存）
- 私密数据库：`data/private.db`（带 `__bind_key__ = 'private'` 的模型 → Position / RebalanceConfig / StockWeight / PositionPlan / DailySnapshot / Trade / Settlement / BankTransfer）。直连查询用 `sqlite3.connect('data/private.db')`，不要连 `stock.db`
- 内存缓存持久化：`data/memory_cache/{stock_code}/{cache_type}.pkl`
- 上传图片：`uploads/`

## 常用命令的 Windows 坑点

**脚本中查询数据库**（禁用调度器，避免后台任务阻塞）：

```bash
SCHEDULER_ENABLED=0 python -c "from app import create_app; app = create_app(); ..."
```

**Windows 下 python -c 打印含 emoji 的对象**：需指定 UTF-8 避免 cp950 编码错误

```bash
PYTHONIOENCODING=utf-8 python -c "..."
```

**PYTHONIOENCODING 作用域限制**：`PYTHONIOENCODING` 只管 stdout/stderr。`Path.write_text()` / `open()` 写含中文的文件默认仍用 cp950，必须显式 `encoding='utf-8'` 否则 `UnicodeEncodeError`。

**Windows bash 管道吞 stdout**：`| grep` 或 PowerShell `Select-String` 可能静默吞掉 python 脚本 stdout；验证脚本时改用 `open(path, 'w').write(...)` 直接写文件再用 Read 工具读取，稳过管道。

**后台 bash 日志填满输出缓冲**：`2>&1 | tail -N` 时，并行调度的 stderr 日志（429 重试 / apscheduler shutdown）可能填满 N 行，把你的 print 顶出去。解决方案：只关心脚本输出时用 `2>/dev/null`，或把分隔标记写到固定文件再 Read。

**create_app() 启动链路开销**：即便带 `SCHEDULER_ENABLED=0`，`create_app()` 仍会启动调度器（17 任务）+ OCR + crawl4ai + LLM。只测路由/配置层时直接用 `Flask() + register_blueprint(<bp>)` 直接注入，秒级、零副作用。例外：渲染 HTML 的路由会因 base.html 跨 blueprint url_for（briefing.index 等）抛 BuildError → HTML 测试必须走 `create_app()`。

**只读 DB 巡检最快方案**：不需要 `create_app()`，直接 sqlite3 最快：

```bash
PYTHONIOENCODING=utf-8 python -c "import sqlite3; c=sqlite3.connect('data/stock.db').cursor(); c.execute('SELECT ...'); ..."
```

**不确定表名先查 sqlite_master**：表名不一定能从 SQLAlchemy model 名推（`Stock` 类 → 表 `stock` 单数；`StockCategory` 类 → 表 `stock_categories` 复数）。一句话列全表：`c.execute("SELECT name FROM sqlite_master WHERE type='table'"); [print(r[0]) for r in c.fetchall()]`。

**Windows `wc -l` 不可靠**：Git Bash 的 `wc -l` 对 UTF-8 含中文的 markdown 文件偶发误报（实测 156 行报 91）。脚本里算行数用 `python -c "print(sum(1 for _ in open(path, encoding='utf-8')))"`。

**多行 python 嵌套引号 / heredoc 在 Windows bash 易失配**：多行 python 嵌套引号 / heredoc 在 Windows bash 易 `EOF` 失配（`unexpected EOF looking for matching '`）。改用 `Write → scripts/_xxx.py → python scripts/_xxx.py` 跑完 `rm`，比 heredoc 稳。

**`rtk` 与 env 前缀顺序**：env 赋值必须在 `rtk` 之前 —— `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python ...`。写成 `rtk PYTHONIOENCODING=utf-8 ... python` 会让 rtk 把 `PYTHONIOENCODING=utf-8` 当程序名报 `Binary not found`。

**Bash 工具 cwd 跨调用持久**：一次 `cd 子目录 && ...` 会泄漏到后续所有 Bash 调用的 cwd，导致相对路径（`.omc/artifacts/` 等）解析到错目录、文件散落。脚本/校验一律用绝对路径，避免裸 `cd`。

## 开发规范

**测试目录布局**：单测放 `tests/test_*.py` 平铺，不用 `tests/services/` 等子目录（仅存空 `__pycache__`）

**一次性脚本不入库**：仅用于本次任务数据采集 / 验证、不会复用的脚本（如 `scripts/verify_*_quotes.py`），任务结束后必须 `rm`，不进 git。逻辑通过 `.omc/plans/` 计划文件 + commit message 留痕；产物 JSON 可保留在 `.omc/artifacts/`（已 gitignore）。

**`scripts/_xxx.py` 内 import `app` 必加 sys.path**：`python scripts/_xxx.py` 默认只把 `scripts/` 加入 `sys.path`，repo root 不在其中，`from app import create_app` 会 `ModuleNotFoundError: No module named 'app'`。脚本顶部加 `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))`。`run.py` 在 root 不受影响。

**配置变更同步**：新增/修改环境变量配置时，需同步更新 `CLAUDE.md`、`README.md`、`.env.sample` 三处

**安装第三方仓库时**：无论是 Claude Code skill/plugin 还是其他工具仓库，完成安装后需同步添加到 `app/config/github_releases.py` 的 `GITHUB_RELEASE_REPOS`，以便监控新版本

**`git commit --amend` 前重新验证 HEAD**：long-running subagent 完成后做 amend，期间可能有并行 session 已落新 commit，HEAD 已不是你的目标。Amend 前先 `git rev-parse HEAD` 对比预期 SHA；不一致就改成新建 cleanup commit，避免污染他人提交。

**并行 session 抢 git index**：多 Claude session 同跑一仓时，`git add` 暂存的文件会被另一 session 的 `git reset`/`git add` 在你两次 Bash 调用之间清空（实测 staged 下一条命令就消失，`git diff --cached` 变空 → 提交漏文件）。铁律：**`git add` 与 `git commit` 放进同一条 Bash 命令链**（`git add <精确路径...> && git commit -F .git/MSG.txt`，中文多行 message 走文件避免 heredoc 失配），切勿跨工具调用分开；提交后 `git show --stat <sha>` 确认只含本任务文件、未裹挟他人在写档。删除文件用 `git rm -q --ignore-unmatch <path>` 同链处理（文件已不在磁盘时 `git add` 该路径会 pathspec 报错）。
