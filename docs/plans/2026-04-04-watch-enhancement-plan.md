# 盯盘功能增强 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 后端调度器主动预取盯盘数据，前端只读缓存不触发API，修复7日tab卡死问题，迁移到localStorage分key缓存。

**Architecture:** 新增 `watch_preload` 调度策略每分钟预取价格、每15分钟预取走势。现有端点改为只读缓存。前端 `WatchCache`（sessionStorage单key）替换为 `WatchStore`（localStorage按市场分key）。7日tab改为渐进渲染+超时兜底。

**Tech Stack:** Flask, APScheduler, JavaScript (原生), ECharts, localStorage

---

## File Structure

| 文件 | 操作 | 职责 |
|------|------|------|
| `app/strategies/watch_preload/__init__.py` | 新建 | 数据预取调度策略 |
| `app/strategies/watch_preload/config.yaml` | 新建 | 策略配置 |
| `app/services/market_session.py` | 修改:19 | TTL_TRADING 30min→1min |
| `app/routes/watch.py` | 修改:38-108 | prices/chart-data/analyze 端点改只读 |
| `app/static/js/watch.js` | 修改 | WatchCache→WatchStore，7日渐进渲染 |

---

### Task 1: TTL_TRADING 调整

**Files:**
- Modify: `app/services/market_session.py:19`

- [ ] **Step 1: 修改 TTL_TRADING**

```python
TTL_TRADING = timedelta(minutes=1)     # 交易时段内 TTL（配合 watch_preload 每分钟预取）
```

将 `market_session.py` 第19行的 `timedelta(minutes=30)` 改为 `timedelta(minutes=1)`。同时更新第4行注释中的 `短TTL (30分钟)` 为 `短TTL (1分钟)`。

- [ ] **Step 2: Commit**

```bash
git add app/services/market_session.py
git commit -m "refactor: TTL_TRADING 从30分钟降为1分钟，配合盯盘预取策略"
```

---

### Task 2: 新增 watch_preload 调度策略

**Files:**
- Create: `app/strategies/watch_preload/__init__.py`
- Create: `app/strategies/watch_preload/config.yaml`

- [ ] **Step 1: 创建 config.yaml**

```yaml
# watch_preload 策略配置
trend_interval: 15  # 每N次tick预取走势数据
```

- [ ] **Step 2: 创建策略文件**

```python
"""盯盘数据预取策略 — 每分钟预取价格，每15分钟预取走势"""
import logging
from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)


class WatchPreloadStrategy(Strategy):
    name = "watch_preload"
    description = "盯盘数据预取（每分钟价格，每15分钟走势）"
    schedule = "interval_minutes:1"
    needs_llm = False

    _tick_count = 0

    def scan(self) -> list[Signal]:
        from app.services.watch_service import WatchService
        from app.services.trading_calendar import TradingCalendarService
        from app.services.unified_stock_data import unified_stock_data_service
        from app.utils.market_identifier import MarketIdentifier

        codes = WatchService.get_watch_codes()
        if not codes:
            return []

        markets = WatchService.get_watched_markets()
        open_markets = {m for m in markets if TradingCalendarService.is_market_open(m)}
        if not open_markets:
            return []

        market_codes = {}
        for code in codes:
            market = MarketIdentifier.identify(code) or 'A'
            if market in open_markets:
                market_codes.setdefault(market, []).append(code)

        active_codes = [c for codes_list in market_codes.values() for c in codes_list]
        if not active_codes:
            return []

        # 每次预取价格
        try:
            unified_stock_data_service.get_realtime_prices(active_codes, force_refresh=True)
            logger.debug(f'[盯盘预取] 价格预取完成: {len(active_codes)}只')
        except Exception as e:
            logger.error(f'[盯盘预取] 价格预取失败: {e}')

        # 每 trend_interval 次预取走势
        trend_interval = self._config.get('trend_interval', 15)
        if self._tick_count % trend_interval == 0:
            try:
                unified_stock_data_service.get_trend_data(active_codes, days=7)
                unified_stock_data_service.get_trend_data(active_codes, days=30)
                logger.info(f'[盯盘预取] 走势预取完成: {len(active_codes)}只 (tick={self._tick_count})')
            except Exception as e:
                logger.error(f'[盯盘预取] 走势预取失败: {e}')

        self._tick_count += 1
        return []
```

