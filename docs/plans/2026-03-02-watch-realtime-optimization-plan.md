# 盯盘助手实时走势优化 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 优化盯盘助手的数据获取和走势图更新：前端 sessionStorage 缓存层、走势图增量追加数据点、合并 benchmarks 到 /prices 接口、market-status 降频。

**Architecture:** 后端 `/watch/prices` 接口合并返回基准标的数据，消除独立的 `/watch/benchmarks` 调用。前端新增 `WatchCache` 缓存管理器（sessionStorage），`init()` 先从缓存恢复再后台更新。60 秒刷新周期仅调 `/prices`，从报价中提取数据点追加到本地分时数组，ECharts 增量更新。

**Tech Stack:** Flask, JavaScript (vanilla), ECharts, sessionStorage

**设计文档:** `docs/plans/2026-03-02-watch-realtime-optimization-design.md`

---

### Task 1: 后端 /prices 接口合并基准标的

**Files:**
- Modify: `app/routes/watch.py:63-85` (`prices()` 函数)
- Modify: `app/routes/watch.py:17-37` (`benchmarks()` 函数 — 保留但标记可选)

**Step 1: 修改 prices() 函数，合并返回 benchmarks 数据**

在 `app/routes/watch.py` 的 `prices()` 函数中，除了返回盯盘股票报价外，同时获取并返回基准标的报价：

```python
@watch_bp.route('/prices')
def prices():
    from app.services.unified_stock_data import unified_stock_data_service
    from app.config.stock_codes import BENCHMARK_CODES

    codes = WatchService.get_watch_codes()
    cache_only = request.args.get('cache_only', 'false').lower() == 'true'

    # 盯盘股票报价
    price_list = []
    if codes:
        raw_prices = unified_stock_data_service.get_realtime_prices(codes, cache_only=cache_only)
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

    # 基准标的报价
    bench_codes = [b['code'] for b in BENCHMARK_CODES]
    bench_raw = unified_stock_data_service.get_realtime_prices(bench_codes, cache_only=cache_only)
    benchmark_list = []
    for b in BENCHMARK_CODES:
        data = bench_raw.get(b['code'], {})
        benchmark_list.append({
            'code': b['code'],
            'name': b['name'],
            'market': b['market'],
            'price': data.get('current_price'),
            'change': data.get('change'),
            'change_pct': data.get('change_percent'),
        })

    return jsonify({'success': True, 'prices': price_list, 'benchmarks': benchmark_list})
```

**Step 2: 删除独立的 benchmarks() 路由**

删除 `app/routes/watch.py` 第 17-37 行的 `@watch_bp.route('/benchmarks')` 函数，数据已合并到 `/prices`。

**Step 3: 验证**

启动应用，浏览器访问 `http://127.0.0.1:5000/watch/prices`，确认响应中同时包含 `prices` 和 `benchmarks` 两个字段。

**Step 4: Commit**

```bash
git add app/routes/watch.py
git commit -m "refactor: 合并 benchmarks 到 /prices 接口，减少一个独立请求"
```

---

### Task 2: 前端缓存管理器 WatchCache

**Files:**
- Modify: `app/static/js/watch.js` — 在文件开头（Watch 对象之前）添加 WatchCache

**Step 1: 在 watch.js 顶部添加 WatchCache 对象**

在 `const Watch = {` 之前插入：

