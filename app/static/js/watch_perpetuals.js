const WatchPerpetuals = {
    rows: [],

    formatTime(timestamp) {
        return timestamp ? new Date(timestamp).toLocaleString('zh-CN', {
            timeZone: 'Asia/Shanghai', hour12: false,
        }) : '—';
    },

    render(unavailable = false) {
        const body = document.getElementById('perpetualRows');
        body.replaceChildren();
        for (const row of this.rows) {
            const available = !unavailable && row.available &&
                Date.now() / 1000 - row.updated_at <= 180;
            const tr = document.createElement('tr');
            const cells = [
                `${row.name} (${row.source_code}) / ${row.symbol}`,
                `${row.kind} / ${row.price_unit}`,
                available ? row.price.toLocaleString('zh-CN', { maximumFractionDigits: 8 }) : '—',
                available ? `${row.change_pct >= 0 ? '+' : ''}${row.change_pct.toFixed(2)}%` : '—',
                available ? row.mark_price.toLocaleString('zh-CN', { maximumFractionDigits: 8 }) : '—',
                available ? `${row.funding_rate_pct >= 0 ? '+' : ''}${row.funding_rate_pct.toFixed(4)}%` : '—',
                available ? this.formatTime(row.next_funding_time) : '—',
                `${available ? '交易中' : '行情不可用'} / ${this.formatTime(row.updated_at * 1000)}`,
            ];
            cells.forEach((value, index) => {
                const td = document.createElement('td');
                td.textContent = value;
                if (index >= 2 && index <= 5) td.classList.add('text-end');
                if (index === 3 && available) {
                    td.classList.add(row.change_pct > 0 ? 'price-up' : row.change_pct < 0 ? 'price-down' : 'price-flat');
                }
                if (!available) td.classList.add('text-muted');
                tr.appendChild(td);
            });
            body.appendChild(tr);
        }
        if (!this.rows.length) {
            const td = document.createElement('td');
            td.colSpan = 8;
            td.className = 'text-center text-muted';
            td.textContent = unavailable ? '行情不可用' : '暂无已配置的对应合约';
            const tr = document.createElement('tr');
            tr.appendChild(td);
            body.appendChild(tr);
        }
    },

    async refresh() {
        const status = document.getElementById('perpetualStatus');
        try {
            const response = await fetch('/watch/perpetuals', { signal: AbortSignal.timeout(15000) });
            if (!response.ok) throw new Error('request_failed');
            const result = await response.json();
            if (!result.success) throw new Error('invalid_response');
            this.rows = result.data || [];
            this.render();
            status.textContent = result.error || '时间均为北京时间；无法获取新鲜报价的合约暂停异动提醒';
        } catch {
            this.render(true);
            status.textContent = '行情不可用，稍后自动重试';
        }
    },

    init() {
        this.refresh();
        setInterval(() => this.refresh(), 60000);
    },
};

document.addEventListener('DOMContentLoaded', () => WatchPerpetuals.init());
