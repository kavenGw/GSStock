# 新闻看板 - 公司Tab设计

## 目标

在新闻看板新增第三个Tab「公司」，针对用户配置的 CompanyKeyword 主动爬取关联新闻并展示。

## 数据层

复用 `NewsItem` 模型，不新增表：
- `source_name`: `'google_news'` / `'xueqiu'`
- `source_id`: URL hash（去重）
- `content`: 新闻标题 + AI摘要
- `is_interest = True`
- `matched_keywords`: 匹配的公司名

news_config.py 新增来源标签：
- `google_news` → 标签「Google」红色
- `xueqiu` → 标签「雪球」绿色

公司Tab筛选逻辑：所有 `matched_keywords` 中包含任意 CompanyKeyword 的 NewsItem。

## 爬取服务

新建 `app/services/company_news_service.py`：

```
CompanyNewsService.fetch_company_news(companies)
  ├── 对每个公司并发：
  │   ├── _search_google_news(name) → 3条URL+标题
  │   └── _search_xueqiu(name) → 雪球个股新闻
  ├── 合并去重
  ├── crawl4ai 批量爬取内容
  ├── GLM Flash AI摘要（50-100字）
  └── 存入 NewsItem
```

触发链路：`poll_news()` 异步执行，与 InterestPipeline 并行。

限流：
- 每次轮询最多 3 个公司（`COMPANY_NEWS_MAX_COMPANIES`）
- 每个公司最多 5 条新闻（`COMPANY_NEWS_MAX_ARTICLES`）
- 单条超时 30 秒，整体超时 120 秒
- source_id 去重

## 前端

Tab栏：`全部 | 兴趣 | 公司`

公司Tab复用统一时间线渲染，数据通过 `/news/items?tab=company` 获取。新闻条目显示来源badge。

## 环境变量

| 变量 | 说明 | 默认值 |
|-----|------|-------|
| `COMPANY_NEWS_MAX_COMPANIES` | 每次轮询最多处理公司数 | `3` |
| `COMPANY_NEWS_MAX_ARTICLES` | 每公司最多爬取文章数 | `5` |

默认开启，无需 ENABLED 开关。
