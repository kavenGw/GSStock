---
paths:
  - "app/services/**"
  - "app/config/github_releases.py"
  - "app/config/blog_monitor.py"
---
# 新闻 / 研报 / 监控源

> **何时读**：调新闻轮询、新增新闻源、改博客/Trending/Release 监控、plugin discovery、加仓库到 GITHUB_RELEASE_REPOS

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `NEWS_INTERVAL_MINUTES` | 新闻轮询间隔（分钟） | `3` |
| `NEWS_FETCH_TIMEOUT` | 新闻源超时（秒） | `15` |
| `NEWS_DEDUP_WINDOW_MINUTES` | 推送去重窗口（分钟） | `1440` |
| `COMPANY_NEWS_MAX_COMPANIES` | 每轮最多处理公司数 | `3` |
| `COMPANY_NEWS_MAX_ARTICLES` | 每公司最多文章数 | `5` |
| `COMPANY_NEWS_INTERVAL_MINUTES` | 公司新闻间隔（分钟） | `30` |
| `WALLSTREET_NEWS_ENABLED` | 华尔街见闻投行观点 | `true` |
| `WALLSTREET_NEWS_FETCH_TIMEOUT` | crawl4ai 全文超时（秒） | `10` |
| `NOMURA_RESEARCH_ENABLED` | 野村研报 | `true` |
| `BLOG_MONITOR_ENABLED` | 博客监控 | `true` |
| `GITHUB_TRENDING_ENABLED` | GitHub Trending | `true` |
| `GITHUB_TRENDING_TOP_N` | Trending 取前 N | `10` |
| `GITHUB_RELEASE_ENABLED` | GitHub Release | `true` |
| `CLAUDE_PLUGINS_DIR` | 插件目录（动态发现已装插件仓库） | `~/.claude/plugins` |

## 各源调度

| 源 | 时机 | 处理 | 频道 |
|----|------|------|------|
| 华尔街见闻 | 工作日 20:00 | 关键词过滤投行观点 → crawl4ai 全文 → GLM 整理 | `news_research` |
| 野村 nomuraconnects | 工作日 20:10 | economics / central-banks，过滤亚洲/中国 → GLM | `news_research` |
| 博客（Anthropic Eng / OpenAI / DeepMind） | 每日 5:00 | 新文章 crawl4ai + GLM 中文摘要；源在 `app/config/blog_monitor.py` | `news_ai_tool` |
| GitHub Trending | 每日 5:00 | Top N 与已推记录比对，只推新上榜；首次只记录 | `news_ai_tool` |
| GitHub Release | 每 6 小时 | 发现新 Release 即推 | `news_ai_tool` |

## GitHub Release 仓库列表

监控列表 = `app/config/github_releases.py:GITHUB_RELEASE_REPOS` ∪ 本地已装 Claude Code 插件的 marketplace 仓库（`app/services/plugin_discovery.py` 读 `installed_plugins.json`，动态条目 key 加 `marketplace_` 前缀），按 `repo` 去重、静态优先。非 github 源 / 目录缺失 / JSON 损坏静默降级为只用静态配置。

- 安装任何第三方仓库（skill/plugin/工具）后加入 `GITHUB_RELEASE_REPOS`。
- 不用 GitHub Releases 发版的仓库纳入后不会推送。
- smoke test 返回 `([], [])` 通常是 `data/github_release_<key>_last_version.txt` 已被调度更新，删标记文件或写更老版本号即可复测。
