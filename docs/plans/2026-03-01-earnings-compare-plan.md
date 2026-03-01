# 财报对比分析 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 当新闻看板识别到财报新闻时，自动从 API 获取当期+上期财报数据，LLM 生成对比分析，结果复用 NewsDerivation 展示。

**Architecture:** 扩展 InterestPipeline 的 GLM 分类步骤识别财报新闻（新增 is_earnings/stock_code/report_type 字段），命中后触发新建的 EarningsCompareService，通过 akshare（A股）/ yfinance（美股港股）获取两期财报数据，LLM 生成对比分析写入 NewsDerivation。

**Tech Stack:** akshare (`stock_yjbb_em`)、yfinance (`ticker.quarterly_financials` / `ticker.financials`)、智谱 GLM（Flash 层）

---

### Task 1: 创建财报对比 LLM Prompt

**Files:**
- Create: `app/llm/prompts/earnings_compare.py`

**Step 1: 创建 prompt 文件**

```python
"""财报对比分析 prompts"""

EARNINGS_COMPARE_SYSTEM_PROMPT = """你是专业的财务分析师。根据提供的公司两期财报数据，进行对比分析。

要求：
1. 自行选择最有价值的指标进行分析（不同行业侧重不同）
2. 指出关键变化和趋势
3. 给出简洁的投资参考观点
4. 200-400字，结构化输出

格式：
**核心指标变化**：（列出3-5个关键指标的同比变化）
**分析**：（解读变化原因和意义）
**关注点**：（投资者应关注的风险或机会）

直接返回分析文本。"""


def build_earnings_compare_prompt(company_name: str, stock_code: str,
                                   report_type: str,
                                   current_data: dict,
                                   previous_data: dict) -> str:
    """构建财报对比 prompt"""
    import json
    return (
        f"公司：{company_name}（{stock_code}）\n"
        f"报告类型：{report_type}\n\n"
        f"当期数据：\n{json.dumps(current_data, ensure_ascii=False, indent=2)}\n\n"
        f"上期数据：\n{json.dumps(previous_data, ensure_ascii=False, indent=2)}\n\n"
        f"请进行对比分析。"
    )
```

**Step 2: Commit**

```bash
git add app/llm/prompts/earnings_compare.py
git commit -m "feat: 新增财报对比分析 LLM prompt"
```

---

### Task 2: 扩展 GLM 分类 Prompt 识别财报新闻

**Files:**
- Modify: `app/llm/prompts/news_classify.py:1-9`

**Step 1: 修改 CLASSIFY_SYSTEM_PROMPT**

将现有 prompt（第 3-9 行）替换为：

```python
CLASSIFY_SYSTEM_PROMPT = """你是新闻分析助手。对每条新闻评估重要性并提取关键词。
返回严格的JSON数组，每个元素包含:
- index: 新闻序号(从0开始)
- importance: 重要性评分1-5 (1=日常，3=值得关注，5=重大事件)
- keywords: 关键词列表(2-5个，中文)
- is_earnings: 是否为财报/业绩相关新闻(true/false)
- stock_code: 若为财报新闻，提取股票代码(A股6位数字如001309，美股字母代码如AAPL)，否则null
- report_type: 若为财报新闻，报告类型(年报/半年报/一季报/三季报/业绩预告/业绩快报)，否则null

财报新闻判断标准：内容涉及公司财报发布、营收/净利润/EPS等财务数据披露。

只返回JSON，不要其他文字。"""
```

**Step 2: Commit**

```bash
git add app/llm/prompts/news_classify.py
git commit -m "feat: GLM 分类 prompt 新增财报识别字段"
```

---

### Task 3: 创建 EarningsCompareService — A股财报数据获取

**Files:**
- Create: `app/services/earnings_compare_service.py`

**Step 1: 创建服务文件**

