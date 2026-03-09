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

const Watch = {
    REFRESH_INTERVAL: 60,
    ANALYSIS_INTERVAL: 15 * 60,
    MARKET_STATUS_INTERVAL: 5 * 60,
    searchDebounce: null,
    stocks: [],
    prices: [],
    benchmarks: [],
    marketStatus: {},
    analyses: {},
    chartInstances: {},
    chartData: {},
    chartMeta: {},
    refreshTimer: null,
    analysisTimer: null,
    marketStatusTimer: null,

    async init() {
        // 阶段1：从缓存恢复（立即渲染）
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

        // 阶段2：后台更新真实数据
        await this.loadList(true);

        // 阶段3：自动触发分析 + 启动定时器
        this.autoAnalyze();
        this.startRefreshLoop();
        this.startAnalysisLoop();
        this.startMarketStatusLoop();
    },

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

            WatchCache.save(WatchCache.snapshot(this));
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

    async loadAllCharts() {
        const promises = this.stocks.map(s => this.loadChartData(s.stock_code));
        await Promise.all(promises);
    },

    loadAllChartsFromCache() {
        for (const stock of this.stocks) {
            const code = stock.stock_code;
            if (this.chartData[code] && this.chartData[code].length > 0) {
                this.renderChart(code);
            }
        }
    },

    async loadChartData(code) {
        const container = document.getElementById(`chart-${code}`);
        if (!container) return;

        try {
            const resp = await fetch(`/watch/chart-data?code=${encodeURIComponent(code)}&period=intraday`);
            const result = await resp.json();
            if (!result.success) return;

            this.chartData[code] = result.data || [];
            this.chartMeta[code] = {
                tradingDate: result.trading_date,
                isTrading: result.is_trading,
                tradingSessions: result.trading_sessions || [],
                prevDayData: result.prev_day_data || [],
            };
            this.renderChart(code);
            WatchCache.save(WatchCache.snapshot(this));
        } catch (e) {
            console.error(`[Watch] chart load failed ${code}:`, e);
            container.innerHTML = '<div class="text-muted text-center small py-4">图表加载失败</div>';
        }
    },

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
            }

            const hasActiveMarket = Object.values(this.marketStatus).some(m => m.status === 'trading');
            if (!hasActiveMarket) {
                this.stopRefreshLoop();
                this.stopAnalysisLoop();
            } else if (!this.analysisTimer) {
                this.startAnalysisLoop();
            }

            WatchCache.save(WatchCache.snapshot(this));
        } catch (e) {
            console.error('[Watch] refresh failed:', e);
        }
    },

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

            if (data.length > 0 && data[data.length - 1].time === timeKey) {
                data[data.length - 1].close = p.price;
            } else {
                data.push(newPoint);
            }
            this.chartData[code] = data;
            this.renderChart(code);
        }
    },

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
                WatchCache.save(WatchCache.snapshot(this));
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
                <div class="chart-container mb-2" id="chart-${code}">
                    <div class="skeleton skeleton-card" style="height:100%;"></div>
                </div>
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
    },

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

    _mapDataToTimeAxis(rawData, fullAxis) {
        const timeMap = {};
        for (const d of rawData) {
            timeMap[d.time] = d.close;
        }
        return fullAxis.map(t => timeMap[t] != null ? timeMap[t] : null);
    },

    renderChart(code) {
        const container = document.getElementById(`chart-${code}`);
        if (!container) return;
        const data = this.chartData[code] || [];

        if (data.length === 0) {
            container.innerHTML = '<div class="text-muted text-center small py-4">暂无分时数据</div>';
            return;
        }

        const meta = this.chartMeta[code] || {};
        if (meta.tradingDate) {
            const hintId = `chart-hint-${code}`;
            let hintEl = document.getElementById(hintId);
            if (!hintEl) {
                hintEl = document.createElement('div');
                hintEl.id = hintId;
                hintEl.className = 'text-muted text-center small';
                container.parentNode.insertBefore(hintEl, container);
            }
            const label = meta.isTrading ? '今日分时' : `${meta.tradingDate} 分时`;
            hintEl.textContent = label;
        }

        const sessions = meta.tradingSessions || [];
        const fullAxis = sessions.length > 0 ? this._generateFullTimeAxis(sessions) : data.map(d => d.time);
        const prices = sessions.length > 0 ? this._mapDataToTimeAxis(data, fullAxis) : data.map(d => d.close);

        const prevData = meta.prevDayData || [];
        const prevPrices = sessions.length > 0 && prevData.length > 0
            ? this._mapDataToTimeAxis(prevData, fullAxis) : [];

        if (this.chartInstances[code]) {
            const seriesUpdate = [{ data: prices }];
            if (prevPrices.length > 0) seriesUpdate.push({ data: prevPrices });
            this.chartInstances[code].setOption({
                xAxis: { data: fullAxis },
                series: seriesUpdate,
            });
            return;
        }

        container.innerHTML = '';
        const chart = echarts.init(container);
        this.chartInstances[code] = chart;

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

        const seriesList = [{
            type: 'line',
            data: prices,
            smooth: true,
            symbol: 'none',
            connectNulls: false,
            lineStyle: { width: 1.5, color: '#1890ff' },
            areaStyle: { color: 'rgba(24,144,255,0.08)' },
            markLine: markLines.length > 0 ? { silent: true, symbol: 'none', data: markLines } : undefined,
        }];

        if (prevPrices.length > 0) {
            seriesList.push({
                type: 'line',
                data: prevPrices,
                smooth: true,
                symbol: 'none',
                connectNulls: false,
                lineStyle: { width: 1, color: '#888', type: 'dashed' },
                opacity: 0.4,
            });
        }

        chart.setOption({
            grid: { left: 8, right: 55, top: 8, bottom: 20, containLabel: false },
            tooltip: {
                trigger: 'axis',
                formatter: params => {
                    let html = params[0].axisValue;
                    params.forEach(p => {
                        if (p.value != null) {
                            const label = p.seriesIndex === 0 ? '' : '昨日 ';
                            html += `<br/>${label}${Number(p.value).toFixed(2)}`;
                        }
                    });
                    return html;
                },
            },
            xAxis: {
                type: 'category',
                data: fullAxis,
                boundaryGap: false,
                axisLabel: { fontSize: 9, interval: Math.floor(fullAxis.length / 5) },
                axisLine: { lineStyle: { color: '#ddd' } },
            },
            yAxis: {
                type: 'value',
                scale: true,
                splitLine: { lineStyle: { color: '#f0f0f0' } },
                axisLabel: { fontSize: 9 },
            },
            series: seriesList,
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
        if (summary) html += `<div class="mb-1">${summary}</div>`;
        if (supports.length > 0) html += `<span class="text-success small me-2">支撑: ${supports.join(' / ')}</span>`;
        if (resistances.length > 0) html += `<span class="text-danger small">阻力: ${resistances.join(' / ')}</span>`;
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

    updateMarketStatusBadges() {
        document.querySelectorAll('.market-group').forEach(group => {
            const badge = group.querySelector('.badge');
            const marketName = group.querySelector('.fw-bold');
            if (!badge || !marketName) return;

            const marketEntry = Object.entries(this.marketStatus).find(([_, ms]) =>
                marketName.textContent.includes(ms.name)
            );
            if (!marketEntry) return;

            const [, ms] = marketEntry;
            const statusBadge = this.getStatusBadgeClass(ms.status || 'closed');
            const statusIcon = this.getStatusIcon(ms.status || 'closed');
            badge.className = `badge ${statusBadge} ms-2`;
            badge.textContent = `${statusIcon} ${ms.status_text || ''}`;
        });
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