```javascript
const WatchCache = {
    KEY: 'watch_cache',
    _saveTimer: null,

    _today() {
        return new Date().toISOString().slice(0, 10);
    },

    load() {
        try {
            const raw = sessionStorage.getItem(this.KEY);
            if (!raw) return null;
            const cache = JSON.parse(raw);
            if (cache.date !== this._today()) {
                sessionStorage.removeItem(this.KEY);
                return null;
            }
            return cache;
        } catch {
            sessionStorage.removeItem(this.KEY);
            return null;
        }
    },

    save(data) {
        clearTimeout(this._saveTimer);
        this._saveTimer = setTimeout(() => {
            try {
                data.date = this._today();
                sessionStorage.setItem(this.KEY, JSON.stringify(data));
            } catch (e) {
                console.warn('[WatchCache] save failed:', e);
            }
        }, 500);
    },

    clear() {
        sessionStorage.removeItem(this.KEY);
    },

    snapshot(watch) {
        return {
            date: this._today(),
            prices: watch.prices,
            benchmarks: watch.benchmarks,
            intradayData: watch.chartData,
            chartMeta: watch.chartMeta,
            analyses: watch.analyses,
            marketStatus: watch.marketStatus,
        };
    },

    restore(watch, cache) {
        watch.prices = cache.prices || [];
        watch.benchmarks = cache.benchmarks || [];
        watch.chartData = cache.intradayData || {};
        watch.chartMeta = cache.chartMeta || {};
        watch.analyses = cache.analyses || {};
        watch.marketStatus = cache.marketStatus || {};
    },
};
```

**Step 2: 验证**

在浏览器控制台测试：
```javascript
WatchCache.save({ date: '2026-03-02', prices: [{ code: 'test' }] });
console.log(WatchCache.load()); // 应返回保存的对象
WatchCache.clear();
```

**Step 3: Commit**

```bash
git add app/static/js/watch.js
git commit -m "feat: 添加 WatchCache sessionStorage 缓存管理器"
```

---

### Task 3: 重构 init() — 缓存优先加载

**Files:**
- Modify: `app/static/js/watch.js` — `Watch.init()` 方法

**Step 1: 重写 init() 支持缓存优先**

```javascript
async init() {
    // 阶段1：从缓存恢复（立即渲染）
    const cache = WatchCache.load();
    if (cache && cache.prices && cache.prices.length > 0) {
        WatchCache.restore(this, cache);
        // 需要先获取列表才能渲染卡片
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

    // 阶段2：后台更新真实数据
    await this.loadList(true);

    // 阶段3：自动触发分析 + 启动定时器
    this.autoAnalyze();
    this.startRefreshLoop();
    this.startAnalysisLoop();
    this.startMarketStatusLoop();
},
```

**Step 2: 添加 loadAllChartsFromCache() 方法**

```javascript
loadAllChartsFromCache() {
    for (const stock of this.stocks) {
        const code = stock.stock_code;
        if (this.chartData[code] && this.chartData[code].length > 0) {
            this.renderChart(code);
        }
    }
},
```

**Step 3: Commit**

```bash
git add app/static/js/watch.js
git commit -m "feat: init() 缓存优先加载，页面刷新零等待"
```

---

### Task 4: 重构 loadList() — 从 /prices 获取 benchmarks

**Files:**
- Modify: `app/static/js/watch.js` — `Watch.loadList()` 和 `Watch.loadBenchmarks()`

**Step 1: 修改 loadList()，从 /prices 响应中提取 benchmarks**

```javascript
async loadList(cacheOnly = false) {
    try {
        const priceUrl = cacheOnly ? '/watch/prices?cache_only=true' : '/watch/prices';
        const [listResp, priceResp, marketResp] = await Promise.all([
            fetch('/watch/list'),
            fetch(priceUrl),
            fetch('/watch/market-status'),
        ]);
        const listData = await listResp.json();
        const priceData = await priceResp.json();
        const marketData = await marketResp.json();

        if (!listData.success) return;
        this.stocks = listData.data || [];
        this.prices = priceData.prices || [];
        this.benchmarks = priceData.benchmarks || [];
        this.marketStatus = marketData.data || {};

        this.renderBenchmarks();

        if (this.stocks.length === 0) {
            this.showEmpty();
            return;
        }

        this.renderCards();
        this.updateStatus(`${this.stocks.length} 只股票`);
        await this.loadAllCharts();

        // 保存到缓存
        WatchCache.save(WatchCache.snapshot(this));
    } catch (e) {
        console.error('[Watch] loadList failed:', e);
        this.updateStatus('加载失败');
    }
},
```

**Step 2: 删除 loadBenchmarks() 方法**

删除 `Watch.loadBenchmarks()` 方法（第 74-85 行），不再需要独立获取基准标的。