```python
"""财报对比分析服务：识别财报新闻后获取两期数据并生成对比分析"""
import logging
from datetime import date

from app import db
from app.models.news import NewsItem, NewsDerivation
from app.utils.market_identifier import MarketIdentifier

logger = logging.getLogger(__name__)

# 报告类型 → akshare 日期后缀映射
REPORT_TYPE_DATE_SUFFIX = {
    '年报': '1231',
    '半年报': '0630',
    '一季报': '0331',
    '三季报': '0930',
}


class EarningsCompareService:

    @staticmethod
    def process(news_item: NewsItem, stock_code: str, report_type: str):
        """处理单条财报新闻的对比分析"""
        if not stock_code or not report_type:
            logger.warning(f'[财报对比] 缺少 stock_code 或 report_type, news_id={news_item.id}')
            return

        existing = NewsDerivation.query.filter_by(news_item_id=news_item.id).first()
        if existing:
            return

        market = MarketIdentifier.identify(stock_code)
        if not market:
            logger.warning(f'[财报对比] 无法识别市场: {stock_code}')
            return

        try:
            if market == 'A':
                current_data, previous_data = EarningsCompareService._fetch_a_share(stock_code, report_type)
            else:
                current_data, previous_data = EarningsCompareService._fetch_yfinance(stock_code, report_type)

            if not current_data or not previous_data:
                logger.warning(f'[财报对比] 无法获取两期数据: {stock_code} {report_type}')
                return

            company_name = current_data.get('stock_name', stock_code)
            summary = EarningsCompareService._generate_analysis(
                company_name, stock_code, report_type, current_data, previous_data
            )

            if not summary:
                return

            derivation = NewsDerivation(
                news_item_id=news_item.id,
                search_query=f'{company_name} {report_type}对比',
                sources=[],
                summary=summary,
                importance=news_item.importance,
            )
            db.session.add(derivation)
            db.session.commit()
            logger.info(f'[财报对比] 完成 news_id={news_item.id}, {stock_code} {report_type}')

        except Exception as e:
            logger.error(f'[财报对比] 处理失败 news_id={news_item.id}: {e}')

    @staticmethod
    def _get_report_dates(report_type: str) -> tuple[str, str] | None:
        """根据报告类型计算当期和上期的日期字符串（YYYYMMDD格式）"""
        suffix = REPORT_TYPE_DATE_SUFFIX.get(report_type)
        if not suffix:
            if report_type in ('业绩预告', '业绩快报'):
                suffix = '1231'
            else:
                return None

        current_year = date.today().year
        # 当期：优先用今年，如果日期还没到就用去年
        month_day = int(suffix[:2]) * 100 + int(suffix[2:])
        today_md = date.today().month * 100 + date.today().day

        if today_md >= month_day:
            current_date = f'{current_year}{suffix}'
            previous_date = f'{current_year - 1}{suffix}'
        else:
            current_date = f'{current_year - 1}{suffix}'
            previous_date = f'{current_year - 2}{suffix}'

        return current_date, previous_date

    @staticmethod
    def _fetch_a_share(stock_code: str, report_type: str) -> tuple[dict | None, dict | None]:
        """获取A股两期财报数据（akshare）"""
        import akshare as ak

        dates = EarningsCompareService._get_report_dates(report_type)
        if not dates:
            return None, None

        current_date, previous_date = dates
        current_data = None
        previous_data = None

        for target_date, label in [(current_date, '当期'), (previous_date, '上期')]:
            try:
                df = ak.stock_yjbb_em(date=target_date)
                if df is None or df.empty:
                    logger.warning(f'[财报对比] akshare {label}数据为空: {target_date}')
                    continue

                row = df[df['股票代码'] == stock_code]
                if row.empty:
                    row = df[df['股票代码'] == stock_code.zfill(6)]

                if row.empty:
                    logger.warning(f'[财报对比] 未找到 {stock_code} 的{label}数据: {target_date}')
                    continue

                row = row.iloc[0]
                data = {
                    'stock_code': stock_code,
                    'stock_name': str(row.get('股票简称', stock_code)),
                    'report_date': target_date,
                    'revenue': row.get('营业收入-营业收入'),
                    'revenue_yoy': row.get('营业收入-同比增长'),
                    'revenue_qoq': row.get('营业收入-季度环比增长'),
                    'net_profit': row.get('净利润-净利润'),
                    'net_profit_yoy': row.get('净利润-同比增长'),
                    'net_profit_qoq': row.get('净利润-季度环比增长'),
                    'eps': row.get('每股收益'),
                    'bvps': row.get('每股净资产'),
                    'roe': row.get('净资产收益率'),
                    'gross_margin': row.get('销售毛利率'),
                    'debt_ratio': row.get('资产负债比率'),
                    'ocf_per_share': row.get('每股经营现金流量'),
                }
                # 清理 NaN
                data = {k: (None if v != v else v) if isinstance(v, float) else v
                        for k, v in data.items()}

                if label == '当期':
                    current_data = data
                else:
                    previous_data = data

            except Exception as e:
                logger.error(f'[财报对比] akshare获取{label}数据失败: {e}')

        return current_data, previous_data

    @staticmethod
    def _fetch_yfinance(stock_code: str, report_type: str) -> tuple[dict | None, dict | None]:
        """获取美股/港股两期财报数据（yfinance）"""
        import yfinance as yf

        yf_code = MarketIdentifier.to_yfinance(stock_code)
        try:
            ticker = yf.Ticker(yf_code)

            is_annual = report_type in ('年报',)
            financials = ticker.financials if is_annual else ticker.quarterly_financials

            if financials is None or financials.empty:
                logger.warning(f'[财报对比] yfinance 无财报数据: {yf_code}')
                return None, None

            if len(financials.columns) < 2:
                logger.warning(f'[财报对比] yfinance 数据不足两期: {yf_code}')
                return None, None

            def extract_period(col_idx: int) -> dict:
                period = financials.iloc[:, col_idx]
                period_date = str(financials.columns[col_idx])[:10]
                data = {
                    'stock_code': stock_code,
                    'stock_name': stock_code,
                    'report_date': period_date,
                }
                for field in period.index:
                    val = period[field]
                    if val != val:  # NaN check
                        val = None
                    elif hasattr(val, 'item'):
                        val = val.item()
                    data[str(field)] = val
                return data

            current_data = extract_period(0)
            previous_data = extract_period(1)

            # 尝试获取公司名
            try:
                info = ticker.info
                name = info.get('shortName') or info.get('longName') or stock_code
                current_data['stock_name'] = name
                previous_data['stock_name'] = name
            except Exception:
                pass

            return current_data, previous_data

        except Exception as e:
            logger.error(f'[财报对比] yfinance获取失败 {yf_code}: {e}')
            return None, None

    @staticmethod
    def _generate_analysis(company_name: str, stock_code: str,
                           report_type: str,
                           current_data: dict, previous_data: dict) -> str | None:
        """LLM 生成对比分析"""
        from app.llm.router import llm_router
        from app.llm.prompts.earnings_compare import (
            EARNINGS_COMPARE_SYSTEM_PROMPT, build_earnings_compare_prompt
        )

        provider = llm_router.route('news_classify')
        if not provider:
            return None

        try:
            user_prompt = build_earnings_compare_prompt(
                company_name, stock_code, report_type, current_data, previous_data
            )
            response = provider.chat([
                {'role': 'system', 'content': EARNINGS_COMPARE_SYSTEM_PROMPT},
                {'role': 'user', 'content': user_prompt},
            ], temperature=0.3, max_tokens=800)
            return response.strip()
        except Exception as e:
            logger.error(f'[财报对比] LLM分析失败: {e}')
            return None
```

