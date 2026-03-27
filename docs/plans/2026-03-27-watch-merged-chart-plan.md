# 盯盘页面合并图表 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将盯盘页面同市场股票合并到一张图中，Y轴用百分比（基于昨收），图下方显示股票列表（当前价-支撑价），支持实时/7日两种视图切换。

**Architecture:** 前端重构 watch.js 的渲染逻辑，将"每只股票一张图+卡片"改为"每个市场一张合并图+股票摘要表"。后端 API 不变，前端数据转换层将价格转为百分比。移除昨日走势线，新增市场级别的实时/7日视图切换。

**Tech Stack:** ECharts (多系列折线图), 原生 JavaScript, Flask/Jinja2

---

## 文件结构

| 文件 | 变更类型 | 职责 |
|------|---------|------|
| `app/static/js/watch.js` | 修改 | 核心重构：合并图表渲染、百分比转换、摘要表 |
| `app/templates/watch.html` | 修改 | 调整 CSS 样式（合并图表高度、摘要表样式） |

后端无需改动，复用现有 `/watch/chart-data` 和 `/watch/prices` API。

---

## 设计要点

### 数据模型变更

**现有**：`chartInstances[stockCode]` → 每只股票一个 ECharts 实例
**新**：`chartInstances[market]` → 每个市场一个 ECharts 实例

### 百分比转换

```javascript
// prevClose 为昨收价（0%基准线）
pct = (price - prevClose) / prevClose * 100
```

Y轴显示 `+1.5%` / `-0.8%` 格式，tooltip 同时显示百分比和绝对价格。

### 颜色分配

每只股票分配不同颜色，通过 ECharts 内置调色盘自动分配。图例显示股票名称，点击可隐藏/显示。

### 视图切换

市场级别两个按钮：**实时**（分时百分比线）和 **7日**（7日涨跌幅折线）。

- 实时：复用现有 intraday 数据，转为百分比
- 7日：复用现有 `/watch/chart-data?period=7d` 数据，每日收盘价转为百分比（基于7日前收盘价）

### 摘要表

图下方表格，每只股票一行：

| 股票 | 现价 | 涨跌% | 支撑位 | 距支撑 | 操作 |
|------|------|-------|--------|--------|------|

"距支撑" = 现价 - 最近支撑价，帮助判断做T空间。

---

### Task 1: 重构 renderCards — 市场级合并布局

**Files:**
- Modify: `app/static/js/watch.js:491-541` (renderCards 方法)
- Modify: `app/static/js/watch.js:425-489` (renderStockCard → 删除，替换为 renderMarketSection)
- Modify: `app/templates/watch.html:5-48` (CSS 样式)

- [ ] **Step 1: 修改 watch.html CSS 样式**

替换现有 `.stock-card` / `.chart-container` / `.bottom-panel` 样式：

```css
.market-section { border-radius: 8px; }
.market-chart { height: 320px; border-radius: 4px; background: #fafafa; }
.stock-summary-table { font-size: 0.82rem; }
.stock-summary-table td, .stock-summary-table th { padding: 0.3rem 0.5rem; }
.stock-summary-table .stock-name { font-weight: 600; }
.view-toggle .btn { padding: 0.15rem 0.6rem; font-size: 0.78rem; }
.view-toggle .btn.active { font-weight: 600; }
```

- [ ] **Step 2: 重写 renderCards 方法**

将 `renderCards()` 改为按市场分组，每个市场渲染：
1. 市场标题行（带状态 badge + 视图切换按钮）
2. 合并图表容器 `<div id="chart-market-{market}">`
3. 股票摘要表

