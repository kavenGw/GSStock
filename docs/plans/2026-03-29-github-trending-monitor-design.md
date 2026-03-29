# GitHub Trending 监控设计

## 概述

监控 GitHub Trending（github.com/trending）每日趋势项目，只推送新上榜的项目到 Slack `news_ai_tool` 频道，附带 LLM 中文摘要。

## 需求

- 数据源：爬取 github.com/trending 页面 HTML
- 范围：全语言，每日趋势，取 Top 10
- 去重：已推送过的项目不再推送，仅推送新进入 Top 10 的
- 推送内容：仓库名 + 描述 + star 数 + 今日新增 star + 链接 + LLM 中文摘要
- 频率：每天一次，跟随每日简报推送（8:30am）
- 推送频道：`news_ai_tool`

## 方案

独立 Service + Config，复用现有博客监控/GitHub Release 监控模式，通过每日简报统一推送。

## 配置层

**新建 `app/config/github_trending.py`**：

```python
GITHUB_TRENDING_CONFIG = {
    'enabled': True,
    'url': 'https://github.com/trending',
    'top_n': 10,
    'language': None,
    'since': 'daily',
}
```

**环境变量**：

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `GITHUB_TRENDING_ENABLED` | 是否启用 GitHub Trending 监控 | `true` |
| `GITHUB_TRENDING_TOP_N` | 取前 N 个项目 | `10` |

## Service 层

**新建 `app/services/github_trending_service.py`**：

### 核心流程

1. `fetch_trending()` — 请求 github.com/trending，用 requests 获取 HTML
2. `_parse_html(html)` — 解析提取 Top N 项目信息（repo 全名、描述、star 数、今日新增 star、链接）
3. `_filter_new(repos)` — 读取 `data/github_trending_pushed.json`，过滤掉已推送的
4. `_summarize(repos)` — 对新项目调用 LLM（GLM），生成中文一句话摘要
5. `mark_pushed(repos)` — 将新推送的 repo 全名追加到 JSON 文件

### 去重逻辑

- JSON 文件 `data/github_trending_pushed.json` 存储已推送 repo 全名集合（如 `"microsoft/vscode"`）
- 首次运行：标记当前 Top 10 为已推送，不触发推送（跟博客监控一致）
- 后续运行：只推送不在集合中的新项目

### 数据结构

每个 repo 提取的信息：
```json
{
  "full_name": "microsoft/vscode",
  "description": "Visual Studio Code",
  "stars": "158,000",
  "today_stars": "+520",
  "url": "https://github.com/microsoft/vscode",
  "summary": "LLM 生成的中文摘要"
}
```

## 推送集成

### 格式化方法

`NotificationService.format_github_trending_updates()`:
- 调用 `GitHubTrendingService.fetch_trending()` 获取新项目
- 无新项目时返回空列表

### Slack 消息格式

```
🔥 GitHub Trending 新上榜（3个）

⭐ microsoft/vscode - Visual Studio Code
⭐ 158,000 | 今日 +520
微软开源代码编辑器，支持插件扩展...
🔗 https://github.com/microsoft/vscode

⭐ another/repo - 描述
⭐ 12,000 | 今日 +300
中文摘要...
🔗 https://github.com/another/repo
```

### 每日简报集成

在 `push_daily_report()`（工作日）和 `push_daily_extras()`（周末）中：
- 与 GitHub Release、博客更新一起汇总
- 推送到 `news_ai_tool` 频道

## 文件变更清单

| 操作 | 文件 |
|------|------|
| 新建 | `app/config/github_trending.py` |
| 新建 | `app/services/github_trending_service.py` |
| 修改 | `app/services/notification.py` — 新增 `format_github_trending_updates()`，集成到每日简报 |
| 修改 | `CLAUDE.md` — 新增 GitHub Trending 配置说明 |
| 修改 | `README.md` — 新增 GitHub Trending 配置说明 |
| 修改 | `.env.sample` — 新增环境变量 |