**Step 2: Commit**

```bash
git add app/services/earnings_compare_service.py
git commit -m "feat: 新增 EarningsCompareService 财报对比分析服务"
```

---

### Task 4: 集成到 InterestPipeline

**Files:**
- Modify: `app/services/interest_pipeline.py`

**Step 1: 修改 `_classify_items` 返回值**

在 `_classify_items` 方法中（第 46-83 行），`for r in results` 循环内（第 73-76 行之后），增加读取财报字段并设置 category：

在第 76 行 `items[idx].importance = r.get('importance', 0)` 之后追加：

```python
                    if r.get('is_earnings') and r.get('stock_code'):
                        items[idx].category = 'earnings'
```

**Step 2: 修改 `process_new_items` 增加财报对比触发**

在 `process_new_items` 方法末尾（第 43 行之后），增加 Step 3b：

```python
            # Step 3b: 财报新闻触发对比分析
            earnings_classified = [
                (items[r['index']], r) for r in classified
                if r.get('is_earnings') and r.get('stock_code')
                and 0 <= r.get('index', -1) < len(items)
            ]
            if earnings_classified:
                from app.services.earnings_compare_service import EarningsCompareService
                for item, info in earnings_classified:
                    try:
                        EarningsCompareService.process(
                            item, info['stock_code'], info.get('report_type', '年报')
                        )
                    except Exception as e:
                        logger.error(f'[财报对比] 触发失败 news_id={item.id}: {e}')
```

**Step 3: Commit**

```bash
git add app/services/interest_pipeline.py
git commit -m "feat: InterestPipeline 集成财报对比触发逻辑"
```

---

### Task 5: 注册 LLM 路由 + 端到端验证

**Files:**
- Modify: `app/llm/router.py` (if needed — check if `news_classify` route is sufficient)

**Step 1: 检查 LLM 路由**

`EarningsCompareService._generate_analysis` 使用 `llm_router.route('news_classify')`（Flash 层），无需新增路由。确认无需修改。

**Step 2: 手动验证**

启动应用 `python run.py`，在新闻看板等待下一次 poll，或手动触发：

1. 确认 GLM 分类返回包含 `is_earnings`/`stock_code`/`report_type` 字段
2. 确认财报新闻的 `category` 被设为 `"earnings"`
3. 确认 `NewsDerivation` 表中生成了对比分析记录
4. 确认前端新闻看板能展示财报对比内容（衍生报告区域）

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat: 财报对比分析功能完成"
```
