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

    function cell(text, className = '') {
        const element = document.createElement('td');
        element.textContent = text;
        element.className = className;
        return element;
    }

    function sortValue(row) {
        return sort.endsWith('_qoq') ? row[sort].value : row[sort];
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
        descending = button.dataset.sort === sort ? !descending : true;
        sort = button.dataset.sort;
        render();
    }));
    render();
})();
