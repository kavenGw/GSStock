# 盯盘助手架构重整 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 重整盯盘助手架构，实现缓存优先加载、休市显示上一交易日、自动AI分析、按市场分组显示。

**Architecture:** 在现有三层缓存 + Flask API 基础上增量改造。后端增加 cache_only 模式和休市日期自动回退；前端改为两阶段初始化 + 双定时器 + 市场分组渲染。

**Tech Stack:** Flask, SQLAlchemy, JavaScript (vanilla), ECharts

---

### Task 1: 后端 — `get_realtime_prices` 增加 `cache_only` 参数

**Files:**
- Modify: `app/services/unified_stock_data.py:390` — `get_realtime_prices` 方法
- Modify: `app/routes/watch.py:40-61` — `/prices` 路由

**Step 1: 修改 `get_realtime_prices` 签名和逻辑**

在 `app/services/unified_stock_data.py` 的 `get_realtime_prices` 方法中增加 `cache_only` 参数：

```python
def get_realtime_prices(self, stock_codes: list, force_refresh: bool = False, cache_only: bool = False) -> dict:
```

在第一层内存缓存和第二层DB缓存查询之后、第三层API获取（`need_refresh` 列表处理）之前，加入判断：

```python
# cache_only 模式：不触发API获取，直接返回已有缓存
if cache_only:
    logger.info(f"[数据服务.实时价格] cache_only模式: 返回 {len(result)}只缓存数据, 跳过 {len(need_refresh)}只")
    return result
```

**Step 2: 修改 `/watch/prices` 路由支持 `cache_only` 参数**

在 `app/routes/watch.py` 的 `prices()` 函数中：

```python
@watch_bp.route('/prices')
def prices():
    from app.services.unified_stock_data import unified_stock_data_service

    codes = WatchService.get_watch_codes()
    if not codes:
        return jsonify({'success': True, 'prices': []})

    cache_only = request.args.get('cache_only', 'false').lower() == 'true'
    raw_prices = unified_stock_data_service.get_realtime_prices(codes, cache_only=cache_only)
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

**Step 3: Commit**

```bash
git add app/services/unified_stock_data.py app/routes/watch.py
git commit -m "feat(watch): add cache_only mode to prices API"
```

---

### Task 2: 后端 — `/chart-data` 休市自动返回上一交易日分时线

**Files:**
- Modify: `app/routes/watch.py:250-321` — `/chart-data` 路由的 intraday 分支

**Step 1: 修改 chart_data 函数的 intraday 分支**

在 `period == 'intraday'` 分支中，休市且无数据时回退到上一交易日。响应增加 `trading_date` 和 `is_trading` 字段：

```python
if period == 'intraday':
    market = MarketIdentifier.identify(code) or 'A'
    is_open = TradingCalendarService.is_market_open(market)

    intraday = unified_stock_data_service.get_intraday_data([code])
    stocks = intraday.get('stocks', [])
    all_data = stocks[0]['data'] if stocks else []

    from app.services.market_session import SmartCacheStrategy
    effective_date = SmartCacheStrategy.get_effective_cache_date(code)
    trading_date = effective_date.strftime('%Y-%m-%d')

    if last_timestamp and all_data:
        all_data = [d for d in all_data if d.get('time', '') > last_timestamp]

    result['data'] = all_data
    result['chart_type'] = 'line'
    result['is_open'] = is_open
    result['is_trading'] = is_open
    result['trading_date'] = trading_date