**Step 3: Commit**

```bash
git add app/static/js/watch.js
git commit -m "refactor: loadList 从 /prices 响应中获取 benchmarks，删除独立 loadBenchmarks"
```

---

### Task 5: 重构 refreshIncrementalData() — 走势图增量追加

**Files:**
- Modify: `app/static/js/watch.js` — `Watch.refreshIncrementalData()`

**Step 1: 重写 refreshIncrementalData()，用报价数据追加走势图**

核心变化：不再调用 `/watch/chart-data`，从 `/prices` 报价中提取时间+价格追加到本地 `chartData`。

```javascript
async refreshIncrementalData() {
    try {
        const priceResp = await fetch('/watch/prices');
        const priceData = await priceResp.json();

        if (priceData.success) {
            this.prices = priceData.prices || [];
            this.benchmarks = priceData.benchmarks || [];
            this.updateAllPrices();
            this.renderBenchmarks();

            // 将报价追加为走势图数据点
            this.appendPricesToCharts();
        }

        // 检查是否需要停止
        const hasActiveMarket = Object.values(this.marketStatus).some(m => m.status === 'trading');
        if (!hasActiveMarket) {
            this.stopRefreshLoop();
            this.stopAnalysisLoop();
        } else if (!this.analysisTimer) {
            this.startAnalysisLoop();
        }

        // 保存到缓存
        WatchCache.save(WatchCache.snapshot(this));
    } catch (e) {
        console.error('[Watch] refresh failed:', e);
    }
},
```

**Step 2: 添加 appendPricesToCharts() 方法**

```javascript
appendPricesToCharts() {
    const now = new Date();
    const timeKey = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;

    const pricesMap = {};
    this.prices.forEach(p => { pricesMap[p.code] = p; });

    for (const stock of this.stocks) {
        const code = stock.stock_code;
        const market = stock.market || 'A';
        const ms = this.marketStatus[market];
        if (!ms || ms.status !== 'trading') continue;

        const p = pricesMap[code];
        if (!p || p.price == null) continue;

        const data = this.chartData[code] || [];
        const newPoint = { time: timeKey, close: p.price };

        // 同一分钟的数据点覆盖
        if (data.length > 0 && data[data.length - 1].time === timeKey) {
            data[data.length - 1].close = p.price;
        } else {
            data.push(newPoint);
        }
        this.chartData[code] = data;

        this.renderChart(code);
    }
},
```

**Step 3: Commit**

```bash
git add app/static/js/watch.js
git commit -m "feat: 走势图从报价增量追加数据点，消除定时 chart-data 请求"
```

---

### Task 6: 添加 market-status 独立定时器（降频到5分钟）

**Files:**
- Modify: `app/static/js/watch.js` — 添加 `marketStatusTimer` 和相关方法

**Step 1: 在 Watch 对象中添加 market-status 定时器**

在 `Watch` 对象属性区域添加：

```javascript
MARKET_STATUS_INTERVAL: 5 * 60,  // 5分钟
marketStatusTimer: null,
```

**Step 2: 添加 startMarketStatusLoop / stopMarketStatusLoop 方法**

```javascript
startMarketStatusLoop() {
    this.stopMarketStatusLoop();
    this.marketStatusTimer = setInterval(async () => {
        try {
            const resp = await fetch('/watch/market-status');
            const data = await resp.json();
            if (data.success) {
                this.marketStatus = data.data || {};
                this.updateMarketStatusBadges();

                const hasActive = Object.values(this.marketStatus).some(m => m.status === 'trading');
                if (hasActive && !this.refreshTimer) {
                    this.startRefreshLoop();
                }
            }
        } catch (e) {
            console.error('[Watch] market status update failed:', e);
        }
    }, this.MARKET_STATUS_INTERVAL * 1000);
},

stopMarketStatusLoop() {
    if (this.marketStatusTimer) {
        clearInterval(this.marketStatusTimer);
        this.marketStatusTimer = null;
    }
},
```

**Step 3: 添加 updateMarketStatusBadges() 方法**

