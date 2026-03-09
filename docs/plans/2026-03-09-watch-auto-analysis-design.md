# 盯盘助手自动化分析 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 移除盯盘手动AI分析按钮，将分析完全自动化 — 7d/30d 绑定每日推送，realtime 后台每15分钟执行，结果包含在 Slack 消息中。

**Architecture:** 从路由层抽出分析逻辑到 `WatchAnalysisService`，新建 `watch_realtime` 策略处理开盘时段实时分析，扩展 `DailyBriefingStrategy` 在推送前计算 7d/30d 并格式化进 Slack 消息。前端移除手动触发，改为纯读取 DB 缓存展示。

**Tech Stack:** Flask, APScheduler, SQLAlchemy, 智谱GLM (FLASH层)

---

### Task 1: 新建 WatchAnalysisService

**Files:**
- Create: `app/services/watch_analysis_service.py`
- Modify: `app/routes/watch.py:81-183`

**Step 1: 创建 WatchAnalysisService**

从 `watch.py` 的 `/analyze` 端点提取核心逻辑到独立 service：

```python
"""盯盘AI分析服务"""
import json
import logging

from app import db
from app.services.watch_service import WatchService

logger = logging.getLogger(__name__)


class WatchAnalysisService:
    """盯盘AI分析 — 统一分析入口，供路由/策略/定时任务调用"""

    @staticmethod
    def analyze_stocks(period: str, force: bool = False) -> dict:
        """对盯盘列表所有股票执行指定周期的AI分析

        Args:
            period: 'realtime', '7d', '30d'
            force: 是否强制刷新（忽略缓存）

        Returns:
            dict: {stock_code: {period: analysis_data, ...}, ...}
        """
        from app.services.unified_stock_data import unified_stock_data_service
        from app.llm.router import llm_router
        from app.llm.prompts.watch_analysis import (
            SYSTEM_PROMPT, build_realtime_analysis_prompt,
            build_7d_analysis_prompt, build_30d_analysis_prompt,
        )

        codes = WatchService.get_watch_codes()
        if not codes:
            return {}

        trend_60d = unified_stock_data_service.get_trend_data(codes, days=60)
        trend_60d_map = {s['stock_code']: s for s in trend_60d.get('stocks', [])}

        if period != 'realtime' and not force:
            existing = WatchService.get_all_today_analyses()
            all_cached = all(existing.get(c, {}).get(period) for c in codes)
            if all_cached:
                return existing

        intraday_map = {}
        trend_map = {}
        if period == 'realtime':
            intraday = unified_stock_data_service.get_intraday_data(codes)
            intraday_map = {s['stock_code']: s for s in intraday.get('stocks', [])}

        if period in ('7d', '30d'):
            days = 7 if period == '7d' else 30
            trend = unified_stock_data_service.get_trend_data(codes, days=days)
            trend_map = {s['stock_code']: s for s in trend.get('stocks', [])}

        raw_prices = unified_stock_data_service.get_realtime_prices(codes)

        provider = llm_router.route('watch_analysis')
        if not provider:
            logger.warning('[盯盘AI] LLM 不可用，跳过分析')
            return WatchService.get_all_today_analyses()

        for code in codes:
            price_data = raw_prices.get(code, {})
            current_price = price_data.get('current_price', 0)
            stock_name = price_data.get('name', code)
            if not current_price:
                continue

            if period != 'realtime' and not force:
                existing_analysis = WatchService.get_today_analysis(code, period)
                if existing_analysis:
                    continue

            try:
                if period == 'realtime':
                    intraday_stock = intraday_map.get(code, {})
                    intraday_data = intraday_stock.get('data', [])
                    if not intraday_data:
                        continue
                    ohlc_60d = trend_60d_map.get(code, {}).get('data', [])
                    prompt = build_realtime_analysis_prompt(stock_name, code, intraday_data, current_price, ohlc_60d)
                elif period == '7d':
                    trend_stock = trend_map.get(code, {})
                    ohlc = trend_stock.get('data', [])
                    if not ohlc:
                        continue
                    prompt = build_7d_analysis_prompt(stock_name, code, ohlc, current_price)
                else:
                    trend_stock = trend_map.get(code, {})
                    ohlc = trend_stock.get('data', [])
                    if not ohlc:
                        continue
                    prompt = build_30d_analysis_prompt(stock_name, code, ohlc, current_price)

                response = provider.chat([
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': prompt},
                ])
                cleaned = response.strip()
                if cleaned.startswith('```'):
                    cleaned = cleaned.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
                parsed = json.loads(cleaned)
                WatchService.save_analysis(
                    stock_code=code,
                    period=period,
                    support_levels=parsed.get('support_levels', []),
                    resistance_levels=parsed.get('resistance_levels', []),
                    summary=parsed.get('summary', ''),
                    signal=parsed.get('signal', ''),
                    detail={
                        'signal_text': parsed.get('signal_text', ''),
                        'ma_levels': parsed.get('ma_levels', {}),
                        'price_range': parsed.get('price_range', {}),
                    },
                )
            except Exception as e:
                db.session.rollback()
                logger.error(f"[盯盘AI] {code} {period}分析失败: {e}")

        return WatchService.get_all_today_analyses()