```

注意：`get_intraday_data` 内部已通过 `SmartCacheStrategy.get_effective_cache_date()` 自动选择有效缓存日期，非交易时间会自动返回上一交易日的缓存数据。这里用同一方法获取 `trading_date` 保持一致。

**Step 2: Commit**

```bash
git add app/routes/watch.py
git commit -m "feat(watch): return trading_date in chart-data response"
```

---

### Task 3: 前端 — 两阶段初始化 + autoAnalyze

**Files:**
- Modify: `app/static/js/watch.js` — `init()`, `loadList()` 方法，新增 `autoAnalyze()`

**Step 1: 重写 init() 为两阶段**

```javascript
async init() {
    // 阶段1：快速加载（缓存优先）
    await this.loadList(true);

    // 阶段2：自动触发AI分析（7d/30d，有缓存跳过）
    this.autoAnalyze();

    // 阶段3：启动定时器
    this.startRefreshLoop();
    this.startAnalysisLoop();
},
```

**Step 2: 修改 loadList 支持 cache_only 参数**

```javascript
async loadList(cacheOnly = false) {
    try {
        const priceUrl = cacheOnly ? '/watch/prices?cache_only=true' : '/watch/prices';
        const [listResp, priceResp, marketResp] = await Promise.all([
            fetch('/watch/list'),
            fetch(priceUrl),
            fetch('/watch/market-status'),
        ]);
        // ... 后续逻辑不变
```

**Step 3: 新增 autoAnalyze 方法**

```javascript
async autoAnalyze() {
    try {
        await Promise.all([
            fetch('/watch/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ period: '7d', force: false }),
            }),
            fetch('/watch/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ period: '30d', force: false }),
            }),
        ]);
        await this.loadAnalysis();
    } catch (e) {
        console.error('[Watch] autoAnalyze failed:', e);
    }
},
```

**Step 4: Commit**

```bash
git add app/static/js/watch.js
git commit -m "feat(watch): two-phase init with cache-first loading and auto-analyze"
```

---

### Task 4: 前端 — 15分钟 AI 分析定时器

**Files:**
- Modify: `app/static/js/watch.js` — 新增定时器相关方法

**Step 1: 添加状态和定时器方法**

在 Watch 对象中添加：

```javascript
analysisTimer: null,
ANALYSIS_INTERVAL: 15 * 60,  // 15分钟（秒）

startAnalysisLoop() {
    this.stopAnalysisLoop();
    const hasActiveMarket = Object.values(this.marketStatus).some(m => m.status === 'trading');
    if (!hasActiveMarket) return;

    this.analysisTimer = setInterval(async () => {
        const hasActive = Object.values(this.marketStatus).some(m => m.status === 'trading');
        if (!hasActive) {
            this.stopAnalysisLoop();
            return;
        }
        try {
            await fetch('/watch/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ period: 'realtime', force: true }),
            });
            await this.loadAnalysis();
        } catch (e) {
            console.error('[Watch] analysis loop failed:', e);
        }
    }, this.ANALYSIS_INTERVAL * 1000);
},

