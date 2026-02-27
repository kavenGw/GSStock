# 盯盘助手优化 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 重写盯盘助手前端，改为卡片式布局+实时分时线；后端改造AI分析为三维度；移除后台策略扫描。

**Architecture:** 前端重写为每只股票一个大卡片（内嵌ECharts分时线），定时轮询60秒追加数据。后端改造 `/watch/chart-data` 支持增量模式，`/watch/analyze` 支持三维度分析。删除后台策略和通知逻辑。

**Tech Stack:** Flask, SQLAlchemy, ECharts, Bootstrap 5, 智谱GLM

---

### Task 1: 删除后台策略和清理相关代码

**Files:**
- Delete: `app/strategies/watch_assistant/__init__.py`
- Modify: `app/scheduler/engine.py:20-27`
- Modify: `app/routes/watch.py:40-88` (prices路由清理策略引用)

**Step 1: 删除策略文件**

删除 `app/strategies/watch_assistant/` 整个目录。

**Step 2: 清理 scheduler/engine.py**

从 `init_app` 中移除 watch_assistant 相关的 import 和 if 分支：

```python
# 删除这行
from app.config.watch_config import WATCH_INTERVAL_MINUTES

# 删除这个 if 分支
if strategy.name == 'watch_assistant':
    trigger = IntervalTrigger(minutes=WATCH_INTERVAL_MINUTES)
    schedule_desc = f'every {WATCH_INTERVAL_MINUTES}min'
```

**Step 3: 简化 prices 路由**

移除 `app/routes/watch.py` 中 `prices()` 函数里对 `registry`、`strategy`、`cooldown`、`notification` 的所有引用。简化为只返回价格数据和分析结果中的支撑/阻力/摘要：

```python
@watch_bp.route('/prices')
def prices():
    from app.services.unified_stock_data import unified_stock_data_service

    codes = WatchService.get_watch_codes()
    if not codes:
        return jsonify({'success': True, 'prices': []})

    raw_prices = unified_stock_data_service.get_realtime_prices(codes)
    price_list = []
    for code, data in raw_prices.items():
        price_list.append({
            'code': code,
            'name': data.get('name', code),
            'price': data.get('current_price'),
            'change': data.get('change'),
            'change_pct': data.get('change_percent'),
            'volume': data.get('volume'),
            'market': data.get('market', ''),
        })

    return jsonify({'success': True, 'prices': price_list})
```

**Step 4: 删除 watch_config.py**

删除 `app/config/watch_config.py`（不再需要后台间隔配置）。

**Step 5: Commit**

```bash
git add -A
git commit -m "refactor: 移除盯盘助手后台策略扫描和通知逻辑"
```

---

### Task 2: 改造 WatchAnalysis 模型（新增 period 字段）

**Files:**
- Modify: `app/models/watch_list.py`
- Modify: `app/services/watch_service.py`

**Step 1: 修改 WatchAnalysis 模型**

```python
class WatchAnalysis(db.Model):
    __tablename__ = 'watch_analysis'
    __table_args__ = (
        db.UniqueConstraint('stock_code', 'analysis_date', 'period', name='uq_watch_analysis_code_date_period'),
    )

    id = db.Column(db.Integer, primary_key=True)
    stock_code = db.Column(db.String(20), nullable=False)
    analysis_date = db.Column(db.Date, nullable=False)
    period = db.Column(db.String(10), nullable=False, default='30d')  # 'realtime', '7d', '30d'
    support_levels = db.Column(db.Text)  # JSON
    resistance_levels = db.Column(db.Text)  # JSON
    analysis_summary = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
```

注意：移除了 `volatility_threshold` 字段。

**Step 2: 修改 WatchService 方法**

更新所有涉及 WatchAnalysis 的方法，增加 `period` 参数：

`get_today_analysis(stock_code, period=None)` — period 为 None 时返回所有维度：
```python
@staticmethod
def get_today_analysis(stock_code: str, period: str = None) -> dict | None:
    today = date.today()
    if period:
        analysis = WatchAnalysis.query.filter_by(
            stock_code=stock_code, analysis_date=today, period=period
        ).first()
        if not analysis:
            return None
        return {
            'stock_code': analysis.stock_code,
            'period': analysis.period,
            'support_levels': json.loads(analysis.support_levels) if analysis.support_levels else [],
            'resistance_levels': json.loads(analysis.resistance_levels) if analysis.resistance_levels else [],
            'summary': analysis.analysis_summary,
        }
    else:
        analyses = WatchAnalysis.query.filter_by(
            stock_code=stock_code, analysis_date=today
        ).all()
        if not analyses:
            return None
        result = {}
        for a in analyses:
            result[a.period] = {
                'support_levels': json.loads(a.support_levels) if a.support_levels else [],
                'resistance_levels': json.loads(a.resistance_levels) if a.resistance_levels else [],
                'summary': a.analysis_summary,
            }
        return result
```

