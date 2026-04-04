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

const Watch = {
    REFRESH_INTERVAL: 60,
    ANALYSIS_INTERVAL: 15 * 60,
    MARKET_STATUS_INTERVAL: 5 * 60,
    CHART_COLORS: ['#1890ff', '#f5222d', '#52c41a', '#fa8c16', '#722ed1', '#13c2c2', '#eb2f96', '#faad14'],
    searchDebounce: null,
    stocks: [],
    prices: [],
    benchmarks: [],
    marketStatus: {},
    analyses: {},
    chartInstances: {},
    chartData: {},
    chartMeta: {},
    tdSequential: {},
    tdSequentialIntraday: {},
    _marketViewMode: {},
    _weeklyChartData: {},
    lastRefreshTime: null,
    refreshTimer: null,
    analysisTimer: null,
    marketStatusTimer: null,

    async init() {
        WatchStore.init();
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
            this.benchmarks = priceData.benchmarks || [];
            this.marketStatus = marketData.data || {};

            this.renderBenchmarks();

            if (this.stocks.length === 0) {
                this.showEmpty();
                return;
            }

            this.renderCards();
            this.updateStatus(`${this.stocks.length} 只股票`);
            this.recordRefreshTime();
            await this.loadAllCharts();

            this._saveToStore();
        } catch (e) {
            console.error('[Watch] loadList failed:', e);
            this.updateStatus('加载失败');
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

    // --- 市场分组工具 ---
    _getMarketGroups() {
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
        return { groups, sortedMarkets };
    },

    // --- 渲染 ---
    renderCards() {
        Object.values(this.chartInstances).forEach(c => c.dispose());
        this.chartInstances = {};

        const { groups, sortedMarkets } = this._getMarketGroups();
        const container = document.getElementById('stockCards');
        let html = '';

        for (const market of sortedMarkets) {
            const ms = this.marketStatus[market] || {};
            const icon = ms.icon || '';
            const name = ms.name || market;
            const statusText = ms.status_text || '';
            const statusBadge = this.getStatusBadgeClass(ms.status || 'closed');
            const statusIcon = this.getStatusIcon(ms.status || 'closed');
            const viewMode = this._marketViewMode[market] || 'intraday';

            html += `<div class="card market-section mb-4" id="market-section-${market}">
                <div class="card-body">
                    <div class="d-flex align-items-center justify-content-between mb-2">
                        <div class="d-flex align-items-center gap-2">
                            <span class="fw-bold">${icon} ${name}</span>
                            <span class="badge ${statusBadge}">${statusIcon} ${statusText}</span>
                        </div>
                        <div class="view-toggle btn-group btn-group-sm">
                            <button class="btn btn-outline-secondary${viewMode === 'intraday' ? ' active' : ''}" onclick="Watch.switchMarketView('${market}','intraday',this)">实时</button>
                            <button class="btn btn-outline-secondary${viewMode === '7d' ? ' active' : ''}" onclick="Watch.switchMarketView('${market}','7d',this)">7日</button>
                        </div>
                    </div>
                    <div class="market-chart" id="chart-market-${market}">
                        <div class="skeleton skeleton-card" style="height:100%;"></div>
                    </div>
                    <div id="summary-table-${market}" class="mt-2"></div>
                </div>
            </div>`;
        }

        container.innerHTML = html;
        document.getElementById('loadingState').classList.add('d-none');
        document.getElementById('emptyState').classList.add('d-none');
        container.classList.remove('d-none');

        this._updateAllSummaryTables();
    },

    _renderSummaryTable(market) {
        const el = document.getElementById(`summary-table-${market}`);
        if (!el) return;

        const { groups } = this._getMarketGroups();
        const stocks = groups[market] || [];
        const pricesMap = {};
        this.prices.forEach(p => { pricesMap[p.code] = p; });

        let html = `<table class="table table-sm table-hover stock-summary-table mb-0">
            <thead><tr>
                <th>股票</th><th class="text-end">涨跌%</th><th class="text-end">压力位</th>
                <th class="text-end">现价</th><th class="text-end">支撑位</th>
                <th>AI摘要</th><th></th>
            </tr></thead><tbody>`;

        for (const stock of stocks) {
            const code = stock.stock_code;
            const name = stock.stock_name || code;
            const mkt = stock.market || 'A';
            const p = pricesMap[code] || {};

            const td = this.tdSequential[code] || {};
            let tdBadge = '';
            if (td.direction && td.count > 0) {
                const tdClass = td.direction === 'buy' ? 'td-badge-buy' : 'td-badge-sell';
                const warn = td.count >= 7 ? ' td-badge-warn' : '';
                const check = td.completed ? ' ✓' : '';
                const label = td.direction === 'buy' ? '买' : '卖';
                tdBadge = ` <span class="td-badge ${tdClass}${warn}">${label}${td.count}${check}</span>`;
            }

            const priceDisplay = p.price != null ? this.formatPrice(p.price, mkt) : '--';
            const pctClass = p.change_pct > 0 ? 'price-up' : p.change_pct < 0 ? 'price-down' : 'price-flat';
            const pctSign = p.change_pct > 0 ? '+' : '';
            const pctDisplay = p.change_pct != null ? `${pctSign}${p.change_pct.toFixed(2)}%` : '--';

            const meta = this.chartMeta[code] || {};
            const supports = (meta.supportLevels || []).filter(s => p.price != null && s < p.price);
            const nearestSupport = supports.length > 0 ? Math.max(...supports) : null;
            const supportDisplay = nearestSupport != null ? nearestSupport.toFixed(2) : '--';
            const supportDist = nearestSupport != null && p.price != null ? (p.price - nearestSupport).toFixed(2) : null;

            const resistances = (meta.resistanceLevels || []).filter(r => p.price != null && r > p.price);
            const nearestResistance = resistances.length > 0 ? Math.min(...resistances) : null;
            const resistanceDisplay = nearestResistance != null ? nearestResistance.toFixed(2) : '--';
            const resistanceDist = nearestResistance != null && p.price != null ? (nearestResistance - p.price).toFixed(2) : null;

            const codeAnalysis = this.analyses[code] || {};
            const rtData = codeAnalysis['realtime'] || {};
            let aiHtml = '<span class="text-muted">--</span>';
            if (rtData.summary) {
                const signal = rtData.signal || '';
                const signalText = rtData.detail?.signal_text || this._signalTextMap(signal);
                let badge = signal ? `<span class="entry-signal signal-${signal} me-1">${signalText}</span>` : '';
                const summaryText = rtData.summary.length > 30 ? rtData.summary.slice(0, 30) + '...' : rtData.summary;
                aiHtml = `${badge}<span class="small">${summaryText}</span>`;
            }

            const resistanceCell = resistanceDist != null ? `${resistanceDisplay} <small class="text-muted">(${resistanceDist})</small>` : resistanceDisplay;
            const supportCell = supportDist != null ? `${supportDisplay} <small class="text-muted">(${supportDist})</small>` : supportDisplay;

            html += `<tr>
                <td class="stock-name">${name}${tdBadge}</td>
                <td class="text-end ${pctClass} fw-bold">${pctDisplay}</td>
                <td class="text-end text-danger">${resistanceCell}</td>
                <td class="text-end fw-bold">${priceDisplay}</td>
                <td class="text-end text-success">${supportCell}</td>
                <td>${aiHtml}</td>
                <td class="text-end"><button class="btn btn-sm btn-link text-muted p-0" onclick="Watch.removeStock('${code}')" title="移除"><i class="bi bi-x-lg"></i></button></td>
            </tr>`;
        }

        html += '</tbody></table>';
        el.innerHTML = html;
    },

    _updateAllSummaryTables() {
        const { sortedMarkets } = this._getMarketGroups();
        for (const market of sortedMarkets) {
            this._renderSummaryTable(market);
        }
    },

    // --- 图表 ---
    async loadAllCharts() {
        const promises = this.stocks.map(s => this.loadChartData(s.stock_code));
        await Promise.all(promises);
        this._renderAllMarketCharts();
    },

    loadAllChartsFromCache() {
        this._renderAllMarketCharts();
    },

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
            if (result.td_sequential) {
                this.tdSequential[code] = result.td_sequential;
            }
            if (result.td_sequential_intraday) {
                this.tdSequentialIntraday[code] = result.td_sequential_intraday;
            }
            this._saveToStore();
        } catch (e) {
            console.error(`[Watch] chart load failed ${code}:`, e);
        }
    },

    _renderAllMarketCharts() {
        const { sortedMarkets } = this._getMarketGroups();
        for (const market of sortedMarkets) {
            this.renderMarketChart(market);
        }
    },

    renderMarketChart(market) {
        const mode = this._marketViewMode[market] || 'intraday';
        const { groups } = this._getMarketGroups();
        const stocks = groups[market] || [];
        const container = document.getElementById(`chart-market-${market}`);
        if (!container || stocks.length === 0) return;

        if (mode === '7d') {
            this._renderWeeklyChart(market, container, stocks);
        } else {
            this._renderIntradayChart(market, container, stocks);
        }
    },

    _getPrevClose(code) {
        const meta = this.chartMeta[code] || {};
        if (meta.prevClose != null) return meta.prevClose;
        const p = this.prices.find(pr => pr.code === code);
        if (p && p.price != null && p.change != null) {
            return Math.round((p.price - p.change) * 100) / 100;
        }
        return null;
    },

    _generateFullTimeAxis(sessions) {
        const times = [];
        for (const [start, end] of sessions) {
            const [sh, sm] = start.split(':').map(Number);
            const [eh, em] = end.split(':').map(Number);
            let mins = sh * 60 + sm;
            const endMins = eh * 60 + em;
            while (mins <= endMins) {
                times.push(`${String(Math.floor(mins / 60)).padStart(2, '0')}:${String(mins % 60).padStart(2, '0')}`);
                mins++;
            }
        }
        return times;
    },

    _getKeyTimePoints(sessions) {
        const keys = new Set();
        for (let i = 0; i < sessions.length; i++) {
            const [start, end] = sessions[i];
            keys.add(start);
            if (i === sessions.length - 1) keys.add(end);
            const [sh] = start.split(':').map(Number);
            const [eh, em] = end.split(':').map(Number);
            for (let h = sh + 1; h <= eh; h++) {
                if (h * 60 <= eh * 60 + em) {
                    keys.add(`${String(h).padStart(2, '0')}:00`);
                }
            }
        }
        return keys;
    },

    _mapDataToTimeAxis(rawData, fullAxis) {
        const timeMap = {};
        for (const d of rawData) {
            timeMap[d.time] = d.close;
        }
        return fullAxis.map(t => timeMap[t] != null ? timeMap[t] : null);
    },

    _renderIntradayChart(market, container, stocks) {
        if (this.chartInstances[market]) {
            this.chartInstances[market].dispose();
            delete this.chartInstances[market];
        }

        let sessions = [];
        for (const stock of stocks) {
            const meta = this.chartMeta[stock.stock_code] || {};
            if (meta.tradingSessions && meta.tradingSessions.length > 0) {
                sessions = meta.tradingSessions;
                break;
            }
        }

        const hasData = stocks.some(s => (this.chartData[s.stock_code] || []).length > 0);
        if (!hasData) {
            container.innerHTML = '<div class="text-muted text-center small py-4">暂无分时数据</div>';
            return;
        }

        const fullAxis = sessions.length > 0
            ? this._generateFullTimeAxis(sessions)
            : (() => {
                const allTimes = new Set();
                stocks.forEach(s => (this.chartData[s.stock_code] || []).forEach(d => allTimes.add(d.time)));
                return [...allTimes].sort();
            })();

        const keyTimes = sessions.length > 0 ? this._getKeyTimePoints(sessions) : new Set(fullAxis.filter(t => t.endsWith(':00')));

        container.innerHTML = '';
        const chart = echarts.init(container);
        this.chartInstances[market] = chart;

        const seriesList = [];
        const legendData = [];

        stocks.forEach((stock, idx) => {
            const code = stock.stock_code;
            const name = stock.stock_name || code;
            const color = this.CHART_COLORS[idx % this.CHART_COLORS.length];
            const data = this.chartData[code] || [];
            const prevClose = this._getPrevClose(code);

            const prices = sessions.length > 0
                ? this._mapDataToTimeAxis(data, fullAxis)
                : fullAxis.map(t => { const d = data.find(x => x.time === t); return d ? d.close : null; });

            const pctData = prices.map(p => {
                if (p == null || prevClose == null || prevClose === 0) return null;
                return Math.round((p - prevClose) / prevClose * 10000) / 100;
            });

            legendData.push(name);

            const tdMarkPoints = this._buildTDIntradayMarkPointsPct(code, fullAxis, prevClose);

            seriesList.push({
                name,
                type: 'line',
                data: pctData,
                smooth: true,
                symbol: 'none',
                connectNulls: false,
                lineStyle: { width: 1.5, color },
                itemStyle: { color },
                markPoint: tdMarkPoints.length > 0 ? { silent: true, data: tdMarkPoints } : undefined,
            });
        });

        chart.setOption({
            grid: { left: 10, right: 10, top: 30, bottom: 20, containLabel: true },
            legend: { data: legendData, top: 0, textStyle: { fontSize: 11 }, selectedMode: true },
            tooltip: {
                trigger: 'axis',
                formatter: params => {
                    let html = params[0].axisValue;
                    params.forEach(p => {
                        if (p.value != null) {
                            const sign = p.value > 0 ? '+' : '';
                            html += `<br/><span style="color:${p.color}">\u25CF</span> ${p.seriesName}: ${sign}${p.value.toFixed(2)}%`;
                        }
                    });
                    return html;
                },
            },
            xAxis: {
                type: 'category',
                data: fullAxis,
                boundaryGap: false,
                axisLabel: { fontSize: 9, interval: (idx, value) => keyTimes.has(value) },
                axisTick: { alignWithLabel: true, interval: (idx) => keyTimes.has(fullAxis[idx]) },
                axisLine: { lineStyle: { color: '#ddd' } },
            },
            yAxis: {
                type: 'value',
                scale: true,
                splitLine: { lineStyle: { color: '#f0f0f0' } },
                axisLabel: {
                    fontSize: 9,
                    formatter: v => (v > 0 ? '+' : '') + v.toFixed(2) + '%',
                },
            },
            series: seriesList,
        });

        new ResizeObserver(() => chart.resize()).observe(container);
    },

    _renderWeeklyChart(market, container, stocks) {
        if (this.chartInstances[market]) {
            this.chartInstances[market].dispose();
            delete this.chartInstances[market];
        }

        const hasData = stocks.some(s => (this._weeklyChartData[s.stock_code] || []).length > 0);
        if (!hasData) {
            container.innerHTML = '<div class="text-muted text-center small py-4">暂无7日数据</div>';
            return;
        }

        const allDates = new Set();
        stocks.forEach(s => (this._weeklyChartData[s.stock_code] || []).forEach(d => allDates.add(d.date)));
        const dateAxis = [...allDates].sort();
        const displayAxis = dateAxis.map(d => d.slice(5));

        container.innerHTML = '';
        const chart = echarts.init(container);
        this.chartInstances[market] = chart;

        const seriesList = [];
        const legendData = [];

        stocks.forEach((stock, idx) => {
            const code = stock.stock_code;
            const name = stock.stock_name || code;
            const color = this.CHART_COLORS[idx % this.CHART_COLORS.length];
            const data = this._weeklyChartData[code] || [];

            const dateMap = {};
            data.forEach(d => { dateMap[d.date] = d.close; });

            const baseClose = data.length > 0 ? data[0].close : null;
            const pctData = dateAxis.map(date => {
                const close = dateMap[date];
                if (close == null || baseClose == null || baseClose === 0) return null;
                return Math.round((close - baseClose) / baseClose * 10000) / 100;
            });

            legendData.push(name);
            seriesList.push({
                name,
                type: 'line',
                data: pctData,
                smooth: true,
                symbol: 'circle',
                symbolSize: 4,
                connectNulls: false,
                lineStyle: { width: 1.5, color },
                itemStyle: { color },
            });
        });

        chart.setOption({
            grid: { left: 10, right: 10, top: 30, bottom: 20, containLabel: true },
            legend: { data: legendData, top: 0, textStyle: { fontSize: 11 }, selectedMode: true },
            tooltip: {
                trigger: 'axis',
                formatter: params => {
                    let html = params[0].axisValue;
                    params.forEach(p => {
                        if (p.value != null) {
                            const sign = p.value > 0 ? '+' : '';
                            html += `<br/><span style="color:${p.color}">\u25CF</span> ${p.seriesName}: ${sign}${p.value.toFixed(2)}%`;
                        }
                    });
                    return html;
                },
            },
            xAxis: {
                type: 'category',
                data: displayAxis,
                boundaryGap: false,
                axisLabel: { fontSize: 9 },
                axisLine: { lineStyle: { color: '#ddd' } },
            },
            yAxis: {
                type: 'value',
                scale: true,
                splitLine: { lineStyle: { color: '#f0f0f0' } },
                axisLabel: {
                    fontSize: 9,
                    formatter: v => (v > 0 ? '+' : '') + v.toFixed(2) + '%',
                },
            },
            series: seriesList,
        });

        new ResizeObserver(() => chart.resize()).observe(container);
    },

    _buildTDIntradayMarkPointsPct(code, fullAxis, prevClose) {
        const tdIntraday = this.tdSequentialIntraday[code] || {};
        const tdHistory = tdIntraday.history || [];
        const markData = [];
        if (tdHistory.length === 0 || fullAxis.length === 0 || prevClose == null || prevClose === 0) return markData;

        for (const h of tdHistory) {
            const idx = fullAxis.indexOf(h.time);
            if (idx === -1) continue;
            const pctValue = (h.price - prevClose) / prevClose * 100;
            const isBuy = h.direction === 'buy';
            markData.push({
                coord: [idx, pctValue],
                value: h.count,
                symbol: h.count === 9 ? 'circle' : 'none',
                symbolSize: h.count === 9 ? 16 : 1,
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
                    fontSize: 11,
                    fontWeight: h.count >= 7 ? 'bold' : 'normal',
                    offset: isBuy ? [0, 4] : [0, -4],
                },
            });
        }
        return markData;
    },

    switchMarketView(market, mode, btn) {
        this._marketViewMode[market] = mode;
        const section = document.getElementById(`market-section-${market}`);
        if (section) {
            section.querySelectorAll('.view-toggle .btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        }
        if (mode === '7d') {
            this._loadAndRenderWeeklyChart(market);
        } else {
            this.renderMarketChart(market);
        }
        this._saveToStore();
    },

    async _loadAndRenderWeeklyChart(market) {
        const { groups } = this._getMarketGroups();
        const stocks = groups[market] || [];
        const cached = stocks.filter(s => this._weeklyChartData[s.stock_code] && this._weeklyChartData[s.stock_code].length > 0);
        const missing = stocks.filter(s => !(this._weeklyChartData[s.stock_code] && this._weeklyChartData[s.stock_code].length > 0));

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

    // --- 数据刷新 ---
    async refreshIncrementalData() {
        try {
            const priceResp = await fetch('/watch/prices');
            const priceData = await priceResp.json();

            if (priceData.success) {
                this.prices = priceData.prices || [];
                this.benchmarks = priceData.benchmarks || [];
                this.updateAllPrices();
                this.renderBenchmarks();
                this.appendPricesToCharts();
                this.recordRefreshTime();
            }

            const hasActiveMarket = Object.values(this.marketStatus).some(m => m.status === 'trading');
            if (!hasActiveMarket) {
                this.stopRefreshLoop();
                this.stopAnalysisLoop();
            } else if (!this.analysisTimer) {
                this.startAnalysisLoop();
            }

            this._saveToStore();
        } catch (e) {
            console.error('[Watch] refresh failed:', e);
        }
    },

    appendPricesToCharts() {
        const now = new Date();
        const timeKey = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;

        const pricesMap = {};
        this.prices.forEach(p => { pricesMap[p.code] = p; });

        const affectedMarkets = new Set();

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
            affectedMarkets.add(market);
        }

        for (const market of affectedMarkets) {
            const mode = this._marketViewMode[market] || 'intraday';
            if (mode === 'intraday') {
                this.renderMarketChart(market);
            }
        }

        this._updateAllSummaryTables();
    },

    updateAllPrices() {
        this._updateAllSummaryTables();
    },

    updateAllAnalysisPanels() {
        this._updateAllSummaryTables();
    },

    // --- 定时器 ---
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

    startAnalysisLoop() {
        this.stopAnalysisLoop();
        this.analysisTimer = setInterval(async () => {
            await this.loadAnalysis();
        }, this.ANALYSIS_INTERVAL * 1000);
    },

    stopAnalysisLoop() {
        if (this.analysisTimer) {
            clearInterval(this.analysisTimer);
            this.analysisTimer = null;
        }
    },

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

    async loadAnalysis() {
        try {
            const resp = await fetch('/watch/analysis');
            const data = await resp.json();
            if (data.success) {
                this.analyses = data.data || {};
                this.updateAllAnalysisPanels();
                this._saveToStore();
            }
        } catch (e) {
            console.error('[Watch] loadAnalysis failed:', e);
        }
    },

    // --- 增删 ---
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
                Object.values(this.chartInstances).forEach(c => c.dispose());
                this.chartInstances = {};
                delete this.chartData[code];
                delete this._weeklyChartData[code];
                this.stocks = this.stocks.filter(s => s.stock_code !== code);
                this.prices = this.prices.filter(p => p.code !== code);
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

    // --- UI工具 ---
    updateMarketStatusBadges() {
        const { sortedMarkets } = this._getMarketGroups();
        for (const market of sortedMarkets) {
            const section = document.getElementById(`market-section-${market}`);
            if (!section) continue;
            const badge = section.querySelector('.badge');
            if (!badge) continue;
            const ms = this.marketStatus[market] || {};
            badge.className = `badge ${this.getStatusBadgeClass(ms.status || 'closed')}`;
            badge.textContent = `${this.getStatusIcon(ms.status || 'closed')} ${ms.status_text || ''}`;
        }
    },

    showEmpty() {
        document.getElementById('loadingState').classList.add('d-none');
        document.getElementById('stockCards').classList.add('d-none');
        document.getElementById('emptyState').classList.remove('d-none');
        this.updateStatus('暂无盯盘股票');
    },

    updateStatus(text) {
        document.getElementById('watchStatus').textContent = text;
    },

    showRefreshTime() {
        const el = document.getElementById('lastRefreshTime');
        if (el && this.lastRefreshTime) {
            el.textContent = `· 最后刷新 ${this.lastRefreshTime}`;
            el.style.display = '';
        }
    },

    recordRefreshTime() {
        this.lastRefreshTime = new Date().toLocaleTimeString('zh-CN', {hour: '2-digit', minute: '2-digit', second: '2-digit'});
        this.showRefreshTime();
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

    _signalTextMap(signal) {
        const map = { buy: '买入', sell: '卖出', hold: '持有', watch: '观望' };
        return map[signal] || '观望';
    },

    _formatLargeNumber(num) {
        if (num == null || num === 0) return '--';
        const abs = Math.abs(num);
        const sign = num < 0 ? '-' : '';
        if (abs >= 1e12) return sign + (abs / 1e12).toFixed(1) + 'T';
        if (abs >= 1e9) return sign + (abs / 1e9).toFixed(1) + 'B';
        if (abs >= 1e8) return sign + (abs / 1e8).toFixed(1) + '亿';
        if (abs >= 1e4) return sign + (abs / 1e4).toFixed(0) + '万';
        return sign + abs.toFixed(0);
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
