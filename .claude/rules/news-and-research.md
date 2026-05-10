# 新闻 / 研报 / 监控源

> **何时读**：调整新闻轮询参数、新增新闻源、修改博客/Trending/Release 监控、修改 plugin discovery、新增第三方仓库到 GITHUB_RELEASE_REPOS
> **不必读**：盯盘 / 持仓 / 股票数据获取主链路

## 新闻轮询配置

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `NEWS_INTERVAL_MINUTES` | 新闻后台轮询间隔（分钟） | `3` |

## 公司新闻配置

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `COMPANY_NEWS_MAX_COMPANIES` | 每次轮询最多处理的公司数 | `3` |
| `COMPANY_NEWS_MAX_ARTICLES` | 每个公司最多爬取文章数 | `5` |
| `COMPANY_NEWS_INTERVAL_MINUTES` | 公司新闻获取间隔（分钟） | `30` |
| `NEWS_FETCH_TIMEOUT` | 新闻源获取超时（秒） | `15` |
| `NEWS_DEDUP_WINDOW_MINUTES` | 新闻推送去重窗口（分钟） | `1440` |

## 华尔街见闻投行观点配置

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `WALLSTREET_NEWS_ENABLED` | 是否启用华尔街见闻策略 | `true` |
| `WALLSTREET_NEWS_FETCH_TIMEOUT` | crawl4ai 全文爬取超时（秒） | `10` |

每日 20:00（工作日）自动抓取华尔街见闻快讯流和文章列表，关键词过滤投行/机构观点（高盛、摩根、花旗等），crawl4ai 爬取全文，GLM Flash 整理关键信息后 Slack 推送到 `news_research` 频道。

## 野村证券研报配置

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `NOMURA_RESEARCH_ENABLED` | 是否启用野村研报爬虫 | `true` |

每日 20:10（工作日）抓取 nomuraconnects.com 的 economics 和 central-banks 分类，关键词过滤亚洲/中国相关文章，crawl4ai 爬取全文，GLM Flash 整理关键观点后推送到 `news_research` 频道。

## 博客监控配置

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `BLOG_MONITOR_ENABLED` | 是否启用博客监控 | `true` |

每日 5:00 独立调度检查 Anthropic Engineering / OpenAI Blog / DeepMind Blog 新文章，crawl4ai 抓取全文 + GLM 中文摘要，推送到 `news_ai_tool` 频道。博客源配置在 `app/config/blog_monitor.py`。

## GitHub Trending 监控配置

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `GITHUB_TRENDING_ENABLED` | 是否启用 GitHub Trending 监控 | `true` |
| `GITHUB_TRENDING_TOP_N` | 取前 N 个项目 | `10` |

每日 5:00 独立调度爬取 github.com/trending 页面 Top N 项目，与已推送记录比对，仅推送新上榜的项目（含 GLM 中文摘要）到 `news_ai_tool` 频道。首次运行只记录不推送。

## GitHub Release 监控配置

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `GITHUB_RELEASE_ENABLED` | 是否启用 GitHub Release 监控 | `true` |
| `CLAUDE_PLUGINS_DIR` | Claude Code 插件目录（动态发现本地已装插件所属仓库） | `~/.claude/plugins` |

独立调度策略 `github_release`：每 6 小时检查一次新版本（`0 */6 * * *`），发现新 Release 立即推送到 `news_ai_tool` 频道。

监控仓库列表 = 静态配置（`app/config/github_releases.py` 的 `GITHUB_RELEASE_REPOS`） ∪ 本地已装 Claude Code 插件对应 marketplace 仓库，按 `repo` 去重（静态优先保留自定义 `name`/`emoji`/`key`）。

动态发现逻辑（`app/services/plugin_discovery.py`）：
- 读取 `$CLAUDE_PLUGINS_DIR/installed_plugins.json` 提取已装插件所属的 marketplace 名
- 在 `known_marketplaces.json` 查每个 marketplace 的 `source`，支持 `{source: 'github', repo: ...}` 和 `{source: 'git', url: 'https://github.com/.../.git'}`
- 非 github.com 源、目录不存在、JSON 损坏均安全降级为空列表（只用静态配置）
- 动态条目 `key` 统一加 `marketplace_` 前缀避免与静态 key 冲突

注意：不使用 GitHub Releases 发版的仓库（仅 commit 或 tag，如 `anthropics/claude-plugins-official`、`supabase/agent-skills`）纳入监控后不会产生推送，直到其首次发 Release。

**smoke test 空列表 != 代码坏**：`format_github_release_updates` 返回 `([], [])` 通常是 `data/github_release_<key>_last_version.txt` 已被并行调度更新过。强制复测可临时删除该标记文件或写入更老版本号。
