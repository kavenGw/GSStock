(function() {
    let stocks = [];
    let currentPeriod = '30d';

    document.addEventListener('DOMContentLoaded', () => {
        loadStocks();
        document.getElementById('period-toggle').addEventListener('click', e => {
            const btn = e.target.closest('[data-period]');
            if (!btn) return;
            currentPeriod = btn.dataset.period;
            document.querySelectorAll('#period-toggle .btn').forEach(b => {
                b.classList.toggle('btn-primary', b.dataset.period === currentPeriod);
                b.classList.toggle('btn-outline-primary', b.dataset.period !== currentPeriod);
            });
            render();
        });
    });

    async function loadStocks() {
        try {
            const resp = await fetch('/value-dip/api/stocks');
            const data = await resp.json();
            stocks = data.stocks || [];
            render();
        } catch (e) {
            console.error('加载盯盘股数据失败:', e);
        }
    }

    function fmtChange(v) {
        if (v === null || v === undefined) return '<span class="text-muted">N/A</span>';
        const cls = v >= 0 ? 'text-success' : 'text-danger';
        return `<span class="${cls}">${v >= 0 ? '+' : ''}${v}%</span>`;
    }

    function fmtPullback(v) {
        if (v === null || v === undefined) return '<span class="text-muted">N/A</span>';
        const cls = v < -10 ? 'text-danger fw-bold' : v < -5 ? 'text-danger' : 'text-muted';
        return `<span class="${cls}">${v}%</span>`;
    }

    function esc(s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[c]));
    }

    function render() {
        const tbody = document.getElementById('stock-body');
        const th = document.getElementById('pullback-th');
        const days = { '7d': 7, '30d': 30, '90d': 90 }[currentPeriod];
        if (th) th.textContent = `${days}日高点回退`;

        const pbKey = 'pullback_' + currentPeriod;
        const sorted = [...stocks].sort((a, b) => {
            const av = a[pbKey], bv = b[pbKey];
            if (av === null || av === undefined) return 1;
            if (bv === null || bv === undefined) return -1;
            return av - bv;
        });

        if (!sorted.length) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-3">暂无数据</td></tr>';
            return;
        }

        tbody.innerHTML = sorted.map(s => `
            <tr>
                <td>${esc(s.name)}<span class="text-muted small ms-1">${esc(s.code)}</span></td>
                <td>${esc(s.market || '')}</td>
                <td class="text-end">${s.price == null ? '—' : s.price}</td>
                <td class="text-end">${fmtChange(s.change_7d)}</td>
                <td class="text-end">${fmtChange(s.change_30d)}</td>
                <td class="text-end">${fmtChange(s.change_90d)}</td>
                <td class="text-end">${fmtPullback(s[pbKey])}</td>
            </tr>
        `).join('');
    }
})();
