document.addEventListener('DOMContentLoaded', function() {
    if (!window.chartData || !window.chartData.profit_distribution || window.chartData.profit_distribution.length === 0) {
        return;
    }

    const profitData = window.chartData.profit_distribution;
    const cumulativeData = window.chartData.cumulative_profit;
    const periodFilter = document.getElementById('periodFilter');

    let categoryChart = null;
    let holdingChart = null;
    let trendChart = null;

    // 盈亏分布柱状图
    const profitCtx = document.getElementById('profitChart');
    if (profitCtx) {
        new Chart(profitCtx, {
            type: 'bar',
            data: {
                labels: profitData.map(d => d.stock_name || d.stock_code),
                datasets: [{
                    label: '盈亏金额',
                    data: profitData.map(d => d.profit),
                    backgroundColor: profitData.map(d => d.profit >= 0 ? 'rgba(40, 167, 69, 0.8)' : 'rgba(220, 53, 69, 0.8)'),
                    borderColor: profitData.map(d => d.profit >= 0 ? '#28a745' : '#dc3545'),
                    borderWidth: 1,
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(ctx) {
                                return '盈亏: ¥' + ctx.raw.toFixed(2);
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return '¥' + value;
                            }
                        }
                    }
                },
                onClick: function(evt, elements) {
                    if (elements.length > 0) {
                        const idx = elements[0].index;
                        const stockCode = profitData[idx].stock_code;
                        highlightTableRow(stockCode);
                    }
                }
            }
        });
    }

    // 累计盈亏曲线图
    const cumulativeCtx = document.getElementById('cumulativeChart');
    if (cumulativeCtx && cumulativeData.length > 0) {
        new Chart(cumulativeCtx, {
            type: 'line',
            data: {
                labels: cumulativeData.map(d => d.date),
                datasets: [{
                    label: '累计盈亏',
                    data: cumulativeData.map(d => d.cumulative),
                    borderColor: '#007bff',
                    backgroundColor: 'rgba(0, 123, 255, 0.1)',
                    fill: true,
                    tension: 0.3,
                    pointRadius: 4,
                    pointHoverRadius: 6
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    tooltip: {
                        callbacks: {
                            title: function(ctx) {
                                const idx = ctx[0].dataIndex;
                                return cumulativeData[idx].date + ' - ' + (cumulativeData[idx].stock_name || '');
                            },
                            label: function(ctx) {
                                return '累计: ¥' + ctx.raw.toFixed(2);
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        ticks: {
                            callback: function(value) {
                                return '¥' + value;
                            }
                        }
                    }
                }
            }
        });
    }

    // 加载分类收益图
    loadCategoryChart();

    // 加载持仓周期分析图
    loadHoldingChart();

    // 加载月度/季度趋势图
    loadTrendChart();

    // 时间周期切换
    periodFilter?.addEventListener('change', function() {
        loadTrendChart();
    });

    // 分类收益旭日图
    function loadCategoryChart() {
        fetch('/trades/api/category-profit')
            .then(res => res.json())
            .then(data => renderCategoryChart(data.sunburst))
            .catch(err => console.error('加载分类数据失败:', err));
    }

    function renderCategoryChart(data) {
        const container = document.getElementById('categoryChart');
        if (!container) return;

        if (!data || data.length === 0) {
            container.innerHTML = '<div class="text-center text-muted py-5">暂无分类数据</div>';
            return;
        }

        if (!categoryChart) {
            categoryChart = echarts.init(container);
        }

        const option = {
            tooltip: {
                trigger: 'item',
                formatter: function(params) {
                    const pct = params.percent ? ` (${params.percent}%)` : '';
                    return `${params.name}<br/>盈亏: ¥${params.value.toLocaleString()}${pct}`;
                }
            },
            series: [{
                type: 'sunburst',
                data: data,
                radius: ['15%', '90%'],
                label: {
                    rotate: 'radial',
                    fontSize: 11
                },
                itemStyle: {
                    borderRadius: 4,
                    borderWidth: 2
                },
                levels: [
                    {},
                    {
                        r0: '15%',
                        r: '55%',
                        itemStyle: {
                            borderWidth: 2
                        },
                        label: {
                            fontSize: 12,
                            fontWeight: 'bold'
                        }
                    },
                    {
                        r0: '55%',
                        r: '90%',
                        label: {
                            fontSize: 10
                        },
                        itemStyle: {
                            borderWidth: 1
                        }
                    }
                ]
            }]
        };

        categoryChart.setOption(option);
    }

    // 持仓周期分析散点图
    function loadHoldingChart() {
        fetch('/trades/api/holding-analysis')
            .then(res => res.json())
            .then(data => renderHoldingChart(data.scatter))
            .catch(err => console.error('加载持仓数据失败:', err));
    }

    function renderHoldingChart(data) {
        const container = document.getElementById('holdingChart');
        if (!container) return;

        if (!data || data.length === 0) {
            container.innerHTML = '<div class="text-center text-muted py-5">暂无持仓数据</div>';
            return;
        }

        if (!holdingChart) {
            holdingChart = echarts.init(container);
        }

        const scatterData = data.map(d => ({
            name: d.name,
            value: [d.holding_days, d.profit_pct, d.profit]
        }));

        const option = {
            tooltip: {
                trigger: 'item',
                formatter: function(params) {
                    const d = params.data;
                    return `${d.name}<br/>持仓: ${d.value[0]}天<br/>盈亏率: ${d.value[1]}%<br/>盈亏: ¥${d.value[2].toLocaleString()}`;
                }
            },
            grid: {
                left: '10%',
                right: '10%',
                bottom: '15%',
                top: '10%'
            },
            xAxis: {
                type: 'value',
                name: '持仓天数',
                nameLocation: 'middle',
                nameGap: 30,
                axisLabel: {
                    formatter: '{value}天'
                }
            },
            yAxis: {
                type: 'value',
                name: '盈亏率',
                nameLocation: 'middle',
                nameGap: 40,
                axisLabel: {
                    formatter: '{value}%'
                }
            },
            visualMap: {
                show: true,
                dimension: 1,
                min: Math.min(...data.map(d => d.profit_pct)),
                max: Math.max(...data.map(d => d.profit_pct)),
                inRange: {
                    color: ['#dc3545', '#ffc107', '#28a745']
                },
                text: ['盈利', '亏损'],
                orient: 'horizontal',
                left: 'center',
                bottom: 0
            },
            series: [{
                type: 'scatter',
                data: scatterData,
                symbolSize: function(data) {
                    return Math.min(Math.max(Math.abs(data[2]) / 100, 10), 40);
                },
                label: {
                    show: true,
                    formatter: function(params) {
                        return params.data.name;
                    },
                    position: 'top',
                    fontSize: 10
                },
                emphasis: {
                    itemStyle: {
                        shadowBlur: 10,
                        shadowColor: 'rgba(0, 0, 0, 0.5)'
                    }
                }
            }]
        };

        holdingChart.setOption(option);
    }

    // 月度/季度趋势图
    function loadTrendChart() {
        const period = periodFilter?.value || 'month';
        fetch(`/trades/api/period-trend?period=${period}`)
            .then(res => res.json())
            .then(data => renderTrendChart(data))
            .catch(err => console.error('加载趋势数据失败:', err));
    }

    function renderTrendChart(data) {
        const container = document.getElementById('trendChart');
        if (!container) return;

        if (!data || !data.labels || data.labels.length === 0) {
            container.innerHTML = '<div class="text-center text-muted py-5">暂无趋势数据</div>';
            return;
        }

        if (!trendChart) {
            trendChart = echarts.init(container);
        }

        const option = {
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'cross' },
                formatter: function(params) {
                    let result = params[0].axisValue + '<br/>';
                    params.forEach(p => {
                        if (p.seriesName === '盈亏金额') {
                            result += `${p.marker}${p.seriesName}: ¥${p.value.toLocaleString()}<br/>`;
                        } else if (p.seriesName === '胜率') {
                            result += `${p.marker}${p.seriesName}: ${p.value}%<br/>`;
                        } else {
                            result += `${p.marker}${p.seriesName}: ${p.value}笔<br/>`;
                        }
                    });
                    return result;
                }
            },
            legend: {
                data: ['盈亏金额', '交易笔数', '胜率']
            },
            grid: {
                left: '3%',
                right: '10%',
                bottom: '3%',
                containLabel: true
            },
            xAxis: {
                type: 'category',
                data: data.labels,
                axisLabel: { rotate: 30 }
            },
            yAxis: [
                {
                    type: 'value',
                    name: '盈亏金额',
                    position: 'left',
                    axisLabel: {
                        formatter: function(value) {
                            if (Math.abs(value) >= 10000) {
                                return '¥' + (value / 10000).toFixed(0) + '万';
                            }
                            return '¥' + value;
                        }
                    }
                },
                {
                    type: 'value',
                    name: '交易笔数',
                    position: 'right'
                },
                {
                    type: 'value',
                    name: '胜率',
                    position: 'right',
                    offset: 60,
                    min: 0,
                    max: 100,
                    axisLabel: {
                        formatter: '{value}%'
                    }
                }
            ],
            series: [
                {
                    name: '盈亏金额',
                    type: 'bar',
                    data: data.profits,
                    itemStyle: {
                        color: function(params) {
                            return params.value >= 0 ? '#28a745' : '#dc3545';
                        },
                        borderRadius: [4, 4, 0, 0]
                    }
                },
                {
                    name: '交易笔数',
                    type: 'line',
                    yAxisIndex: 1,
                    data: data.trade_counts,
                    smooth: true,
                    itemStyle: { color: '#007bff' },
                    areaStyle: { opacity: 0.1 }
                },
                {
                    name: '胜率',
                    type: 'line',
                    yAxisIndex: 2,
                    data: data.win_rates,
                    smooth: true,
                    itemStyle: { color: '#ffc107' },
                    lineStyle: { type: 'dashed' }
                }
            ]
        };

        trendChart.setOption(option);
    }

    // 高亮表格行
    function highlightTableRow(stockCode) {
        document.querySelectorAll('#settlementTable tbody tr').forEach(tr => {
            tr.classList.remove('table-warning');
            if (tr.dataset.stockCode === stockCode) {
                tr.classList.add('table-warning');
                tr.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        });
    }

    // 窗口大小变化时调整图表
    window.addEventListener('resize', function() {
        categoryChart?.resize();
        holdingChart?.resize();
        trendChart?.resize();
    });
});
