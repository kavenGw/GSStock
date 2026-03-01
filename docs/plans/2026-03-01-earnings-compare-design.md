# 财报对比分析功能设计

## 概述

当新闻看板获取到公司财报新闻时，自动识别并通过 API 获取当期+上期财报数据，LLM 生成对比分析，结果复用 NewsDerivation 机制展示。

## 数据流

```
poll_news()
  └→ InterestPipeline.process_new_items()
       └→ Step 1: GLM分类（新增 is_earnings / stock_code / report_type）
            └→ 命中财报 → EarningsCompareService.process()
                 ├→ A股: akshare 获取财报数据
                 ├→ 美股/港股: yfinance 获取财报数据
                 └→ LLM 生成对比分析 → 存入 NewsDerivation
```

## 设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 数据来源 | 全部走 API（不从新闻文本提取） | 数据更准确完整 |
| 展示方式 | 复用 NewsDerivation | 零前端改动 |
| 触发时机 | InterestPipeline GLM 分类时识别 | 统一流程，零额外 LLM 调用成本 |
| 对比指标 | 由 LLM 自行判断 | 不同行业关注点不同 |
| 市场范围 | A股 + 美股/港股 | 全市场覆盖 |

## 1. GLM 分类扩展

**修改文件**：`app/llm/prompts/news_classify.py`

`CLASSIFY_SYSTEM_PROMPT` 新增三个字段：

- `is_earnings` (boolean)：是否为财报/业绩相关新闻
- `stock_code` (string|null)：股票代码（A股6位数字，美股字母代码）
- `report_type` (string|null)：年报/半年报/一季报/三季报/业绩预告/业绩快报

返回示例：
```json
[
  {"index": 0, "importance": 4, "keywords": ["德明利", "年报"],
   "is_earnings": true, "stock_code": "001309", "report_type": "年报"}
]
```

**修改文件**：`app/services/interest_pipeline.py`

`_classify_items` 解析循环中读取新字段，存入 `NewsItem.category = "earnings"`，运行时字典缓存 stock_code 和 report_type 供后续步骤使用。

## 2. EarningsCompareService

**新建文件**：`app/services/earnings_compare_service.py`

```
process(news_item, stock_code, report_type)
  ├→ MarketIdentifier.identify(stock_code) 识别市场
  ├→ A股: ak.stock_yjbb_em(date) 获取业绩报表
  ├→ 美股/港股: yfinance ticker.quarterly_financials / ticker.financials
  ├→ 按 report_type 推算上期日期，匹配两期数据
  └→ LLM 对比分析 → NewsDerivation
```

**上期日期推算规则**：
- 年报 → 去年年报
- 半年报 → 去年半年报
- 一季报 → 去年一季报
- 三季报 → 去年三季报

## 3. LLM 对比分析 Prompt

**新建文件**：`app/llm/prompts/earnings_compare.py`

- 输入：当期数据 JSON + 上期数据 JSON + 公司名
- LLM 自行选择重点指标进行分析
- 输出：200-400字结构化分析
- 结果写入 `NewsDerivation(news_item_id, search_query="财报对比", summary=分析内容)`

## 4. Pipeline 集成

在 `process_new_items` 末尾，与衍生搜索独立并行：

```python
earnings_items = [(item, info) for item, info in classified_with_earnings if info['is_earnings']]
for item, info in earnings_items:
    EarningsCompareService.process(item, info['stock_code'], info['report_type'])
```

## 涉及文件

| 文件 | 操作 |
|------|------|
| `app/llm/prompts/news_classify.py` | 修改：扩展分类 prompt |
| `app/llm/prompts/earnings_compare.py` | 新建：对比分析 prompt |
| `app/services/earnings_compare_service.py` | 新建：财报对比服务 |
| `app/services/interest_pipeline.py` | 修改：集成财报对比触发 |

无新数据库表/字段，无前端改动，无新路由。
