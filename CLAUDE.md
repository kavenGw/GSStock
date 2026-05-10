# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

个人股票管理工具（Flask + SQLAlchemy + SQLite + akshare/yfinance + 智谱GLM/Gemini + APScheduler）。
管理多个证券账户的持仓情况，支持上传持仓截图自动识别、多账户合并、操作建议记录。
访问地址：http://127.0.0.1:5000

## 硬约束（所有任务通用，不可漏读）

- **响应中文**；不写多余注释 / backup 文件（git 留痕足够）
- **rtk 前缀**：所有 git/cargo/npm/pytest 命令前加 `rtk`，链式 `&&` 中也要
- **测试/脚本环境**：`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0`（Windows + 避免调度器副作用）
- **Volume 单位**：A 股 OHLC/realtime 的 volume 全部"手"（1手=100股）。契约变更 bump `VOLUME_UNIT_SCHEMA_VERSION`
- **缓存时区**：用 `SmartCacheStrategy.get_effective_cache_date()`，禁用 `date.today()`
- **私有数据库**：Position/RebalanceConfig/StockWeight/PositionPlan/DailySnapshot/Trade/Settlement/BankTransfer 带 `__bind_key__='private'`，sqlite3 直连查 `data/private.db` 不是 `stock.db`
- **Flask context 守卫**：`app/services/__init__.py` 模块级单例 init 期访问 `db.session` 必须 `has_app_context()` 守卫
- **stock_name 反查**：先精确 `=` 再 `LIKE 'X%'` fallback；多于 1 行视为冲突放弃
- **commit --amend 前**：先 `git rev-parse HEAD` 比对预期 SHA，并行 session 可能已落新 commit
- **新建分析文档前**：`Glob "docs/**/*<股票名>*"` 和 `Glob "docs/**/*<代码>*"` 找历史档案，正文头部 `>` 反向引用

## 常用命令

```bash
# 启动应用
python run.py
# 一键启动（启动并打开浏览器）
start.bat
# Linux 部署（拉取代码 + 更新依赖 + 重启）
./update_and_run.sh
# 安装依赖
pip install -r requirements.txt
# 单测
rtk PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/ -v
# 只读 DB 巡检（别走 create_app —— 会启 17 任务 + crawl4ai + LLM）
PYTHONIOENCODING=utf-8 python -c "import sqlite3; c=sqlite3.connect('data/stock.db').cursor(); c.execute('SELECT ...'); ..."
```

更多 Windows 编码 / heredoc / 管道吞 stdout 等坑点见 `.claude/rules/dev-conventions.md`。

## Rules（按需 Read，路径用反引号、不用 @ 触发自动 import）

- `.claude/rules/data-architecture.md` — 数据/缓存/Volume/A 股特征/产业链图谱 — 改 services/ 或写 SQL 前
- `.claude/rules/notification-formatting.md` — Slack 频道/盯盘告警 7 类格式/排版规范 — 改推送前
- `.claude/rules/news-and-research.md` — 新闻/公司/华尔街/野村/博客/Trending/Release 配置 — 调轮询或加新源前
- `.claude/rules/esports.md` — NBA/LoL 推送 + 失败重试队列 — 改 esports_service.py 前
- `.claude/rules/watch.md` — 盯盘前端架构 + AI 分析调度（realtime/7d/30d）— 改 watch 模块前
- `.claude/rules/llm.md` — 智谱/Gemini/llama-server 环境变量 — 改 llm/ 前
- `.claude/rules/data-fetch-conventions.md` — akshare/PDF/股票名查询坑 — 写新数据脚本前
- `.claude/rules/docs-and-portfolio.md` — docs 命名 + frontmatter + portfolio skill — 写分析或调 portfolio 前
- `.claude/rules/dev-conventions.md` — 技术栈/双 DB/测试布局/commit 协议/第三方仓库监控 — 改 schema 或提 commit 前

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- After modifying code files in this session, run `python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"` to keep the graph current
- Top god nodes are minified vendor bundles (echarts.min.js / chart.umd.min.js — `E()`, `T()`, `js()` etc.); skip them. Real architectural cores are `Stock`, `MarketIdentifier`, `UnifiedStockCache`, `UnifiedStockDataService`.