- [ ] **Step 3: 验证策略能被自动发现**

运行：
```bash
SCHEDULER_ENABLED=0 python -c "
from app import create_app
app = create_app()
with app.app_context():
    from app.strategies.registry import registry
    registry.discover()
    s = registry.get('watch_preload')
    print(f'Found: {s.name}, schedule: {s.schedule}')
    print(f'Config: {s.get_config()}')
"
```

期望输出包含 `Found: watch_preload, schedule: interval_minutes:1`。

- [ ] **Step 4: Commit**

```bash
git add app/strategies/watch_preload/__init__.py app/strategies/watch_preload/config.yaml
git commit -m "feat: 新增 watch_preload 策略，每分钟预取价格/每15分钟预取走势"
```

---

### Task 3: 端点改为只读缓存

**Files:**
- Modify: `app/routes/watch.py:38-108`

- [ ] **Step 1: 改造 `/watch/prices` 端点**

将 `app/routes/watch.py` 第38-96行的 `prices()` 函数替换。核心变化：移除 `_fetch_prices_with_cache` 中对 `refresh_codes` 的 `force_refresh=True` 调用，改为纯缓存读取。缓存 miss 时返回空数据 + `stale` 标记。

```python
@watch_bp.route('/prices')
def prices():
    from app.services.unified_stock_data import unified_stock_data_service
    from app.config.stock_codes import BENCHMARK_CODES

    codes = WatchService.get_watch_codes()

    def _read_cached_prices(target_codes: list) -> dict:
        if not target_codes:
            return {}
        cached, missing = unified_stock_data_service.get_prices_cached_only(target_codes)
        return cached

    price_list = []
    if codes:
        raw_prices = _read_cached_prices(codes)
        for code in codes:
            data = raw_prices.get(code, {})
            price_list.append({
                'code': code,
                'name': data.get('name', code),
                'price': data.get('current_price'),
                'change': data.get('change'),
                'change_pct': data.get('change_percent'),
                'volume': data.get('volume'),
                'market': data.get('market', ''),
                'stale': code not in raw_prices or data.get('_is_degraded', False),
            })

    bench_codes = [b['code'] for b in BENCHMARK_CODES]
    bench_raw = _read_cached_prices(bench_codes)
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

- [ ] **Step 2: 改造 `/watch/chart-data` 端点的走势分支**

在 `app/routes/watch.py` 的 `chart_data()` 函数中，将第272-298行的 `else` 分支（非 intraday）的 `get_trend_data` 调用改为缓存优先，缓存 miss 返回空数据。

找到这段代码（约第272-298行）：
```python
    else:
        days_map = {'7d': 7, '30d': 30, '90d': 90}
        days = days_map.get(period, 30)
        fetch_days = days + 20
        trend = unified_stock_data_service.get_trend_data([code], days=fetch_days)
        stocks = trend.get('stocks', [])
        ohlc_data = stocks[0]['data'] if stocks else []
```

替换为：
```python
    else:
        days_map = {'7d': 7, '30d': 30, '90d': 90}
        days = days_map.get(period, 30)
        fetch_days = days + 20
        trend = unified_stock_data_service.get_trend_data([code], days=fetch_days)
        stocks = trend.get('stocks', [])
        ohlc_data = stocks[0]['data'] if stocks else []
        if not ohlc_data:
            result['stale'] = True
```

注意：`get_trend_data` 自身有缓存逻辑，缓存命中时直接返回、不触发API（因为 TTL_TRADING 已降到1分钟，且 `watch_preload` 每分钟刷新缓存，所以这里总是能命中缓存）。如果确实缓存全 miss（首次启动等场景），数据为空时标记 `stale`。

- [ ] **Step 3: 改造 `/watch/analyze` 端点**

将 `app/routes/watch.py` 第99-108行替换：

```python
@watch_bp.route('/analyze')
def analyze():
    """只读今日分析结果（数据由 watch_realtime 策略预填充）"""
    period = request.args.get('period')
    analyses = WatchService.get_all_today_analyses()
    if period:
        filtered = {}
        for code, periods in analyses.items():
            if period in periods:
                filtered[code] = {period: periods[period]}
        analyses = filtered
    return jsonify({'success': True, 'data': analyses})
