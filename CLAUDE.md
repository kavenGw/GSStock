# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

个人股票管理工具（Flask + SQLAlchemy + SQLite + akshare/yfinance + 智谱GLM/Gemini + APScheduler），OCR 识别用 RapidOCR(ONNX)，行情补充数据源 Twelve Data / Polygon，可选 PyTorch（`app/ml/` AI 走势预测，未安装自动跳过）。
管理多个证券账户的持仓情况，支持上传持仓截图自动识别、多账户合并、操作建议记录。
访问地址：http://127.0.0.1:5000

**通用约定**：响应中文；不写多余注释；不写 backup 文件（git 留痕足够）；所有 git/cargo/npm/pytest 命令前加 `rtk`，链式 `&&` 中也要。

**投研 skill 路由**：个股/持仓/板块投研一律走本仓 skill（`buffett` / `stock-deep-redo` / `analyze-category` / `portfolio-init` / `portfolio-rebalance` / `news-impact` / `liquidation-strategy`）。全局插件 `equity-research` / `investment-banking` / `private-equity` 面向卖方/PE 工作流，**不适用于本仓**，勿因"分析某股"等模糊请求误触发。

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
# 单测（禁用调度器 + UTF-8 编码）—— env 赋值必须在 rtk 之前
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ -v
# 只读 DB 巡检（不走 create_app —— 会启 17 任务 + crawl4ai + LLM）
PYTHONIOENCODING=utf-8 python -c "import sqlite3; c=sqlite3.connect('data/stock.db').cursor(); c.execute('SELECT ...'); ..."
```

## Rules（按需 Read，路径用反引号、不用 @ 触发自动 import）

- `.claude/rules/data-architecture.md` — 数据/缓存/Volume/A 股特征/统一数据 API — 改 services/ 或写 SQL 前
- `.claude/rules/supply-chain.md` — 产业链图谱 SUPPLY_CHAIN_GRAPHS 配置 + tag 同步 — 改 supply_chain.py 或加图谱前
- `.claude/rules/notification-formatting.md` — Slack 频道/盯盘告警 7 类格式/排版规范 — 改推送前
- `.claude/rules/news-and-research.md` — 新闻/公司/华尔街/野村/博客/Trending/Release 配置 — 调轮询或加新源前
- `.claude/rules/esports.md` — NBA/LoL 推送 + 失败重试队列 — 改 esports_service.py 前
- `.claude/rules/watch.md` — 盯盘前端架构 + AI 分析调度（realtime/7d/30d）— 改 watch 模块前
- `.claude/rules/llm.md` — 智谱/Gemini/llama-server 环境变量 — 改 llm/ 前
- `.claude/rules/data-fetch-conventions.md` — akshare/PDF/股票名查询坑/腾讯HTTP/港股/A+H 取数 — 写新数据脚本前
- `.claude/rules/docs-and-portfolio.md` — docs/stock-analytics 目录 + frontmatter + lint + portfolio skill — 写分析、改 frontmatter、跑 lint、调 portfolio 前
- `.claude/rules/dev-conventions.md` — 技术栈/双 DB/测试布局/commit 协议/第三方仓库监控 — 改 schema 或提 commit 前

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- When answering architecture or codebase questions, consult graphify-out/GRAPH_REPORT.md for god nodes and community structure — but the graph may lag recent edits, so treat current source as authoritative on any conflict
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- The graph is a navigation aid, not a source of truth. Optionally refresh after substantial code changes (skip for small edits): `python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"`
- Top god nodes are minified vendor bundles (echarts.min.js / chart.umd.min.js — `E()`, `T()`, `js()` etc.); skip them. Real architectural cores are `Stock`, `MarketIdentifier`, `UnifiedStockCache`, `UnifiedStockDataService`.
