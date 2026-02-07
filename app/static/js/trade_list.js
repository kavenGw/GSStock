document.addEventListener('DOMContentLoaded', function() {
    const dateRangeFilter = document.getElementById('dateRangeFilter');
    const stockCodeFilter = document.getElementById('stockCodeFilter');
    const tradeTypeFilter = document.getElementById('tradeTypeFilter');
    const timelineStockSelect = document.getElementById('timelineStockSelect');
    const editModal = document.getElementById('editModal') ? new bootstrap.Modal(document.getElementById('editModal')) : null;

    let amountDistChart = null;
    let buySellChart = null;
    let frequencyChart = null;
    let timelineChart = null;
    let transferFlowChart = null;
    let chartsLoaded = false;
    let transfersLoaded = false;
    const transferModal = document.getElementById('transferModal') ? new bootstrap.Modal(document.getElementById('transferModal')) : null;

    const STORAGE_KEY = 'trade_list_state';

    // 保存状态到 localStorage
    function saveState() {
        const state = {
            dateRange: dateRangeFilter?.value,
            activeTab: document.querySelector('#tradeTabs .nav-link.active')?.id,
            timelineStock: timelineStockSelect?.value
        };
        localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    }

    // 恢复状态
    function restoreState() {
        try {
            const state = JSON.parse(localStorage.getItem(STORAGE_KEY));
            if (!state) return;

            if (state.dateRange && dateRangeFilter) {
                dateRangeFilter.value = state.dateRange;
            }

            if (state.activeTab) {
                const tab = document.getElementById(state.activeTab);
                if (tab) {
                    bootstrap.Tab.getOrCreateInstance(tab).show();
                }
            }

            if (state.timelineStock && timelineStockSelect) {
                timelineStockSelect.value = state.timelineStock;
                if (state.timelineStock) {
                    timelineStockSelect.dispatchEvent(new Event('change'));
                }
            }
        } catch (e) {
            console.error('恢复状态失败:', e);
        }
    }

    // 筛选功能 - 应用到列表
    function applyFilter() {
        const stockCode = stockCodeFilter.value;
        const tradeType = tradeTypeFilter.value;
        const params = new URLSearchParams();
        if (stockCode) params.set('stock_code', stockCode);
        if (tradeType) params.set('trade_type', tradeType);
        window.location.href = '/trades/?' + params.toString();
    }

    stockCodeFilter.addEventListener('change', applyFilter);
    tradeTypeFilter.addEventListener('change', applyFilter);

    // 时间范围变化 - 刷新图表并保存状态
    dateRangeFilter.addEventListener('change', function() {
        saveState();
        if (chartsLoaded) {
            loadChartData();
        }
    });

    // 标签页切换 - 保存状态
    document.querySelectorAll('#tradeTabs .nav-link').forEach(tab => {
        tab.addEventListener('shown.bs.tab', saveState);
    });

    document.getElementById('chart-tab')?.addEventListener('shown.bs.tab', function() {
        if (!chartsLoaded) {
            loadChartData();
            chartsLoaded = true;
        } else {
            frequencyChart?.resize();
            timelineChart?.resize();
        }
    });

    document.getElementById('transfer-tab')?.addEventListener('shown.bs.tab', function() {
        if (!transfersLoaded) {
            loadTransferData();
            transfersLoaded = true;
        } else {
            transferFlowChart?.resize();
        }
    });

    // 页面加载时恢复状态
    restoreState();

    // 加载图表数据
    function loadChartData() {
        const days = dateRangeFilter.value;
        const stockCode = stockCodeFilter.value;
        const params = new URLSearchParams();
        if (days) params.set('days', days);
        if (stockCode) params.set('stock_code', stockCode);

        fetch('/trades/api/list-charts?' + params.toString())
            .then(res => res.json())
            .then(data => {
                renderAmountDistChart(data.amount_distribution);
                renderBuySellChart(data.buy_sell_compare);
                renderFrequencyChart(data.trade_frequency);
            })
            .catch(err => console.error('加载图表数据失败:', err));
    }

    // 交易金额分布饼图
    function renderAmountDistChart(data) {
        const ctx = document.getElementById('amountDistChart');
        if (!ctx) return;

        if (amountDistChart) amountDistChart.destroy();

        if (!data || data.length === 0) {
            ctx.parentElement.innerHTML = '<div class="text-center text-muted py-5">暂无数据</div>';
            return;
        }

        const colors = generateColors(data.length);

        amountDistChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.map(d => d.name),
                datasets: [{
                    data: data.map(d => d.value),
                    backgroundColor: colors,
                    borderWidth: 2,
                    borderColor: '#fff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: { boxWidth: 12 }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(ctx) {
                                const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                                const pct = (ctx.raw / total * 100).toFixed(1);
                                return `${ctx.label}: ¥${ctx.raw.toLocaleString()} (${pct}%)`;
                            }
                        }
                    }
                },
                onClick: function(evt, elements) {
                    if (elements.length > 0) {
                        const idx = elements[0].index;
                        const stockName = data[idx].name;
                        highlightTableRows('name', stockName);
                    }
                }
            }
        });
    }

    // 买卖金额对比柱状图
    function renderBuySellChart(data) {
        const ctx = document.getElementById('buySellChart');
        if (!ctx) return;

        if (buySellChart) buySellChart.destroy();

        if (!data || data.length === 0) {
            ctx.parentElement.innerHTML = '<div class="text-center text-muted py-5">暂无数据</div>';
            return;
        }

        buySellChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.map(d => d.name),
                datasets: [
                    {
                        label: '买入',
                        data: data.map(d => d.buy),
                        backgroundColor: 'rgba(40, 167, 69, 0.8)',
                        borderColor: '#28a745',
                        borderWidth: 1
                    },
                    {
                        label: '卖出',
                        data: data.map(d => d.sell),
                        backgroundColor: 'rgba(220, 53, 69, 0.8)',
                        borderColor: '#dc3545',
                        borderWidth: 1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: function(ctx) {
                                return `${ctx.dataset.label}: ¥${ctx.raw.toLocaleString()}`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            callback: function(value) {
                                return '¥' + value.toLocaleString();
                            }
                        }
                    }
                },
                onClick: function(evt, elements) {
                    if (elements.length > 0) {
                        const idx = elements[0].index;
                        const stockName = data[idx].name;
                        highlightTableRows('name', stockName);
                    }
                }
            }
        });
    }

    // 交易频率趋势图 (ECharts)
    function renderFrequencyChart(data) {
        const container = document.getElementById('frequencyChart');
        if (!container) return;

        if (!data || data.length === 0) {
            container.innerHTML = '<div class="text-center text-muted py-5">暂无数据</div>';
            return;
        }

        if (!frequencyChart) {
            frequencyChart = echarts.init(container);
        }

        const option = {
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'cross' },
                formatter: function(params) {
                    let result = params[0].axisValue + '<br/>';
                    params.forEach(p => {
                        if (p.seriesName === '交易金额') {
                            result += `${p.marker}${p.seriesName}: ¥${p.value.toLocaleString()}<br/>`;
                        } else {
                            result += `${p.marker}${p.seriesName}: ${p.value}笔<br/>`;
                        }
                    });
                    return result;
                }
            },
            legend: {
                data: ['买入笔数', '卖出笔数', '交易金额']
            },
            grid: {
                left: '3%',
                right: '4%',
                bottom: '15%',
                containLabel: true
            },
            xAxis: {
                type: 'category',
                data: data.map(d => d.date),
                axisLabel: { rotate: 45 }
            },
            yAxis: [
                {
                    type: 'value',
                    name: '笔数',
                    position: 'left'
                },
                {
                    type: 'value',
                    name: '金额',
                    position: 'right',
                    axisLabel: {
                        formatter: function(value) {
                            return '¥' + (value / 10000).toFixed(0) + '万';
                        }
                    }
                }
            ],
            dataZoom: [
                {
                    type: 'inside',
                    start: 0,
                    end: 100
                },
                {
                    type: 'slider',
                    start: 0,
                    end: 100
                }
            ],
            series: [
                {
                    name: '买入笔数',
                    type: 'bar',
                    stack: 'count',
                    data: data.map(d => d.buy_count),
                    itemStyle: { color: '#28a745' }
                },
                {
                    name: '卖出笔数',
                    type: 'bar',
                    stack: 'count',
                    data: data.map(d => d.sell_count),
                    itemStyle: { color: '#dc3545' }
                },
                {
                    name: '交易金额',
                    type: 'line',
                    yAxisIndex: 1,
                    data: data.map(d => d.total_amount),
                    smooth: true,
                    areaStyle: { opacity: 0.3 },
                    itemStyle: { color: '#007bff' }
                }
            ]
        };

        frequencyChart.setOption(option);
    }

    // 单股交易时间线
    timelineStockSelect?.addEventListener('change', function() {
        const stockCode = this.value;
        saveState();
        if (!stockCode) {
            document.getElementById('timelineChart').style.display = 'none';
            document.getElementById('timelineEmpty').style.display = 'block';
            return;
        }

        const days = dateRangeFilter.value || 365;
        fetch(`/trades/api/timeline/${stockCode}?days=${days}`)
            .then(res => res.json())
            .then(data => renderTimelineChart(data))
            .catch(err => console.error('加载时间线数据失败:', err));
    });

    function renderTimelineChart(data) {
        const container = document.getElementById('timelineChart');
        const emptyHint = document.getElementById('timelineEmpty');

        if (!data || !data.trades || data.trades.length === 0) {
            container.style.display = 'none';
            emptyHint.style.display = 'block';
            emptyHint.textContent = '该股票暂无交易记录';
            return;
        }

        container.style.display = 'block';
        emptyHint.style.display = 'none';

        if (!timelineChart) {
            timelineChart = echarts.init(container);
        }

        // K线数据 - ECharts candlestick 格式: [open, close, low, high]
        const dates = data.ohlc ? data.ohlc.map(d => d.date) : [];
        const candlestickData = data.ohlc ? data.ohlc.map(d => [d.open, d.close, d.low, d.high]) : [];

        // 交易点数据 - 转换为 [日期, 价格, 数量, 金额]
        const buyData = [];
        const sellData = [];
        data.trades.forEach(t => {
            const point = [t.date, t.price, t.quantity, t.amount];
            if (t.type === 'buy') {
                buyData.push(point);
            } else {
                sellData.push(point);
            }
        });

        const series = [];

        // 添加K线图（如果有数据）
        if (candlestickData.length > 0) {
            series.push({
                name: 'K线',
                type: 'candlestick',
                data: candlestickData,
                itemStyle: {
                    color: '#dc3545',        // 上涨色（收盘>开盘）
                    color0: '#28a745',       // 下跌色
                    borderColor: '#dc3545',
                    borderColor0: '#28a745'
                }
            });
        }

        // 添加买入散点 - B + 数量
        series.push({
            name: '买入',
            type: 'scatter',
            data: buyData,
            symbolSize: function(data) {
                const qty = data[2];
                const digits = String(qty).length;
                return Math.max(28, 20 + digits * 6);
            },
            symbol: 'circle',
            itemStyle: {
                color: '#28a745',
                borderColor: '#fff',
                borderWidth: 2
            },
            z: 10,
            label: {
                show: true,
                position: 'inside',
                formatter: function(params) {
                    return 'B' + params.data[2];
                },
                fontSize: 10,
                fontWeight: 'bold',
                color: '#fff'
            }
        });

        // 添加卖出散点 - S + 数量
        series.push({
            name: '卖出',
            type: 'scatter',
            data: sellData,
            symbolSize: function(data) {
                const qty = data[2];
                const digits = String(qty).length;
                return Math.max(28, 20 + digits * 6);
            },
            symbol: 'circle',
            itemStyle: {
                color: '#dc3545',
                borderColor: '#fff',
                borderWidth: 2
            },
            z: 10,
            label: {
                show: true,
                position: 'inside',
                formatter: function(params) {
                    return 'S' + params.data[2];
                },
                fontSize: 10,
                fontWeight: 'bold',
                color: '#fff'
            }
        });

        // x轴配置：有K线用category，否则用time
        const xAxisConfig = candlestickData.length > 0 ? {
            type: 'category',
            data: dates,
            axisLabel: { rotate: 45 },
            boundaryGap: true
        } : {
            type: 'time',
            axisLabel: { formatter: '{yyyy}-{MM}-{dd}' }
        };

        const option = {
            title: {
                text: `${data.stock_name || data.stock_code} 交易时间线`,
                left: 'center'
            },
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'cross' },
                formatter: function(params) {
                    if (!params || params.length === 0) return '';
                    let result = params[0].axisValue + '<br/>';
                    params.forEach(p => {
                        if (p.seriesName === 'K线' && p.data) {
                            result += `开: ¥${p.data[1]} 收: ¥${p.data[2]}<br/>`;
                            result += `低: ¥${p.data[3]} 高: ¥${p.data[4]}<br/>`;
                        } else if ((p.seriesName === '买入' || p.seriesName === '卖出') && p.data) {
                            const color = p.seriesName === '买入' ? '#28a745' : '#dc3545';
                            const label = p.seriesName === '买入' ? 'B' : 'S';
                            result += `<span style="display:inline-block;width:14px;height:14px;border-radius:50%;background:${color};color:#fff;text-align:center;line-height:14px;font-size:10px;font-weight:bold;margin-right:4px;">${label}</span>${p.seriesName}: ¥${p.data[1]} × ${p.data[2]}股 = ¥${p.data[3].toLocaleString()}<br/>`;
                        }
                    });
                    return result;
                }
            },
            legend: {
                data: candlestickData.length > 0 ? ['K线', '买入', '卖出'] : ['买入', '卖出'],
                top: 30
            },
            grid: {
                left: '3%',
                right: '4%',
                bottom: '15%',
                top: '15%',
                containLabel: true
            },
            xAxis: xAxisConfig,
            yAxis: {
                type: 'value',
                name: '价格',
                scale: true,
                axisLabel: {
                    formatter: '¥{value}'
                }
            },
            dataZoom: [
                {
                    type: 'inside',
                    start: 0,
                    end: 100
                },
                {
                    type: 'slider',
                    start: 0,
                    end: 100
                }
            ],
            series: series
        };

        timelineChart.setOption(option, true);
    }

    // 高亮表格行
    function highlightTableRows(type, value) {
        document.querySelectorAll('#tradeTable tr').forEach(tr => {
            tr.classList.remove('table-warning');
        });

        // 切换到列表视图
        const listTab = document.getElementById('list-tab');
        if (listTab) {
            bootstrap.Tab.getOrCreateInstance(listTab).show();
        }

        // 高亮匹配行
        document.querySelectorAll('#tradeTable tr').forEach(tr => {
            const nameCell = tr.querySelector('td:nth-child(3)');
            if (nameCell && nameCell.textContent.trim() === value) {
                tr.classList.add('table-warning');
            }
        });
    }

    // 生成颜色
    function generateColors(count) {
        const baseColors = [
            '#007bff', '#28a745', '#dc3545', '#ffc107', '#17a2b8',
            '#6610f2', '#e83e8c', '#fd7e14', '#20c997', '#6f42c1'
        ];
        const colors = [];
        for (let i = 0; i < count; i++) {
            colors.push(baseColors[i % baseColors.length]);
        }
        return colors;
    }

    // 删除功能
    document.querySelectorAll('.btn-delete').forEach(btn => {
        btn.addEventListener('click', function() {
            if (!confirm('确定要删除这条交易记录吗？')) return;

            const tr = this.closest('tr');
            const tradeId = tr.dataset.tradeId;

            fetch(`/trades/${tradeId}`, { method: 'DELETE' })
                .then(res => res.json())
                .then(data => {
                    if (data.error) {
                        alert(data.error);
                        return;
                    }
                    tr.remove();
                    chartsLoaded = false;  // 重新加载图表
                })
                .catch(err => alert('删除失败: ' + err.message));
        });
    });

    // 编辑功能
    document.querySelectorAll('.btn-edit').forEach(btn => {
        btn.addEventListener('click', function() {
            const trade = JSON.parse(this.dataset.trade);
            document.getElementById('editTradeId').value = trade.id;
            document.getElementById('editStockInfo').value = `${trade.stock_code} ${trade.stock_name}`;
            document.getElementById('editTradeDate').value = trade.trade_date;
            document.getElementById('editTradeType').value = trade.trade_type;
            document.getElementById('editQuantity').value = trade.quantity;
            document.getElementById('editPrice').value = trade.price;
            document.getElementById('editError').style.display = 'none';
            editModal.show();
        });
    });

    document.getElementById('saveEditBtn')?.addEventListener('click', function() {
        const tradeId = document.getElementById('editTradeId').value;
        const data = {
            trade_date: document.getElementById('editTradeDate').value,
            trade_type: document.getElementById('editTradeType').value,
            quantity: parseInt(document.getElementById('editQuantity').value),
            price: parseFloat(document.getElementById('editPrice').value),
        };

        fetch(`/trades/${tradeId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        })
        .then(res => res.json())
        .then(result => {
            if (result.error) {
                document.getElementById('editError').textContent = result.error;
                document.getElementById('editError').style.display = 'block';
                return;
            }
            editModal.hide();
            window.location.reload();
        })
        .catch(err => {
            document.getElementById('editError').textContent = '保存失败: ' + err.message;
            document.getElementById('editError').style.display = 'block';
        });
    });

    // 结算功能
    document.querySelectorAll('.btn-settle').forEach(btn => {
        btn.addEventListener('click', function() {
            const stockCode = this.dataset.stockCode;
            if (!confirm(`确定要结算股票 ${stockCode} 吗？结算后该股票的所有交易记录将被统计。`)) return;

            fetch(`/trades/settle/${stockCode}`, { method: 'POST' })
                .then(res => res.json())
                .then(data => {
                    if (data.error) {
                        alert(data.error);
                        return;
                    }
                    alert('结算成功！');
                    window.location.href = '/trades/stats';
                })
                .catch(err => alert('结算失败: ' + err.message));
        });
    });

    // 加载转账数据
    function loadTransferData() {
        // 加载统计数据和图表
        fetch('/trades/api/transfer-stats')
            .then(res => res.json())
            .then(data => {
                renderTransferStats(data);
                renderTransferFlowChart(data.monthly_trend);
            })
            .catch(err => console.error('加载转账统计失败:', err));

        // 加载转账列表
        loadTransferList();
    }

    function renderTransferStats(data) {
        document.getElementById('totalTransferIn').textContent =
            '¥' + data.total_in.toLocaleString('zh-CN', {minimumFractionDigits: 2});
        document.getElementById('totalTransferOut').textContent =
            '¥' + data.total_out.toLocaleString('zh-CN', {minimumFractionDigits: 2});

        const netFlow = document.getElementById('netTransferFlow');
        netFlow.textContent = '¥' + data.net_flow.toLocaleString('zh-CN', {minimumFractionDigits: 2});
        netFlow.className = 'card-title ' + (data.net_flow >= 0 ? 'text-success' : 'text-danger');

        document.getElementById('transferCount').textContent = data.count + '笔';
    }

    function renderTransferFlowChart(monthlyData) {
        const container = document.getElementById('transferFlowChart');
        if (!container) return;

        if (!monthlyData || monthlyData.length === 0) {
            container.innerHTML = '<div class="text-center text-muted py-5">暂无数据</div>';
            return;
        }

        if (!transferFlowChart) {
            transferFlowChart = echarts.init(container);
        }

        const option = {
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'shadow' },
                formatter: function(params) {
                    let result = params[0].axisValue + '<br/>';
                    params.forEach(p => {
                        result += `${p.marker}${p.seriesName}: ¥${p.value.toLocaleString()}<br/>`;
                    });
                    return result;
                }
            },
            legend: {
                data: ['转入', '转出', '净流入']
            },
            grid: {
                left: '3%',
                right: '4%',
                bottom: '3%',
                containLabel: true
            },
            xAxis: {
                type: 'category',
                data: monthlyData.map(d => d.month),
                axisLabel: { rotate: 45 }
            },
            yAxis: {
                type: 'value',
                axisLabel: {
                    formatter: function(value) {
                        return '¥' + (value / 10000).toFixed(0) + '万';
                    }
                }
            },
            series: [
                {
                    name: '转入',
                    type: 'bar',
                    data: monthlyData.map(d => d.transfer_in),
                    itemStyle: { color: '#28a745' }
                },
                {
                    name: '转出',
                    type: 'bar',
                    data: monthlyData.map(d => d.transfer_out),
                    itemStyle: { color: '#dc3545' }
                },
                {
                    name: '净流入',
                    type: 'line',
                    data: monthlyData.map(d => d.net),
                    smooth: true,
                    itemStyle: { color: '#007bff' }
                }
            ]
        };

        transferFlowChart.setOption(option);
    }

    function loadTransferList() {
        fetch('/trades/transfers')
            .then(res => res.json())
            .then(data => {
                renderTransferTable(data.transfers);
            })
            .catch(err => console.error('加载转账列表失败:', err));
    }

    function renderTransferTable(transfers) {
        const tbody = document.getElementById('transferTableBody');
        if (!tbody) return;

        if (!transfers || transfers.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="text-center text-muted">暂无转账记录</td></tr>';
            return;
        }

        tbody.innerHTML = transfers.map(t => {
            const typeText = t.transfer_type === 'in' ? '转入' : '转出';
            const typeBadge = t.transfer_type === 'in'
                ? '<span class="badge bg-success">转入</span>'
                : '<span class="badge bg-danger">转出</span>';
            return `
                <tr data-transfer-id="${t.id}">
                    <td>${t.transfer_date}</td>
                    <td>${typeBadge}</td>
                    <td>¥${t.amount.toLocaleString('zh-CN', {minimumFractionDigits: 2})}</td>
                    <td>${t.note || '-'}</td>
                    <td>
                        <div class="btn-group btn-group-sm">
                            <button class="btn btn-outline-primary btn-edit-transfer"
                                    data-transfer='${JSON.stringify(t)}'>编辑</button>
                            <button class="btn btn-outline-danger btn-delete-transfer">删除</button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');

        // 绑定编辑和删除事件
        tbody.querySelectorAll('.btn-edit-transfer').forEach(btn => {
            btn.addEventListener('click', function() {
                const transfer = JSON.parse(this.dataset.transfer);
                openTransferModal(transfer);
            });
        });

        tbody.querySelectorAll('.btn-delete-transfer').forEach(btn => {
            btn.addEventListener('click', function() {
                if (!confirm('确定要删除这条转账记录吗？')) return;
                const tr = this.closest('tr');
                const transferId = tr.dataset.transferId;
                deleteTransfer(transferId, tr);
            });
        });
    }

    function openTransferModal(transfer = null) {
        document.getElementById('editTransferId').value = transfer ? transfer.id : '';
        document.getElementById('editTransferDate').value = transfer ? transfer.transfer_date : new Date().toISOString().split('T')[0];
        document.getElementById('editTransferType').value = transfer ? transfer.transfer_type : 'in';
        document.getElementById('editTransferAmount').value = transfer ? transfer.amount : '';
        document.getElementById('editTransferNote').value = transfer ? (transfer.note || '') : '';
        document.getElementById('transferError').style.display = 'none';
        document.getElementById('transferModalLabel').textContent = transfer ? '编辑转账' : '新增转账';
        transferModal.show();
    }

    document.getElementById('addTransferBtn')?.addEventListener('click', () => {
        openTransferModal();
    });

    document.getElementById('saveTransferBtn')?.addEventListener('click', function() {
        const transferId = document.getElementById('editTransferId').value;
        const data = {
            transfer_date: document.getElementById('editTransferDate').value,
            transfer_type: document.getElementById('editTransferType').value,
            amount: parseFloat(document.getElementById('editTransferAmount').value),
            note: document.getElementById('editTransferNote').value
        };

        if (!data.amount || data.amount <= 0) {
            document.getElementById('transferError').textContent = '金额必须大于0';
            document.getElementById('transferError').style.display = 'block';
            return;
        }

        const url = transferId ? `/trades/transfers/${transferId}` : '/trades/transfers';
        const method = transferId ? 'PUT' : 'POST';

        fetch(url, {
            method: method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        })
        .then(res => res.json())
        .then(result => {
            if (result.error) {
                document.getElementById('transferError').textContent = result.error;
                document.getElementById('transferError').style.display = 'block';
                return;
            }
            transferModal.hide();
            loadTransferData();
        })
        .catch(err => {
            document.getElementById('transferError').textContent = '保存失败: ' + err.message;
            document.getElementById('transferError').style.display = 'block';
        });
    });

    function deleteTransfer(transferId, tr) {
        fetch(`/trades/transfers/${transferId}`, { method: 'DELETE' })
            .then(res => res.json())
            .then(data => {
                if (data.error) {
                    alert(data.error);
                    return;
                }
                tr.remove();
                loadTransferData();
            })
            .catch(err => alert('删除失败: ' + err.message));
    }

    // 窗口大小变化时调整图表
    window.addEventListener('resize', function() {
        frequencyChart?.resize();
        timelineChart?.resize();
        transferFlowChart?.resize();
    });
});