```

关键变化：`POST` → `GET`，移除 `WatchAnalysisService.analyze_stocks()` 调用，只读 DB。

- [ ] **Step 4: Commit**

```bash
git add app/routes/watch.py
git commit -m "refactor: 盯盘端点改为只读缓存，不再触发API/LLM调用"
```

---

### Task 4: 前端 WatchStore 替换 WatchCache

**Files:**
- Modify: `app/static/js/watch.js:1-71`（替换 WatchCache 对象）

- [ ] **Step 1: 替换 WatchCache 为 WatchStore**

删除 `watch.js` 第1-71行的 `WatchCache` 对象，替换为：

```javascript
const WatchStore = {
    PREFIX: 'watch_',
    STALE_MS: 2 * 60 * 1000,

    _today() {
        return new Date().toISOString().slice(0, 10);
    },

    _key(type, market) {
        return market ? `${this.PREFIX}${type}_${market}` : `${this.PREFIX}${type}`;
    },

    init() {
        try {
            const meta = this.get('meta');
            if (!meta || meta.date !== this._today()) {
                this.clearAll();
            }
        } catch {
            this.clearAll();
        }
    },

    get(type, market) {
        try {
            const raw = localStorage.getItem(this._key(type, market));
            if (!raw) return null;
            return JSON.parse(raw);
        } catch {
            return null;
        }
    },

    set(type, market, data) {
        try {
            const wrapped = { data, timestamp: Date.now() };
            localStorage.setItem(this._key(type, market), JSON.stringify(wrapped));
            // 更新 meta
            const meta = this.get('meta') || {};
            meta.date = this._today();
            localStorage.setItem(this._key('meta'), JSON.stringify(meta));
        } catch (e) {
            console.warn('[WatchStore] save failed:', e);
        }
    },

    isStale(type, market) {
        try {
            const raw = localStorage.getItem(this._key(type, market));
            if (!raw) return true;
            const parsed = JSON.parse(raw);
            return !parsed.timestamp || (Date.now() - parsed.timestamp) > this.STALE_MS;
        } catch {
            return true;
        }
    },

    clearAll() {
        const keysToRemove = [];
        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key && key.startsWith(this.PREFIX)) {
                keysToRemove.push(key);
            }
        }
        keysToRemove.forEach(k => localStorage.removeItem(k));
    },
};
```

- [ ] **Step 2: 修改 Watch.init() 中的缓存恢复逻辑**

将 `watch.js` 中 `Watch.init()` 方法（第96-122行）替换为：

```javascript
    async init() {
        WatchStore.init();
        // 从 localStorage 恢复缓存渲染
        this._restoreFromStore();
        if (this.prices.length > 0) {
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
                this.showRefreshTime();
            }
        }

        await this.loadList();

        this.loadAnalysis();
        this.startRefreshLoop();
        this.startAnalysisLoop();
        this.startMarketStatusLoop();
    },