该方法更新已渲染卡片上的市场状态 badge，无需重新渲染整个卡片列表：

```javascript
updateMarketStatusBadges() {
    document.querySelectorAll('.market-group').forEach(group => {
        const badge = group.querySelector('.badge');
        const marketName = group.querySelector('.fw-bold');
        if (!badge || !marketName) return;

        const marketEntry = Object.entries(this.marketStatus).find(([_, ms]) =>
            marketName.textContent.includes(ms.name)
        );
        if (!marketEntry) return;

        const [_, ms] = marketEntry;
        const statusBadge = this.getStatusBadgeClass(ms.status || 'closed');
        const statusIcon = this.getStatusIcon(ms.status || 'closed');
        badge.className = `badge ${statusBadge} ms-2`;
        badge.textContent = `${statusIcon} ${ms.status_text || ''}`;
    });
},
```

**Step 4: 从 refreshIncrementalData 中移除 market-status 请求**

确认 `refreshIncrementalData()` 中不再调用 `/watch/market-status`（Task 5 已处理）。

**Step 5: Commit**

```bash
git add app/static/js/watch.js
git commit -m "feat: market-status 独立定时器，降频到每5分钟"
```

---

### Task 7: 在 loadAllCharts 和 loadAnalysis 中写入缓存

**Files:**
- Modify: `app/static/js/watch.js` — `loadAllCharts()`, `loadChartData()`, `loadAnalysis()`

**Step 1: 在 loadChartData() 末尾保存缓存**

在现有 `loadChartData()` 方法的 `this.renderChart(code);` 之后追加：

```javascript
// 保存到缓存
WatchCache.save(WatchCache.snapshot(this));
```

**Step 2: 在 loadAnalysis() 中保存缓存**

在 `this.updateAllAnalysisPanels();` 之后追加：

```javascript
// 保存到缓存
WatchCache.save(WatchCache.snapshot(this));
```

**Step 3: Commit**

```bash
git add app/static/js/watch.js
git commit -m "feat: 分时数据和分析结果变更时同步写入 sessionStorage 缓存"
```

---

### Task 8: 清理与最终验证

**Files:**
- Modify: `app/static/js/watch.js` — 清理废弃代码
- Modify: `app/routes/watch.py` — 清理废弃路由

**Step 1: 清理 watch.js 中的废弃代码**

确认以下已删除/调整：
- `loadBenchmarks()` 方法已删除（Task 4）
- `refreshIncrementalData()` 中不再调用 `/watch/benchmarks` 和 `/watch/market-status`（Task 5）
- `refreshIncrementalData()` 中不再逐只调用 `/watch/chart-data`（Task 5）

**Step 2: 清理 watch.py 中的废弃路由**

确认 `benchmarks()` 路由已删除（Task 1）。

**Step 3: 功能验证**

启动应用 `python run.py`，验证：
1. 打开盯盘页面 → 报价和基准标的正常显示
2. 等待 60 秒 → 价格刷新，走势图自动追加新数据点
3. F5 刷新页面 → 立即显示之前的数据（来自 sessionStorage）
4. 等待 5 分钟 → 市场状态更新
5. 浏览器控制台无报错

**Step 4: Commit**

```bash
git add app/routes/watch.py app/static/js/watch.js
git commit -m "chore: 清理废弃的 benchmarks 路由和冗余请求代码"
```

---

## 变更摘要

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `app/routes/watch.py` | 修改 | `/prices` 合并返回 benchmarks；删除独立 `/benchmarks` 路由 |
| `app/static/js/watch.js` | 修改 | 新增 WatchCache；init 缓存优先；走势图增量追加；market-status 降频 |

## 请求优化效果

| 场景 | 优化前（每60秒） | 优化后（每60秒） |
|------|-----------------|-----------------|
| 总请求数 | 3 + N（prices + benchmarks + market-status + N只chart-data） | 1（prices only） |
| 每5分钟额外 | — | +1（market-status） |
| 示例：5只股票 | 8 次/分钟 | 1 次/分钟 |