```javascript
renderCards() {
    Object.values(this.chartInstances).forEach(c => c.dispose());
    this.chartInstances = {};

    const pricesMap = {};
    this.prices.forEach(p => { pricesMap[p.code] = p; });

    const groups = {};
    this.stocks.forEach(stock => {
        const market = stock.market || 'A';
        if (!groups[market]) groups[market] = [];
        groups[market].push(stock);
    });

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

        html += `<div class="card market-section mb-4" data-market="${market}">
            <div class="card-body">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <div class="d-flex align-items-center gap-2">
                        <span class="fw-bold">${icon} ${name}</span>
                        <span class="badge ${statusBadge}">${statusIcon} ${statusText}</span>
                    </div>
                    <div class="view-toggle btn-group">
                        <button class="btn btn-outline-secondary btn-sm active" onclick="Watch.switchMarketView('${market}','intraday',this)">实时</button>
                        <button class="btn btn-outline-secondary btn-sm" onclick="Watch.switchMarketView('${market}','7d',this)">7日</button>
                    </div>
                </div>
                <div class="market-chart" id="chart-market-${market}">
                    <div class="skeleton skeleton-card" style="height:100%;"></div>
                </div>
                <div class="mt-2" id="summary-table-${market}">
                    ${this._renderSummaryTable(groups[market], pricesMap)}
                </div>
            </div>
        </div>`;
    }

    container.innerHTML = html;
    document.getElementById('loadingState').classList.add('d-none');
    document.getElementById('emptyState').classList.add('d-none');
    container.classList.remove('d-none');
},
```

- [ ] **Step 3: 新增 _renderSummaryTable 方法**

```javascript
_renderSummaryTable(stocks, pricesMap) {
    let rows = '';
    for (const stock of stocks) {
        const code = stock.stock_code;
        const name = stock.stock_name || code;
        const market = stock.market || 'A';
        const p = pricesMap[code] || {};
        const price = p.price != null ? this.formatPrice(p.price, market) : '--';
        const pctClass = p.change_pct > 0 ? 'price-up' : p.change_pct < 0 ? 'price-down' : 'price-flat';
        const pctSign = p.change_pct > 0 ? '+' : '';
        const pctDisplay = p.change_pct != null ? `${pctSign}${p.change_pct.toFixed(2)}%` : '--';

        // 支撑位：取 AI 分析或算法支撑
        const meta = this.chartMeta[code] || {};
        const supports = meta.supportLevels || [];
        const nearestSupport = supports.length > 0 && p.price != null
            ? supports.filter(s => s < p.price).sort((a, b) => b - a)[0] : null;
        const supportDisplay = nearestSupport != null ? nearestSupport.toFixed(2) : '--';
        const gapDisplay = nearestSupport != null && p.price != null
            ? (p.price - nearestSupport).toFixed(2) : '--';

        // TD 信号
        const td = this.tdSequential[code] || {};
        let tdHtml = '';
        if (td.direction && td.count > 0) {
            const tdClass = td.direction === 'buy' ? 'td-badge-buy' : 'td-badge-sell';
            const warn = td.count >= 7 ? ' td-badge-warn' : '';
            const check = td.completed ? ' ✓' : '';
            const label = td.direction === 'buy' ? '买' : '卖';
            tdHtml = `<span class="td-badge ${tdClass}${warn}">${label}${td.count}${check}</span>`;
        }

        rows += `<tr data-code="${code}">
            <td class="stock-name">${name} <small class="text-muted">${code}</small> ${tdHtml}</td>
            <td class="text-end">${price}</td>
            <td class="text-end ${pctClass} fw-bold">${pctDisplay}</td>
            <td class="text-end">${supportDisplay}</td>
            <td class="text-end">${gapDisplay}</td>
            <td class="text-end">
                <button class="btn btn-sm btn-link text-muted p-0" onclick="Watch.removeStock('${code}')" title="移除">
                    <i class="bi bi-x-lg"></i>
                </button>
            </td>
        </tr>`;
    }

    return `<table class="table table-sm table-hover stock-summary-table mb-0">
        <thead><tr>
            <th>股票</th><th class="text-end">现价</th><th class="text-end">涨跌</th>
            <th class="text-end">支撑</th><th class="text-end">距支撑</th><th></th>
        </tr></thead>
        <tbody>${rows}</tbody>
    </table>`;
},
```

- [ ] **Step 4: 删除旧的 renderStockCard 方法**

删除 `renderStockCard(stock, pricesMap)` (425-489行)。

- [ ] **Step 5: 验证页面加载，确认市场分组和摘要表正确渲染**

在浏览器中打开 `/watch/`，确认：
- 同市场股票分到同一个 section
- 摘要表显示所有字段
- 图表容器存在但暂无图表（下一步实现）

---

### Task 2: 重写 renderChart — 合并多系列百分比图表

