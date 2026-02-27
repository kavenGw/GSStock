const Watch = {
    REFRESH_INTERVAL: 60,
    searchDebounce: null,
    stocks: [],
    prices: [],
    marketStatus: {},
    analyses: {},
    chartInstances: {},
    chartData: {},
    refreshTimer: null,

    async init() {
        await this.loadList();
        await this.loadAnalysis();
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
            this.marketStatus = marketData.data || {};

            if (this.stocks.length === 0) {
                this.showEmpty();
                return;
            }

            this.renderMarketBar();
            this.renderCards();
            this.updateStatus(`${this.stocks.length} 只股票`);
            await this.loadAllCharts();
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

        const times = data.map(d => d.time);
        const prices = data.map(d => d.close);

        if (this.chartInstances[code]) {
            this.chartInstances[code].setOption({
                xAxis: { data: times },
                series: [{ data: prices }],
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
