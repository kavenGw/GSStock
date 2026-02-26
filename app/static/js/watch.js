const Watch = {
    countdownTimers: {},
    countdowns: {},
    REFRESH_INTERVAL: 60,
    searchDebounce: null,
    stocks: [],
    prices: [],
    marketStatus: {},
    analyses: {},
    _analysisTimer: null,
    ANALYSIS_INTERVAL: 30 * 60,
    analysisCountdown: 0,
    chartInstances: {},
    chartPeriods: {},

    async init() {
        await this.loadList();
        await this.loadAnalysis();
        this.startAnalysisCountdown();
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

            this.renderGroups();
            this.updateStatus(`${this.stocks.length} 只股票`);
            this.startAllCountdowns();
        } catch (e) {
            console.error('[Watch] loadList failed:', e);
            this.updateStatus('加载失败');
        }
    },

    async refreshPrices() {
        try {
            const [priceResp, marketResp] = await Promise.all([
                fetch('/watch/prices'),
                fetch('/watch/market-status'),
            ]);
            const priceData = await priceResp.json();
            const marketData = await marketResp.json();
            if (!priceData.success) return;

            this.prices = priceData.prices || [];
            this.marketStatus = marketData.data || {};
            this.updatePrices();
            this.updateMarketHeaders();
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
                await this.refreshPrices();
                await this.loadAnalysis();
                this.resetAnalysisCountdown();
            }
        } catch (e) {
            console.error('[Watch] triggerAnalysis failed:', e);
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
                this.stocks = this.stocks.filter(s => s.stock_code !== code);
                this.prices = this.prices.filter(p => p.code !== code);
                if (this.stocks.length === 0) {
                    this.showEmpty();
                } else {
                    this.renderGroups();
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

    async loadAnalysis() {
        try {
            const resp = await fetch('/watch/analysis');
            const data = await resp.json();
            if (!data.success) return;
            this.analyses = data.data || {};
            this.renderAnalysisPanel();
        } catch (e) {
            console.error('[Watch] loadAnalysis failed:', e);
        }
    },

    renderAnalysisPanel() {
        const panel = document.getElementById('analysisPanel');
        const cardsEl = document.getElementById('analysisCards');
        const summaryEl = document.getElementById('analysisSummary');
        const summaryContent = document.getElementById('summaryContent');
        const timeEl = document.getElementById('analysisTime');

        const codes = Object.keys(this.analyses);
        if (codes.length === 0) {
            panel.classList.add('d-none');
            return;
        }

        panel.classList.remove('d-none');
        timeEl.textContent = `更新于 ${new Date().toLocaleTimeString('zh-CN', {hour: '2-digit', minute: '2-digit'})}`;

        const pricesMap = {};
        this.prices.forEach(p => { pricesMap[p.code] = p; });

        let cardsHtml = '';
        const summaries = [];

        this.stocks.forEach(stock => {
            const code = stock.stock_code;
            const a = this.analyses[code];
            if (!a) return;

            const name = stock.stock_name || code;
            const p = pricesMap[code] || {};
            const supports = a.support_levels || [];
            const resistances = a.resistance_levels || [];
            const threshold = a.volatility_threshold || 0.02;
            const summary = a.summary || '';

            if (summary) summaries.push(`${name}: ${summary}`);

            const currentPrice = p.price;
            let proximityHtml = '';
            if (currentPrice && supports.length > 0) {
                const nearest = supports.reduce((a, b) => Math.abs(b - currentPrice) < Math.abs(a - currentPrice) ? b : a);
                const dist = ((currentPrice - nearest) / nearest * 100).toFixed(1);
                proximityHtml += `<span class="text-success small">距支撑 ${nearest}: ${dist}%</span> `;
            }
            if (currentPrice && resistances.length > 0) {
                const nearest = resistances.reduce((a, b) => Math.abs(b - currentPrice) < Math.abs(a - currentPrice) ? b : a);
                const dist = ((currentPrice - nearest) / nearest * 100).toFixed(1);
                proximityHtml += `<span class="text-danger small">距阻力 ${nearest}: ${dist}%</span>`;
            }

            cardsHtml += `<div class="card mb-2">
            <div class="card-body py-2 px-3">
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <strong class="small">${name}</strong>
                    <span class="text-muted small">${code}</span>
                </div>
                <div class="small mb-1">
                    ${supports.length > 0 ? `<span class="text-success">支撑: ${supports.join(' / ')}</span>` : ''}
                    ${supports.length > 0 && resistances.length > 0 ? '<span class="text-muted mx-1">|</span>' : ''}
                    ${resistances.length > 0 ? `<span class="text-danger">阻力: ${resistances.join(' / ')}</span>` : ''}
                </div>
                ${proximityHtml ? `<div class="mb-1">${proximityHtml}</div>` : ''}
                <div class="d-flex justify-content-between small text-muted">
                    <span>阈值: ${(threshold * 100).toFixed(1)}%</span>
                </div>
                ${summary ? `<div class="small text-muted mt-1 fst-italic">${summary}</div>` : ''}
            </div>
        </div>`;
        });

        cardsEl.innerHTML = cardsHtml || '<p class="text-muted small">暂无分析数据，点击 AI 分析开始</p>';

        if (summaries.length > 0) {
            summaryEl.classList.remove('d-none');
            summaryContent.innerHTML = summaries.map(s => `<div>• ${s}</div>`).join('');
        } else {
            summaryEl.classList.add('d-none');
        }
    },

    // --- 渲染 ---

    renderGroups() {
        Object.values(this.chartInstances).forEach(chart => chart.dispose());
        this.chartInstances = {};

        const pricesMap = {};
        this.prices.forEach(p => { pricesMap[p.code] = p; });

        // 动态收集市场，按优先级排序
        const priority = ['A', 'US', 'HK', 'KR', 'TW', 'JP'];
        const groups = {};
        this.stocks.forEach(stock => {
            const market = stock.market || 'A';
            if (!groups[market]) groups[market] = [];
            groups[market].push(stock);
        });
        const marketOrder = [...priority.filter(m => groups[m]), ...Object.keys(groups).filter(m => !priority.includes(m))];

        const container = document.getElementById('watchGroups');
        let html = '';

        marketOrder.forEach(market => {
            const stocks = groups[market];
            if (!stocks || stocks.length === 0) return;

            const ms = this.marketStatus[market] || {};
            const statusIcon = this.getStatusIcon(ms.status);
            const isTrading = ms.status === 'trading';
            const isLunch = ms.status === 'lunch';

            let countdownHtml = '';
            if (isTrading) {
                countdownHtml = `<span class="badge bg-secondary bg-opacity-50 text-light" data-market-countdown="${market}" title="下次刷新">--s</span>`;
            } else if (isLunch) {
                countdownHtml = `<span class="badge bg-warning bg-opacity-25 text-warning" data-market-countdown="${market}" title="距下午开盘">⏳ --:-- 后开盘</span>`;
            }

            html += `<div class="mb-4" data-market-group="${market}">
                <div class="d-flex align-items-center mb-2 pb-2 border-bottom">
                    <span class="me-2">${ms.icon || ''}</span>
                    <strong class="me-2">${ms.name || market}</strong>
                    <span class="text-muted small me-2" data-market-time="${market}">${ms.time || '--:--'}</span>
                    <span class="badge ${this.getStatusBadgeClass(ms.status)} me-2">${statusIcon} ${ms.status_text || '--'}</span>
                    ${countdownHtml}
                </div>
                <div class="list-group">
                    ${stocks.map(stock => this.renderStockRow(stock, pricesMap[stock.stock_code] || {})).join('')}
                </div>
            </div>`;
        });

        container.innerHTML = html;
        document.getElementById('loadingState').classList.add('d-none');
        document.getElementById('emptyState').classList.add('d-none');
        container.classList.remove('d-none');
    },

    renderStockRow(stock, price) {
        const code = stock.stock_code;
        const name = stock.stock_name || code;
        const market = stock.market || 'A';

        const currentPrice = price.price ?? null;
        const changePct = price.change_pct ?? null;
        const changeAmt = price.change ?? null;
        const notification = price.notification || {};

        const priceDisplay = currentPrice !== null ? this.formatPrice(currentPrice, market) : '--';
        const pctClass = changePct > 0 ? 'text-danger' : changePct < 0 ? 'text-success' : 'text-muted';
        const pctSign = changePct > 0 ? '+' : '';
        const pctDisplay = changePct !== null ? `${pctSign}${changePct.toFixed(2)}%` : '--';
        const amtSign = changeAmt > 0 ? '+' : '';
        const amtDisplay = changeAmt !== null ? `${amtSign}${changeAmt.toFixed(2)}` : '';

        const supports = notification.support_levels || [];
        const resistances = notification.resistance_levels || [];
        const levelsHtml = this.renderLevels(supports, resistances);

        const threshold = notification.threshold || 0.02;
        const cooldown = notification.cooldown_remaining || 0;
        const thresholdText = `阈值 ${(threshold * 100).toFixed(1)}%`;
        const cooldownText = cooldown > 0
            ? `<span class="text-warning">冷却中 剩${Math.ceil(cooldown / 60)}分</span>`
            : '<span class="text-success">就绪</span>';

        return `<div class="list-group-item" id="watch-row-${code}">
            <div class="d-flex justify-content-between align-items-start">
                <div class="flex-grow-1" style="cursor:pointer" onclick="Watch.toggleChart('${code}')">
                    <div class="d-flex align-items-center mb-1">
                        <i class="bi bi-chevron-right small text-muted me-1 chart-toggle-icon" id="chart-icon-${code}"></i>
                        <span class="fw-bold me-2">${name}</span>
                        <small class="text-muted me-3">${code}</small>
                        <span class="fs-5 fw-bold me-2" data-field="price" data-code="${code}">${priceDisplay}</span>
                        <span class="${pctClass} fw-bold me-1" data-field="change_pct" data-code="${code}">${pctDisplay}</span>
                        <span class="${pctClass} small" data-field="change" data-code="${code}">${amtDisplay}</span>
                    </div>
                    <div class="d-flex align-items-center small" data-field="extra" data-code="${code}">
                        ${levelsHtml}
                        <span class="text-muted mx-1">|</span>
                        <span class="text-muted me-1">${thresholdText}</span>
                        <span class="text-muted mx-1">|</span>
                        ${cooldownText}
                    </div>
                </div>
                <button class="btn btn-sm btn-link text-muted p-0 ms-2" onclick="event.stopPropagation(); Watch.removeStock('${code}')" title="移除">
                    <i class="bi bi-x-lg"></i>
                </button>
            </div>
            <div class="chart-section mt-2 d-none" id="chart-section-${code}">
                <div class="d-flex align-items-center mb-1">
                    <div class="btn-group btn-group-sm" role="group">
                        <button type="button" class="btn btn-outline-secondary btn-xs active" onclick="event.stopPropagation(); Watch.switchChartPeriod('${code}', 'intraday', this)">分时</button>
                        <button type="button" class="btn btn-outline-secondary btn-xs" onclick="event.stopPropagation(); Watch.switchChartPeriod('${code}', '7d', this)">7天</button>
                        <button type="button" class="btn btn-outline-secondary btn-xs" onclick="event.stopPropagation(); Watch.switchChartPeriod('${code}', '30d', this)">30天</button>
                        <button type="button" class="btn btn-outline-secondary btn-xs" onclick="event.stopPropagation(); Watch.switchChartPeriod('${code}', '90d', this)">90天</button>
                    </div>
                </div>
                <div class="chart-container" id="chart-${code}" style="height: 160px;">
                    <div class="skeleton skeleton-card" style="height:100%;"></div>
                </div>
            </div>
        </div>`;
    },

    renderLevels(supports, resistances) {
        if (supports.length === 0 && resistances.length === 0) {
            return '<span class="text-muted">暂无点位</span>';
        }
        let parts = [];
        if (supports.length > 0) {
            parts.push(`<span class="text-success">支撑: ${supports.join(' / ')}</span>`);
        }
        if (resistances.length > 0) {
            parts.push(`<span class="text-danger">阻力: ${resistances.join(' / ')}</span>`);
        }
        return parts.join('<span class="text-muted mx-1">|</span>');
    },

    toggleChart(code) {
        const section = document.getElementById(`chart-section-${code}`);
        const icon = document.getElementById(`chart-icon-${code}`);
        if (!section) return;

        const isHidden = section.classList.contains('d-none');
        if (isHidden) {
            section.classList.remove('d-none');
            if (icon) icon.classList.replace('bi-chevron-right', 'bi-chevron-down');
            if (!this.chartInstances[code]) {
                this.loadChartData(code, 'intraday');
            }
        } else {
            section.classList.add('d-none');
            if (icon) icon.classList.replace('bi-chevron-down', 'bi-chevron-right');
        }
    },

    async loadChartData(code, period) {
        const container = document.getElementById(`chart-${code}`);
        if (!container) return;

        container.innerHTML = '<div class="skeleton skeleton-card" style="height:100%;"></div>';

        try {
            const resp = await fetch(`/watch/chart-data?code=${encodeURIComponent(code)}&period=${period}`);
            const result = await resp.json();
            if (!result.success || !result.data?.length) {
                container.innerHTML = '<div class="text-muted text-center small py-4">暂无数据</div>';
                return;
            }
            this.chartPeriods[code] = period;
            this.renderChart(code, result);
        } catch (e) {
            console.error(`[Watch] chart load failed for ${code}:`, e);
            container.innerHTML = '<div class="text-muted text-center small py-4">加载失败</div>';
        }
    },

    switchChartPeriod(code, period, btn) {
        const group = btn.parentElement;
        group.querySelectorAll('.btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        this.loadChartData(code, period);
    },

    renderChart(code, result) {
        const container = document.getElementById(`chart-${code}`);
        container.innerHTML = '';

        if (this.chartInstances[code]) {
            this.chartInstances[code].dispose();
        }

        const chart = echarts.init(container);
        this.chartInstances[code] = chart;

        const option = result.chart_type === 'line'
            ? this.buildIntradayOption(result)
            : this.buildCandlestickOption(result);

        chart.setOption(option);
        new ResizeObserver(() => chart.resize()).observe(container);
    },

    buildIntradayOption(result) {
        const data = result.data;
        const times = data.map(d => d.time);
        const prices = data.map(d => d.close);
        const support = result.support_levels || [];
        const resistance = result.resistance_levels || [];

        const markLines = [];
        support.forEach(level => {
            markLines.push({
                yAxis: level,
                lineStyle: { color: '#28a745', type: 'dashed', width: 1 },
                label: { formatter: String(level), position: 'end', fontSize: 9, color: '#28a745' },
            });
        });
        resistance.forEach(level => {
            markLines.push({
                yAxis: level,
                lineStyle: { color: '#dc3545', type: 'dashed', width: 1 },
                label: { formatter: String(level), position: 'end', fontSize: 9, color: '#dc3545' },
            });
        });

        return {
            grid: { left: 8, right: 55, top: 8, bottom: 20, containLabel: false },
            tooltip: {
                trigger: 'axis',
                formatter: params => {
                    const p = params[0];
                    return `${p.axisValue}<br/>${p.value.toFixed(2)}`;
                },
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
        };
    },

    buildCandlestickOption(result) {
        const data = result.data;
        const bollinger = result.bollinger || [];
        const support = result.support_levels || [];
        const resistance = result.resistance_levels || [];

        const dates = data.map(d => d.date);
        const ohlc = data.map(d => [d.open, d.close, d.low, d.high]);

        const markLines = [];
        support.forEach(level => {
            markLines.push({
                yAxis: level,
                lineStyle: { color: '#28a745', type: 'dashed', width: 1 },
                label: { formatter: String(level), position: 'end', fontSize: 9, color: '#28a745' },
            });
        });
        resistance.forEach(level => {
            markLines.push({
                yAxis: level,
                lineStyle: { color: '#dc3545', type: 'dashed', width: 1 },
                label: { formatter: String(level), position: 'end', fontSize: 9, color: '#dc3545' },
            });
        });

        const series = [
            {
                type: 'candlestick',
                data: ohlc,
                itemStyle: {
                    color: '#ef5350',
                    color0: '#26a69a',
                    borderColor: '#ef5350',
                    borderColor0: '#26a69a',
                },
                markLine: markLines.length > 0 ? { silent: true, symbol: 'none', data: markLines } : undefined,
            },
        ];

        const bbUpper = bollinger.map(b => b ? b.upper : null);
        const bbMiddle = bollinger.map(b => b ? b.middle : null);
        const bbLower = bollinger.map(b => b ? b.lower : null);

        if (bollinger.some(b => b !== null)) {
            series.push(
                { type: 'line', data: bbUpper, smooth: true, symbol: 'none', lineStyle: { width: 1, color: 'rgba(150,150,150,0.5)', type: 'dotted' }, z: 0 },
                { type: 'line', data: bbMiddle, smooth: true, symbol: 'none', lineStyle: { width: 1, color: 'rgba(150,150,150,0.7)' }, z: 0 },
                { type: 'line', data: bbLower, smooth: true, symbol: 'none', lineStyle: { width: 1, color: 'rgba(150,150,150,0.5)', type: 'dotted' }, z: 0 },
            );
        }

        return {
            grid: { left: 8, right: 55, top: 8, bottom: 20, containLabel: false },
            tooltip: {
                trigger: 'axis',
                formatter: params => {
                    const candle = params.find(p => p.seriesType === 'candlestick');
                    if (!candle) return '';
                    const [open, close, low, high] = candle.value;
                    return `${candle.axisValue}<br/>开:${open} 高:${high}<br/>低:${low} 收:${close}`;
                },
            },
            xAxis: {
                type: 'category',
                data: dates,
                axisLabel: { fontSize: 9, interval: Math.floor(dates.length / 4) },
                axisLine: { lineStyle: { color: '#ddd' } },
            },
            yAxis: {
                type: 'value',
                scale: true,
                splitLine: { lineStyle: { color: '#f0f0f0' } },
                axisLabel: { fontSize: 9 },
            },
            series,
        };
    },

    // --- 实时更新 ---

    updatePrices() {
        const pricesMap = {};
        this.prices.forEach(p => { pricesMap[p.code] = p; });

        this.stocks.forEach(stock => {
            const code = stock.stock_code;
            const market = stock.market || 'A';
            const p = pricesMap[code];
            if (!p) return;

            const notification = p.notification || {};

            const priceEl = document.querySelector(`[data-field="price"][data-code="${code}"]`);
            if (priceEl && p.price != null) priceEl.textContent = this.formatPrice(p.price, market);

            const pctClass = p.change_pct > 0 ? 'text-danger' : p.change_pct < 0 ? 'text-success' : 'text-muted';
            const pctSign = p.change_pct > 0 ? '+' : '';
            const pctEl = document.querySelector(`[data-field="change_pct"][data-code="${code}"]`);
            if (pctEl && p.change_pct != null) {
                pctEl.textContent = `${pctSign}${p.change_pct.toFixed(2)}%`;
                pctEl.className = `${pctClass} fw-bold me-1`;
            }
            const amtEl = document.querySelector(`[data-field="change"][data-code="${code}"]`);
            if (amtEl && p.change != null) {
                const amtSign = p.change > 0 ? '+' : '';
                amtEl.textContent = `${amtSign}${p.change.toFixed(2)}`;
                amtEl.className = `${pctClass} small`;
            }

            const extraEl = document.querySelector(`[data-field="extra"][data-code="${code}"]`);
            if (extraEl) {
                const supports = notification.support_levels || [];
                const resistances = notification.resistance_levels || [];
                const threshold = notification.threshold || 0.02;
                const cooldown = notification.cooldown_remaining || 0;
                const thresholdText = `阈值 ${(threshold * 100).toFixed(1)}%`;
                const cooldownText = cooldown > 0
                    ? `<span class="text-warning">冷却中 剩${Math.ceil(cooldown / 60)}分</span>`
                    : '<span class="text-success">就绪</span>';

                extraEl.innerHTML = `${this.renderLevels(supports, resistances)}
                    <span class="text-muted mx-1">|</span>
                    <span class="text-muted me-1">${thresholdText}</span>
                    <span class="text-muted mx-1">|</span>
                    ${cooldownText}`;
            }
        });
    },

    updateMarketHeaders() {
        Object.keys(this.marketStatus).forEach(market => {
            const ms = this.marketStatus[market];
            const group = document.querySelector(`[data-market-group="${market}"]`);
            if (!group) return;

            const timeEl = group.querySelector(`[data-market-time="${market}"]`);
            if (timeEl) timeEl.textContent = ms.time || '--:--';

            const badge = group.querySelector('.badge:not([data-market-countdown])');
            if (badge) {
                badge.className = `badge ${this.getStatusBadgeClass(ms.status)} me-2`;
                badge.innerHTML = `${this.getStatusIcon(ms.status)} ${ms.status_text || '--'}`;
            }

            const isTrading = ms.status === 'trading';
            const isLunch = ms.status === 'lunch';
            const cdEl = group.querySelector(`[data-market-countdown="${market}"]`);

            if (isTrading && !this.countdownTimers[market]) {
                if (!cdEl) {
                    badge?.insertAdjacentHTML('afterend',
                        `<span class="badge bg-secondary bg-opacity-50 text-light" data-market-countdown="${market}" title="下次刷新">--s</span>`);
                }
                this.startCountdown(market);
            } else if (isLunch && !this.countdownTimers[market]) {
                const secs = ms.seconds_to_open;
                if (!cdEl) {
                    badge?.insertAdjacentHTML('afterend',
                        `<span class="badge bg-warning bg-opacity-25 text-warning" data-market-countdown="${market}" title="距下午开盘">⏳ --:-- 后开盘</span>`);
                }
                if (secs > 0) this.startLunchCountdown(market, secs);
            } else if (!isTrading && !isLunch && cdEl) {
                cdEl.remove();
                this.stopCountdown(market);
            }
        });
    },

    // --- 每市场独立倒计时 ---

    startAllCountdowns() {
        this.stopAllCountdowns();
        this.getActiveMarkets().forEach(market => this.startCountdown(market));
        this.getLunchMarkets().forEach(market => {
            const secs = this.marketStatus[market]?.seconds_to_open;
            if (secs > 0) this.startLunchCountdown(market, secs);
        });
    },

    startCountdown(market) {
        this.stopCountdown(market);
        this.countdowns[market] = this.REFRESH_INTERVAL;
        this.updateCountdownDisplay(market);

        this.countdownTimers[market] = setInterval(() => {
            this.countdowns[market]--;
            if (this.countdowns[market] <= 0) {
                this.countdowns[market] = this.REFRESH_INTERVAL;
                this.refreshPrices();
            }
            this.updateCountdownDisplay(market);
        }, 1000);
    },

    startLunchCountdown(market, seconds) {
        this.stopCountdown(market);
        this.countdowns[market] = seconds;
        this.updateCountdownDisplay(market);

        this.countdownTimers[market] = setInterval(() => {
            this.countdowns[market]--;
            if (this.countdowns[market] <= 0) {
                this.stopCountdown(market);
                this.loadList();
                return;
            }
            this.updateCountdownDisplay(market);
        }, 1000);
    },

    stopCountdown(market) {
        if (this.countdownTimers[market]) {
            clearInterval(this.countdownTimers[market]);
            delete this.countdownTimers[market];
        }
    },

    stopAllCountdowns() {
        Object.keys(this.countdownTimers).forEach(m => this.stopCountdown(m));
    },

    // --- AI 分析定时 ---

    startAnalysisCountdown() {
        this.analysisCountdown = this.ANALYSIS_INTERVAL;
        if (this._analysisTimer) clearInterval(this._analysisTimer);
        this._analysisTimer = setInterval(() => {
            this.analysisCountdown--;
            this.updateAnalysisCountdownDisplay();
            if (this.analysisCountdown <= 0) {
                if (this.getActiveMarkets().length > 0) {
                    this.triggerAnalysis(true);
                }
                this.analysisCountdown = this.ANALYSIS_INTERVAL;
            }
        }, 1000);
        this.updateAnalysisCountdownDisplay();
    },

    resetAnalysisCountdown() {
        this.analysisCountdown = this.ANALYSIS_INTERVAL;
        this.updateAnalysisCountdownDisplay();
    },

    updateAnalysisCountdownDisplay() {
        const el = document.getElementById('analysisCountdown');
        if (!el) return;
        const m = Math.floor(this.analysisCountdown / 60);
        const s = this.analysisCountdown % 60;
        el.textContent = `下次分析 ${m}:${String(s).padStart(2, '0')}`;
    },

    updateCountdownDisplay(market) {
        const el = document.querySelector(`[data-market-countdown="${market}"]`);
        if (!el) return;
        const secs = this.countdowns[market];
        const isLunch = this.marketStatus[market]?.status === 'lunch';
        if (isLunch) {
            const m = Math.floor(secs / 60);
            const s = secs % 60;
            el.textContent = `⏳ ${m}:${String(s).padStart(2, '0')} 后开盘`;
        } else {
            el.textContent = `${secs}s`;
        }
    },

    getActiveMarkets() {
        return Object.keys(this.marketStatus).filter(m => {
            return this.marketStatus[m]?.status === 'trading';
        });
    },

    getLunchMarkets() {
        return Object.keys(this.marketStatus).filter(m => {
            return this.marketStatus[m]?.status === 'lunch';
        });
    },

    // --- 工具函数 ---

    showEmpty() {
        document.getElementById('loadingState').classList.add('d-none');
        document.getElementById('watchGroups').classList.add('d-none');
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