**Files:**
- Modify: `app/static/js/watch.js:595-730` (renderChart → renderMarketChart)
- Modify: `app/static/js/watch.js:575-593` (_getPrevClose, _mapDataToTimeAxis)

- [ ] **Step 1: 新增 renderMarketChart(market) 方法**

替代原来的 `renderChart(code)`，一次性渲染一个市场的所有股票：

```javascript
renderMarketChart(market) {
    const container = document.getElementById(`chart-market-${market}`);
    if (!container) return;

    const stocks = this.stocks.filter(s => (s.market || 'A') === market);
    if (stocks.length === 0) return;

    const viewMode = this._marketViewMode[market] || 'intraday';

    if (viewMode === 'intraday') {
        this._renderIntradayChart(market, container, stocks);
    } else {
        this._renderWeeklyChart(market, container, stocks);
    }
},
```

- [ ] **Step 2: 实现 _renderIntradayChart**

```javascript
_renderIntradayChart(market, container, stocks) {
    // 获取交易时间轴（取第一只股票的 meta）
    const firstCode = stocks[0].stock_code;
    const meta = this.chartMeta[firstCode] || {};
    const sessions = meta.tradingSessions || [];
    const fullAxis = sessions.length > 0 ? this._generateFullTimeAxis(sessions) : [];

    if (fullAxis.length === 0) {
        container.innerHTML = '<div class="text-muted text-center small py-4">暂无分时数据</div>';
        return;
    }

    const COLORS = ['#1890ff', '#f5222d', '#52c41a', '#fa8c16', '#722ed1', '#13c2c2', '#eb2f96', '#faad14'];

    const seriesList = [];
    const legendData = [];

    stocks.forEach((stock, idx) => {
        const code = stock.stock_code;
        const name = stock.stock_name || code;
        const data = this.chartData[code] || [];
        const prevClose = this._getPrevClose(code);

        if (data.length === 0 || prevClose == null || prevClose === 0) return;

        // 将价格转为百分比
        const rawPrices = sessions.length > 0
            ? this._mapDataToTimeAxis(data, fullAxis)
            : data.map(d => d.close);
        const pctPrices = rawPrices.map(p => p != null ? Math.round((p - prevClose) / prevClose * 10000) / 100 : null);

        const color = COLORS[idx % COLORS.length];
        legendData.push(name);

        // TD 分钟信号作为 markPoint
        const tdMarkPoints = this._buildTDIntradayMarkPointsPct(code, fullAxis, prevClose);

        seriesList.push({
            name: name,
            type: 'line',
            data: pctPrices,
            smooth: true,
            symbol: 'none',
            connectNulls: false,
            lineStyle: { width: 1.5, color },
            markPoint: tdMarkPoints.length > 0 ? { silent: true, data: tdMarkPoints } : undefined,
        });
    });

    if (seriesList.length === 0) {
        container.innerHTML = '<div class="text-muted text-center small py-4">暂无分时数据</div>';
        return;
    }

    const keyTimes = sessions.length > 0 ? this._getKeyTimePoints(sessions) : new Set();

    // 复用或新建 chart 实例
    if (this.chartInstances[market]) {
        this.chartInstances[market].setOption({
            legend: { data: legendData },
            xAxis: { data: fullAxis },
            series: seriesList,
        }, { replaceMerge: ['series'] });
        return;
    }

    container.innerHTML = '';
    const chart = echarts.init(container);
    this.chartInstances[market] = chart;

    chart.setOption({
        grid: { left: 10, right: 20, top: 35, bottom: 20, containLabel: true },
        legend: {
            data: legendData,
            top: 0,
            textStyle: { fontSize: 11 },
            itemWidth: 16,
            itemHeight: 2,
        },
        tooltip: {
            trigger: 'axis',
            formatter: params => {
                let html = params[0].axisValue;
                params.forEach(p => {
                    if (p.value != null) {
                        const sign = p.value >= 0 ? '+' : '';
                        html += `<br/>${p.marker}${p.seriesName}: ${sign}${p.value.toFixed(2)}%`;
                    }
                });
                return html;
            },
        },
        xAxis: {
            type: 'category',
            data: fullAxis,
            boundaryGap: false,
            axisLabel: {
                fontSize: 9,
                interval: (idx, value) => keyTimes.has(value),
            },
            axisTick: { alignWithLabel: true, interval: (idx, value) => keyTimes.has(fullAxis[idx]) },
            axisLine: { lineStyle: { color: '#ddd' } },
        },
        yAxis: {
            type: 'value',
            scale: true,
            splitLine: { lineStyle: { color: '#f0f0f0' } },
            axisLabel: {
                fontSize: 9,
                formatter: value => `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`,
            },
            // 0%基准线
        },
        series: seriesList,
    });

    new ResizeObserver(() => chart.resize()).observe(container);
},
```

