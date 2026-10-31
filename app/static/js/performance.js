(() => {
    const data = document.getElementById('performanceData');
    if (!data) return;
    const rows = JSON.parse(data.textContent);
    const period = document.getElementById('performancePeriod');
    const search = document.getElementById('performanceSearch');
    const body = document.getElementById('performanceBody');
    const empty = document.getElementById('performanceEmpty');
    const count = document.getElementById('performanceCount');
    const buttons = [...document.querySelectorAll('[data-sort]')];
    const formatter = new Intl.NumberFormat('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2});
    let sort = 'revenue';
    let descending = true;
    let marketCaps = {};
    let marketCapMissing = '市值加载中';
    const marketCapStatus = document.getElementById('performanceMarketCapStatus');

    function cell(text, className = '') {
        const element = document.createElement('td');
        element.textContent = text;
        element.className = className;
        return element;
    }

    function valuation(row) {
        const quote = marketCaps[row.stock_code];
        const cap = quote?.market_cap ?? null;
        const profit = row.adjusted_profit;
        const unavailable = {cap, pe: null, label: '—'};
        if (profit == null) return {...unavailable, title: row.missing_reasons?.adjusted_profit || '未取得扣非数据'};
        if (profit < 0) return {cap, pe: null, label: '亏损', title: '当季扣非亏损，PE 无意义'};
        if (profit === 0) return {...unavailable, title: '当季扣非为零，无法计算 PE'};
        if (cap == null) return {...unavailable, title: marketCapMissing};
        return {cap, pe: cap / (profit * 4), label: null, title: ''};
    }

    function sortValue(row) {
        if (sort === 'market_cap') return valuation(row).cap;
        if (sort === 'adjusted_pe') return valuation(row).pe;
        return sort.endsWith('_qoq') ? row[sort].value : row[sort];
    }

    async function loadMarketCaps() {
        try {
            const response = await fetch(data.dataset.marketCapUrl);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const result = await response.json();
            marketCaps = result.market_caps;
            if (Object.keys(marketCaps).length === 0) throw new Error('无可用市值');
            marketCapMissing = '行情暂不可用';
            marketCapStatus.textContent = result.as_of ? `市值截至 ${result.as_of.slice(5)}` : '市值时间未知';
        } catch (error) {
            console.warn('业绩页市值加载失败', error);
            marketCapMissing = '行情暂不可用';
            marketCapStatus.textContent = '行情暂不可用';
        }
        render();
    }

    function render() {
        const query = search.value.trim().toLowerCase();
        const quarterRows = rows.filter(row => row.period === period.value);
        const filtered = quarterRows.filter(row => `${row.stock_name} ${row.stock_code}`.toLowerCase().includes(query));
        filtered.sort((a, b) => {
            const av = sortValue(a), bv = sortValue(b);
            if (av == null && bv != null) return 1;
            if (bv == null && av != null) return -1;
            return (av == null ? 0 : (av - bv) * (descending ? -1 : 1)) || a.stock_code.localeCompare(b.stock_code);
        });
        body.replaceChildren();
        for (const row of filtered) {
            const tr = document.createElement('tr');
            const company = cell('', 'performance-company');
            const link = document.createElement('a');
            link.href = row.research_url;
            link.textContent = row.stock_name;
            company.append(link);
            const code = document.createElement('small');
            code.textContent = row.stock_code;
            company.append(code);
            tr.append(company);
            const {cap, pe, label, title} = valuation(row);
            const capCell = cell(cap == null ? '—' : formatter.format(cap), 'performance-number');
            const quote = marketCaps[row.stock_code];
            capCell.title = cap == null ? marketCapMissing
                : quote.basis === 'H' ? `H 股现价 × 总股本，按 1 港币 = ${quote.fx} 元折算` : '';
            tr.append(capCell);
            const peCell = cell(pe == null ? label : formatter.format(pe), 'performance-number');
            peCell.title = title;
            tr.append(peCell);
            for (const metric of ['revenue', 'adjusted_profit', 'inventory']) {
                const value = row[metric];
                const amount = cell(value == null ? '—' : formatter.format(value), 'performance-number');
                if (value == null) amount.title = row.missing_reasons?.[metric] || '未取得数据';
                tr.append(amount);
                const change = row[`${metric}_qoq`];
                const percentage = change.value;
                const text = percentage == null ? change.label : `${percentage > 0 ? '+' : ''}${formatter.format(percentage)}%`;
                const growth = cell(text, 'performance-number');
                if (metric !== 'inventory' && percentage != null) {
                    growth.classList.add(percentage > 0 ? 'performance-positive' : percentage < 0 ? 'performance-negative' : 'text-muted');
                }
                if (text === '—') growth.title = '当季数据或上一季度同口径基数缺失';
                tr.append(growth);
            }
            const sources = cell('', 'performance-sources');
            const details = document.createElement('details');
            const summary = document.createElement('summary');
            summary.textContent = '财报来源';
            details.append(summary);
            for (const source of row.sources) {
                const sourceLink = document.createElement('a');
                sourceLink.href = source.url;
                sourceLink.textContent = source.title;
                sourceLink.target = '_blank';
                sourceLink.rel = 'noopener noreferrer';
                const locator = document.createElement('small');
                locator.textContent = source.locator;
                details.append(sourceLink, locator);
            }
            if (row.notes) {
                const notes = document.createElement('small');
                notes.textContent = row.notes;
                details.append(notes);
            }
            const updated = document.createElement('small');
            updated.textContent = `更新于 ${row.updated_at}`;
            details.append(updated);
            sources.append(details);
            tr.append(sources);
            body.append(tr);
        }
        count.textContent = `${period.value || ''} · ${filtered.length} / ${quarterRows.length} 家公司`;
        empty.hidden = filtered.length > 0;
        empty.textContent = quarterRows.length ? '没有匹配的公司。' : '暂无业绩记录，研究完成后会自动收录。';
        for (const button of buttons) {
            const active = button.dataset.sort === sort;
            button.closest('th').setAttribute('aria-sort', active ? descending ? 'descending' : 'ascending' : 'none');
            button.querySelector('.sort-indicator').textContent = active ? descending ? '↓' : '↑' : '↕';
        }
    }

    period.addEventListener('change', render);
    search.addEventListener('input', render);
    buttons.forEach(button => button.addEventListener('click', () => {
        descending = button.dataset.sort === sort ? !descending : button.dataset.sort !== 'adjusted_pe';
        sort = button.dataset.sort;
        render();
    }));
    render();
    loadMarketCaps();
})();