`save_analysis(stock_code, period, support_levels, resistance_levels, summary)` — 新增 period 参数：
```python
@staticmethod
def save_analysis(stock_code: str, period: str, support_levels: list,
                  resistance_levels: list, summary: str):
    today = date.today()
    existing = WatchAnalysis.query.filter_by(
        stock_code=stock_code, analysis_date=today, period=period
    ).first()
    if existing:
        existing.support_levels = json.dumps(support_levels)
        existing.resistance_levels = json.dumps(resistance_levels)
        existing.analysis_summary = summary
    else:
        analysis = WatchAnalysis(
            stock_code=stock_code, analysis_date=today, period=period,
            support_levels=json.dumps(support_levels),
            resistance_levels=json.dumps(resistance_levels),
            analysis_summary=summary,
        )
        db.session.add(analysis)
    db.session.commit()
```

`get_all_today_analyses()` — 返回按 period 分组的结果：
```python
@staticmethod
def get_all_today_analyses() -> dict:
    today = date.today()
    analyses = WatchAnalysis.query.filter_by(analysis_date=today).all()
    result = {}
    for a in analyses:
        if a.stock_code not in result:
            result[a.stock_code] = {}
        result[a.stock_code][a.period] = {
            'support_levels': json.loads(a.support_levels) if a.support_levels else [],
            'resistance_levels': json.loads(a.resistance_levels) if a.resistance_levels else [],
            'summary': a.analysis_summary,
        }
    return result
```

**Step 3: 数据库迁移**

SQLite 不支持直接 ALTER TABLE 删除列。用以下方式处理：
- 新增 `period` 列（带默认值 `'30d'`）
- 删除旧的唯一约束，添加新约束
- `volatility_threshold` 列保留但不再使用（SQLite 限制）

在 `app/__init__.py` 的 `create_app` 中，在 `db.create_all()` 之后执行迁移：

```python
# 在 create_app 的 db.create_all() 后添加
with app.app_context():
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    columns = [c['name'] for c in inspector.get_columns('watch_analysis')]
    if 'period' not in columns:
        db.session.execute(text("ALTER TABLE watch_analysis ADD COLUMN period VARCHAR(10) NOT NULL DEFAULT '30d'"))
        db.session.commit()
```

**Step 4: Commit**

```bash
git add -A
git commit -m "refactor: WatchAnalysis 新增 period 字段，支持三维度分析"
```

---

### Task 3: 改造 LLM Prompts（三维度分析）

**Files:**
- Modify: `app/llm/prompts/watch_analysis.py`

**Step 1: 重写 prompts**

```python
"""盯盘助手三维度技术分析 Prompt"""

SYSTEM_PROMPT = "你是专业的技术分析师，擅长识别趋势、关键位和市场形态。用简洁中文回答，数据以JSON格式返回。"


def build_realtime_analysis_prompt(stock_name: str, stock_code: str,
                                    intraday_data: list, current_price: float) -> str:
    data_lines = []
    for d in intraday_data[-60:]:
        data_lines.append(f"{d.get('time', '')}: {d.get('close', '')}")
    data_text = "\n".join(data_lines)

    return f"""分析 {stock_name}({stock_code}) 的当日走势，当前价格 {current_price}。

今日分时数据（最近60个点）：
{data_text}

请返回JSON（不要markdown代码块包裹）：
{{
  "support_levels": [当日支撑位1, 支撑位2],
  "resistance_levels": [当日阻力位1, 阻力位2],
  "summary": "50字以内的当日走势解读和短线信号"
}}"""


def build_7d_analysis_prompt(stock_name: str, stock_code: str,
                              ohlc_data: list, current_price: float) -> str:
    data_lines = []
    for d in ohlc_data[-7:]:
        data_lines.append(f"{d['date']}: O={d['open']} H={d['high']} L={d['low']} C={d['close']} V={d.get('volume', 'N/A')}")
    data_text = "\n".join(data_lines)

    return f"""分析 {stock_name}({stock_code}) 的短期趋势，当前价格 {current_price}。

近7日K线数据：
{data_text}

请返回JSON（不要markdown代码块包裹）：
{{
  "support_levels": [短期支撑位1, 支撑位2],
  "resistance_levels": [短期阻力位1, 阻力位2],
  "summary": "80字以内的短期趋势分析，含量价关系和方向判断"
}}"""


def build_30d_analysis_prompt(stock_name: str, stock_code: str,
                               ohlc_data: list, current_price: float) -> str:
    data_lines = []
    for d in ohlc_data[-30:]:
        data_lines.append(f"{d['date']}: O={d['open']} H={d['high']} L={d['low']} C={d['close']} V={d.get('volume', 'N/A')}")
    data_text = "\n".join(data_lines)

    return f"""分析 {stock_name}({stock_code}) 的中期趋势，当前价格 {current_price}。

近30日K线数据：
{data_text}

请返回JSON（不要markdown代码块包裹）：
{{
  "support_levels": [中期支撑位1, 支撑位2],
  "resistance_levels": [中期阻力位1, 阻力位2],
  "summary": "100字以内的中期形态和趋势分析"
}}"""
```