- [ ] **Step 3: 实现 _buildTDIntradayMarkPointsPct**

将 TD 信号的绝对价格坐标转为百分比坐标：

```javascript
_buildTDIntradayMarkPointsPct(code, fullAxis, prevClose) {
    const tdIntraday = this.tdSequentialIntraday[code] || {};
    const tdHistory = tdIntraday.history || [];
    const markData = [];
    if (tdHistory.length === 0 || !prevClose) return markData;

    for (const h of tdHistory) {
        const idx = fullAxis.indexOf(h.time);
        if (idx === -1) continue;
        const pct = (h.price - prevClose) / prevClose * 100;
        const isBuy = h.direction === 'buy';
        markData.push({
            coord: [idx, Math.round(pct * 100) / 100],
            value: h.count,
            symbol: h.count === 9 ? 'circle' : 'none',
            symbolSize: h.count === 9 ? 14 : 1,
            itemStyle: h.count === 9 ? {
                color: isBuy ? 'rgba(22,163,74,0.2)' : 'rgba(220,38,38,0.2)',
                borderColor: isBuy ? '#16a34a' : '#dc2626',
                borderWidth: 1,
            } : undefined,
            label: {
                show: true,
                formatter: String(h.count),
                position: isBuy ? 'bottom' : 'top',
                color: isBuy ? '#16a34a' : '#dc2626',
                fontSize: 10,
                fontWeight: h.count >= 7 ? 'bold' : 'normal',
            },
        });
    }
    return markData;
},
```

- [ ] **Step 4: 删除旧的 renderChart(code)、_buildMarkLines、_buildHighLowMarkPoints、_renderTDGraphic 方法**

这些方法在合并图表中不再需要（支撑/阻力移到摘要表，高低点在百分比图中不适用，TD graphic 移到 markPoint）。

- [ ] **Step 5: 验证实时分时合并图表**

打开 `/watch/`，确认：
- 同市场多只股票在一张图上以不同颜色折线显示
- Y轴显示百分比，0%为基准线
- 图例可点击隐藏/显示
- TD信号正确显示在各自折线上

---

### Task 3: 实现7日视图切换

**Files:**
- Modify: `app/static/js/watch.js` (新增 _renderWeeklyChart, switchMarketView, _marketViewMode)

- [ ] **Step 1: 新增状态和视图切换**

```javascript
// 在 Watch 对象中新增
_marketViewMode: {},   // { 'A': 'intraday', 'US': '7d' }
_weeklyChartData: {},  // { code: [{date, close, ...}, ...] }

switchMarketView(market, mode, btn) {
    this._marketViewMode[market] = mode;
    // 切换按钮 active 状态
    const section = document.querySelector(`.market-section[data-market="${market}"]`);
    if (section) {
        section.querySelectorAll('.view-toggle .btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
    }
    // 销毁当前图表实例（因为系列数据结构不同）
    if (this.chartInstances[market]) {
        this.chartInstances[market].dispose();
        delete this.chartInstances[market];
    }
    if (mode === '7d') {
        this._loadAndRenderWeeklyChart(market);
    } else {
        this.renderMarketChart(market);
    }
},
```

- [ ] **Step 2: 实现 _loadAndRenderWeeklyChart**

