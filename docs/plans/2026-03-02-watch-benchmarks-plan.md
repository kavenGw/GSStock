# 盯盘助手 - 预置商品/指数监控区域 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在盯盘助手页面顶部新增固定的"商品/指数"横向卡片区域，展示黄金、白银、纳指100的实时价格和涨跌幅。

**Architecture:** 在 `stock_codes.py` 新增 `BENCHMARK_CODES` 配置，`watch.py` 路由新增 `/watch/benchmarks` 端点获取实时价格，前端在页面标题和自选股之间渲染一行紧凑的横向卡片，并随自选股一起 60 秒自动刷新。

**Tech Stack:** Flask, yfinance (via UnifiedStockDataService), Bootstrap 5, 原生 JavaScript

---

### Task 1: 后端 - 新增 BENCHMARK_CODES 配置

**Files:**
- Modify: `app/config/stock_codes.py:64` (文件末尾)

**Step 1: 在 stock_codes.py 末尾追加配置**

在 `CATEGORY_NAMES` 之后添加：

```python
# 盯盘助手预置基准标的
BENCHMARK_CODES = [
    {'code': 'GC=F', 'name': 'COMEX黄金', 'market': 'US'},
    {'code': 'SI=F', 'name': 'COMEX白银', 'market': 'US'},
    {'code': '^NDX', 'name': '纳指100', 'market': 'US'},
]
```

---

### Task 2: 后端 - 新增 /watch/benchmarks 端点

**Files:**
- Modify: `app/routes/watch.py:14` (在 index 路由之后)

**Step 1: 在 `index()` 路由之后添加 benchmarks 端点**

```python
@watch_bp.route('/benchmarks')
def benchmarks():
    from app.services.unified_stock_data import unified_stock_data_service
    from app.config.stock_codes import BENCHMARK_CODES

    codes = [b['code'] for b in BENCHMARK_CODES]
    raw_prices = unified_stock_data_service.get_realtime_prices(codes)

    result = []
    for b in BENCHMARK_CODES:
        data = raw_prices.get(b['code'], {})
        result.append({
            'code': b['code'],
            'name': b['name'],
            'market': b['market'],
            'price': data.get('current_price'),
            'change': data.get('change'),
            'change_pct': data.get('change_percent'),
        })

    return jsonify({'success': True, 'data': result})
```

---

### Task 3: 前端 - HTML 新增基准标的区域

**Files:**
- Modify: `app/templates/watch.html:34-36` (page-header 之后、loadingState 之前)

**Step 1: 在 page-header div 之后插入基准标的容器**

在 `</div><!-- page-header -->` 和 `<!-- 骨架屏 -->` 之间插入：

```html
<!-- 基准标的 -->
<div id="benchmarkBar" class="mb-3">
    <div class="d-flex gap-2 flex-wrap" id="benchmarkCards">
        <div class="skeleton skeleton-card" style="height:48px;width:160px;"></div>
        <div class="skeleton skeleton-card" style="height:48px;width:160px;"></div>
        <div class="skeleton skeleton-card" style="height:48px;width:160px;"></div>
    </div>
</div>
```

---

### Task 4: 前端 - JS 加载和渲染基准标的

**Files:**
- Modify: `app/static/js/watch.js`

**Step 1: 在 Watch 对象新增 benchmarks 属性（第 6 行附近）**

在 `prices: [],` 之后添加：

```javascript
benchmarks: [],
```

**Step 2: 新增 loadBenchmarks 方法（在 loadList 之后）**

```javascript
async loadBenchmarks() {
    try {
        const resp = await fetch('/watch/benchmarks');
        const data = await resp.json();
        if (data.success) {
            this.benchmarks = data.data || [];
            this.renderBenchmarks();
        }
    } catch (e) {
        console.error('[Watch] loadBenchmarks failed:', e);
    }
},

renderBenchmarks() {
    const container = document.getElementById('benchmarkCards');
    if (!container || this.benchmarks.length === 0) return;

    container.innerHTML = this.benchmarks.map(b => {
        const price = b.price != null ? b.price.toFixed(2) : '--';
        const pctClass = b.change_pct > 0 ? 'price-up' : b.change_pct < 0 ? 'price-down' : 'price-flat';
        const pctSign = b.change_pct > 0 ? '+' : '';
        const pctDisplay = b.change_pct != null ? `${pctSign}${b.change_pct.toFixed(2)}%` : '--';

        return `<div class="card px-3 py-2" style="min-width:140px;">
            <div class="d-flex align-items-center gap-2">
                <span class="fw-bold small">${b.name}</span>
                <span class="small" data-bench-price="${b.code}">${price}</span>
                <span class="${pctClass} small fw-bold" data-bench-pct="${b.code}">${pctDisplay}</span>
            </div>
        </div>`;
    }).join('');
},
```

**Step 3: 修改 init() 并行加载 benchmarks（第 16 行）**

将 `init()` 修改为：

```javascript
async init() {
    await Promise.all([this.loadList(true), this.loadBenchmarks()]);
    this.autoAnalyze();
    this.startRefreshLoop();
    this.startAnalysisLoop();
},
```

**Step 4: 修改 refreshIncrementalData() 加入 benchmarks 刷新**

在 `refreshIncrementalData()` 的 `Promise.all` 中添加 benchmarks 请求，并在返回后更新：

```javascript
// 在 Promise.all 中加入 fetch('/watch/benchmarks')
// 刷新后调用 this.renderBenchmarks()
```

具体：将第 101-106 行改为：

```javascript
const [priceResp, marketResp, benchResp] = await Promise.all([
    fetch('/watch/prices'),
    fetch('/watch/market-status'),
    fetch('/watch/benchmarks'),
]);
const priceData = await priceResp.json();
const marketData = await marketResp.json();
const benchData = await benchResp.json();
```

在 `this.marketStatus = marketData.data || {};` 之后添加：

```javascript
if (benchData.success) {
    this.benchmarks = benchData.data || [];
    this.renderBenchmarks();
}
```