```

- [ ] **Step 3: 添加 _restoreFromStore 和 _saveToStore 方法**

在 `Watch` 对象中添加以下两个方法：

```javascript
    _restoreFromStore() {
        const markets = ['A', 'US', 'HK', 'KR', 'TW', 'JP'];
        let allPrices = [];
        for (const m of markets) {
            const priceData = WatchStore.get('prices', m);
            if (priceData && priceData.data) {
                allPrices = allPrices.concat(priceData.data);
            }
            const chart7d = WatchStore.get('chart7d', m);
            if (chart7d && chart7d.data) {
                Object.assign(this._weeklyChartData, chart7d.data);
            }
            const analysis = WatchStore.get('analysis', m);
            if (analysis && analysis.data) {
                Object.assign(this.analyses, analysis.data);
            }
        }
        if (allPrices.length > 0) this.prices = allPrices;

        const benchData = WatchStore.get('benchmarks');
        if (benchData && benchData.data) this.benchmarks = benchData.data;

        const marketStatus = WatchStore.get('marketStatus');
        if (marketStatus && marketStatus.data) this.marketStatus = marketStatus.data;

        const viewMode = WatchStore.get('viewMode');
        if (viewMode && viewMode.data) this._marketViewMode = viewMode.data;

        const refreshTime = WatchStore.get('refreshTime');
        if (refreshTime && refreshTime.data) this.lastRefreshTime = refreshTime.data;
    },

    _saveToStore() {
        const { groups } = this._getMarketGroups();
        for (const [market, stocks] of Object.entries(groups)) {
            const codes = stocks.map(s => s.stock_code);
            const marketPrices = this.prices.filter(p => codes.includes(p.code));
            WatchStore.set('prices', market, marketPrices);

            const marketChart7d = {};
            for (const code of codes) {
                if (this._weeklyChartData[code]) {
                    marketChart7d[code] = this._weeklyChartData[code];
                }
            }
            if (Object.keys(marketChart7d).length > 0) {
                WatchStore.set('chart7d', market, marketChart7d);
            }

            const marketAnalysis = {};
            for (const code of codes) {
                if (this.analyses[code]) {
                    marketAnalysis[code] = this.analyses[code];
                }
            }
            if (Object.keys(marketAnalysis).length > 0) {
                WatchStore.set('analysis', market, marketAnalysis);
            }
        }
        WatchStore.set('benchmarks', null, this.benchmarks);
        WatchStore.set('marketStatus', null, this.marketStatus);
        WatchStore.set('viewMode', null, this._marketViewMode);
        WatchStore.set('refreshTime', null, this.lastRefreshTime);
    },
```

- [ ] **Step 4: 全局替换 WatchCache 调用**

在 `watch.js` 全文中将所有 `WatchCache.save(WatchCache.snapshot(this))` 替换为 `this._saveToStore()`。

需要替换的位置包括：
- `switchMarketView` 方法末尾
- `_loadAndRenderWeeklyChart` 中 `Promise.all` 完成后
- `refreshIncrementalData` 末尾
- `loadList` 中的保存
- 其他调用 `WatchCache.save` 的位置

同时删除所有 `WatchCache.load()`、`WatchCache.restore()` 的调用（已被 `_restoreFromStore` 替代）。

- [ ] **Step 5: Commit**

```bash
git add app/static/js/watch.js
git commit -m "refactor: 前端缓存从 sessionStorage 迁移到 localStorage 按市场分key"
```

---

### Task 5: 7日tab渐进渲染 + 超时兜底

**Files:**
- Modify: `app/static/js/watch.js`（`_loadAndRenderWeeklyChart` 方法）

- [ ] **Step 1: 重写 _loadAndRenderWeeklyChart**

将 `watch.js` 中的 `_loadAndRenderWeeklyChart` 方法（约第688-713行）替换为：

```javascript
    async _loadAndRenderWeeklyChart(market) {
        const { groups } = this._getMarketGroups();
        const stocks = groups[market] || [];
        const cached = stocks.filter(s => this._weeklyChartData[s.stock_code] && this._weeklyChartData[s.stock_code].length > 0);
        const missing = stocks.filter(s => !(this._weeklyChartData[s.stock_code] && this._weeklyChartData[s.stock_code].length > 0));

        // 有缓存数据先渲染
        if (cached.length > 0) {
            this.renderMarketChart(market);
        }

        if (missing.length === 0) return;

        const container = document.getElementById(`chart-market-${market}`);
        const total = missing.length;
        let loaded = 0;
        const SINGLE_TIMEOUT = 5000;
        const TOTAL_TIMEOUT = 15000;

        if (cached.length === 0 && container) {
            container.innerHTML = `<div class="text-muted text-center small py-4">加载7日数据 (0/${total})...</div>`;
        }

        const controller = new AbortController();
        const totalTimer = setTimeout(() => controller.abort(), TOTAL_TIMEOUT);

        const fetchOne = async (stock) => {
            try {
                const singleController = new AbortController();
                const singleTimer = setTimeout(() => singleController.abort(), SINGLE_TIMEOUT);

                // 双重取消：单只超时或总超时
                controller.signal.addEventListener('abort', () => singleController.abort());

                const resp = await fetch(
                    `/watch/chart-data?code=${encodeURIComponent(stock.stock_code)}&period=7d`,
                    { signal: singleController.signal }
                );
                clearTimeout(singleTimer);
                const result = await resp.json();

                if (result.success && result.data && result.data.length > 0) {
                    this._weeklyChartData[stock.stock_code] = result.data;
                }
                if (result.stale) {
                    console.warn(`[Watch] ${stock.stock_code} 7d data is stale`);
                }
            } catch (e) {
                if (e.name === 'AbortError') {
                    console.warn(`[Watch] ${stock.stock_code} 7d fetch timeout`);
                } else {
                    console.error(`[Watch] ${stock.stock_code} 7d fetch error:`, e);
                }
            }
            loaded++;
            // 渐进渲染：每只加载完就重绘
            this.renderMarketChart(market);
            if (container) {
                const progress = container.querySelector('.watch-load-progress');
                if (progress) progress.textContent = `${loaded}/${total}`;
            }
        };

        await Promise.allSettled(missing.map(s => fetchOne(s)));
        clearTimeout(totalTimer);

        this._saveToStore();
    },
