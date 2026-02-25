const Watch = {
    refreshTimer: null,
    analyses: {},
    searchDebounce: null,
    stocks: [],
    prices: [],

    async init() {
        await this.loadList();
        await this.loadAnalysis();
        this.startAutoRefresh();
    },

    async loadList() {
        try {
            const resp = await fetch('/watch/list');
            const data = await resp.json();
            if (!data.success) return;

            this.stocks = data.data || [];
            if (this.stocks.length === 0) {
                this.showEmpty();
                return;
            }

            const priceResp = await fetch('/watch/prices');
            const priceData = await priceResp.json();
            this.prices = priceData.prices || [];

            this.renderCards(this.stocks, this.prices);
            this.updateStatus(`${this.stocks.length} 只股票`);
        } catch (e) {
            console.error('[Watch] loadList failed:', e);
            this.updateStatus('加载失败');
        }
    },

    async refreshPrices() {
        try {
            const resp = await fetch('/watch/prices');
            const data = await resp.json();
            if (!data.success) return;
            this.prices = data.prices || [];
            this.updatePrices(this.prices);
        } catch (e) {
            console.error('[Watch] refreshPrices failed:', e);
        }
    },

    async triggerAnalysis(force = false) {
        const btn = document.getElementById('btnAnalyze');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> 分析中...';

        try {
            const resp = await fetch('/watch/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ force }),
            });
            const data = await resp.json();
            if (data.success) {
                this.analyses = data.data || {};
                this.applyAnalyses();
            }
        } catch (e) {
            console.error('[Watch] triggerAnalysis failed:', e);
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-robot"></i> AI 分析';
        }
    },

    async loadAnalysis() {
        try {
            const resp = await fetch('/watch/analysis');
            const data = await resp.json();
            if (data.success) {
                this.analyses = data.data || {};
                this.applyAnalyses();
                if (this.stocks.length > 0 && Object.keys(this.analyses).length === 0) {
                    this.triggerAnalysis();
                }
            }
        } catch (e) {
            console.error('[Watch] loadAnalysis failed:', e);
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
                this.triggerAnalysis();
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
                const card = document.getElementById(`watch-card-${code}`);
                if (card) card.remove();
                this.stocks = this.stocks.filter(s => s.stock_code !== code);
                delete this.analyses[code];
                if (this.stocks.length === 0) this.showEmpty();
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
            if (!query.trim()) {
                container.innerHTML = '';
                return;
            }
            try {
                const resp = await fetch(`/watch/stocks/search?q=${encodeURIComponent(query)}`);
                const data = await resp.json();
                if (!data.success) return;

                const existingCodes = new Set(this.stocks.map(s => s.stock_code));
                container.innerHTML = (data.data || []).map(s => {
                    const added = existingCodes.has(s.stock_code);
                    return `<div class="list-group-item d-flex justify-content-between align-items-center">
                        <div>
                            <span class="fw-bold">${s.stock_name}</span>
                            <small class="text-muted ms-2">${s.stock_code}</small>
                        </div>
                        ${added
                            ? '<span class="badge bg-secondary">已添加</span>'
                            : `<button class="btn btn-sm btn-outline-primary" onclick="Watch.addStock('${s.stock_code}','${s.stock_name}')">添加</button>`
                        }
                    </div>`;
                }).join('');

                if ((data.data || []).length === 0) {
                    container.innerHTML = '<div class="list-group-item text-muted text-center">无匹配结果</div>';
                }
            } catch (e) {
                console.error('[Watch] searchStocks failed:', e);
            }
        }, 300);
    },

    renderCards(stocks, prices) {
        const pricesMap = {};
        prices.forEach(p => { pricesMap[p.code] = p; });

        const container = document.getElementById('watchCards');
        container.innerHTML = stocks.map(stock => {
            const price = pricesMap[stock.stock_code] || {};
            const analysis = this.analyses[stock.stock_code] || {};
            return this.renderCard(stock, price, analysis);
        }).join('');

        document.getElementById('loadingState').classList.add('d-none');
        document.getElementById('emptyState').classList.add('d-none');
        container.classList.remove('d-none');
    },

    renderCard(stock, price, analysis) {
        const code = stock.stock_code;
        const name = stock.stock_name || code;
        const market = stock.market || 'A';

        const currentPrice = price.price ?? null;
        const changePct = price.change_pct ?? null;
        const changeAmt = price.change ?? null;

        const priceDisplay = currentPrice !== null ? this.formatPrice(currentPrice, market) : '--';
        const pctClass = changePct > 0 ? 'text-danger' : changePct < 0 ? 'text-success' : 'text-muted';
        const pctSign = changePct > 0 ? '+' : '';
        const pctDisplay = changePct !== null ? `${pctSign}${changePct.toFixed(2)}%` : '--';
        const amtSign = changeAmt > 0 ? '+' : '';
        const amtDisplay = changeAmt !== null ? `${amtSign}${changeAmt.toFixed(2)}` : '';

        const marketBadge = this.getMarketBadge(market);
        const marketStatus = this.getMarketStatus(market);

        let analysisHtml = '<div class="text-muted small mt-2">暂无AI分析</div>';
        if (analysis.summary) {
            const supports = (analysis.support_levels || []).map(v =>
                `<span class="badge bg-success bg-opacity-25 text-success me-1">${v}</span>`
            ).join('');
            const resistances = (analysis.resistance_levels || []).map(v =>
                `<span class="badge bg-danger bg-opacity-25 text-danger me-1">${v}</span>`
            ).join('');
            const threshold = analysis.volatility_threshold
                ? `<span class="badge bg-warning bg-opacity-25 text-warning">波动 ${(analysis.volatility_threshold * 100).toFixed(1)}%</span>`
                : '';

            analysisHtml = `<div class="mt-2 small">
                ${supports ? `<div class="mb-1"><span class="text-muted">支撑:</span> ${supports}</div>` : ''}
                ${resistances ? `<div class="mb-1"><span class="text-muted">阻力:</span> ${resistances}</div>` : ''}
                ${threshold ? `<div class="mb-1">${threshold}</div>` : ''}
                <div class="text-muted fst-italic">${analysis.summary}</div>
            </div>`;
        }

        return `<div class="col-md-6 col-lg-4" id="watch-card-${code}">
            <div class="card h-100">
                <div class="card-body pb-2">
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <div>
                            <span class="fw-bold">${name}</span>
                            <small class="text-muted ms-1">${code}</small>
                            ${marketBadge}
                        </div>
                        <button class="btn btn-sm btn-link text-muted p-0" onclick="Watch.removeStock('${code}')" title="移除">
                            <i class="bi bi-x-lg"></i>
                        </button>
                    </div>
                    <div class="mb-1">
                        <span class="fs-4 fw-bold" data-field="price" data-code="${code}">${priceDisplay}</span>
                    </div>
                    <div class="mb-2">
                        <span class="${pctClass} fw-bold" data-field="change_pct" data-code="${code}">${pctDisplay}</span>
                        <span class="${pctClass} small ms-2" data-field="change" data-code="${code}">${amtDisplay}</span>
                    </div>
                    <div data-field="analysis" data-code="${code}">
                        ${analysisHtml}
                    </div>
                </div>
                <div class="card-footer py-1">
                    <small class="text-muted">${marketStatus}</small>
                </div>
            </div>
        </div>`;
    },

    updatePrices(prices) {
        const pricesMap = {};
        prices.forEach(p => { pricesMap[p.code] = p; });

        this.stocks.forEach(stock => {
            const code = stock.stock_code;
            const market = stock.market || 'A';
            const p = pricesMap[code];
            if (!p) return;

            const priceEl = document.querySelector(`[data-field="price"][data-code="${code}"]`);
            const pctEl = document.querySelector(`[data-field="change_pct"][data-code="${code}"]`);
            const amtEl = document.querySelector(`[data-field="change"][data-code="${code}"]`);

            if (priceEl) priceEl.textContent = this.formatPrice(p.price, market);

            const pctClass = p.change_pct > 0 ? 'text-danger' : p.change_pct < 0 ? 'text-success' : 'text-muted';
            const pctSign = p.change_pct > 0 ? '+' : '';
            if (pctEl) {
                pctEl.textContent = `${pctSign}${p.change_pct.toFixed(2)}%`;
                pctEl.className = `${pctClass} fw-bold`;
            }
            const amtSign = p.change > 0 ? '+' : '';
            if (amtEl) {
                amtEl.textContent = `${amtSign}${p.change.toFixed(2)}`;
                amtEl.className = `${pctClass} small ms-2`;
            }
        });
    },

    applyAnalyses() {
        Object.keys(this.analyses).forEach(code => {
            const el = document.querySelector(`[data-field="analysis"][data-code="${code}"]`);
            if (!el) return;
            const analysis = this.analyses[code];
            if (!analysis.summary) return;

            const supports = (analysis.support_levels || []).map(v =>
                `<span class="badge bg-success bg-opacity-25 text-success me-1">${v}</span>`
            ).join('');
            const resistances = (analysis.resistance_levels || []).map(v =>
                `<span class="badge bg-danger bg-opacity-25 text-danger me-1">${v}</span>`
            ).join('');
            const threshold = analysis.volatility_threshold
                ? `<span class="badge bg-warning bg-opacity-25 text-warning">波动 ${(analysis.volatility_threshold * 100).toFixed(1)}%</span>`
                : '';

            el.innerHTML = `<div class="mt-2 small">
                ${supports ? `<div class="mb-1"><span class="text-muted">支撑:</span> ${supports}</div>` : ''}
                ${resistances ? `<div class="mb-1"><span class="text-muted">阻力:</span> ${resistances}</div>` : ''}
                ${threshold ? `<div class="mb-1">${threshold}</div>` : ''}
                <div class="text-muted fst-italic">${analysis.summary}</div>
            </div>`;
        });
    },

    startAutoRefresh() {
        this.stopAutoRefresh();
        this.refreshTimer = setInterval(() => this.refreshPrices(), 60000);
    },

    stopAutoRefresh() {
        if (this.refreshTimer) {
            clearInterval(this.refreshTimer);
            this.refreshTimer = null;
        }
    },

    showEmpty() {
        document.getElementById('loadingState').classList.add('d-none');
        document.getElementById('watchCards').classList.add('d-none');
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
        return `${val}`;
    },

    getMarketBadge(market) {
        const map = {
            A: '<span class="badge bg-primary ms-1">A</span>',
            US: '<span class="badge bg-success ms-1">US</span>',
            HK: '<span class="badge bg-warning text-dark ms-1">HK</span>',
        };
        return map[market] || '';
    },

    getMarketStatus(market) {
        const now = new Date();
        const h = now.getHours();
        const m = now.getMinutes();
        const t = h * 60 + m;
        const weekday = now.getDay();

        if (weekday === 0 || weekday === 6) return '休市';

        if (market === 'A') {
            if (t >= 570 && t < 690) return '交易中';
            if (t >= 690 && t < 780) return '午休';
            if (t >= 780 && t < 900) return '交易中';
            return '已收盘';
        }
        if (market === 'US') {
            if (t >= 1290 || t < 240) return '交易中';
            return '已收盘';
        }
        if (market === 'HK') {
            if (t >= 570 && t < 720) return '交易中';
            if (t >= 720 && t < 780) return '午休';
            if (t >= 780 && t < 960) return '交易中';
            return '已收盘';
        }
        return '--';
    },
};

document.addEventListener('DOMContentLoaded', () => Watch.init());