```javascript
async _loadAndRenderWeeklyChart(market) {
    const stocks = this.stocks.filter(s => (s.market || 'A') === market);
    const container = document.getElementById(`chart-market-${market}`);
    if (!container) return;

    // 加载缺失的7日数据
    const needFetch = stocks.filter(s => !this._weeklyChartData[s.stock_code]);
    if (needFetch.length > 0) {
        container.innerHTML = '<div class="text-muted text-center small py-4">加载7日数据...</div>';
        await Promise.all(needFetch.map(async s => {
            try {
                const resp = await fetch(`/watch/chart-data?code=${encodeURIComponent(s.stock_code)}&period=7d`);
                const result = await resp.json();
                if (result.success) {
                    this._weeklyChartData[s.stock_code] = result.data || [];
                }
            } catch (e) {
                console.error(`[Watch] 7d data load failed ${s.stock_code}:`, e);
            }
        }));
    }

    this._renderWeeklyChart(market, container, stocks);
},
```

- [ ] **Step 3: 实现 _renderWeeklyChart**

```javascript
_renderWeeklyChart(market, container, stocks) {
    const COLORS = ['#1890ff', '#f5222d', '#52c41a', '#fa8c16', '#722ed1', '#13c2c2', '#eb2f96', '#faad14'];
    const seriesList = [];
    const legendData = [];
    let dateAxis = [];

    stocks.forEach((stock, idx) => {
        const code = stock.stock_code;
        const name = stock.stock_name || code;
        const data = this._weeklyChartData[code] || [];
        if (data.length < 2) return;

        const baseClose = data[0].close;
        if (!baseClose) return;

        if (dateAxis.length === 0) {
            dateAxis = data.map(d => d.date.slice(5)); // MM-DD
        }

        const pctData = data.map(d => Math.round((d.close - baseClose) / baseClose * 10000) / 100);
        const color = COLORS[idx % COLORS.length];
        legendData.push(name);

        seriesList.push({
            name,
            type: 'line',
            data: pctData,
            smooth: true,
            symbol: 'circle',
            symbolSize: 4,
            lineStyle: { width: 1.5, color },
            itemStyle: { color },
        });
    });

    if (seriesList.length === 0) {
        container.innerHTML = '<div class="text-muted text-center small py-4">暂无7日数据</div>';
        return;
    }

    container.innerHTML = '';
    const chart = echarts.init(container);
    this.chartInstances[market] = chart;

    chart.setOption({
        grid: { left: 10, right: 20, top: 35, bottom: 20, containLabel: true },
        legend: { data: legendData, top: 0, textStyle: { fontSize: 11 }, itemWidth: 16, itemHeight: 2 },
        tooltip: {
            trigger: 'axis',
            formatter: params => {
                let html = params[0].axisValue;
                params.forEach(p => {
                    if (p.value != null) {
                        const sign = p.value >= 0 ? '+' : '';
                        html += `<br/>${p.marker}${p.seriesName}: ${sign}${p.value.toFixed(2)}%`;
                    }
                });
                return html;
            },
        },
        xAxis: { type: 'category', data: dateAxis, boundaryGap: false, axisLabel: { fontSize: 9 }, axisLine: { lineStyle: { color: '#ddd' } } },
        yAxis: {
            type: 'value', scale: true,
            splitLine: { lineStyle: { color: '#f0f0f0' } },
            axisLabel: { fontSize: 9, formatter: v => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%` },
        },
        series: seriesList,
    });

    new ResizeObserver(() => chart.resize()).observe(container);
},
```

- [ ] **Step 4: 验证7日视图**

点击"7日"按钮，确认：
- 图表切换为7日折线
- Y轴百分比基于7日前收盘价
- 切回"实时"恢复分时图

---

### Task 4: 更新数据刷新链路

**Files:**
- Modify: `app/static/js/watch.js` (loadAllCharts, loadChartData, appendPricesToCharts, loadAllChartsFromCache, updateAllPrices)

- [ ] **Step 1: 修改 loadAllCharts 和 loadChartData**

`loadChartData` 保持不变（仍按单股获取数据），但渲染改为按市场触发：

```javascript
async loadAllCharts() {
    const promises = this.stocks.map(s => this.loadChartData(s.stock_code));
    await Promise.all(promises);
    // 所有数据加载完毕后，按市场渲染
    this._renderAllMarketCharts();
},