```

**Step 2: 简化 watch.py 路由**

将 `/analyze` 端点改为调用 `WatchAnalysisService`：

```python
@watch_bp.route('/analyze', methods=['POST'])
def analyze():
    from app.services.watch_analysis_service import WatchAnalysisService

    data = request.get_json() or {}
    period = data.get('period', '30d')
    force = data.get('force', False)

    all_analyses = WatchAnalysisService.analyze_stocks(period, force)
    return jsonify({'success': True, 'data': all_analyses})
```

**Step 3: Commit**

```
feat: 新建 WatchAnalysisService，从路由抽出分析逻辑
```

---

### Task 2: 新建 watch_realtime 策略

**Files:**
- Create: `app/strategies/watch_realtime/__init__.py`

**Step 1: 创建策略文件**

```python
"""盯盘实时分析策略 — 开盘时段每15分钟自动分析"""
import logging
from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)


class WatchRealtimeStrategy(Strategy):
    name = "watch_realtime"
    description = "盯盘实时分析（开盘时段每15分钟）"
    schedule = "*/15 9-23 * * 1-5"
    needs_llm = True

    def scan(self) -> list[Signal]:
        from app.services.watch_service import WatchService
        from app.services.trading_calendar import TradingCalendarService

        codes = WatchService.get_watch_codes()
        if not codes:
            return []

        # 检查是否有市场正在交易
        markets = WatchService.get_watched_markets()
        has_active = any(TradingCalendarService.is_market_open(m) for m in markets)
        if not has_active:
            return []

        from app.services.watch_analysis_service import WatchAnalysisService
        try:
            WatchAnalysisService.analyze_stocks('realtime', force=True)
            logger.info('[盯盘实时] 分析完成')
        except Exception as e:
            logger.error(f'[盯盘实时] 分析失败: {e}')

        return []
```

> **注意**：schedule 用 `*/15 9-23 * * 1-5` 覆盖 A股(9-15)+美股(21-次日4) 等多市场时段，策略内部通过 `is_market_open()` 判断是否有活跃市场。

**Step 2: Commit**

```
feat: 新建 watch_realtime 策略，开盘时段每15分钟自动分析
```

---

### Task 3: 扩展每日推送 — 7d/30d 分析 + Slack 消息

**Files:**
- Modify: `app/strategies/daily_briefing/__init__.py:14-26`
- Modify: `app/services/notification.py:233-298`

**Step 1: 在 NotificationService 新增 format_watch_analysis()**

在 `format_ai_report()` 之后添加：

```python
@staticmethod
def format_watch_analysis(analyses: dict) -> dict:
    """格式化盯盘AI分析结果用于推送"""
    if not analyses:
        return {'text': ''}

    from app.services.watch_service import WatchService
    watch_list = WatchService.get_watch_list()
    name_map = {w['stock_code']: w['stock_name'] for w in watch_list}

    signal_map = {'buy': '买入', 'sell': '卖出', 'hold': '持有', 'watch': '观望'}
    lines = []

    for code, periods in analyses.items():
        name = name_map.get(code, code)
        parts = []
        for period in ('7d', '30d'):
            data = periods.get(period)
            if not data:
                continue
            signal = signal_map.get(data.get('signal', ''), '观望')
            summary = data.get('summary', '')
            parts.append(f"[{period}]{signal} {summary}")
        if parts:
            lines.append(f"  {name}({code}): {' | '.join(parts)}")

    if not lines:
        return {'text': ''}

    text = "盯盘分析\n" + "\n".join(lines) + "\n"
    return {'text': text}