**Step 2: Commit**

```bash
git add app/llm/prompts/watch_analysis.py
git commit -m "refactor: 盯盘AI分析拆分为实时/7天/30天三个prompt"
```

---

### Task 4: 改造后端路由（analyze + chart-data）

**Files:**
- Modify: `app/routes/watch.py`

**Step 1: 改造 analyze 路由**

支持 `period` 参数，三个维度独立分析：

```python
@watch_bp.route('/analyze', methods=['POST'])
def analyze():
    from app.services.unified_stock_data import unified_stock_data_service
    from app.llm.router import llm_router
    from app.llm.prompts.watch_analysis import (
        SYSTEM_PROMPT, build_realtime_analysis_prompt,
        build_7d_analysis_prompt, build_30d_analysis_prompt,
    )

    data = request.get_json() or {}
    period = data.get('period', '30d')  # 'realtime', '7d', '30d'
    force = data.get('force', False)

    codes = WatchService.get_watch_codes()
    if not codes:
        return jsonify({'success': True, 'data': {}, 'message': '盯盘列表为空'})

    # 7d/30d 检查缓存
    if period != 'realtime' and not force:
        existing = WatchService.get_all_today_analyses()
        all_cached = all(
            existing.get(c, {}).get(period) for c in codes
        )
        if all_cached:
            return jsonify({'success': True, 'data': existing, 'message': f'{period} 使用今日缓存'})

    # 获取数据
    if period == 'realtime':
        intraday = unified_stock_data_service.get_intraday_data(codes)
        intraday_map = {s['stock_code']: s for s in intraday.get('stocks', [])}

    days = 7 if period == '7d' else 30
    if period in ('7d', '30d'):
        trend = unified_stock_data_service.get_trend_data(codes, days=days)
        trend_map = {s['stock_code']: s for s in trend.get('stocks', [])}

    raw_prices = unified_stock_data_service.get_realtime_prices(codes)

    provider = llm_router.route('watch_analysis')
    if not provider:
        return jsonify({'success': False, 'message': 'LLM 不可用'})

    for code in codes:
        price_data = raw_prices.get(code, {})
        current_price = price_data.get('current_price', 0)
        stock_name = price_data.get('name', code)
        if not current_price:
            continue

        # 7d/30d 跳过已缓存（非强制）
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
                prompt = build_realtime_analysis_prompt(stock_name, code, intraday_data, current_price)
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
            )
        except Exception as e:
            logger.error(f"[盯盘AI] {code} {period}分析失败: {e}")

    all_analyses = WatchService.get_all_today_analyses()
    return jsonify({'success': True, 'data': all_analyses})
```

**Step 2: 改造 chart-data 路由**

增加 `last_timestamp` 增量模式，收盘时返回上一交易日数据：

```python
@watch_bp.route('/chart-data')
def chart_data():
    from app.services.unified_stock_data import unified_stock_data_service
    from app.services.trading_calendar import TradingCalendarService
    from app.utils.market_identifier import MarketIdentifier

    code = request.args.get('code', '').strip()
    period = request.args.get('period', 'intraday')
    last_timestamp = request.args.get('last_timestamp', '').strip()

    if not code:
        return jsonify({'success': False, 'message': '缺少股票代码'})

    result = {'success': True, 'code': code, 'period': period}

    if period == 'intraday':
        market = MarketIdentifier.identify(code) or 'A'
        is_open = TradingCalendarService.is_market_open(market)

        intraday = unified_stock_data_service.get_intraday_data([code])
        stocks = intraday.get('stocks', [])
        all_data = stocks[0]['data'] if stocks else []

        if last_timestamp and all_data:
            # 增量模式：只返回 last_timestamp 之后的数据
            all_data = [d for d in all_data if d.get('time', '') > last_timestamp]

        result['data'] = all_data
        result['chart_type'] = 'line'
        result['is_open'] = is_open
    else:
        days_map = {'7d': 7, '30d': 30, '90d': 90}
        days = days_map.get(period, 30)
        fetch_days = days + 20
        trend = unified_stock_data_service.get_trend_data([code], days=fetch_days)
        stocks = trend.get('stocks', [])
        ohlc_data = stocks[0]['data'] if stocks else []

        bollinger = []
        if len(ohlc_data) >= 20:
            closes = [d['close'] for d in ohlc_data]
            for i in range(len(closes)):
                if i < 19:
                    bollinger.append(None)
                    continue
                window = closes[i-19:i+1]
                ma = sum(window) / 20
                std = (sum((x - ma) ** 2 for x in window) / 20) ** 0.5
                bollinger.append({
                    'upper': round(ma + 2 * std, 2),
                    'middle': round(ma, 2),
                    'lower': round(ma - 2 * std, 2),
                })

        result['data'] = ohlc_data[-days:]
        result['bollinger'] = bollinger[-days:]
        result['chart_type'] = 'candlestick'

    # 所有维度的分析
    analysis_data = WatchService.get_today_analysis(code)
    if analysis_data and isinstance(analysis_data, dict):
        # 合并所有维度的支撑/阻力
        all_supports = []
        all_resistances = []
        for p_data in analysis_data.values():
            all_supports.extend(p_data.get('support_levels', []))
            all_resistances.extend(p_data.get('resistance_levels', []))
        result['support_levels'] = sorted(set(all_supports))
        result['resistance_levels'] = sorted(set(all_resistances))
    else:
        result['support_levels'] = []
        result['resistance_levels'] = []

    return jsonify(result)
```