_renderAllMarketCharts() {
    const markets = new Set(this.stocks.map(s => s.market || 'A'));
    for (const market of markets) {
        this.renderMarketChart(market);
    }
},
```

- [ ] **Step 2: 修改 loadChartData — 不再调用 renderChart(code)**

```javascript
async loadChartData(code) {
    try {
        const resp = await fetch(`/watch/chart-data?code=${encodeURIComponent(code)}&period=intraday`);
        const result = await resp.json();
        if (!result.success) return;

        this.chartData[code] = result.data || [];
        this.chartMeta[code] = {
            tradingDate: result.trading_date,
            isTrading: result.is_trading,
            tradingSessions: result.trading_sessions || [],
            prevClose: result.prev_close || null,
            supportLevels: result.support_levels || [],
            resistanceLevels: result.resistance_levels || [],
        };
        if (result.td_sequential) this.tdSequential[code] = result.td_sequential;
        if (result.td_sequential_intraday) this.tdSequentialIntraday[code] = result.td_sequential_intraday;
        WatchCache.save(WatchCache.snapshot(this));
    } catch (e) {
        console.error(`[Watch] chart load failed ${code}:`, e);
    }
},
```

注意：移除了 `prevDayData` 的保存（不再需要昨日走势）。

- [ ] **Step 3: 修改 appendPricesToCharts — 按市场刷新**

```javascript
appendPricesToCharts() {
    const now = new Date();
    const timeKey = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
    const pricesMap = {};
    this.prices.forEach(p => { pricesMap[p.code] = p; });

    const updatedMarkets = new Set();

    for (const stock of this.stocks) {
        const code = stock.stock_code;
        const market = stock.market || 'A';
        const ms = this.marketStatus[market];
        if (!ms || ms.status !== 'trading') continue;

        const p = pricesMap[code];
        if (!p || p.price == null) continue;

        const data = this.chartData[code] || [];
        const newPoint = { time: timeKey, close: p.price };

        if (data.length > 0 && data[data.length - 1].time === timeKey) {
            data[data.length - 1].close = p.price;
        } else {
            data.push(newPoint);
        }
        this.chartData[code] = data;
        updatedMarkets.add(market);
    }

    // 批量刷新受影响的市场图表
    for (const market of updatedMarkets) {
        if ((this._marketViewMode[market] || 'intraday') === 'intraday') {
            this.renderMarketChart(market);
        }
    }

    // 更新摘要表价格
    this._updateAllSummaryTables();
},
```

- [ ] **Step 4: 新增 _updateAllSummaryTables**

```javascript
_updateAllSummaryTables() {
    const pricesMap = {};
    this.prices.forEach(p => { pricesMap[p.code] = p; });

    const groups = {};
    this.stocks.forEach(stock => {
        const market = stock.market || 'A';
        if (!groups[market]) groups[market] = [];
        groups[market].push(stock);
    });

    for (const [market, stocks] of Object.entries(groups)) {
        const el = document.getElementById(`summary-table-${market}`);
        if (el) {
            el.innerHTML = this._renderSummaryTable(stocks, pricesMap);
        }
    }
},
```

- [ ] **Step 5: 修改 loadAllChartsFromCache**

```javascript
loadAllChartsFromCache() {
    this._renderAllMarketCharts();
},
```

- [ ] **Step 6: 修改 updateAllPrices — 同时更新摘要表**

在 `updateAllPrices()` 末尾追加 `this._updateAllSummaryTables();`

- [ ] **Step 7: 验证实时刷新**

开盘时段确认：
- 价格每60秒刷新
- 图表追加新数据点
- 摘要表数据同步更新

---

### Task 5: 清理旧代码和缓存兼容性

**Files:**
- Modify: `app/static/js/watch.js` (删除废弃方法，更新缓存)
- Modify: `app/templates/watch.html` (删除旧 CSS)

- [ ] **Step 1: 删除废弃方法**

删除以下方法：
- `renderStockCard()` — 已被 `_renderSummaryTable` 替代
- `renderChart(code)` — 已被 `renderMarketChart(market)` 替代
- `_buildMarkLines(code)` — 支撑/阻力移到摘要表
- `_buildHighLowMarkPoints()` — 合并图中不再标注单股高低点
- `_renderTDGraphic()` — TD 信号改用 markPoint
- `_buildTDIntradayMarkPoints()` — 已被 `_buildTDIntradayMarkPointsPct` 替代
- `renderAnalysisContent()` — 后续可考虑保留作为摘要表的展开详情
- `switchAnalysisTab()` — 同上
- `updateAllAnalysisPanels()` — 同上
- `renderEarnings()` — 不再有独立财报面板
- `loadEarnings()` — 同上

- [ ] **Step 2: 更新 WatchCache.snapshot/restore**

移除 `prevDayData` 字段，新增 `_weeklyChartData` 和 `_marketViewMode`：

```javascript
snapshot(watch) {
    return {
        date: this._today(),
        prices: watch.prices,
        benchmarks: watch.benchmarks,
        intradayData: watch.chartData,
        chartMeta: watch.chartMeta,
        analyses: watch.analyses,
        marketStatus: watch.marketStatus,
        tdSequential: watch.tdSequential,
        tdSequentialIntraday: watch.tdSequentialIntraday,
        weeklyChartData: watch._weeklyChartData,
        marketViewMode: watch._marketViewMode,
        lastRefreshTime: watch.lastRefreshTime,
    };
},

