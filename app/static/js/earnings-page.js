const EarningsPage = {
    data: { categories: [], stocks: [] },
    config: {
        enabledCategories: new Set(),
        activeTab: 'profit',
        sortField: 'pe_dynamic',
        sortOrder: 'asc',
    },

    init() {
        this.loadConfig();
        this.initCategories();
        this.bindEvents();
        this.fetchData();
    },

    loadConfig() {
        try {
            const saved = JSON.parse(localStorage.getItem('earningsPageConfig'));
            if (saved) {
                this.config.enabledCategories = new Set(saved.enabledCategories || []);
                this.config.activeTab = saved.activeTab || 'profit';
            }
        } catch (e) { /* ignore */ }
    },

    saveConfig() {
        localStorage.setItem('earningsPageConfig', JSON.stringify({
            enabledCategories: [...this.config.enabledCategories],
            activeTab: this.config.activeTab,
        }));
    },

    initCategories() {
        const cats = typeof INITIAL_CATEGORIES !== 'undefined' ? INITIAL_CATEGORIES : [];
        this.data.categories = cats;

        if (this.config.enabledCategories.size === 0) {
            cats.forEach(c => {
                if (c.has_position) this.config.enabledCategories.add(c.id);
            });
            this.saveConfig();
        }

        this.renderToggles();
    },

    renderToggles() {
        const container = document.getElementById('categoryToggleFilter');
        if (!container) return;

        container.innerHTML = this.data.categories.map(cat => {
            const isOn = this.config.enabledCategories.has(cat.id);
            return `
                <div class="category-toggle ${isOn ? 'is-on' : ''}" data-id="${cat.id}">
                    <span class="toggle-label">${cat.name} (${cat.count})</span>
                    <label class="toggle-switch">
                        <input type="checkbox" ${isOn ? 'checked' : ''}>
                        <span class="toggle-slider"></span>
                    </label>
                </div>
            `;
        }).join('');

        container.querySelectorAll('.category-toggle input[type="checkbox"]').forEach(cb => {
            cb.addEventListener('change', (e) => {
                const toggle = e.target.closest('.category-toggle');
                const catId = Number(toggle.dataset.id);
                if (e.target.checked) {
                    this.config.enabledCategories.add(catId);
                    toggle.classList.add('is-on');
                } else {
                    this.config.enabledCategories.delete(catId);
                    toggle.classList.remove('is-on');
                }
                this.saveConfig();
                this.fetchData();
            });
        });
    },

    bindEvents() {
        document.getElementById('tabProfit')?.addEventListener('click', () => this.switchTab('profit'));
        document.getElementById('tabRevenue')?.addEventListener('click', () => this.switchTab('revenue'));
        document.getElementById('refreshBtn')?.addEventListener('click', () => this.refresh());
    },

    switchTab(tab) {
        this.config.activeTab = tab;
        this.config.sortField = tab === 'profit' ? 'pe_dynamic' : 'ps_dynamic';
        this.config.sortOrder = 'asc';

        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.getElementById(tab === 'profit' ? 'tabProfit' : 'tabRevenue')?.classList.add('active');

        this.saveConfig();
        this.renderTable();
    },

    async fetchData() {
        const catIds = [...this.config.enabledCategories].join(',');
        const url = `/earnings/api/data?categories=${catIds}&sort=${this.config.sortField}&order=${this.config.sortOrder}`;

        document.getElementById('loadingState')?.classList.remove('d-none');
        document.getElementById('dataContainer')?.classList.add('d-none');
        document.getElementById('emptyState')?.classList.add('d-none');

        try {
            const resp = await fetch(url);
            const data = await resp.json();
            this.data.stocks = data.stocks || [];
            this.data.categories = data.categories || this.data.categories;

            const info = document.getElementById('snapshotInfo');
            if (info) {
                if (data.snapshot_date) {
                    const status = data.is_today ? '' : ' (非今日数据)';
                    info.textContent = `快照日期: ${data.snapshot_date}${status}`;
                } else {
                    info.textContent = '暂无快照数据';
                }
            }

            document.getElementById('loadingState')?.classList.add('d-none');

            if (this.data.stocks.length === 0) {
                document.getElementById('emptyState')?.classList.remove('d-none');
            } else {
                document.getElementById('dataContainer')?.classList.remove('d-none');
                this.renderTable();
            }
        } catch (e) {
            console.error('获取数据失败:', e);
            document.getElementById('loadingState')?.classList.add('d-none');
            document.getElementById('emptyState')?.classList.remove('d-none');
        }
    },

    renderTable() {
        const isProfit = this.config.activeTab === 'profit';
        const stocks = this.sortStocks([...this.data.stocks]);

        const header = document.getElementById('tableHeader');
        const qLabels = stocks.length > 0 ? stocks[0].quarters : ['Q1', 'Q2', 'Q3', 'Q4'];
        const dataLabel = isProfit ? '利润' : '营收';
        const valuationLabel = isProfit ? 'PE动态' : 'PS动态';
        const valuationField = isProfit ? 'pe_dynamic' : 'ps_dynamic';

        header.innerHTML = `
            <th>代码</th>
            <th>名称</th>
            <th class="number" data-sort="market_cap">市值</th>
            ${qLabels.map((q, i) => `<th class="number">${q || 'Q' + (i + 1)}${dataLabel}</th>`).join('')}
            <th class="number sorted" data-sort="${valuationField}">${valuationLabel} <span class="sort-icon">${this.config.sortOrder === 'asc' ? '↑' : '↓'}</span></th>
        `;

        header.querySelectorAll('th[data-sort]').forEach(th => {
            th.addEventListener('click', () => {
                const field = th.dataset.sort;
                if (this.config.sortField === field) {
                    this.config.sortOrder = this.config.sortOrder === 'asc' ? 'desc' : 'asc';
                } else {
                    this.config.sortField = field;
                    this.config.sortOrder = 'asc';
                }
                this.renderTable();
            });
        });

        const body = document.getElementById('tableBody');
        body.innerHTML = stocks.map(s => {
            const values = isProfit ? s.profit : s.revenue;
            const valuation = isProfit ? s.pe_dynamic : s.ps_dynamic;
            return `
                <tr>
                    <td class="stock-code">${s.stock_code}</td>
                    <td class="stock-name">${s.stock_name}</td>
                    <td class="number">${this.formatMarketCap(s.market_cap)}</td>
                    ${values.map(v => `<td class="number">${this.formatAmount(v)}</td>`).join('')}
                    <td class="${valuation != null ? 'valuation' : 'loss'}">${valuation != null ? valuation.toFixed(1) : '亏损'}</td>
                </tr>
            `;
        }).join('');
    },

    sortStocks(stocks) {
        const field = this.config.sortField;
        const asc = this.config.sortOrder === 'asc';
        return stocks.sort((a, b) => {
            const va = a[field], vb = b[field];
            if (va == null && vb == null) return 0;
            if (va == null) return 1;
            if (vb == null) return -1;
            return asc ? va - vb : vb - va;
        });
    },

    formatMarketCap(val) {
        if (val == null) return '-';
        if (val >= 1e12) return (val / 1e12).toFixed(2) + '万亿';
        if (val >= 1e8) return (val / 1e8).toFixed(0) + '亿';
        if (val >= 1e4) return (val / 1e4).toFixed(0) + '万';
        return val.toFixed(0);
    },

    formatAmount(val) {
        if (val == null) return '-';
        if (Math.abs(val) >= 1e8) return (val / 1e8).toFixed(1) + '亿';
        if (Math.abs(val) >= 1e4) return (val / 1e4).toFixed(0) + '万';
        return val.toFixed(0);
    },

    async refresh() {
        try {
            const resp = await fetch('/earnings/api/refresh', { method: 'POST' });
            const data = await resp.json();
            const toast = document.createElement('div');
            toast.className = 'refresh-toast';
            toast.textContent = data.message || '正在刷新...';
            document.body.appendChild(toast);
            setTimeout(() => toast.remove(), 3000);
        } catch (e) {
            console.error('刷新失败:', e);
        }
    },
};

document.addEventListener('DOMContentLoaded', () => EarningsPage.init());