**Step 3: Commit**

```bash
git add app/routes/watch.py
git commit -m "refactor: 盯盘路由支持三维度分析和增量分时数据"
```

---

### Task 5: 重写前端页面 watch.html

**Files:**
- Rewrite: `app/templates/watch.html`

**Step 1: 重写页面布局**

新布局：全宽单列，每股票一个大卡片（内嵌分时线 + AI分析 tab）：

```html
{% extends 'base.html' %}
{% block title %}盯盘助手{% endblock %}

{% block extra_css %}
<style>
.stock-card { border-radius: 8px; transition: box-shadow 0.2s; }
.stock-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
.chart-container { height: 200px; border-radius: 4px; background: #fafafa; }
.analysis-tab .nav-link { padding: 0.25rem 0.75rem; font-size: 0.8rem; }
.analysis-tab .nav-link.active { font-weight: 600; }
.analysis-content { font-size: 0.85rem; min-height: 40px; }
.market-bar { background: #f8f9fa; border-radius: 6px; padding: 0.5rem 1rem; }
.price-up { color: #dc3545; }
.price-down { color: #28a745; }
.price-flat { color: #6c757d; }
</style>
{% endblock %}

{% block content %}
<div class="page-header mb-3">
    <div class="d-flex justify-content-between align-items-center">
        <div>
            <h4 class="mb-1"><i class="bi bi-eye"></i> 盯盘助手</h4>
            <small class="text-muted" id="watchStatus">加载中...</small>
        </div>
        <div class="d-flex align-items-center gap-2">
            <button class="btn btn-outline-primary btn-sm" id="btnAnalyze" onclick="Watch.triggerAllAnalysis()">
                <i class="bi bi-robot"></i> AI 分析
            </button>
            <button class="btn btn-primary btn-sm" data-bs-toggle="modal" data-bs-target="#addStockModal">
                <i class="bi bi-plus-lg"></i> 添加
            </button>
        </div>
    </div>
</div>

<!-- 市场状态栏 -->
<div id="marketBar" class="market-bar mb-3 d-none"></div>

<!-- 骨架屏 -->
<div id="loadingState" class="py-3">
    <div class="skeleton-card skeleton mb-3" style="height:300px;"></div>
    <div class="skeleton-card skeleton mb-3" style="height:300px;"></div>
</div>

<!-- 空状态 -->
<div id="emptyState" class="text-center py-5 d-none">
    <i class="bi bi-eye-slash text-muted" style="font-size: 3rem;"></i>
    <p class="mt-3 text-muted">暂无盯盘股票</p>
    <button class="btn btn-primary btn-sm" data-bs-toggle="modal" data-bs-target="#addStockModal">
        <i class="bi bi-plus-lg"></i> 添加股票
    </button>
</div>

<!-- 股票卡片列表 -->
<div id="stockCards" class="d-none"></div>

<!-- 添加股票 Modal（同现有） -->
<div class="modal fade" id="addStockModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title"><i class="bi bi-plus-circle"></i> 添加盯盘股票</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <div class="mb-3">
                    <input type="text" class="form-control" id="stockSearchInput"
                           placeholder="搜索股票代码或名称..." oninput="Watch.searchStocks(this.value)">
                </div>
                <div id="searchResults" class="list-group" style="max-height: 300px; overflow-y: auto;"></div>
            </div>
        </div>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script src="{{ url_for('static', filename='js/watch.js') }}"></script>
{% endblock %}
```

**Step 2: Commit**

```bash
git add app/templates/watch.html
git commit -m "refactor: 重写盯盘助手页面布局为卡片式"
```

---

### Task 6: 重写前端 JS — watch.js

**Files:**
- Rewrite: `app/static/js/watch.js`

**Step 1: 重写完整 JS**

核心变更点：
1. 每只股票默认展开分时线（不再折叠）
2. 前端60秒定时轮询，开盘时增量追加分时数据
3. AI分析按三维度分别请求和显示
4. 移除通知冷却/波动阈值相关UI