restore(watch, cache) {
    watch.prices = cache.prices || [];
    watch.benchmarks = cache.benchmarks || [];
    watch.chartData = cache.intradayData || {};
    watch.chartMeta = cache.chartMeta || {};
    watch.analyses = cache.analyses || {};
    watch.marketStatus = cache.marketStatus || {};
    watch.tdSequential = cache.tdSequential || {};
    watch.tdSequentialIntraday = cache.tdSequentialIntraday || {};
    watch._weeklyChartData = cache.weeklyChartData || {};
    watch._marketViewMode = cache.marketViewMode || {};
    watch.lastRefreshTime = cache.lastRefreshTime || null;
},
```

- [ ] **Step 3: 删除 watch.html 中旧的 CSS 规则**

删除 `.stock-card`、`.chart-container`、`.bottom-panel`、`.panel-left`、`.panel-right`、`.analysis-tab`、`.analysis-content`、`.earnings-table` 等不再使用的样式。

- [ ] **Step 4: 修改 removeStock — 刷新市场图表而非单独卡片**

```javascript
async removeStock(code) {
    if (!confirm('确定移除该股票？')) return;
    try {
        const resp = await fetch(`/watch/remove/${code}`, { method: 'DELETE' });
        const data = await resp.json();
        if (data.success) {
            delete this.chartData[code];
            delete this.chartMeta[code];
            delete this._weeklyChartData[code];
            this.stocks = this.stocks.filter(s => s.stock_code !== code);
            this.prices = this.prices.filter(p => p.code !== code);

            // 销毁所有图表实例重新渲染
            Object.values(this.chartInstances).forEach(c => c.dispose());
            this.chartInstances = {};

            if (this.stocks.length === 0) {
                this.showEmpty();
            } else {
                this.renderCards();
                this._renderAllMarketCharts();
            }
            this.updateStatus(`${this.stocks.length} 只股票`);
        }
    } catch (e) {
        console.error('[Watch] removeStock failed:', e);
    }
},
```

- [ ] **Step 5: 完整测试**

验证所有场景：
1. 页面首次加载 — 合并图表正确显示
2. 缓存恢复 — 刷新页面后快速渲染
3. 实时刷新 — 60秒价格更新，图表追加点
4. 视图切换 — 实时/7日来回切换
5. 添加/删除股票 — 图表和表格正确更新
6. 单市场单只股票 — 不crash
7. 多市场混合 — 各市场独立图表

---

### Task 6: 后端优化 — chart-data 移除昨日数据获取

**Files:**
- Modify: `app/routes/watch.py:252-265` (删除 prev_day_data 查询)

- [ ] **Step 1: 删除 prev_day_data 查询逻辑**

在 `chart_data()` 路由的 `period == 'intraday'` 分支中，删除 252-265 行（prev_day_data 的查询和返回），同时从 result 中移除 `result['prev_day_data']`。

保留 `prev_close` 的获取（百分比计算需要）。

- [ ] **Step 2: 验证 API 响应**

访问 `/watch/chart-data?code=603986&period=intraday`，确认响应不再包含 `prev_day_data` 字段。