stopAnalysisLoop() {
    if (this.analysisTimer) {
        clearInterval(this.analysisTimer);
        this.analysisTimer = null;
    }
},
```

**Step 2: 在 refreshIncrementalData 末尾管理定时器**

```javascript
// 在 refreshIncrementalData() 末尾添加
const hasActiveMarket = Object.values(this.marketStatus).some(m => m.status === 'trading');
if (!hasActiveMarket) {
    this.stopRefreshLoop();
    this.stopAnalysisLoop();
} else if (!this.analysisTimer) {
    this.startAnalysisLoop();
}
```

**Step 3: Commit**

```bash
git add app/static/js/watch.js
git commit -m "feat(watch): add 15-minute auto AI analysis timer"
```

---

### Task 5: 前端 — 按市场分组渲染

**Files:**
- Modify: `app/static/js/watch.js` — `renderCards()` 方法
- Modify: `app/templates/watch.html` — 删除独立市场状态栏

**Step 1: 提取 renderStockCard 方法**

把现有 `renderCards()` 中单个卡片的 HTML 生成逻辑提取为：

```javascript
renderStockCard(stock, pricesMap) {
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
            <!-- 同现有卡片内容完全一致 -->
        </div>
    </div>`;
},
```

**Step 2: 重写 renderCards() 按市场分组**

```javascript
renderCards() {
    Object.values(this.chartInstances).forEach(c => c.dispose());
    this.chartInstances = {};

    const pricesMap = {};
    this.prices.forEach(p => { pricesMap[p.code] = p; });

    // 按市场分组
    const groups = {};
    this.stocks.forEach(stock => {
        const market = stock.market || 'A';
        if (!groups[market]) groups[market] = [];
        groups[market].push(stock);
    });

    // 按 marketStatus 中的顺序排列
    const marketOrder = Object.keys(this.marketStatus);
    const sortedMarkets = Object.keys(groups).sort((a, b) => {
        const ai = marketOrder.indexOf(a);
        const bi = marketOrder.indexOf(b);
        return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
    });

    const container = document.getElementById('stockCards');
    let html = '';

    for (const market of sortedMarkets) {
        const ms = this.marketStatus[market] || {};
        const icon = ms.icon || '';
        const name = ms.name || market;
        const statusText = ms.status_text || '';
        const statusBadge = this.getStatusBadgeClass(ms.status || 'closed');
        const statusIcon = this.getStatusIcon(ms.status || 'closed');

        html += `<div class="market-group mb-4">
            <div class="d-flex align-items-center mb-2">
                <span class="fw-bold">${icon} ${name}</span>
                <span class="badge ${statusBadge} ms-2">${statusIcon} ${statusText}</span>
            </div>
            <div class="market-stocks">`;

        for (const stock of groups[market]) {
            html += this.renderStockCard(stock, pricesMap);
        }

        html += `</div></div>`;
    }

    container.innerHTML = html;
    document.getElementById('loadingState').classList.add('d-none');
    document.getElementById('emptyState').classList.add('d-none');
    container.classList.remove('d-none');
},
```

**Step 3: 删除独立市场状态栏**

- 从 `watch.html` 中删除 `<div id="marketBar" ...>`
- 从 `watch.js` 中删除 `renderMarketBar()` 方法及其调用

**Step 4: Commit**

```bash
git add app/static/js/watch.js app/templates/watch.html
git commit -m "feat(watch): render stock cards grouped by market with inline status"
```

---

### Task 6: 前端 — 图表显示交易日期提示

**Files:**
- Modify: `app/static/js/watch.js` — `loadChartData()`, `renderChart()`

**Step 1: 添加 chartMeta 状态**

```javascript
chartMeta: {},  // 添加到 Watch 对象顶部
```

**Step 2: 在 loadChartData 中保存 meta**

```javascript
async loadChartData(code) {
    // ... 获取数据后
    this.chartData[code] = result.data || [];
    this.chartMeta[code] = {
        tradingDate: result.trading_date,
        isTrading: result.is_trading,
    };
    this.renderChart(code);
},
```

**Step 3: 在 renderChart 中显示日期提示**

当 `isTrading === false` 时，在图表上方显示提示：

```javascript
renderChart(code) {
    const container = document.getElementById(`chart-${code}`);
    if (!container) return;
    const data = this.chartData[code] || [];

    if (data.length === 0) {
        container.innerHTML = '<div class="text-muted text-center small py-4">暂无分时数据</div>';
        return;
    }

    // 日期提示（休市时显示）
    const meta = this.chartMeta[code] || {};
    const dateHint = (meta.isTrading === false && meta.tradingDate)
        ? `<div class="text-muted text-center small mb-1">${meta.tradingDate} 分时数据</div>`
        : '';

    // ... 现有 ECharts 逻辑
```

**Step 4: Commit**

```bash
git add app/static/js/watch.js
git commit -m "feat(watch): show trading date hint for closed market charts"
```

---

### Task 7: 集成验证

**Step 1: 全流程测试**

启动应用 `python run.py`，打开盯盘页面验证：
1. 页面首次加载走 cache_only 快速渲染
2. 股票按市场分组显示，分组标题含市场状态
3. 7d/30d 分析自动触发（有缓存跳过）
4. 开市中：价格定时刷新 + 15分钟AI分析自动执行
5. 休市：显示上一交易日分时线 + 日期提示
6. 手动 AI 分析按钮正常工作
7. 添加/移除股票后分组正确更新

**Step 2: Final Commit（如有修复）**
