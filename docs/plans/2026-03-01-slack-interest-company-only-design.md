# Slack 推送仅限兴趣+公司新闻

## 背景

当前所有快讯新闻入库后都会推送到 Slack，信息量过大。改为仅推送兴趣新闻和公司新闻。

## 变更范围

策略预警（涨跌幅、价格、威科夫）和每日简报的 Slack 通知保持不变。

### 1. `app/services/news_service.py`

- 删除 `poll_news()` 中的 `_executor.submit(NewsService._notify_slack, ...)` 调用
- 删除 `_notify_slack()` 方法
- 删除 `_ai_select_key_news()` 方法

### 2. `app/services/interest_pipeline.py`

- 在 `process_new_items()` 的 `db.session.commit()` 之后，筛选 `is_interest=True` 的条目
- 逐条推送到 Slack，格式：`📰 {content}`

### 3. `app/services/company_news_service.py`

- 在 `fetch_company_news()` 的 `_save_results()` 完成后，推送新增的公司新闻
- 格式：`🏢 [{公司名}] {content}`

## 推送逻辑

- 兴趣新闻已经过 AI 分类+关键词匹配筛选，不需要 AI 二次筛选
- 公司新闻来自主动爬取，数量由 `COMPANY_NEWS_MAX_COMPANIES` 和 `COMPANY_NEWS_MAX_ARTICLES` 控制
