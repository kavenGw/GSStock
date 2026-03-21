(function() {
    let sectorData = null;
    let currentPeriod = '30d';
    let expandedSector = null;
    let chartInstances = [];
    let compareChart = null;
    let compareVisible = false;

    const SECTOR_COLORS = [
        '#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de',
        '#3ba272', '#fc8452', '#9a60b4', '#ea7ccc', '#5b8ff9'
    ];

    window.addEventListener('resize', () => {
        chartInstances.forEach(c => c.resize());
        if (compareChart) compareChart.resize();
    });

    document.addEventListener('DOMContentLoaded', () => {
        loadSectors();
        document.getElementById('period-toggle').addEventListener('click', e => {
            const btn = e.target.closest('[data-period]');
            if (!btn) return;
            currentPeriod = btn.dataset.period;
            document.querySelectorAll('#period-toggle .btn').forEach(b => {
                b.classList.toggle('btn-primary', b.dataset.period === currentPeriod);
                b.classList.toggle('btn-outline-primary', b.dataset.period !== currentPeriod);
            });
            renderCards();
            if (expandedSector) renderTrend(expandedSector);
            if (compareVisible) renderCompareChart();
        });

        document.getElementById('compare-btn').addEventListener('click', () => {
            compareVisible = !compareVisible;
            const container = document.getElementById('compare-container');
            container.classList.toggle('d-none', !compareVisible);
            if (compareVisible) renderCompareChart();
        });

        document.getElementById('compare-close').addEventListener('click', () => {
            compareVisible = false;
            document.getElementById('compare-container').classList.add('d-none');
        });
    });

    async function loadSectors() {
        try {
            const resp = await fetch('/value-dip/api/sectors');
            sectorData = await resp.json();
            renderCards();
        } catch (e) {
            console.error('加载板块数据失败:', e);
        }
    }

    function renderCards() {
        const container = document.getElementById('sector-cards');
        if (!sectorData || !sectorData.sectors) return;

        const sorted = [...sectorData.sectors].sort((a, b) =>
            (b['change_' + currentPeriod] || 0) - (a['change_' + currentPeriod] || 0)
        );

        container.innerHTML = sorted.map(sector => {
            const change = sector['change_' + currentPeriod];
            const isDip = sector['is_dip_' + currentPeriod];
            const changeStr = change !== null ? (change >= 0 ? '+' : '') + change + '%' : 'N/A';
            const changeColor = isDip ? 'text-danger' : (change >= 0 ? 'text-success' : 'text-danger');
            const borderClass = isDip ? 'border-danger border-2' : '';
            const activeClass = expandedSector === sector.key ? 'bg-primary bg-opacity-10' : '';

            const otherPeriods = ['7d', '30d', '90d'].filter(p => p !== currentPeriod);
            const otherText = otherPeriods.map(p => {
                const v = sector['change_' + p];
                return `${p} ${v !== null ? (v >= 0 ? '+' : '') + v + '%' : 'N/A'}`;
            }).join(' | ');

            return `
                <div class="col">
                    <div class="card h-100 cursor-pointer ${borderClass} ${activeClass}"
                         onclick="window.valueDip.toggleSector('${sector.key}')"
                         style="cursor:pointer">
                        <div class="card-body text-center py-3">
                            <div class="small text-muted">${sector.name}${isDip ? ' ⚠' : ''}</div>
                            <div class="fs-4 fw-bold ${changeColor}">${changeStr}</div>
                            <div class="small text-muted">${otherText}</div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    function toggleSector(key) {
        if (expandedSector === key) {
            expandedSector = null;
            document.getElementById('trend-container').classList.add('d-none');
        } else {
            expandedSector = key;
            renderTrend(key);
        }
        renderCards();
    }

    function renderCompareChart() {
        if (!sectorData || !sectorData.sectors) return;

        const el = document.getElementById('compare-chart');
        if (compareChart) {
            compareChart.dispose();
        }
        compareChart = echarts.init(el);

        // 计算每个板块的平均涨跌幅走势
        const periodDays = { '7d': 7, '30d': 30, '90d': 90 };
        const days = periodDays[currentPeriod] || 30;

        const seriesData = [];
        let maxLen = 0;
        let commonDates = [];

        sectorData.sectors.forEach((sector, idx) => {
            // 收集板块内所有股票的走势数据，计算平均涨跌幅
            const stocksWithData = sector.stocks.filter(s => s.trend_data && s.trend_data.length > 0);
            if (stocksWithData.length === 0) return;

            // 找到最短的数据长度以对齐
            const minLen = Math.min(...stocksWithData.map(s => s.trend_data.length));
            const dataLen = Math.min(minLen, days);

            if (dataLen > maxLen) {
                maxLen = dataLen;
                commonDates = stocksWithData[0].trend_data.slice(-dataLen).map(d => d.date);
            }

            // 计算每天的平均涨跌幅（相对于第一天）
            const avgChanges = [];
            for (let i = 0; i < dataLen; i++) {
                let sumChange = 0;
                let validCount = 0;
                stocksWithData.forEach(stock => {
                    const data = stock.trend_data;
                    const startIdx = data.length - dataLen;
                    if (startIdx >= 0 && data[startIdx].close > 0) {
                        const basePrice = data[startIdx].close;
                        const currentPrice = data[startIdx + i].close;
                        sumChange += (currentPrice - basePrice) / basePrice * 100;
                        validCount++;
                    }
                });
                avgChanges.push(validCount > 0 ? Math.round(sumChange / validCount * 100) / 100 : 0);
            }

            seriesData.push({
                name: sector.name,
                type: 'line',
                data: avgChanges,
                smooth: true,
                symbol: 'none',
                lineStyle: { width: 2, color: SECTOR_COLORS[idx % SECTOR_COLORS.length] },
                itemStyle: { color: SECTOR_COLORS[idx % SECTOR_COLORS.length] }
            });
        });

        // 截取到当前周期对应的天数
        const displayDays = Math.min(days, maxLen);
        const displayDates = commonDates.slice(-displayDays);
        seriesData.forEach(s => {
            s.data = s.data.slice(-displayDays);
        });

        compareChart.setOption({
            tooltip: {
                trigger: 'axis',
                formatter: params => {
                    let tip = params[0].axisValue + '<br/>';
                    params.forEach(p => {
                        const color = p.color;
                        const value = p.value >= 0 ? '+' + p.value : p.value;
                        tip += `<span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:${color};margin-right:5px;"></span>${p.seriesName}: ${value}%<br/>`;
                    });
                    return tip;
                }
            },
            legend: {
                data: seriesData.map(s => s.name),
                bottom: 0
            },
            grid: { left: '8%', right: '5%', top: '10%', bottom: '15%' },
            xAxis: {
                type: 'category',
                data: displayDates,
                axisLabel: { fontSize: 10, rotate: 30 }
            },
            yAxis: {
                type: 'value',
                axisLabel: {
                    fontSize: 10,
                    formatter: v => v + '%'
                },
                splitLine: { lineStyle: { type: 'dashed' } }
            },
            series: seriesData
        });
    }

    function renderTrend(sectorKey) {
        const sector = sectorData.sectors.find(s => s.key === sectorKey);
        if (!sector) return;

        const container = document.getElementById('trend-container');
        const chartsDiv = document.getElementById('trend-charts');
        document.getElementById('trend-title').textContent = sector.name + ' — 个股走势（90天）';
        container.classList.remove('d-none');

        // 销毁旧 chart 实例
        chartInstances.forEach(c => c.dispose());
        chartInstances = [];

        const colClass = sector.stocks.length <= 2 ? 'col-md-6' : 'col-md-4';

        chartsDiv.innerHTML = sector.stocks.map((stock, i) => `
            <div class="${colClass}">
                <div class="card">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-center mb-2">
                            <span class="fw-bold">${stock.name}</span>
                            <span class="small text-muted">${stock.code}</span>
                        </div>
                        <div id="chart-${i}" style="height: 250px;"></div>
                        <div class="small text-muted text-center mt-1">
                            7d ${fmtChange(stock.change_7d)} |
                            30d ${fmtChange(stock.change_30d)} |
                            90d ${fmtChange(stock.change_90d)}
                        </div>
                    </div>
                </div>
            </div>
        `).join('');

        sector.stocks.forEach((stock, i) => {
            const el = document.getElementById('chart-' + i);
            if (!el || !stock.trend_data || !stock.trend_data.length) return;

            const chart = echarts.init(el);
            chartInstances.push(chart);
            const dates = stock.trend_data.map(d => d.date);
            const closes = stock.trend_data.map(d => d.close);

            chart.setOption({
                grid: { left: '10%', right: '5%', top: '10%', bottom: '15%' },
                xAxis: {
                    type: 'category',
                    data: dates,
                    axisLabel: { fontSize: 10, rotate: 30 }
                },
                yAxis: {
                    type: 'value',
                    scale: true,
                    axisLabel: { fontSize: 10 }
                },
                series: [{
                    type: 'line',
                    data: closes,
                    smooth: true,
                    symbol: 'none',
                    lineStyle: { width: 2 },
                    areaStyle: { opacity: 0.1 }
                }],
                tooltip: {
                    trigger: 'axis',
                    formatter: params => {
                        const p = params[0];
                        return `${p.axisValue}<br/>收盘价: ${p.value}`;
                    }
                }
            });
        });
    }

    function fmtChange(v) {
        if (v === null || v === undefined) return 'N/A';
        return (v >= 0 ? '+' : '') + v + '%';
    }

    window.valueDip = { toggleSector };
})();