```

**Step 2: 修改 push_daily_report() 加入盯盘分析**

在 `push_daily_report()` 的 `if include_ai:` 块之后、`full_text = ...` 之前，加入盯盘分析：

```python
# 盯盘分析（7d + 30d）
try:
    from app.services.watch_analysis_service import WatchAnalysisService
    WatchAnalysisService.analyze_stocks('7d')
    WatchAnalysisService.analyze_stocks('30d')
    from app.services.watch_service import WatchService
    watch_analyses = WatchService.get_all_today_analyses()
    watch_report = NotificationService.format_watch_analysis(watch_analyses)
    if watch_report['text']:
        text_parts.append(watch_report['text'])
except Exception as e:
    logger.warning(f'[通知.盯盘分析] 生成失败: {e}')
```

**Step 3: Commit**

```
feat: 每日推送集成盯盘7d/30d分析，结果包含在Slack消息中
```

---

### Task 4: 前端改造 — 移除手动按钮，改为纯读取

**Files:**
- Modify: `app/templates/watch.html:76-79`
- Modify: `app/static/js/watch.js` (多处)

**Step 1: 移除 watch.html 中的AI分析按钮**

删除行 77-79 的按钮：

```html
<!-- 删除这段 -->
<button class="btn btn-outline-primary btn-sm" id="btnAnalyze" onclick="Watch.triggerAllAnalysis()">
    <i class="bi bi-robot"></i> AI 分析
</button>
```

**Step 2: 修改 watch.js**

2a. 删除 `triggerAllAnalysis()` 方法（行 366-390）

2b. 删除 `autoAnalyze()` 方法（行 110-128）

2c. 修改 `init()` — 移除 `this.autoAnalyze()` 调用，改为 `this.loadAnalysis()`：

```javascript
async init() {
    const cache = WatchCache.load();
    if (cache && cache.prices && cache.prices.length > 0) {
        WatchCache.restore(this, cache);
        try {
            const listResp = await fetch('/watch/list');
            const listData = await listResp.json();
            if (listData.success) this.stocks = listData.data || [];
        } catch (e) {
            console.error('[Watch] list fetch failed:', e);
        }
        if (this.stocks.length > 0) {
            this.renderCards();
            this.renderBenchmarks();
            this.loadAllChartsFromCache();
            this.updateStatus(`${this.stocks.length} 只股票`);
        }
    }

    await this.loadList(true);

    // 从DB读取分析缓存 + 启动定时器
    this.loadAnalysis();
    this.startRefreshLoop();
    this.startAnalysisLoop();
    this.startMarketStatusLoop();
},
```

2d. 修改 `startAnalysisLoop()` — 从 POST 改为 GET 轮询：

```javascript
startAnalysisLoop() {
    this.stopAnalysisLoop();
    this.analysisTimer = setInterval(async () => {
        await this.loadAnalysis();
    }, this.ANALYSIS_INTERVAL * 1000);
},
```

> 每15分钟（`ANALYSIS_INTERVAL` 已是 `15 * 60`）轮询一次 `GET /watch/analysis`，与后台策略同频。无需检查市场状态，读取是轻量操作。

2e. 修改 `renderStockCard()` — 更新分析内容的默认提示文字：

将 `点击「AI 分析」获取分析结果` 改为 `等待分析数据...`

**Step 3: Commit**

```
feat: 盯盘前端移除AI分析按钮，改为自动轮询读取分析缓存
```

---

### Task 5: 清理与验证

**Files:**
- Review: `app/routes/watch.py`
- Review: `app/static/js/watch.js`

**Step 1: 确认路由 `/analyze` 仍可工作**

保留 POST `/analyze` 端点（供可能的手动调试），但前端不再调用它。

**Step 2: 确认策略自动发现**

`watch_realtime` 策略放在 `app/strategies/watch_realtime/__init__.py`，registry 的 `discover()` 会自动扫描注册。无需修改 `registry.py` 或 `engine.py`。

**Step 3: 启动验证**

```bash
python run.py
```

检查日志：
- 应看到 `[策略注册] watch_realtime: 盯盘实时分析（开盘时段每15分钟）`
- 调度器应显示 `watch_realtime(*/15 9-23 * * 1-5)` 已注册

**Step 4: Commit**

```
refactor: 盯盘自动化分析完成，清理无用代码
```
