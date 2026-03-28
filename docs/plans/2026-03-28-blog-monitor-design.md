# 技术博客监控推送设计

## 目标

监控 AI 公司技术博客，检测新文章后生成中文摘要推送到 Slack `news_ai_tool` 频道。

## 监控源

| 博客 | 类型 | URL | 备注 |
|------|------|-----|------|
| Anthropic Engineering | HTML | `https://www.anthropic.com/engineering` | 无 RSS，HTML 解析 |
| OpenAI Blog | RSS | `https://openai.com/blog/rss.xml` | 网页 403，RSS 正常 |
| DeepMind Blog | RSS | `https://deepmind.google/blog/feed/` | RSS 正常 |

## 架构

```
app/config/blog_monitor.py           — 博客源配置列表
app/services/blog_monitor_service.py  — 核心服务
app/services/notification.py          — 推送集成
data/blog_monitor_{key}_pushed.json   — 已推送记录
```

### 新增依赖

- `feedparser` — RSS/Atom feed 解析

## 配置

`app/config/blog_monitor.py`：

```python
BLOG_SOURCES = [
    {
        'key': 'anthropic_engineering',
        'name': 'Anthropic Engineering',
        'type': 'html',
        'list_url': 'https://www.anthropic.com/engineering',
        'base_url': 'https://www.anthropic.com',
        'enabled': True,
    },
    {
        'key': 'openai_blog',
        'name': 'OpenAI Blog',
        'type': 'rss',
        'feed_url': 'https://openai.com/blog/rss.xml',
        'enabled': True,
    },
    {
        'key': 'deepmind_blog',
        'name': 'DeepMind Blog',
        'type': 'rss',
        'feed_url': 'https://deepmind.google/blog/feed/',
        'enabled': True,
    },
]
```

环境变量：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `BLOG_MONITOR_ENABLED` | 是否启用博客监控 | `true` |

## BlogMonitorService

`app/services/blog_monitor_service.py`

### 核心流程

```
check_all_blogs()
  ├→ 遍历 BLOG_SOURCES（仅 enabled）
  ├→ 按 type 分发：_fetch_rss() / _fetch_html_anthropic()
  ├→ 对比 _get_pushed(key)，筛出新文章
  ├→ 首次运行：记录当前文章，不推送
  ├→ 新文章：_fetch_full_content() + _summarize()
  └→ 返回 [{source_name, title, url, summary}]
```

### 方法设计

```python
class BlogMonitorService:
    def check_all_blogs(self) -> list[dict]:
        """遍历所有博客源，返回新文章列表（含摘要）"""

    def _fetch_rss(self, source: dict) -> list[dict]:
        """feedparser 解析 RSS，返回 [{title, url, date, summary}]"""

    def _fetch_html_anthropic(self, source: dict) -> list[dict]:
        """requests GET + 正则解析 Anthropic Engineering 页面"""

    def _get_pushed(self, key: str) -> set[str]:
        """读取 data/blog_monitor_{key}_pushed.json 中的已推送 URL 集合"""

    def _mark_pushed(self, key: str, urls: list[str]):
        """追加写入已推送记录"""

    def _fetch_full_content(self, url: str) -> str:
        """crawl4ai 异步抓取文章全文 markdown，15 秒超时"""

    def _summarize(self, title: str, content: str) -> str:
        """GLM Flash 生成 2-3 句中文摘要，30 秒超时"""
```

### 去重机制

- 文件 `data/blog_monitor_{key}_pushed.json` 存储已推送 URL 集合
- 首次运行检测：文件不存在 → 记录当前所有文章 URL，不推送
- 后续运行：新 URL = 文章列表 URL - 已推送 URL

### Anthropic HTML 解析

页面为卡片列表，每个文章卡片包含 `/engineering/xxx` 链接和标题。用 `requests.get()` 获取 HTML，正则提取文章链接和标题。

### 降级策略

- 全文抓取失败：使用列表页的 summary 字段（RSS 自带，HTML 解析提取）
- LLM 摘要失败：推送标题 + 链接，不附摘要
- 源不可达：跳过该源，不影响其他源

## 推送集成

### notification.py 修改

新增 `format_blog_updates()` 方法：

```python
def format_blog_updates(self) -> list[str]:
    """获取新博客文章并格式化推送文本"""
    articles = BlogMonitorService().check_all_blogs()
    texts = []
    for article in articles:
        text = f"📝 {article['source_name']} 新文章\n"
        text += f"{article['title']}\n\n"
        if article.get('summary'):
            text += f"{article['summary']}\n\n"
        text += f"🔗 {article['url']}"
        texts.append(text)
    return texts
```

### push_daily_report() 集成

与 GitHub Release 并列：

```python
# GitHub Release
github_texts, versions_to_mark = self.format_github_release_updates()

# 博客监控
blog_texts = self.format_blog_updates()

# 合并推送到 news_ai_tool
all_ai_tool_texts = github_texts + blog_texts
if all_ai_tool_texts:
    self.send_slack('\n\n'.join(all_ai_tool_texts), CHANNEL_AI_TOOL)
```

### push_daily_extras() 集成

周末同样检查博客更新。

## 推送格式

```
📝 Anthropic Engineering 新文章
Building a C compiler with a team of parallel Claudes

Opus 4.6 agent 团队以最少的人工干预构建了一个 C 编译器，
揭示了自主开发的关键洞察...

🔗 https://www.anthropic.com/engineering/building-c-compiler
```

## 改动范围

| 文件 | 变更 |
|------|------|
| `app/config/blog_monitor.py` | 新建，博客源配置 |
| `app/services/blog_monitor_service.py` | 新建，核心服务 |
| `app/services/notification.py` | 新增 `format_blog_updates()` + 推送集成 |
| `requirements.txt` | 新增 `feedparser` |
| `CLAUDE.md` | 新增博客监控配置说明 |
| `README.md` | 新增博客监控配置说明 |
| `.env.sample` | 新增 `BLOG_MONITOR_ENABLED` |
