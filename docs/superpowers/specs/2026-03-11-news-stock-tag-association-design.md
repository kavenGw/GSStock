# 新闻-股票标签关联机制设计

## 概述

为每个股票设置关键标签（LLM 自动生成 + 手动编辑），新闻获取后比对所有股票标签进行关联，通知推送时展示关联股票。

## 数据模型变更

### Stock 表新增字段

- `tags` (Text, nullable) — 逗号分隔的关键词，如 `"贵州茅台,茅台,白酒,酱香,Moutai"`

### NewsItem 表新增字段

- `matched_stocks` (Text, nullable) — 逗号分隔的股票代码，如 `"600519,000858"`

## 标签生成

### 方式：调用 GLM 生成

`StockService` 新增：

- `generate_tags(stock_code, stock_name)` — 调用 GLM，prompt 要求根据股票代码和名称生成关联关键词（公司名/简称/产品/行业/概念/英文名），返回逗号分隔字符串，写入 `tags` 字段
- `batch_generate_tags(overwrite=False)` — 遍历所有 `tags` 为空（或 overwrite=True 时全部）的股票，逐个调用 `generate_tags`

### 触发时机

- 添加新股票时自动异步生成
- 页面提供"批量生成标签"按钮处理存量股票

## 匹配逻辑

融入现有 `InterestPipeline._match_keywords()` 步骤：

1. 加载所有股票的 tags，构建反向索引 `{tag_keyword: [stock_code, ...]}`
2. 对每条新闻 content 遍历反向索引做子串匹配
3. 命中的 stock_codes 去重后写入 `news_item.matched_stocks`
4. 不影响现有 `is_interest` 和 `matched_keywords` 逻辑

### 与现有机制的关系

- `InterestKeyword`（全局兴趣关键词）：保持不变
- `CompanyKeyword`（公司名爬取）：保持不变
- 股票标签：作为独立的新匹配维度

## 通知展示

`InterestPipeline._notify_interest_slack()` 中，若 `matched_stocks` 非空：

- 查询对应的 stock_name
- 在消息末尾追加：`\n→ 关联: 600519贵州茅台, AAPL苹果`

## UI 变更

股票代码管理页面（`stock_manage.html`）：

- 表格新增"标签"列，显示 tags 内容，支持双击行内编辑
- 页面顶部新增"批量生成标签"按钮，调用 `batch_generate_tags` API

## 涉及文件

- `app/models/stock.py` — Stock 模型新增 tags 字段
- `app/models/news.py` — NewsItem 模型新增 matched_stocks 字段
- `app/services/stock.py` — 标签生成方法
- `app/services/interest_pipeline.py` — 匹配逻辑扩展
- `app/routes/stock.py` — 标签生成 API
- `app/templates/stock_manage.html` — UI 新增标签列和批量按钮
- `app/templates/partials/stock_row.html` — 行模板新增标签列
