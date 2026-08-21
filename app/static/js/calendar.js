const CalendarPage = {
    data: { events: [], staleHours: null },
    config: { enabledTypes: new Set(['earnings', 'ex_dividend', 'macro', 'manual']) },

    TYPE_LABEL: {
        earnings: '财报',
        ex_dividend: '除权',
        macro: '宏观',
        manual: '手工',
    },

    init() {
        this.loadConfig();
        this.bindEvents();
        this.fetchData();
    },

    loadConfig() {
        try {
            const saved = JSON.parse(localStorage.getItem('calendarPageConfig'));
            if (saved && Array.isArray(saved.enabledTypes)) {
                this.config.enabledTypes = new Set(saved.enabledTypes);
            }
        } catch (e) { /* ignore */ }
        this.syncChips();
    },

    saveConfig() {
        localStorage.setItem('calendarPageConfig', JSON.stringify({
            enabledTypes: [...this.config.enabledTypes],
        }));
    },

    syncChips() {
        document.querySelectorAll('#calTypeFilter .cal-chip').forEach(btn => {
            btn.classList.toggle('is-on', this.config.enabledTypes.has(btn.dataset.type));
        });
    },

    bindEvents() {
        document.getElementById('calTypeFilter').addEventListener('click', e => {
            const btn = e.target.closest('.cal-chip');
            if (!btn) return;
            const t = btn.dataset.type;
            if (this.config.enabledTypes.has(t)) {
                this.config.enabledTypes.delete(t);
            } else {
                this.config.enabledTypes.add(t);
            }
            this.saveConfig();
            this.syncChips();
            this.render();
        });

        document.getElementById('calRefreshBtn').addEventListener('click', () => {
            fetch('/calendar/api/refresh', { method: 'POST' })
                .then(r => r.json())
                .then(d => { alert(d.message); });
        });

        document.getElementById('calDrawerClose').addEventListener('click', () => {
            document.getElementById('calDrawer').classList.remove('is-open');
        });

        document.getElementById('calContainer').addEventListener('click', e => {
            const cell = e.target.closest('.cal-cell[data-date]');
            if (cell) this.openDrawer(cell.dataset.date);
        });

        // 抽屉内的个股条目跳转到全站统一的股票详情抽屉组件（StockDetailDrawer），
        // 而不是 /stocks/<code> —— 该路由不存在，见任务裁决。
        document.getElementById('calDrawerBody').addEventListener('click', e => {
            const link = e.target.closest('.cal-stock-link');
            if (!link) return;
            if (typeof StockDetailDrawer !== 'undefined') {
                StockDetailDrawer.open(link.dataset.code, link.dataset.name);
            }
        });
    },

    fetchData() {
        fetch('/calendar/api/events')
            .then(r => r.json())
            .then(d => {
                this.data.events = d.events || [];
                this.data.staleHours = d.stale_hours;
                this.render();
            })
            .catch(() => {
                document.getElementById('calStaleInfo').textContent = '事件数据加载失败';
            });
    },

    visibleEvents() {
        return this.data.events.filter(e => this.config.enabledTypes.has(e.event_type));
    },

    groupByDate() {
        const map = {};
        this.visibleEvents().forEach(e => {
            (map[e.event_date] = map[e.event_date] || []).push(e);
        });
        return map;
    },

    render() {
        const byDate = this.groupByDate();
        const container = document.getElementById('calContainer');
        container.innerHTML = INITIAL_MONTHS
            .map(m => this.renderMonth(m, byDate)).join('');

        document.getElementById('calLoading').classList.add('d-none');
        container.classList.remove('d-none');
        this.renderStaleInfo();
    },

    renderStaleInfo() {
        const el = document.getElementById('calStaleInfo');
        const h = this.data.staleHours;
        if (h === null || h === undefined) {
            el.textContent = '暂无事件数据，请点击「刷新数据」';
            return;
        }
        el.textContent = h >= 24
            ? `⚠️ 事件数据 ${Math.floor(h)} 小时未更新`
            : `事件数据 ${Math.floor(h)} 小时前更新`;
    },

    renderMonth(m, byDate) {
        const first = new Date(m.year, m.month - 1, 1);
        const daysInMonth = new Date(m.year, m.month, 0).getDate();
        // 周一起始：JS getDay() 周日=0，转成周一=0
        const lead = (first.getDay() + 6) % 7;
        const todayIso = new Date().toLocaleDateString('sv-SE');

        const cells = [];
        for (let i = 0; i < lead; i++) {
            cells.push('<div class="cal-cell is-blank"></div>');
        }
        for (let d = 1; d <= daysInMonth; d++) {
            const iso = `${m.year}-${String(m.month).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
            const evts = byDate[iso] || [];
            cells.push(`
                <div class="cal-cell${iso === todayIso ? ' is-today' : ''}" data-date="${iso}">
                    <div class="cal-daynum">${d}</div>
                    <div class="cal-chips">${this.renderChips(evts)}</div>
                </div>`);
        }

        const heads = ['一', '二', '三', '四', '五', '六', '日']
            .map(w => `<div class="cal-weekhead">${w}</div>`).join('');

        return `
            <div class="cal-month">
                <div class="cal-month-title">${m.label}</div>
                <div class="cal-days">${heads}${cells.join('')}</div>
            </div>`;
    },

    renderChips(evts) {
        const shown = evts.slice(0, 3).map(e => {
            const label = e.stock_name
                ? `${e.stock_name.slice(0, 4)} ${this.TYPE_LABEL[e.event_type] || ''}`
                : e.title;
            const hi = e.priority === 'HIGH' ? ' is-high' : '';
            const tip = this.escape(`${e.title}${e.detail ? ' · ' + e.detail : ''}`);
            return `<span class="cal-ev type-${e.event_type}${hi}" title="${tip}">${this.escape(label)}</span>`;
        }).join('');
        const more = evts.length > 3
            ? `<span class="cal-ev is-more">+${evts.length - 3}</span>` : '';
        return shown + more;
    },

    openDrawer(iso) {
        const evts = this.groupByDate()[iso] || [];
        document.getElementById('calDrawerTitle').textContent = iso;
        document.getElementById('calDrawerBody').innerHTML = evts.length
            ? evts.map(e => `
                <div class="cal-drawer-item type-${e.event_type}">
                    <div class="cal-drawer-item-head">
                        ${e.stock_code
                            ? `<button type="button" class="cal-stock-link" data-code="${this.escape(e.stock_code)}" data-name="${this.escape(e.stock_name || e.stock_code)}">${this.escape(e.stock_name || e.stock_code)} (${this.escape(e.stock_code)})</button>`
                            : this.escape(e.title)}
                    </div>
                    <div class="cal-drawer-item-body">
                        ${this.escape(e.title)}${e.detail ? ' · ' + this.escape(e.detail) : ''}
                    </div>
                </div>`).join('')
            : '<div class="text-muted">当日无事件</div>';
        document.getElementById('calDrawer').classList.add('is-open');
    },

    escape(s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g,
            c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
    },
};

document.addEventListener('DOMContentLoaded', () => CalendarPage.init());