```javascript
const Watch = {
    REFRESH_INTERVAL: 60,
    searchDebounce: null,
    stocks: [],
    prices: [],
    marketStatus: {},
    analyses: {},
    chartInstances: {},
    chartData: {},  // 每只股票缓存的分时数据
    refreshTimer: null,

    async init() {
        await this.loadList();
        await this.loadAnalysis();
    },

    // ========== 数据加载 ==========

    async loadList() {
        try {
            const [listResp, priceResp, marketResp] = await Promise.all([
                fetch('/watch/list'),
                fetch('/watch/prices'),
                fetch('/watch/market-status'),
            ]);
            const listData = await listResp.json();
            const priceData = await priceResp.json();
            const marketData = await marketResp.json();

            if (!listData.success) return;
            this.stocks = listData.data || [];
            this.prices = priceData.prices || [];
            this.marketStatus = marketData.data || {};

            if (this.stocks.length === 0) {
                this.showEmpty();
                return;
            }

            this.renderMarketBar();
            this.renderCards();
            this.updateStatus(`${this.stocks.length} 只股票`);

            // 加载每只股票的分时数据
            await this.loadAllCharts();

            // 启动轮询（如果有市场在交易中）
            this.startRefreshLoop();
        } catch (e) {
            console.error('[Watch] loadList failed:', e);
            this.updateStatus('加载失败');
        }
    },

    async loadAllCharts() {
        const promises = this.stocks.map(s => this.loadChartData(s.stock_code));
        await Promise.all(promises);
    },

    async loadChartData(code) {
        const container = document.getElementById(`chart-${code}`);
        if (!container) return;

        try {
            const resp = await fetch(`/watch/chart-data?code=${encodeURIComponent(code)}&period=intraday`);
            const result = await resp.json();
            if (!result.success) return;

            this.chartData[code] = result.data || [];
            this.renderChart(code);
        } catch (e) {
            console.error(`[Watch] chart load failed ${code}:`, e);
            container.innerHTML = '<div class="text-muted text-center small py-4">图表加载失败</div>';
        }
    },

    async refreshIncrementalData() {
        try {
            const [priceResp, marketResp] = await Promise.all([
                fetch('/watch/prices'),
                fetch('/watch/market-status'),
            ]);
            const priceData = await priceResp.json();
            const marketData = await marketResp.json();

            if (priceData.success) {
                this.prices = priceData.prices || [];
                this.updateAllPrices();
            }
            this.marketStatus = marketData.data || {};
            this.renderMarketBar();

            // 增量更新分时图（仅交易中的股票）
            for (const stock of this.stocks) {
                const market = stock.market || 'A';
                const ms = this.marketStatus[market];
                if (!ms || ms.status !== 'trading') continue;

                const existing = this.chartData[stock.stock_code] || [];
                const lastTime = existing.length > 0 ? existing[existing.length - 1].time : '';

                try {
                    const url = `/watch/chart-data?code=${encodeURIComponent(stock.stock_code)}&period=intraday&last_timestamp=${encodeURIComponent(lastTime)}`;
                    const resp = await fetch(url);
                    const result = await resp.json();
                    if (result.success && result.data && result.data.length > 0) {
                        this.chartData[stock.stock_code] = [...existing, ...result.data];
                        this.renderChart(stock.stock_code);
                    }
                } catch (e) {
                    console.error(`[Watch] incremental update failed ${stock.stock_code}:`, e);
                }
            }
        } catch (e) {
            console.error('[Watch] refresh failed:', e);
        }
    },

    // ========== 轮询控制 ==========

    startRefreshLoop() {
        this.stopRefreshLoop();
        const hasActiveMarket = Object.values(this.marketStatus).some(m => m.status === 'trading');
        if (!hasActiveMarket) return;

        this.refreshTimer = setInterval(() => this.refreshIncrementalData(), this.REFRESH_INTERVAL * 1000);
    },

    stopRefreshLoop() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
            this.refreshTimer = null;
        }
    },

    // ========== AI 分析 ==========

    async loadAnalysis() {
        try {
            const resp = await fetch('/watch/analysis');
            const data = await resp.json();
            if (data.success) {
                this.analyses = data.data || {};
                this.updateAllAnalysisPanels();
            }
        } catch (e) {
            console.error('[Watch] loadAnalysis failed:', e);
        }
    },

    async triggerAllAnalysis() {
        const btn = document.getElementById('btnAnalyze');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> 分析中...';

        try {
            // 三个维度并行请求
            const hasActiveMarket = Object.values(this.marketStatus).some(m => m.status === 'trading');
            const periods = hasActiveMarket ? ['realtime', '7d', '30d'] : ['7d', '30d'];

            await Promise.all(periods.map(period =>
                fetch('/watch/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ period, force: period === 'realtime' }),
                }).then(r => r.json())
            ));

            await this.loadAnalysis();
        } catch (e) {
            console.error('[Watch] triggerAllAnalysis failed:', e);
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-robot"></i> AI 分析';
        }
    },

    // ========== 股票管理 ==========

    async addStock(code, name) {
        try {
            const resp = await fetch('/watch/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ stock_code: code, stock_name: name }),
            });
            const data = await resp.json();
            if (data.success) {
                const modal = bootstrap.Modal.getInstance(document.getElementById('addStockModal'));
                if (modal) modal.hide();
                document.getElementById('stockSearchInput').value = '';
                document.getElementById('searchResults').innerHTML = '';
                await this.loadList();
            } else {
                alert(data.message || '添加失败');
            }
        } catch (e) {
            console.error('[Watch] addStock failed:', e);
        }
    },

    async removeStock(code) {
        if (!confirm('确定移除该股票？')) return;
        try {
            const resp = await fetch(`/watch/remove/${code}`, { method: 'DELETE' });
            const data = await resp.json();
            if (data.success) {
                if (this.chartInstances[code]) {
                    this.chartInstances[code].dispose();
                    delete this.chartInstances[code];
                }
                delete this.chartData[code];
                this.stocks = this.stocks.filter(s => s.stock_code !== code);
                this.prices = this.prices.filter(p => p.code !== code);
                if (this.stocks.length === 0) {
                    this.showEmpty();
                } else {
                    this.renderCards();
                    this.loadAllCharts();
                }
                this.updateStatus(`${this.stocks.length} 只股票`);
            }
        } catch (e) {
            console.error('[Watch] removeStock failed:', e);
        }
    },

    searchStocks(query) {
        clearTimeout(this.searchDebounce);
        this.searchDebounce = setTimeout(async () => {
            const container = document.getElementById('searchResults');
            if (!query.trim()) { container.innerHTML = ''; return; }
            try {
                const resp = await fetch(`/watch/stocks/search?q=${encodeURIComponent(query)}`);
                const data = await resp.json();
                if (!data.success) return;
                const existingCodes = new Set(this.stocks.map(s => s.stock_code));
                container.innerHTML = (data.data || []).map(s => {
                    const added = existingCodes.has(s.stock_code);
                    return `<div class="list-group-item d-flex justify-content-between align-items-center">
                        <div><span class="fw-bold">${s.stock_name}</span> <small class="text-muted ms-2">${s.stock_code}</small></div>
                        ${added
                            ? '<span class="badge bg-secondary">已添加</span>'
                            : `<button class="btn btn-sm btn-outline-primary" onclick="Watch.addStock('${s.stock_code}','${s.stock_name}')">添加</button>`}
                    </div>`;
                }).join('') || '<div class="list-group-item text-muted text-center">无匹配结果</div>';
            } catch (e) { console.error('[Watch] search failed:', e); }
        }, 300);
    },

    // ========== 渲染 ==========

    renderMarketBar() {
        const bar = document.getElementById('marketBar');
        const markets = Object.entries(this.marketStatus);
        if (markets.length === 0) { bar.classList.add('d-none'); return; }

        bar.classList.remove('d-none');
        bar.innerHTML = markets.map(([key, ms]) => {
            const icon = this.getStatusIcon(ms.status);
            return `<span class="me-3">
                ${ms.icon || ''} <strong>${ms.name}</strong>
                <small class="text-muted">${ms.time}</small>
                <span class="badge ${this.getStatusBadgeClass(ms.status)} ms-1">${icon} ${ms.status_text}</span>
            </span>`;
        }).join('');
    },

    renderCards() {
        Object.values(this.chartInstances).forEach(c => c.dispose());
        this.chartInstances = {};

        const pricesMap = {};
        this.prices.forEach(p => { pricesMap[p.code] = p; });

        const container = document.getElementById('stockCards');
        container.innerHTML = this.stocks.map(stock => {
            const code = stock.stock_code;
            const name = stock.stock_name || code;
            const market = stock.market || 'A';
            const p = pricesMap[code] || {};

            const priceDisplay = p.price != null ? this.formatPrice(p.price, market) : '--';
            const pctClass = p.change_pct > 0 ? 'price-up' : p.change_pct < 0 ? 'price-down' : 'price-flat';
            const pctSign = p.change_pct > 0 ? '+' : '';
            const pctDisplay = p.change_pct != null ? `${pctSign}${p.change_pct.toFixed(2)}%` : '--';
            const changeDisplay = p.change != null ? `${p.change > 0 ? '+' : ''}${p.change.toFixed(2)}` : '';

            return `<div class="card stock-card mb-3" id="card-${code}">
                <div class="card-body">
                    <div class="d-flex justify-content-between align-items-center mb-2">
                        <div>
                            <span class="fw-bold fs-6">${name}</span>
                            <small class="text-muted ms-2">${code}</small>
                        </div>
                        <div class="d-flex align-items-center gap-3">
                            <div class="text-end">
                                <span class="fs-5 fw-bold" data-field="price" data-code="${code}">${priceDisplay}</span>
                                <span class="${pctClass} fw-bold ms-2" data-field="change_pct" data-code="${code}">${pctDisplay}</span>
                                <span class="${pctClass} small ms-1" data-field="change" data-code="${code}">${changeDisplay}</span>
                            </div>
                            <button class="btn btn-sm btn-link text-muted p-0" onclick="Watch.removeStock('${code}')" title="移除">
                                <i class="bi bi-x-lg"></i>
                            </button>
                        </div>
                    </div>

                    <!-- 分时线 -->
                    <div class="chart-container mb-2" id="chart-${code}">
                        <div class="skeleton skeleton-card" style="height:100%;"></div>
                    </div>

                    <!-- AI 分析 tabs -->
                    <div class="analysis-section" id="analysis-${code}">
                        <ul class="nav nav-tabs analysis-tab mb-2" role="tablist">
                            <li class="nav-item">
                                <button class="nav-link active" data-period="realtime" onclick="Watch.switchAnalysisTab('${code}', 'realtime', this)">实时</button>
                            </li>
                            <li class="nav-item">
                                <button class="nav-link" data-period="7d" onclick="Watch.switchAnalysisTab('${code}', '7d', this)">7天</button>
                            </li>
                            <li class="nav-item">
                                <button class="nav-link" data-period="30d" onclick="Watch.switchAnalysisTab('${code}', '30d', this)">30天</button>
                            </li>
                        </ul>
                        <div class="analysis-content" id="analysis-content-${code}">
                            <span class="text-muted small">点击「AI 分析」获取分析结果</span>
                        </div>
                    </div>
                </div>
            </div>`;
        }).join('');

        document.getElementById('loadingState').classList.add('d-none');
        document.getElementById('emptyState').classList.add('d-none');
        container.classList.remove('d-none');
    },

    renderChart(code) {
        const container = document.getElementById(`chart-${code}`);
        if (!container) return;
        const data = this.chartData[code] || [];

        if (data.length === 0) {
            container.innerHTML = '<div class="text-muted text-center small py-4">暂无分时数据</div>';
            return;
        }

        if (this.chartInstances[code]) {
            // 增量更新：直接 setOption
            const chart = this.chartInstances[code];
            const times = data.map(d => d.time);
            const prices = data.map(d => d.close);
            chart.setOption({
                xAxis: { data: times },
                series: [{ data: prices }],
            });
            return;
        }

        container.innerHTML = '';
        const chart = echarts.init(container);
        this.chartInstances[code] = chart;

        const times = data.map(d => d.time);
        const prices = data.map(d => d.close);

        // 支撑/阻力线
        const analysis = this.analyses[code] || {};
        const markLines = [];
        const allSupports = new Set();
        const allResistances = new Set();
        Object.values(analysis).forEach(a => {
            (a.support_levels || []).forEach(l => allSupports.add(l));
            (a.resistance_levels || []).forEach(l => allResistances.add(l));
        });
        allSupports.forEach(level => {
            markLines.push({
                yAxis: level,
                lineStyle: { color: '#28a745', type: 'dashed', width: 1 },
                label: { formatter: String(level), position: 'end', fontSize: 9, color: '#28a745' },
            });
        });
        allResistances.forEach(level => {
            markLines.push({
                yAxis: level,
                lineStyle: { color: '#dc3545', type: 'dashed', width: 1 },
                label: { formatter: String(level), position: 'end', fontSize: 9, color: '#dc3545' },
            });
        });

        chart.setOption({
            grid: { left: 8, right: 55, top: 8, bottom: 20, containLabel: false },
            tooltip: {
                trigger: 'axis',
                formatter: params => `${params[0].axisValue}<br/>${params[0].value.toFixed(2)}`,
            },
            xAxis: {
                type: 'category',
                data: times,
                axisLabel: { fontSize: 9, interval: Math.floor(times.length / 4) },
                axisLine: { lineStyle: { color: '#ddd' } },
            },
            yAxis: {
                type: 'value',
                scale: true,
                splitLine: { lineStyle: { color: '#f0f0f0' } },
                axisLabel: { fontSize: 9 },
            },
            series: [{
                type: 'line',
                data: prices,
                smooth: true,
                symbol: 'none',
                lineStyle: { width: 1.5, color: '#1890ff' },
                areaStyle: { color: 'rgba(24,144,255,0.08)' },
                markLine: markLines.length > 0 ? { silent: true, symbol: 'none', data: markLines } : undefined,
            }],
        });

        new ResizeObserver(() => chart.resize()).observe(container);
    },

    switchAnalysisTab(code, period, btn) {
        const section = document.getElementById(`analysis-${code}`);
        section.querySelectorAll('.nav-link').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this.renderAnalysisContent(code, period);
    },

    updateAllAnalysisPanels() {
        this.stocks.forEach(stock => {
            const code = stock.stock_code;
            const section = document.getElementById(`analysis-${code}`);
            if (!section) return;
            const activeBtn = section.querySelector('.nav-link.active');
            const activePeriod = activeBtn ? activeBtn.dataset.period : 'realtime';
            this.renderAnalysisContent(code, activePeriod);
        });
    },

    renderAnalysisContent(code, period) {
        const el = document.getElementById(`analysis-content-${code}`);
        if (!el) return;

        const codeAnalysis = this.analyses[code] || {};
        const periodData = codeAnalysis[period];

        if (!periodData) {
            el.innerHTML = '<span class="text-muted small">暂无分析数据</span>';
            return;
        }

        const supports = periodData.support_levels || [];
        const resistances = periodData.resistance_levels || [];
        const summary = periodData.summary || '';

        let html = '';
        if (summary) {
            html += `<div class="mb-1">${summary}</div>`;
        }
        if (supports.length > 0) {
            html += `<span class="text-success small me-2">支撑: ${supports.join(' / ')}</span>`;
        }
        if (resistances.length > 0) {
            html += `<span class="text-danger small">阻力: ${resistances.join(' / ')}</span>`;
        }
        el.innerHTML = html || '<span class="text-muted small">暂无分析数据</span>';
    },

    updateAllPrices() {
        const pricesMap = {};
        this.prices.forEach(p => { pricesMap[p.code] = p; });

        this.stocks.forEach(stock => {
            const code = stock.stock_code;
            const market = stock.market || 'A';
            const p = pricesMap[code];
            if (!p) return;

            const priceEl = document.querySelector(`[data-field="price"][data-code="${code}"]`);
            if (priceEl && p.price != null) priceEl.textContent = this.formatPrice(p.price, market);

            const pctClass = p.change_pct > 0 ? 'price-up' : p.change_pct < 0 ? 'price-down' : 'price-flat';
            const pctSign = p.change_pct > 0 ? '+' : '';

            const pctEl = document.querySelector(`[data-field="change_pct"][data-code="${code}"]`);
            if (pctEl && p.change_pct != null) {
                pctEl.textContent = `${pctSign}${p.change_pct.toFixed(2)}%`;
                pctEl.className = `${pctClass} fw-bold ms-2`;
            }

            const amtEl = document.querySelector(`[data-field="change"][data-code="${code}"]`);
            if (amtEl && p.change != null) {
                amtEl.textContent = `${p.change > 0 ? '+' : ''}${p.change.toFixed(2)}`;
                amtEl.className = `${pctClass} small ms-1`;
            }
        });
    },

    // ========== 工具函数 ==========

    showEmpty() {
        document.getElementById('loadingState').classList.add('d-none');
        document.getElementById('stockCards').classList.add('d-none');
        document.getElementById('marketBar').classList.add('d-none');
        document.getElementById('emptyState').classList.remove('d-none');
        this.updateStatus('暂无盯盘股票');
    },

    updateStatus(text) {
        document.getElementById('watchStatus').textContent = text;
    },

    formatPrice(price, market) {
        const val = price.toFixed(2);
        if (market === 'US') return `$${val}`;
        if (market === 'HK') return `HK$${val}`;
        if (market === 'KR') return `₩${Math.round(price).toLocaleString()}`;
        if (market === 'JP') return `¥${Math.round(price).toLocaleString()}`;
        if (market === 'TW') return `NT$${val}`;
        return `¥${val}`;
    },

    getStatusIcon(status) {
        const map = { trading: '🟢', lunch: '🟡', closed: '⚫', pre_open: '⚪', holiday: '⚫' };
        return map[status] || '⚫';
    },

    getStatusBadgeClass(status) {
        const map = {
            trading: 'bg-success bg-opacity-25 text-success',
            lunch: 'bg-warning bg-opacity-25 text-warning',
            closed: 'bg-secondary bg-opacity-25 text-secondary',
            pre_open: 'bg-info bg-opacity-25 text-info',
            holiday: 'bg-secondary bg-opacity-25 text-secondary',
        };
        return map[status] || 'bg-secondary';
    },
};

document.addEventListener('DOMContentLoaded', () => Watch.init());
```