```

- [ ] **Step 2: 修改 renderMarketChart 处理空数据占位**

在 `renderMarketChart` 方法中（渲染7日模式的分支），对 `_weeklyChartData` 中没有数据的股票显示"暂无数据"占位，而不是跳过。找到7日图表渲染部分，在遍历 stocks 构建 series 时，对缺失数据的股票添加空 series + 标注。

具体实现：在渲染7日图表时，检查每只股票的数据，若为空则在图表下方展示灰色提示文字。这取决于 `renderMarketChart` 的当前实现方式——如果是 ECharts，通过 `graphic` 组件添加文字提示。

- [ ] **Step 3: Commit**

```bash
git add app/static/js/watch.js
git commit -m "feat: 7日tab渐进渲染+超时兜底，单只5s/总15s超时"
```

---

### Task 6: 前端 analyze 调用适配

**Files:**
- Modify: `app/static/js/watch.js`（`loadAnalysis` 方法及相关调用）

- [ ] **Step 1: 修改 loadAnalysis 方法**

在 `watch.js` 中找到 `loadAnalysis` 方法，将 `POST /watch/analyze` 改为 `GET /watch/analyze`（或改为调用 `GET /watch/analysis`，因为两个端点现在行为相同）。

搜索 `fetch('/watch/analyze'` 或类似的 POST 调用，替换为 GET 请求：

将类似这样的代码：
```javascript
const resp = await fetch('/watch/analyze', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({period, force})
});
```

替换为：
```javascript
const url = period ? `/watch/analyze?period=${period}` : '/watch/analyze';
const resp = await fetch(url);
```

- [ ] **Step 2: 验证分析轮询循环正常**

确认 `startAnalysisLoop` 中的定时器（每15分钟）调用 `loadAnalysis` 时不再触发 LLM，只读取 DB 中的数据。

- [ ] **Step 3: Commit**

```bash
git add app/static/js/watch.js
git commit -m "refactor: 前端 analyze 调用从 POST 改为 GET 只读模式"
```

---

### Task 7: 端到端验证

- [ ] **Step 1: 启动应用验证策略注册**

```bash
python run.py
```

检查启动日志中包含 `watch_preload` 策略注册成功。

- [ ] **Step 2: 验证前端页面功能**

打开浏览器 http://127.0.0.1:5000/watch/，检查：
1. 页面加载 → 价格正常显示（来自缓存）
2. 切换"7日"tab → 不卡死，渐进渲染，有加载进度
3. 刷新页面 → localStorage 恢复缓存，立即渲染
4. 打开新标签页 → 共享 localStorage 数据

- [ ] **Step 3: 验证 localStorage 数据结构**

浏览器 DevTools → Application → Local Storage，确认存在：
- `watch_prices_A`、`watch_prices_US` 等 key
- `watch_meta` 包含 `date` 字段
- 数据包含 `timestamp` 字段

- [ ] **Step 4: Commit + 更新 CLAUDE.md**

更新 `CLAUDE.md` 中盯盘相关配置说明，将 `TTL_TRADING` 变更记录其中。

```bash
git add CLAUDE.md
git commit -m "docs: 更新盯盘功能配置说明"
```