**Step 2: Commit**

```bash
git add app/static/js/watch.js
git commit -m "refactor: 重写盯盘助手JS，实现实时分时线和三维度AI分析"
```

---

### Task 7: 数据库迁移和最终验证

**Files:**
- Modify: `app/__init__.py` (添加迁移代码)

**Step 1: 在 create_app 中添加 watch_analysis 表迁移**

在 `db.create_all()` 之后添加：

```python
from sqlalchemy import inspect, text
inspector = inspect(db.engine)
if 'watch_analysis' in inspector.get_table_names():
    columns = [c['name'] for c in inspector.get_columns('watch_analysis')]
    if 'period' not in columns:
        db.session.execute(text("ALTER TABLE watch_analysis ADD COLUMN period VARCHAR(10) NOT NULL DEFAULT '30d'"))
        db.session.commit()
        logger.info('[迁移] watch_analysis 新增 period 字段')
```

**Step 2: 启动应用验证**

Run: `python run.py`

验证点：
1. 盯盘助手页面能打开
2. 股票列表正常显示
3. 分时图正常加载
4. AI分析三维度正常工作
5. 后台不再有 watch_assistant 策略日志

**Step 3: 最终 Commit**

```bash
git add -A
git commit -m "feat: 盯盘助手优化完成 — 实时分时线 + 三维度AI分析"
```
