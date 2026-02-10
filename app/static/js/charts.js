// 图表模块
const Charts = {
    pieChart: null,
    profitChart: null,
    categoryChart: null,
    categoryProfitChart: null,
    dailyProfitBarChart: null,
    cumulativeProfitChart: null,
    trendChart: null,
    trendData: null,
    detailCharts: {},
    volumeCharts: {},
    supportResistanceData: null,
    // 分类图相关数据缓存
    categoryData: {
        positions: null,
        stockCategories: null,
        categoryTree: null,
        currentParentId: null  // null 表示显示一级分类
    },

    // 带引导线的饼图插件（带防重叠）
    leaderLinePlugin: {
        id: 'leaderLines',
        afterDraw(chart, args, options) {
            const ctx = chart.ctx;
            const chartArea = chart.chartArea;
            const centerX = (chartArea.left + chartArea.right) / 2;
            const centerY = (chartArea.top + chartArea.bottom) / 2;
            const lineHeight = 14;

            chart.data.datasets.forEach((dataset, i) => {
                const meta = chart.getDatasetMeta(i);
                if (!meta.data.length) return;

                const total = dataset.data.reduce((a, b) => a + b, 0);

                // 收集所有标签位置
                const leftLabels = [];
                const rightLabels = [];

                meta.data.forEach((arc, index) => {
                    if (dataset.data[index] === 0) return;

                    const pct = (dataset.data[index] / total * 100).toFixed(1);
                    const label = chart.data.labels[index];
                    const text = `${label} ${pct}%`;

                    const midAngle = (arc.startAngle + arc.endAngle) / 2;
                    const outerRadius = arc.outerRadius;
                    const startX = centerX + Math.cos(midAngle) * outerRadius;
                    const startY = centerY + Math.sin(midAngle) * outerRadius;
                    const midX = centerX + Math.cos(midAngle) * (outerRadius + 15);
                    const midY = centerY + Math.sin(midAngle) * (outerRadius + 15);
                    const isRight = midAngle > -Math.PI / 2 && midAngle < Math.PI / 2;

                    const labelData = { index, text, startX, startY, midX, midY, isRight, color: dataset.backgroundColor[index] };
                    (isRight ? rightLabels : leftLabels).push(labelData);
                });

                // 防重叠：按Y排序后调整位置
                [leftLabels, rightLabels].forEach(labels => {
                    labels.sort((a, b) => a.midY - b.midY);
                    for (let j = 1; j < labels.length; j++) {
                        const prev = labels[j - 1];
                        const curr = labels[j];
                        if (curr.midY - prev.midY < lineHeight) {
                            curr.midY = prev.midY + lineHeight;
                        }
                    }
                });

                // 绘制
                [...leftLabels, ...rightLabels].forEach(l => {
                    const endX = l.isRight ? l.midX + 20 : l.midX - 20;

                    ctx.save();
                    ctx.strokeStyle = l.color;
                    ctx.lineWidth = 1;
                    ctx.beginPath();
                    ctx.moveTo(l.startX, l.startY);
                    ctx.lineTo(l.midX, l.midY);
                    ctx.lineTo(endX, l.midY);
                    ctx.stroke();

                    ctx.fillStyle = '#333';
                    ctx.font = '11px sans-serif';
                    ctx.textAlign = l.isRight ? 'left' : 'right';
                    ctx.textBaseline = 'middle';
                    ctx.fillText(l.text, l.isRight ? endX + 4 : endX - 4, l.midY);
                    ctx.restore();
                });
            });
        }
    },

    // 走势图末端标签插件
    trendEndLabelPlugin: {
        id: 'trendEndLabels',
        afterDraw(chart) {
            const ctx = chart.ctx;
            const chartArea = chart.chartArea;
            const datasets = chart.data.datasets;
            const minGap = 16;

            // 收集所有可见线条的末端点信息
            const labels = [];
            datasets.forEach((ds, i) => {
                const meta = chart.getDatasetMeta(i);
                if (meta.hidden) return;
                if (!meta.data || meta.data.length === 0) return;

                // 找到最后一个有效数据点
                let lastPoint = null;
                for (let j = meta.data.length - 1; j >= 0; j--) {
                    if (ds.data[j] !== null && ds.data[j] !== undefined) {
                        lastPoint = meta.data[j];
                        break;
                    }
                }
                if (!lastPoint) return;

                // 如果有相对差值，在名称后显示
                let displayName = ds.label.slice(0, 6);
                let labelColor = ds._originalColor || ds.borderColor;
                if (ds.stock && ds.stock.relative_diff !== undefined) {
                    const diff = ds.stock.relative_diff;
                    const diffStr = diff >= 0 ? `+${diff.toFixed(1)}` : diff.toFixed(1);
                    // 添加趋势箭头
                    const trend = ds.stock.trend;
                    if (trend && trend.arrow) {
                        displayName = `${displayName}(${diffStr}${trend.arrow})`;
                        // 显著趋势变化时使用颜色标识
                        const significantThreshold = 1.0;
                        if (trend.diff_change > significantThreshold) {
                            labelColor = '#28a745';  // 走强绿色
                        } else if (trend.diff_change < -significantThreshold) {
                            labelColor = '#dc3545';  // 走弱红色
                        }
                    } else {
                        displayName = `${displayName}(${diffStr})`;
                    }
                }

                labels.push({
                    index: i,
                    name: displayName,
                    y: lastPoint.y,
                    originalY: lastPoint.y,
                    color: labelColor
                });
            });

            if (labels.length === 0) return;

            // 按Y坐标排序
            labels.sort((a, b) => a.y - b.y);

            // 防重叠：从上到下调整位置
            for (let i = 1; i < labels.length; i++) {
                if (labels[i].y - labels[i - 1].y < minGap) {
                    labels[i].y = labels[i - 1].y + minGap;
                }
            }

            // 限制在图表区域内
            const maxY = chartArea.bottom - 8;
            const minY = chartArea.top + 8;
            labels.forEach(l => {
                l.y = Math.max(minY, Math.min(maxY, l.y));
            });

            // 保存标签位置用于点击检测
            chart._labelPositions = [];

            // 绘制标签
            const x = chartArea.right + 8;
            ctx.save();
            ctx.font = '12px sans-serif';
            ctx.textAlign = 'left';
            ctx.textBaseline = 'middle';

            labels.forEach(l => {
                const meta = chart.getDatasetMeta(l.index);
                const isHidden = meta.hidden;
                ctx.fillStyle = isHidden ? '#999' : l.color;
                ctx.globalAlpha = isHidden ? 0.5 : 1;
                ctx.fillText(l.name, x, l.y);

                // 保存位置用于点击检测
                const width = ctx.measureText(l.name).width;
                chart._labelPositions.push({
                    index: l.index,
                    x: x,
                    y: l.y - 8,
                    width: width,
                    height: 16
                });
            });

            ctx.restore();
        }
    },

    // K线图 Chart.js 插件
    candlestickPlugin: {
        id: 'candlestick',
        afterDatasetsDraw(chart) {
            const ctx = chart.ctx;
            const yAxis = chart.scales.y;
            const xAxis = chart.scales.x;

            chart.data.datasets.forEach((dataset, datasetIndex) => {
                const meta = chart.getDatasetMeta(datasetIndex);
                if (meta.hidden || !dataset._ohlcData) return;

                const ohlcData = dataset._ohlcData;
                const borderColor = dataset._originalColor || dataset.borderColor;
                const dataCount = ohlcData.length;
                const barWidth = Math.max(2, (xAxis.width / dataCount) * 0.6);

                ohlcData.forEach((d, index) => {
                    if (!d || d.open == null) return;

                    const x = xAxis.getPixelForValue(index);
                    const yOpen = yAxis.getPixelForValue(d.open);
                    const yHigh = yAxis.getPixelForValue(d.high);
                    const yLow = yAxis.getPixelForValue(d.low);
                    const yClose = yAxis.getPixelForValue(d.close);
                    const isRising = d.close >= d.open;

                    Charts.drawCandlestick(ctx, x, yOpen, yHigh, yLow, yClose, barWidth, borderColor, isRising);
                });
            });
        }
    },

    // 迷你图K线插件（无影线，只显示柱体）
    miniCandlestickPlugin: {
        id: 'miniCandlestick',
        afterDatasetsDraw(chart) {
            const ctx = chart.ctx;
            const yAxis = chart.scales.y;
            const xAxis = chart.scales.x;

            chart.data.datasets.forEach((dataset, datasetIndex) => {
                const meta = chart.getDatasetMeta(datasetIndex);
                if (meta.hidden || !dataset._ohlcData) return;

                const ohlcData = dataset._ohlcData;
                const dataCount = ohlcData.length;
                const barWidth = Math.max(2, (xAxis.width / dataCount) * 0.7);
                const borderColor = dataset._originalColor || dataset.borderColor;

                ohlcData.forEach((d, index) => {
                    if (!d) return;
                    const x = xAxis.getPixelForValue(index);
                    const yOpen = yAxis.getPixelForValue(d.open);
                    const yClose = yAxis.getPixelForValue(d.close);
                    const isRising = d.close >= d.open;

                    Charts.drawMiniBar(ctx, x, yOpen, yClose, barWidth, isRising, borderColor);
                });
            });
        }
    },

    // K线绘制辅助函数
    drawCandlestick(ctx, x, yOpen, yHigh, yLow, yClose, width, borderColor, isRising) {
        const fillColor = isRising ? '#e53e3e' : '#48bb78';  // 红涨绿跌
        const halfWidth = width / 2;

        // 绘制上下影线
        ctx.save();
        ctx.strokeStyle = borderColor || fillColor;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x, yHigh);
        ctx.lineTo(x, yLow);
        ctx.stroke();

        // 绘制柱体（开盘到收盘区域）
        const bodyTop = Math.min(yOpen, yClose);
        const bodyHeight = Math.abs(yClose - yOpen) || 1;  // 最小1px

        ctx.fillStyle = fillColor;
        ctx.fillRect(x - halfWidth, bodyTop, width, bodyHeight);
        ctx.strokeStyle = borderColor || fillColor;
        ctx.strokeRect(x - halfWidth, bodyTop, width, bodyHeight);
        ctx.restore();
    },

    // 迷你K线绘制（无影线，只有柱体）
    drawMiniBar(ctx, x, yOpen, yClose, width, isRising, borderColor) {
        const fillColor = isRising ? '#e53e3e' : '#48bb78';  // 红涨绿跌
        const halfWidth = width / 2;

        const bodyTop = Math.min(yOpen, yClose);
        const bodyHeight = Math.abs(yClose - yOpen) || 1;

        ctx.save();
        ctx.fillStyle = fillColor;
        ctx.fillRect(x - halfWidth, bodyTop, width, bodyHeight);
        if (borderColor) {
            ctx.strokeStyle = borderColor;
            ctx.lineWidth = 1;
            ctx.strokeRect(x - halfWidth, bodyTop, width, bodyHeight);
        }
        ctx.restore();
    },

    // 支撑/阻力线插件
    supportResistancePlugin: {
        id: 'supportResistance',
        afterDraw(chart) {
            // 检查开关状态
            if (localStorage.getItem('showSupportResistance') === 'false') return;

            const srData = chart._supportResistanceData;
            if (!srData) return;

            const ctx = chart.ctx;
            const yAxis = chart.scales.y;
            const xAxis = chart.scales.x;

            const drawLine = (value, type) => {
                const yPos = yAxis.getPixelForValue(value);
                if (yPos < yAxis.top || yPos > yAxis.bottom) return;

                const color = type === 'support' ? '#48bb78' : '#e53e3e';
                const sign = value >= 0 ? '+' : '';
                const label = `${sign}${value.toFixed(1)}%`;

                ctx.save();
                ctx.strokeStyle = color;
                ctx.lineWidth = 1;
                ctx.setLineDash([4, 4]);
                ctx.globalAlpha = 0.8;
                ctx.beginPath();
                ctx.moveTo(xAxis.left, yPos);
                ctx.lineTo(xAxis.right, yPos);
                ctx.stroke();

                // 绘制标签
                ctx.fillStyle = color;
                ctx.font = '10px sans-serif';
                ctx.textAlign = 'right';
                ctx.textBaseline = 'middle';
                ctx.fillText(label, xAxis.right - 4, yPos - 8);
                ctx.restore();
            };

            srData.supports.forEach(s => drawLine(s.value, 'support'));
            srData.resistances.forEach(r => drawLine(r.value, 'resistance'));
        }
    },

    // 买卖点信号插件
    tradeSignalPlugin: {
        id: 'tradeSignal',
        afterDatasetsDraw(chart) {
            try {
                // 检查 BS 信号开关状态
                if (chart._showBSSignals === false) {
                    return;
                }

                const signalData = chart._tradeSignals;
                if (!signalData || (!signalData.buySignals && !signalData.sellSignals)) {
                    return;
                }

                // 验证必要的chart属性
                if (!chart.ctx || !chart.scales || !chart.scales.y || !chart.scales.x) {
                    console.warn('[tradeSignalPlugin] 图表scales不可用');
                    return;
                }

                const ctx = chart.ctx;
                const yAxis = chart.scales.y;
                const xAxis = chart.scales.x;

            // 初始化存储位置数据
            if (!chart._tradeSignals.positions) {
                chart._tradeSignals.positions = [];
            }
            chart._tradeSignals.positions = [];
            ctx.save();

            // 绘制买点信号（绿色 B 字母带外框）
            if (signalData.buySignals) {
                signalData.buySignals.forEach((signal, i) => {
                    const datasetIndex = signal.datasetIndex;
                    const dataset = chart.data.datasets[datasetIndex];
                    if (!dataset || !dataset._changePctData) return;

                    // 检查 dataset 是否被隐藏
                    const meta = chart.getDatasetMeta(datasetIndex);
                    if (meta.hidden) return;

                    // 获取该数据点的累计涨幅值
                    const changePct = dataset._changePctData[signal.index];
                    if (changePct === null || changePct === undefined) return;

                    const xPos = xAxis.getPixelForValue(signal.index);
                    const yPos = yAxis.getPixelForValue(changePct);
                    const centerY = yPos + 14;
                    const radius = 8;

                    // 绘制圆形外框
                    ctx.strokeStyle = '#22c55e';
                    ctx.lineWidth = 1.5;
                    ctx.beginPath();
                    ctx.arc(xPos, centerY, radius, 0, Math.PI * 2);
                    ctx.stroke();

                    // 绘制 B 字母
                    ctx.fillStyle = '#22c55e';
                    ctx.font = 'bold 10px Arial';
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.fillText('B', xPos, centerY);

                    // 存储标记位置用于点击检测
                    chart._tradeSignals.positions.push({
                        x: xPos,
                        y: centerY,
                        signal: signal,
                        radius: radius + 2
                    });
                });
            }

            // 绘制卖点信号（红色 S 字母带外框）
            if (signalData.sellSignals) {
                signalData.sellSignals.forEach((signal, i) => {
                    const datasetIndex = signal.datasetIndex;
                    const dataset = chart.data.datasets[datasetIndex];
                    if (!dataset || !dataset._changePctData) return;

                    // 检查 dataset 是否被隐藏
                    const meta = chart.getDatasetMeta(datasetIndex);
                    if (meta.hidden) return;

                    // 获取该数据点的累计涨幅值
                    const changePct = dataset._changePctData[signal.index];
                    if (changePct === null || changePct === undefined) return;

                    const xPos = xAxis.getPixelForValue(signal.index);
                    const yPos = yAxis.getPixelForValue(changePct);
                    const centerY = yPos - 14;
                    const radius = 8;

                    // 绘制圆形外框
                    ctx.strokeStyle = '#ef4444';
                    ctx.lineWidth = 1.5;
                    ctx.beginPath();
                    ctx.arc(xPos, centerY, radius, 0, Math.PI * 2);
                    ctx.stroke();

                    // 绘制 S 字母
                    ctx.fillStyle = '#ef4444';
                    ctx.font = 'bold 10px Arial';
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.fillText('S', xPos, centerY);

                    // 存储标记位置用于点击检测
                    chart._tradeSignals.positions.push({
                        x: xPos,
                        y: centerY,
                        signal: signal,
                        radius: radius + 2
                    });
                });
            }

                ctx.restore();
            } catch (error) {
                console.error('[tradeSignalPlugin] 绘制失败:', error);
                // 确保restore canvas状态,即使出错
                try {
                    chart.ctx.restore();
                } catch (e) {
                    // 忽略restore错误
                }
            }
        }
    },

    // 绑定信号点击事件
    bindSignalClickListener(chart, canvasId) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) {
            console.warn('[Charts] 未找到canvas:', canvasId);
            return;
        }

        // 移除旧的监听器
        if (canvas._signalClickListener) {
            canvas.removeEventListener('click', canvas._signalClickListener);
        }

        const self = this;
        const clickHandler = (event) => {
            if (!chart._tradeSignals || !chart._tradeSignals.positions) return;

            const rect = canvas.getBoundingClientRect();
            const x = event.clientX - rect.left;
            const y = event.clientY - rect.top;

            for (const pos of chart._tradeSignals.positions) {
                const distance = Math.sqrt(Math.pow(x - pos.x, 2) + Math.pow(y - pos.y, 2));
                if (distance <= pos.radius) {
                    self.showSignalModal(pos.signal);
                    return;
                }
            }
        };

        canvas.addEventListener('click', clickHandler);
        canvas._signalClickListener = clickHandler;

        // Hover效果
        if (canvas._signalHoverListener) {
            canvas.removeEventListener('mousemove', canvas._signalHoverListener);
        }

        const hoverHandler = (event) => {
            if (!chart._tradeSignals || !chart._tradeSignals.positions) return;

            const rect = canvas.getBoundingClientRect();
            const x = event.clientX - rect.left;
            const y = event.clientY - rect.top;

            let isHovering = false;
            for (const pos of chart._tradeSignals.positions) {
                const distance = Math.sqrt(Math.pow(x - pos.x, 2) + Math.pow(y - pos.y, 2));
                if (distance <= pos.radius) {
                    isHovering = true;
                    break;
                }
            }
            canvas.style.cursor = isHovering ? 'pointer' : 'default';
        };

        canvas.addEventListener('mousemove', hoverHandler);
        canvas._signalHoverListener = hoverHandler;
    },

    // 显示信号详情弹窗
    showSignalModal(signal) {
        const signalType = signal.type === 'buy' ? '买入信号' : '卖出信号';
        const dateStr = signal.date ? signal.date.substring(5) : '';
        const badgeClass = signal.type === 'buy' ? 'text-success' : 'text-danger';

        // 尝试使用已有的模态框，如果没有则创建临时提示
        let modal = document.getElementById('signalModal');
        if (!modal) {
            // 创建一个简单的提示框
            const existingToast = document.getElementById('signalToast');
            if (existingToast) existingToast.remove();

            const toast = document.createElement('div');
            toast.id = 'signalToast';
            toast.className = 'position-fixed top-50 start-50 translate-middle bg-white p-3 rounded shadow-lg';
            toast.style.zIndex = '9999';
            toast.style.minWidth = '280px';
            toast.innerHTML = `
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <strong class="${badgeClass}">${signalType}</strong>
                    <button type="button" class="btn-close" onclick="this.closest('#signalToast').remove()"></button>
                </div>
                <div class="mb-2"><strong>${signal.stockName}</strong> <small class="text-muted">${dateStr}</small></div>
                <div class="mb-1"><strong>${signal.name}</strong></div>
                <div class="small text-muted">${signal.description}</div>
            `;
            document.body.appendChild(toast);

            setTimeout(() => {
                const t = document.getElementById('signalToast');
                if (t) t.remove();
            }, 5000);
            return;
        }

        // 使用现有的模态框
        const modalHeader = modal.querySelector('.modal-header .signal-type-badge');
        if (modalHeader) {
            const badgeClassModal = signal.type === 'buy' ? 'buy' : 'sell';
            modalHeader.className = `signal-type-badge ${badgeClassModal}`;
            modalHeader.innerHTML = `<strong>${signalType}</strong> ${signal.stockName} <span style="font-size: 0.85em; opacity: 0.8;">${dateStr}</span>`;
        }

        const signalList = modal.querySelector('.signal-list');
        if (signalList) {
            signalList.innerHTML = `
                <div class="signal-item">
                    <div class="signal-name">${signal.name}</div>
                    <div class="signal-desc">${signal.description}</div>
                </div>
            `;
        }

        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
    },

    init() {
        this.bindEvents();
    },

    bindEvents() {
        // 股票名称点击事件由 main.js 处理
    },

    // 渲染仓位饼图（带引导线）
    renderPositionPieChart(positions) {
        const canvas = document.getElementById('positionPieChart');
        if (!canvas) return;

        if (this.pieChart) {
            this.pieChart.destroy();
        }

        if (!positions || positions.length === 0) {
            canvas.parentElement.innerHTML = '<div class="chart-empty">暂无持仓数据</div>';
            return;
        }

        const labels = positions.map(p => p.stock_name);
        const data = positions.map(p => p.current_price * p.quantity);
        const colors = this.generateColors(positions.length);

        this.pieChart = new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: colors,
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: {
                    padding: { left: 80, right: 80, top: 40, bottom: 40 }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                const value = ctx.raw;
                                const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                                const pct = ((value / total) * 100).toFixed(1);
                                return `${ctx.label}: ¥${value.toFixed(2)} (${pct}%)`;
                            }
                        }
                    }
                }
            },
            plugins: [this.leaderLinePlugin]
        });
    },

    // 渲染每日收益饼图（使用每日收益明细数据）
    renderDailyProfitPieChart(dailyProfitBreakdown) {
        const canvas = document.getElementById('profitPieChart');
        if (!canvas) return;

        if (this.profitChart) {
            this.profitChart.destroy();
        }

        if (!dailyProfitBreakdown || dailyProfitBreakdown.length === 0) {
            canvas.parentElement.innerHTML = '<div class="chart-empty">暂无每日收益数据</div>';
            return;
        }

        // 过滤掉 daily_profit 为 0 或 null 的数据
        const profitData = dailyProfitBreakdown
            .filter(p => p.daily_profit !== null && p.daily_profit !== 0)
            .map(p => ({
                name: p.stock_name,
                profit: p.daily_profit,
                absProfit: Math.abs(p.daily_profit)
            }));

        if (profitData.length === 0) {
            canvas.parentElement.innerHTML = '<div class="chart-empty">暂无每日收益数据</div>';
            return;
        }

        // 按绝对值排序
        profitData.sort((a, b) => b.absProfit - a.absProfit);

        const labels = profitData.map(p => p.name);
        const data = profitData.map(p => p.absProfit);
        // 盈利绿色，亏损红色
        const colors = profitData.map(p => p.profit >= 0 ? '#48bb78' : '#e53e3e');

        this.profitChart = new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: colors,
                    borderWidth: 1,
                    profitValues: profitData.map(p => p.profit)
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: {
                    padding: { left: 80, right: 80, top: 40, bottom: 40 }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                const profit = ctx.dataset.profitValues[ctx.dataIndex];
                                const sign = profit >= 0 ? '+' : '';
                                return `${ctx.label}: ${sign}${profit.toFixed(2)}`;
                            }
                        }
                    }
                }
            },
            plugins: [this.profitLeaderLinePlugin]
        });
    },

    // 收益饼图专用引导线插件（显示实际收益值，带防重叠）
    profitLeaderLinePlugin: {
        id: 'profitLeaderLines',
        afterDraw(chart, args, options) {
            const ctx = chart.ctx;
            const chartArea = chart.chartArea;
            const centerX = (chartArea.left + chartArea.right) / 2;
            const centerY = (chartArea.top + chartArea.bottom) / 2;
            const lineHeight = 14;

            chart.data.datasets.forEach((dataset, i) => {
                const meta = chart.getDatasetMeta(i);
                if (!meta.data.length) return;

                // 收集所有标签位置
                const leftLabels = [];
                const rightLabels = [];

                meta.data.forEach((arc, index) => {
                    if (dataset.data[index] === 0) return;

                    const profit = dataset.profitValues[index];
                    const label = chart.data.labels[index];
                    const sign = profit >= 0 ? '+' : '';
                    const text = `${label} ${sign}${profit.toFixed(0)}`;

                    const midAngle = (arc.startAngle + arc.endAngle) / 2;
                    const outerRadius = arc.outerRadius;
                    const startX = centerX + Math.cos(midAngle) * outerRadius;
                    const startY = centerY + Math.sin(midAngle) * outerRadius;
                    const midX = centerX + Math.cos(midAngle) * (outerRadius + 15);
                    const midY = centerY + Math.sin(midAngle) * (outerRadius + 15);
                    const isRight = midAngle > -Math.PI / 2 && midAngle < Math.PI / 2;

                    const labelData = { index, profit, text, startX, startY, midX, midY, isRight, color: dataset.backgroundColor[index] };
                    (isRight ? rightLabels : leftLabels).push(labelData);
                });

                // 防重叠：按Y排序后调整位置
                [leftLabels, rightLabels].forEach(labels => {
                    labels.sort((a, b) => a.midY - b.midY);
                    for (let j = 1; j < labels.length; j++) {
                        const prev = labels[j - 1];
                        const curr = labels[j];
                        if (curr.midY - prev.midY < lineHeight) {
                            curr.midY = prev.midY + lineHeight;
                        }
                    }
                });

                // 绘制
                [...leftLabels, ...rightLabels].forEach(l => {
                    const endX = l.isRight ? l.midX + 20 : l.midX - 20;

                    ctx.save();
                    ctx.strokeStyle = l.color;
                    ctx.lineWidth = 1;
                    ctx.beginPath();
                    ctx.moveTo(l.startX, l.startY);
                    ctx.lineTo(l.midX, l.midY);
                    ctx.lineTo(endX, l.midY);
                    ctx.stroke();

                    ctx.fillStyle = l.profit >= 0 ? '#48bb78' : '#e53e3e';
                    ctx.font = '11px sans-serif';
                    ctx.textAlign = l.isRight ? 'left' : 'right';
                    ctx.textBaseline = 'middle';
                    ctx.fillText(l.text, l.isRight ? endX + 4 : endX - 4, l.midY);
                    ctx.restore();
                });
            });
        }
    },

    // 渲染分类持仓饼图
    renderCategoryPieChart(positions, stockCategories, categoryTree = null) {
        const canvas = document.getElementById('categoryPieChart');
        if (!canvas) return;

        // 缓存数据
        if (positions) this.categoryData.positions = positions;
        if (stockCategories) this.categoryData.stockCategories = stockCategories;
        if (categoryTree) this.categoryData.categoryTree = categoryTree;

        // 使用缓存数据
        positions = this.categoryData.positions;
        stockCategories = this.categoryData.stockCategories;

        if (this.categoryChart) {
            this.categoryChart.destroy();
        }

        const container = canvas.parentElement;
        // 移除旧的返回按钮
        const oldBtn = container.querySelector('.chart-back-btn');
        if (oldBtn) oldBtn.remove();

        if (!positions || positions.length === 0) {
            container.innerHTML = '<div class="chart-empty">暂无持仓数据</div>';
            return;
        }

        const parentId = this.categoryData.currentParentId;
        const { labels, data, categoryIds, hasChildren } = this.aggregateCategoryData(positions, stockCategories, parentId);

        if (labels.length === 0) {
            container.innerHTML = '<div class="chart-empty">暂无分类数据</div>';
            return;
        }

        // 如果在二级分类视图，添加返回按钮
        if (parentId !== null) {
            const backBtn = document.createElement('button');
            backBtn.className = 'chart-back-btn';
            backBtn.textContent = '← 返回';
            backBtn.onclick = () => {
                this.categoryData.currentParentId = null;
                this.renderCategoryPieChart();
            };
            container.appendChild(backBtn);
        }

        const colors = this.generateColors(labels.length);

        this.categoryChart = new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: colors,
                    borderWidth: 1,
                    categoryIds: categoryIds,
                    hasChildren: hasChildren
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: {
                    padding: { left: 80, right: 80, top: 40, bottom: 40 }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                const value = ctx.raw;
                                const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                                const pct = ((value / total) * 100).toFixed(1);
                                const hint = ctx.dataset.hasChildren[ctx.dataIndex] ? ' (点击展开)' : '';
                                return `${ctx.label}: ¥${value.toFixed(2)} (${pct}%)${hint}`;
                            }
                        }
                    }
                },
                onClick: (e, elements) => {
                    if (elements.length > 0) {
                        const idx = elements[0].index;
                        const dataset = this.categoryChart.data.datasets[0];
                        const catId = dataset.categoryIds[idx];
                        const canDrill = dataset.hasChildren[idx];
                        if (canDrill && catId !== null) {
                            this.categoryData.currentParentId = catId;
                            this.renderCategoryPieChart();
                        }
                    }
                }
            },
            plugins: [this.leaderLinePlugin]
        });
    },

    // 汇总分类数据
    aggregateCategoryData(positions, stockCategories, parentId) {
        const categoryTree = this.categoryData.categoryTree || window.categoryTree || [];
        const categoryMap = {};  // { name: { value, id, hasChildren } }

        if (parentId === null) {
            // 按一级分类汇总
            positions.forEach(p => {
                const stockCat = stockCategories[p.stock_code];
                const marketValue = p.current_price * p.quantity;

                if (!stockCat || !stockCat.category_id) {
                    if (!categoryMap['未设板块']) {
                        categoryMap['未设板块'] = { value: 0, id: null, hasChildren: false };
                    }
                    categoryMap['未设板块'].value += marketValue;
                    return;
                }

                // 查找该分类的一级分类
                let parentName = null;
                let parentCatId = null;
                let hasChildrenFlag = false;

                for (const parent of categoryTree) {
                    if (parent.id === stockCat.category_id) {
                        parentName = parent.name;
                        parentCatId = parent.id;
                        hasChildrenFlag = parent.children && parent.children.length > 0;
                        break;
                    }
                    const child = (parent.children || []).find(c => c.id === stockCat.category_id);
                    if (child) {
                        parentName = parent.name;
                        parentCatId = parent.id;
                        hasChildrenFlag = parent.children && parent.children.length > 0;
                        break;
                    }
                }

                if (!parentName) {
                    parentName = '未设板块';
                    parentCatId = null;
                    hasChildrenFlag = false;
                }

                if (!categoryMap[parentName]) {
                    categoryMap[parentName] = { value: 0, id: parentCatId, hasChildren: hasChildrenFlag };
                }
                categoryMap[parentName].value += marketValue;
            });
        } else {
            // 按指定一级分类下的二级分类汇总
            const parentCat = categoryTree.find(c => c.id === parentId);
            if (!parentCat) return { labels: [], data: [], categoryIds: [], hasChildren: [] };

            const childrenIds = new Set((parentCat.children || []).map(c => c.id));
            childrenIds.add(parentId);  // 包含一级分类本身（无子分类时直接分配到一级）

            positions.forEach(p => {
                const stockCat = stockCategories[p.stock_code];
                if (!stockCat || !stockCat.category_id) return;
                if (!childrenIds.has(stockCat.category_id)) return;

                const marketValue = p.current_price * p.quantity;
                let catName = parentCat.name;

                if (stockCat.category_id !== parentId) {
                    const child = (parentCat.children || []).find(c => c.id === stockCat.category_id);
                    if (child) catName = child.name;
                }

                if (!categoryMap[catName]) {
                    categoryMap[catName] = { value: 0, id: stockCat.category_id, hasChildren: false };
                }
                categoryMap[catName].value += marketValue;
            });
        }

        const labels = Object.keys(categoryMap);
        const data = labels.map(l => categoryMap[l].value);
        const categoryIds = labels.map(l => categoryMap[l].id);
        const hasChildren = labels.map(l => categoryMap[l].hasChildren);

        return { labels, data, categoryIds, hasChildren };
    },

    // 渲染分类收益饼图
    renderCategoryProfitChart(dailyProfitData) {
        const canvas = document.getElementById('categoryProfitChart');
        if (!canvas) return;

        if (this.categoryProfitChart) {
            this.categoryProfitChart.destroy();
        }

        if (!dailyProfitData || !dailyProfitData.categories || dailyProfitData.categories.length === 0) {
            canvas.parentElement.innerHTML = '<div class="chart-empty">暂无分类收益数据</div>';
            return;
        }

        const categories = dailyProfitData.categories;
        const labels = categories.map(c => c.name);
        const data = categories.map(c => Math.abs(c.profit));
        const profits = categories.map(c => c.profit);
        const colors = categories.map(c => c.profit >= 0 ? '#48bb78' : '#e53e3e');

        this.categoryProfitChart = new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: colors,
                    borderWidth: 1,
                    profitValues: profits
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: {
                    padding: { left: 80, right: 80, top: 40, bottom: 40 }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                const profit = ctx.dataset.profitValues[ctx.dataIndex];
                                const sign = profit >= 0 ? '+' : '';
                                return `${ctx.label}: ${sign}${profit.toFixed(2)}`;
                            }
                        }
                    }
                }
            },
            plugins: [this.categoryProfitLeaderLinePlugin]
        });
    },

    // 分类收益图引导线插件
    categoryProfitLeaderLinePlugin: {
        id: 'categoryProfitLeaderLines',
        afterDraw(chart, args, options) {
            const ctx = chart.ctx;
            const chartArea = chart.chartArea;
            const centerX = (chartArea.left + chartArea.right) / 2;
            const centerY = (chartArea.top + chartArea.bottom) / 2;
            const lineHeight = 14;

            chart.data.datasets.forEach((dataset, i) => {
                const meta = chart.getDatasetMeta(i);
                if (!meta.data.length) return;

                const leftLabels = [];
                const rightLabels = [];

                meta.data.forEach((arc, index) => {
                    if (dataset.data[index] === 0) return;

                    const profit = dataset.profitValues[index];
                    const label = chart.data.labels[index];
                    const sign = profit >= 0 ? '+' : '';
                    const text = `${label} ${sign}${profit.toFixed(0)}`;

                    const midAngle = (arc.startAngle + arc.endAngle) / 2;
                    const outerRadius = arc.outerRadius;
                    const startX = centerX + Math.cos(midAngle) * outerRadius;
                    const startY = centerY + Math.sin(midAngle) * outerRadius;
                    const midX = centerX + Math.cos(midAngle) * (outerRadius + 15);
                    const midY = centerY + Math.sin(midAngle) * (outerRadius + 15);
                    const isRight = midAngle > -Math.PI / 2 && midAngle < Math.PI / 2;

                    const labelData = { index, profit, text, startX, startY, midX, midY, isRight, color: dataset.backgroundColor[index] };
                    (isRight ? rightLabels : leftLabels).push(labelData);
                });

                [leftLabels, rightLabels].forEach(labels => {
                    labels.sort((a, b) => a.midY - b.midY);
                    for (let j = 1; j < labels.length; j++) {
                        const prev = labels[j - 1];
                        const curr = labels[j];
                        if (curr.midY - prev.midY < lineHeight) {
                            curr.midY = prev.midY + lineHeight;
                        }
                    }
                });

                [...leftLabels, ...rightLabels].forEach(l => {
                    const endX = l.isRight ? l.midX + 20 : l.midX - 20;

                    ctx.save();
                    ctx.strokeStyle = l.color;
                    ctx.lineWidth = 1;
                    ctx.beginPath();
                    ctx.moveTo(l.startX, l.startY);
                    ctx.lineTo(l.midX, l.midY);
                    ctx.lineTo(endX, l.midY);
                    ctx.stroke();

                    ctx.fillStyle = l.profit >= 0 ? '#48bb78' : '#e53e3e';
                    ctx.font = '11px sans-serif';
                    ctx.textAlign = l.isRight ? 'left' : 'right';
                    ctx.textBaseline = 'middle';
                    ctx.fillText(l.text, l.isRight ? endX + 4 : endX - 4, l.midY);
                    ctx.restore();
                });
            });
        }
    },

    // 渲染每日盈亏柱状图
    renderDailyProfitBarChart(profitHistory) {
        const canvas = document.getElementById('dailyProfitBarChart');
        if (!canvas) return;

        if (this.dailyProfitBarChart) {
            this.dailyProfitBarChart.destroy();
        }

        if (!profitHistory || !profitHistory.daily_profits || profitHistory.daily_profits.length === 0) {
            canvas.parentElement.innerHTML = '<div class="chart-empty">暂无收益数据</div>';
            return;
        }

        if (!window.ProfitCharts) {
            console.warn('ProfitCharts not loaded');
            return;
        }

        this.dailyProfitBarChart = window.ProfitCharts.renderDailyProfitBar(
            'dailyProfitBarChart',
            profitHistory.daily_profits
        );
    },

    // 渲染累计收益趋势图
    renderCumulativeProfitChart(profitHistory) {
        const canvas = document.getElementById('cumulativeProfitChart');
        if (!canvas) return;

        if (this.cumulativeProfitChart) {
            this.cumulativeProfitChart.destroy();
        }

        if (!profitHistory || !profitHistory.cumulative_profits || profitHistory.cumulative_profits.length === 0) {
            canvas.parentElement.innerHTML = '<div class="chart-empty">暂无累计收益数据</div>';
            return;
        }

        if (!window.ProfitCharts) {
            console.warn('ProfitCharts not loaded');
            return;
        }

        this.cumulativeProfitChart = window.ProfitCharts.renderCumulativeLine(
            'cumulativeProfitChart',
            profitHistory.cumulative_profits
        );
    },

    // 打开股票详情弹窗
    async openStockDetailModal(stockCode, stockName) {
        const modal = document.getElementById('stockDetailModal');
        if (!modal) return;

        document.getElementById('stockDetailTitle').textContent = `${stockName} (${stockCode})`;

        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();

        // 清空现有图表
        ['quantityChart', 'profitChart', 'positionChart', 'priceChart'].forEach(id => {
            if (this.detailCharts[id]) {
                this.detailCharts[id].destroy();
            }
        });

        const response = await fetch(`/positions/stock-history/${stockCode}?days=30`);
        if (!response.ok) {
            console.error('获取历史数据失败');
            return;
        }

        const data = await response.json();
        if (!data.history || data.history.length === 0) {
            return;
        }

        const labels = data.history.map(h => h.date);

        // 持仓数量图
        this.renderLineChart('quantityChart', labels,
            data.history.map(h => h.quantity), '持仓数量', '#4299e1');

        // 盈亏图
        this.renderLineChart('profitChart', labels,
            data.history.map(h => h.profit), '盈亏', '#48bb78');

        // 仓位占比图
        this.renderLineChart('positionChart', labels,
            data.history.map(h => h.position_pct), '仓位占比 (%)', '#ed8936');

        // 股价K线图（含成本线）- 使用OHLC数据
        const ohlcData = data.ohlc || [];
        const ohlcLabels = ohlcData.map(d => d.date);
        const costPrice = data.history.length > 0 ? data.history[data.history.length - 1].cost_price : null;
        this.renderPriceChart('priceChart', ohlcLabels, ohlcData, costPrice);
    },

    // 渲染折线图
    renderLineChart(canvasId, labels, data, label, color) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        this.detailCharts[canvasId] = new Chart(canvas, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: label,
                    data: data,
                    borderColor: color,
                    backgroundColor: color + '20',
                    fill: true,
                    tension: 0.3,
                    pointRadius: data.length > 10 ? 2 : 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: { display: true, ticks: { font: { size: 10 } } },
                    y: { display: true, ticks: { font: { size: 10 } } }
                }
            }
        });
    },

    // 渲染股价K线图（含成本线）
    renderPriceChart(canvasId, labels, ohlcData, costPrice) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        // 成本价参考线插件
        const costLinePlugin = {
            id: 'costLine',
            beforeDraw(chart) {
                if (!costPrice) return;
                const ctx = chart.ctx;
                const yAxis = chart.scales.y;
                const xAxis = chart.scales.x;
                const yPos = yAxis.getPixelForValue(costPrice);

                if (yPos < yAxis.top || yPos > yAxis.bottom) return;

                ctx.save();
                ctx.strokeStyle = '#e53e3e';
                ctx.lineWidth = 1;
                ctx.setLineDash([5, 5]);
                ctx.beginPath();
                ctx.moveTo(xAxis.left, yPos);
                ctx.lineTo(xAxis.right, yPos);
                ctx.stroke();

                ctx.fillStyle = '#e53e3e';
                ctx.font = '10px sans-serif';
                ctx.textAlign = 'right';
                ctx.fillText(`成本${costPrice.toFixed(2)}`, xAxis.right - 4, yPos - 4);
                ctx.restore();
            }
        };

        // 单只股票的K线插件
        const singleCandlestickPlugin = {
            id: 'singleCandlestick',
            afterDatasetsDraw(chart) {
                const ctx = chart.ctx;
                const yAxis = chart.scales.y;
                const xAxis = chart.scales.x;
                const dataset = chart.data.datasets[0];
                if (!dataset._ohlcData) return;

                const ohlc = dataset._ohlcData;
                const barWidth = Math.max(4, (xAxis.width / ohlc.length) * 0.7);

                ohlc.forEach((d, index) => {
                    if (!d) return;
                    const x = xAxis.getPixelForValue(index);
                    const yOpen = yAxis.getPixelForValue(d.open);
                    const yHigh = yAxis.getPixelForValue(d.high);
                    const yLow = yAxis.getPixelForValue(d.low);
                    const yClose = yAxis.getPixelForValue(d.close);
                    const isRising = d.close >= d.open;

                    Charts.drawCandlestick(ctx, x, yOpen, yHigh, yLow, yClose, barWidth, null, isRising);
                });
            }
        };

        // 计算Y轴范围（包含成本价）
        const allPrices = ohlcData.flatMap(d => d ? [d.high, d.low] : []);
        if (costPrice) allPrices.push(costPrice);
        const minPrice = Math.min(...allPrices) * 0.98;
        const maxPrice = Math.max(...allPrices) * 1.02;

        this.detailCharts[canvasId] = new Chart(canvas, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: '股价',
                    data: ohlcData.map(d => d ? d.close : null),
                    borderColor: 'transparent',
                    backgroundColor: 'transparent',
                    pointRadius: 0,
                    _ohlcData: ohlcData
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => {
                                const d = ohlcData[ctx.dataIndex];
                                if (!d) return null;
                                return `开${d.open} 高${d.high} 低${d.low} 收${d.close}`;
                            }
                        }
                    }
                },
                scales: {
                    x: { display: true, ticks: { font: { size: 10 } } },
                    y: {
                        display: true,
                        min: minPrice,
                        max: maxPrice,
                        ticks: { font: { size: 10 } }
                    }
                }
            },
            plugins: [costLinePlugin, singleCandlestickPlugin]
        });
    },

    // 渲染迷你股价K线图
    async renderSparklines(positions) {
        for (const p of positions) {
            const canvas = document.getElementById(`sparkline-${p.stock_code}`);
            if (!canvas) continue;

            const cell = canvas.closest('.sparkline-cell');
            const costPrice = p.cost_price;
            const currentPrice = p.current_price;

            const response = await fetch(`/positions/stock-history/${p.stock_code}`);
            if (!response.ok) continue;

            const data = await response.json();
            const ohlcData = data.ohlc || [];
            if (ohlcData.length === 0) continue;

            const profitPct = ((currentPrice - costPrice) / costPrice * 100).toFixed(2);
            const isProfit = currentPrice >= costPrice;

            // 计算Y轴范围（包含成本价）
            const allPrices = ohlcData.flatMap(d => d ? [d.high, d.low] : []);
            allPrices.push(costPrice);
            const minPrice = Math.min(...allPrices) * 0.99;
            const maxPrice = Math.max(...allPrices) * 1.01;

            new Chart(canvas, {
                type: 'line',
                data: {
                    labels: ohlcData.map(d => d.date),
                    datasets: [
                        {
                            data: ohlcData.map(d => d.close),
                            borderColor: 'transparent',
                            backgroundColor: 'transparent',
                            pointRadius: 0,
                            _ohlcData: ohlcData
                        },
                        {
                            data: Array(ohlcData.length).fill(costPrice),
                            borderColor: '#e53e3e',
                            borderWidth: 1,
                            borderDash: [3, 3],
                            fill: false,
                            pointRadius: 0
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: { legend: { display: false }, tooltip: { enabled: false } },
                    scales: {
                        x: { display: false },
                        y: { display: false, min: minPrice, max: maxPrice }
                    },
                    elements: { point: { radius: 0 } }
                },
                plugins: [this.miniCandlestickPlugin]
            });

            // 在图表下方添加价格信息
            let priceInfo = cell.querySelector('.sparkline-price-info');
            if (!priceInfo) {
                priceInfo = document.createElement('div');
                priceInfo.className = 'sparkline-price-info';
                cell.appendChild(priceInfo);
            }
            const sign = isProfit ? '+' : '';
            priceInfo.innerHTML = `
                <span class="price-current">${currentPrice.toFixed(2)}</span>
                <span class="price-cost">成本:${costPrice.toFixed(2)}</span>
                <span class="price-pct ${isProfit ? 'profit' : 'loss'}">${sign}${profitPct}%</span>
            `;
        }
    },

    // 生成颜色
    generateColors(count) {
        const baseColors = [
            '#4299e1', '#48bb78', '#ed8936', '#9f7aea', '#f56565',
            '#38b2ac', '#667eea', '#ed64a6', '#ecc94b', '#4fd1c5'
        ];
        const colors = [];
        for (let i = 0; i < count; i++) {
            colors.push(baseColors[i % baseColors.length]);
        }
        return colors;
    },

    // 生成优化的颜色方案（用于走势图）
    generateHighContrastColors(count, stocks = []) {
        const colors = [];

        // 期货代码列表（包括贵金属期货和ETF）
        const futuresCodes = ['AU0', 'GLD', 'AG0', 'SLV', 'CU0', 'HG0', 'LME_CU', 'CPER', 'AL0', '159652.SZ', 'GC=F', 'SI=F', 'HG=F'];

        // 期货使用深色系（饱和度高、亮度低）
        const futuresColors = [
            '#b91c1c',  // 深红
            '#c2410c',  // 深橙
            '#a16207',  // 深黄
            '#15803d',  // 深绿
            '#0369a1',  // 深蓝
            '#6b21a8',  // 深紫
            '#831843',  // 深粉
            '#713f12',  // 深棕
            '#134e4a',  // 深青
            '#701a75',  // 深洋红
        ];

        // 股票使用柔和色系（饱和度中等、亮度适中）
        const stockColors = [
            '#ef4444',  // 柔和红
            '#f97316',  // 柔和橙
            '#f59e0b',  // 柔和黄
            '#10b981',  // 柔和绿
            '#3b82f6',  // 柔和蓝
            '#8b5cf6',  // 柔和紫
            '#ec4899',  // 柔和粉
            '#f97316',  // 柔和橙红
            '#14b8a6',  // 柔和青
            '#a855f7',  // 柔和洋紫
        ];

        let futuresIndex = 0;
        let stockIndex = 0;

        for (let i = 0; i < count; i++) {
            const stock = stocks[i];
            const stockCode = stock?.stock_code || stock?.code;

            // 判断是否为期货
            const isFutures = stockCode && (
                futuresCodes.includes(stockCode) ||
                stockCode.endsWith('=F') ||  // yfinance 期货格式
                (stock?.stock_name && (
                    stock.stock_name.includes('主连') ||
                    stock.stock_name.includes('期货') ||
                    stock.stock_name.includes('沪金') ||
                    stock.stock_name.includes('沪银') ||
                    stock.stock_name.includes('沪铜') ||
                    stock.stock_name.includes('沪铝')
                ))
            );

            if (isFutures) {
                colors.push(futuresColors[futuresIndex % futuresColors.length]);
                futuresIndex++;
            } else {
                colors.push(stockColors[stockIndex % stockColors.length]);
                stockIndex++;
            }
        }

        return colors;
    },

    // HSL转Hex
    hslToHex(h, s, l) {
        s /= 100;
        l /= 100;
        const c = (1 - Math.abs(2 * l - 1)) * s;
        const x = c * (1 - Math.abs((h / 60) % 2 - 1));
        const m = l - c / 2;
        let r = 0, g = 0, b = 0;
        if (h < 60) { r = c; g = x; b = 0; }
        else if (h < 120) { r = x; g = c; b = 0; }
        else if (h < 180) { r = 0; g = c; b = x; }
        else if (h < 240) { r = 0; g = x; b = c; }
        else if (h < 300) { r = x; g = 0; b = c; }
        else { r = c; g = 0; b = x; }
        const toHex = v => Math.round((v + m) * 255).toString(16).padStart(2, '0');
        return `#${toHex(r)}${toHex(g)}${toHex(b)}`;
    },

    // 渲染持仓走势图
    renderTrendChart(trendData, categoryFilter = 'all', canvasId = 'trendChart') {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return null;

        // 如果是默认的 trendChart，销毁旧图表
        if (canvasId === 'trendChart' && this.trendChart) {
            this.trendChart.destroy();
        }

        // 只对默认的 trendChart 进行缓存
        if (canvasId === 'trendChart') {
            if (trendData) {
                this.trendData = trendData;
            }
            trendData = this.trendData;
        }

        if (!trendData || !trendData.stocks || trendData.stocks.length === 0) {
            return null;
        }

        // 按分类筛选
        let filteredStocks = trendData.stocks;
        if (categoryFilter !== 'all') {
            if (categoryFilter === 'uncategorized') {
                filteredStocks = trendData.stocks.filter(s => !s.category_id);
            } else {
                const catId = parseInt(categoryFilter);
                const validIds = new Set([catId]);
                // 添加子分类ID
                if (window.categoryTree) {
                    for (const parent of window.categoryTree) {
                        if (parent.id === catId) {
                            for (const child of parent.children || []) {
                                validIds.add(child.id);
                            }
                            break;
                        }
                    }
                }
                filteredStocks = trendData.stocks.filter(s => validIds.has(s.category_id));
            }
        }

        if (filteredStocks.length === 0) {
            return null;
        }

        // 收集所有日期
        const allDates = new Set();
        filteredStocks.forEach(stock => {
            stock.data.forEach(d => allDates.add(d.date));
        });
        const sortedDates = Array.from(allDates).sort();

        // 为每只股票构建数据集（使用优化颜色方案）
        const colors = this.generateHighContrastColors(filteredStocks.length, filteredStocks);
        const datasets = filteredStocks.map((stock, idx) => {
            const dataMap = {};
            stock.data.forEach(d => {
                dataMap[d.date] = d.change_pct;
            });

            const color = colors[idx];
            const changePctData = sortedDates.map(date => dataMap[date] ?? null);
            return {
                label: stock.stock_name,
                data: changePctData,
                borderColor: color,
                backgroundColor: color + '20',
                fill: false,
                tension: 0.3,
                pointRadius: sortedDates.length > 20 ? 0 : 2,
                pointHoverRadius: 4,
                borderWidth: 2,
                _originalColor: color,
                _changePctData: changePctData  // 保存原始累计涨幅数据用于计算当天涨幅
            };
        });

        // 零线插件
        const zeroLinePlugin = {
            id: 'zeroLine',
            beforeDraw(chart) {
                const ctx = chart.ctx;
                const yAxis = chart.scales.y;
                const xAxis = chart.scales.x;

                if (yAxis.min <= 0 && yAxis.max >= 0) {
                    const yPos = yAxis.getPixelForValue(0);
                    ctx.save();
                    ctx.strokeStyle = '#adb5bd';
                    ctx.lineWidth = 1;
                    ctx.setLineDash([5, 5]);
                    ctx.beginPath();
                    ctx.moveTo(xAxis.left, yPos);
                    ctx.lineTo(xAxis.right, yPos);
                    ctx.stroke();
                    ctx.restore();
                }
            }
        };

        // 计算支撑/阻力线
        const srData = this.calculateSupportResistance(datasets);

        const chartInstance = new Chart(canvas, {
            type: 'line',
            data: {
                labels: sortedDates.map(d => d.substring(5)),
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: {
                    padding: { right: 60 }
                },
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                onHover: (event, elements, chart) => {
                    if (elements.length > 0) {
                        const hoveredIndex = elements[0].datasetIndex;
                        chart.data.datasets.forEach((ds, i) => {
                            if (chart.getDatasetMeta(i).hidden) return;
                            ds.borderWidth = i === hoveredIndex ? 3 : 2;
                            ds.borderColor = i === hoveredIndex
                                ? ds._originalColor
                                : ds._originalColor + '4D';
                        });
                        chart.update('none');
                    } else {
                        chart.data.datasets.forEach((ds) => {
                            ds.borderWidth = 2;
                            ds.borderColor = ds._originalColor;
                        });
                        chart.update('none');
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        // 按当天涨幅排序
                        itemSort: (a, b) => {
                            const dataIndex = a.dataIndex;
                            // 计算当天涨幅
                            const getDailyChange = (item) => {
                                const ds = item.dataset;
                                const data = ds._changePctData || ds.data;
                                const curr = data[dataIndex];
                                if (curr === null || curr === undefined) return -Infinity;
                                if (dataIndex === 0) return curr;
                                const prev = data[dataIndex - 1];
                                if (prev === null || prev === undefined) return curr;
                                return curr - prev;
                            };
                            return getDailyChange(b) - getDailyChange(a);  // 降序排列
                        },
                        callbacks: {
                            title: (items) => {
                                if (items.length > 0) {
                                    const idx = items[0].dataIndex;
                                    return sortedDates[idx];
                                }
                                return '';
                            },
                            label: (ctx) => {
                                const ds = ctx.dataset;
                                const data = ds._changePctData || ds.data;
                                const dataIndex = ctx.dataIndex;
                                const curr = data[dataIndex];
                                if (curr === null || curr === undefined) return null;

                                // 计算当天涨幅（当前累计涨幅 - 前一天累计涨幅）
                                let dailyChange;
                                if (dataIndex === 0) {
                                    dailyChange = curr;
                                } else {
                                    const prev = data[dataIndex - 1];
                                    if (prev === null || prev === undefined) {
                                        dailyChange = curr;
                                    } else {
                                        dailyChange = curr - prev;
                                    }
                                }

                                const sign = dailyChange >= 0 ? '+' : '';
                                let result = `${ds.label}: ${sign}${dailyChange.toFixed(2)}%`;

                                // 显示相对差值和排名
                                if (ds.stock) {
                                    if (ds.stock.relative_diff !== undefined) {
                                        const diffSign = ds.stock.relative_diff >= 0 ? '+' : '';
                                        result += ` (相对:${diffSign}${ds.stock.relative_diff.toFixed(1)}%)`;
                                    }
                                    if (ds.stock.rank) {
                                        result += ` [${ds.stock.rank}]`;
                                    }
                                }
                                return result;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        display: true,
                        ticks: {
                            font: { size: 10 },
                            maxRotation: 45,
                            minRotation: 0
                        },
                        grid: {
                            display: false
                        }
                    },
                    y: {
                        display: true,
                        ticks: {
                            font: { size: 10 },
                            callback: (value) => `${value >= 0 ? '+' : ''}${value}%`
                        },
                        grid: {
                            color: '#e9ecef'
                        }
                    }
                }
            },
            plugins: [zeroLinePlugin, this.trendEndLabelPlugin, this.supportResistancePlugin, this.tradeSignalPlugin]
        });

        // 存储支撑/阻力线数据到 chart 实例
        chartInstance._supportResistanceData = srData;
        // 存储日期数组用于信号索引映射
        chartInstance._sortedDates = sortedDates;

        // 只对默认的 trendChart 存储引用
        if (canvasId === 'trendChart') {
            this.trendChart = chartInstance;
        }

        // 点击标签切换显示/隐藏
        canvas.addEventListener('click', (e) => {
            const chart = Chart.getChart(canvas);
            if (!chart || !chart._labelPositions) return;

            const rect = canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            for (const label of chart._labelPositions) {
                if (x >= label.x && x <= label.x + label.width &&
                    y >= label.y && y <= label.y + label.height) {
                    const meta = chart.getDatasetMeta(label.index);
                    meta.hidden = !meta.hidden;
                    chart.update();
                    break;
                }
            }
        });

        return chartInstance;
    },

    // 加载走势数据
    async loadTrendData(date, category = 'all') {
        const container = document.querySelector('.trend-chart-canvas-wrapper');
        if (!container) return;

        container.innerHTML = '<div class="skeleton skeleton-chart" style="height:280px"></div>';

        const response = await fetch(`/positions/api/trend-data?date=${date}&category=${category}`);
        if (!response.ok) {
            container.innerHTML = '<div class="chart-empty">加载失败</div>';
            return;
        }

        const data = await response.json();
        container.innerHTML = '<canvas id="trendChart"></canvas>';
        this.trendData = data;
        this.renderTrendChart(data, category);
    },

    // 渲染合并走势图（股票+期货）- K线图
    renderCombinedTrendChart(trendData) {
        const wrapper = document.getElementById('combinedTrendChartWrapper');
        if (!wrapper) return;

        if (this.combinedTrendChart) {
            this.combinedTrendChart.destroy();
        }

        if (!trendData || !trendData.stocks || trendData.stocks.length === 0) {
            wrapper.innerHTML = '<div class="chart-empty">暂无走势数据</div>';
            return;
        }

        // 创建 canvas
        wrapper.innerHTML = '<canvas id="combinedTrendChart"></canvas>';
        const canvas = document.getElementById('combinedTrendChart');

        // 收集所有日期
        const allDates = new Set();
        trendData.stocks.forEach(stock => {
            stock.data.forEach(d => allDates.add(d.date));
        });
        const sortedDates = Array.from(allDates).sort();

        // 为每只股票/期货构建数据集（K线数据）
        const colors = this.generateHighContrastColors(trendData.stocks.length, trendData.stocks);
        const datasets = trendData.stocks.map((stock, idx) => {
            const dataMap = {};
            const ohlcMap = {};
            stock.data.forEach(d => {
                dataMap[d.date] = d.change_pct;
                ohlcMap[d.date] = {
                    open: d.open,
                    high: d.high,
                    low: d.low,
                    close: d.close,
                    change_pct: d.change_pct
                };
            });

            const color = colors[idx];
            return {
                label: stock.stock_name,
                data: sortedDates.map(date => dataMap[date] ?? null),
                borderColor: 'transparent',
                backgroundColor: 'transparent',
                fill: false,
                pointRadius: 0,
                pointHoverRadius: 0,
                borderWidth: 0,
                _originalColor: color,
                _ohlcData: sortedDates.map(date => ohlcMap[date] || null)
            };
        });

        // 零线插件
        const zeroLinePlugin = {
            id: 'zeroLine',
            beforeDraw(chart) {
                const ctx = chart.ctx;
                const yAxis = chart.scales.y;
                const xAxis = chart.scales.x;

                if (yAxis.min <= 0 && yAxis.max >= 0) {
                    const yPos = yAxis.getPixelForValue(0);
                    ctx.save();
                    ctx.strokeStyle = '#adb5bd';
                    ctx.lineWidth = 1;
                    ctx.setLineDash([5, 5]);
                    ctx.beginPath();
                    ctx.moveTo(xAxis.left, yPos);
                    ctx.lineTo(xAxis.right, yPos);
                    ctx.stroke();
                    ctx.restore();
                }
            }
        };

        // 计算支撑/阻力线
        const srData = this.calculateSupportResistance(datasets);

        this.combinedTrendChart = new Chart(canvas, {
            type: 'line',
            data: {
                labels: sortedDates.map(d => d.substring(5)),
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: {
                    padding: { right: 60 }
                },
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: (items) => {
                                if (items.length > 0) {
                                    const idx = items[0].dataIndex;
                                    return sortedDates[idx];
                                }
                                return '';
                            },
                            label: (ctx) => {
                                const ohlc = ctx.dataset._ohlcData?.[ctx.dataIndex];
                                if (!ohlc) return null;
                                const sign = ohlc.change_pct >= 0 ? '+' : '';
                                return `${ctx.dataset.label}: 开${ohlc.open} 高${ohlc.high} 低${ohlc.low} 收${ohlc.close} (${sign}${ohlc.change_pct.toFixed(2)}%)`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        display: true,
                        ticks: {
                            font: { size: 10 },
                            maxRotation: 45,
                            minRotation: 0
                        },
                        grid: {
                            display: false
                        }
                    },
                    y: {
                        display: true,
                        ticks: {
                            font: { size: 10 },
                            callback: (value) => `${value >= 0 ? '+' : ''}${value}%`
                        },
                        grid: {
                            color: '#e9ecef'
                        }
                    }
                }
            },
            plugins: [zeroLinePlugin, this.miniCandlestickPlugin, this.trendEndLabelPlugin, this.supportResistancePlugin]
        });

        // 存储支撑/阻力线数据到 chart 实例
        this.combinedTrendChart._supportResistanceData = srData;

        // 点击标签切换显示/隐藏
        canvas.addEventListener('click', (e) => {
            const chart = this.combinedTrendChart;
            if (!chart || !chart._labelPositions) return;

            const rect = canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            for (const label of chart._labelPositions) {
                if (x >= label.x && x <= label.x + label.width &&
                    y >= label.y && y <= label.y + label.height) {
                    const meta = chart.getDatasetMeta(label.index);
                    meta.hidden = !meta.hidden;
                    chart.update();
                    break;
                }
            }
        });
    },

    // 加载合并走势数据
    async loadCombinedTrendData(date) {
        const wrapper = document.getElementById('combinedTrendChartWrapper');
        if (!wrapper) return;

        wrapper.innerHTML = '<div class="chart-loading">加载走势数据中...</div>';

        const response = await fetch(`/positions/api/combined-trend-data?date=${date}`);
        if (!response.ok) {
            wrapper.innerHTML = '<div class="chart-empty">加载失败</div>';
            return;
        }

        const data = await response.json();
        if (!data.stocks || data.stocks.length === 0) {
            wrapper.innerHTML = '<div class="chart-empty">暂无走势数据</div>';
            return;
        }

        this.trendData = data;  // 缓存数据供迷你图使用
        this.renderCombinedTrendChart(data);
        this.renderMiniCandlesticks(data);  // 渲染持仓列表迷你K线图
    },

    // 计算支撑线和阻力线
    calculateSupportResistance(datasets) {
        if (!datasets || datasets.length === 0) return { supports: [], resistances: [] };

        // 收集所有数据点
        const allPoints = [];
        datasets.forEach(ds => {
            if (!ds.data) return;
            ds.data.forEach((val, idx) => {
                if (val !== null && val !== undefined) {
                    allPoints.push({ value: val, index: idx });
                }
            });
        });

        if (allPoints.length < 5) return { supports: [], resistances: [] };

        // 找出所有数据集中的局部极值点
        const supports = [];
        const resistances = [];

        datasets.forEach(ds => {
            if (!ds.data || ds.data.length < 3) return;
            const data = ds.data.filter(v => v !== null && v !== undefined);
            if (data.length < 3) return;

            for (let i = 1; i < data.length - 1; i++) {
                const prev = data[i - 1];
                const curr = data[i];
                const next = data[i + 1];

                // 局部最小值 -> 支撑候选
                if (curr < prev && curr < next) {
                    supports.push(curr);
                }
                // 局部最大值 -> 阻力候选
                if (curr > prev && curr > next) {
                    resistances.push(curr);
                }
            }
        });

        // 计算Y轴范围用于聚类阈值
        const allValues = allPoints.map(p => p.value);
        const minVal = Math.min(...allValues);
        const maxVal = Math.max(...allValues);
        const range = maxVal - minVal;
        const threshold = range * 0.02;

        // 聚类合并相近价位
        const clusterAndRank = (points) => {
            if (points.length === 0) return [];

            points.sort((a, b) => a - b);
            const clusters = [];
            let cluster = [points[0]];

            for (let i = 1; i < points.length; i++) {
                if (points[i] - cluster[cluster.length - 1] <= threshold) {
                    cluster.push(points[i]);
                } else {
                    clusters.push(cluster);
                    cluster = [points[i]];
                }
            }
            clusters.push(cluster);

            // 计算每个聚类的代表值和强度
            return clusters.map(c => ({
                value: c.reduce((a, b) => a + b, 0) / c.length,
                strength: c.length
            })).sort((a, b) => b.strength - a.strength).slice(0, 3);
        };

        return {
            supports: clusterAndRank(supports),
            resistances: clusterAndRank(resistances)
        };
    },

    // 切换支撑/阻力线显示
    toggleSupportResistance() {
        const current = localStorage.getItem('showSupportResistance') !== 'false';
        localStorage.setItem('showSupportResistance', !current);

        // 刷新所有走势图
        if (this.trendChart) this.trendChart.update();
        if (this.combinedTrendChart) this.combinedTrendChart.update();

        return !current;
    },

    // 获取支撑/阻力线显示状态
    isSupportResistanceEnabled() {
        return localStorage.getItem('showSupportResistance') !== 'false';
    },

    // 渲染单个迷你K线图（用于持仓明细和自选股列表）
    renderMiniCandlestick(canvas, ohlcData, options = {}) {
        if (!canvas || !ohlcData || ohlcData.length < 2) return;

        const ctx = canvas.getContext('2d');
        const width = options.width || canvas.offsetWidth || 120;
        const height = options.height || canvas.offsetHeight || 35;
        const upColor = options.upColor || '#ef4444';
        const downColor = options.downColor || '#22c55e';
        const padding = 2;

        // 设置高分辨率
        canvas.width = width * 2;
        canvas.height = height * 2;
        ctx.scale(2, 2);
        ctx.clearRect(0, 0, width, height);

        // 计算价格范围
        let minPrice = Infinity, maxPrice = -Infinity;
        ohlcData.forEach(d => {
            if (d.low != null && d.low < minPrice) minPrice = d.low;
            if (d.high != null && d.high > maxPrice) maxPrice = d.high;
            // 兼容只有 open/close 的情况
            if (d.low == null && d.close != null) {
                if (d.close < minPrice) minPrice = d.close;
                if (d.close > maxPrice) maxPrice = d.close;
            }
            if (d.low == null && d.open != null) {
                if (d.open < minPrice) minPrice = d.open;
                if (d.open > maxPrice) maxPrice = d.open;
            }
        });
        const priceRange = maxPrice - minPrice || 1;

        // 计算K线宽度
        const barWidth = Math.max(2, Math.min(6, (width - padding * 2) / ohlcData.length * 0.8));
        const barSpacing = (width - padding * 2) / ohlcData.length;

        // 绘制每根K线
        ohlcData.forEach((d, i) => {
            if (!d || d.open == null || d.close == null) return;

            const x = padding + barSpacing * i + barSpacing / 2;
            const yOpen = height - padding - ((d.open - minPrice) / priceRange) * (height - padding * 2);
            const yClose = height - padding - ((d.close - minPrice) / priceRange) * (height - padding * 2);
            const isRising = d.close >= d.open;

            this.drawMiniBar(ctx, x, yOpen, yClose, barWidth, isRising);
        });
    },

    // 批量渲染持仓列表中所有股票的迷你K线图
    renderMiniCandlesticks(trendData) {
        if (!trendData || !trendData.stocks) return;

        trendData.stocks.forEach(stock => {
            const canvas = document.getElementById(`minichart-${stock.stock_code}`);
            if (!canvas) return;

            this.renderMiniCandlestick(canvas, stock.data);
        });
    },

    // 格式化成交量显示
    formatVolume(v) {
        if (v == null || v === 0) return '0';
        if (v >= 100000000) return (v / 100000000).toFixed(2) + '亿';
        if (v >= 10000) return (v / 10000).toFixed(2) + '万';
        return v.toLocaleString();
    },

    // 渲染成交量柱状图
    renderVolumeChart(trendData, canvasId) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return null;

        // 销毁旧图表
        if (this.volumeCharts[canvasId]) {
            this.volumeCharts[canvasId].destroy();
        }

        if (!trendData || !trendData.stocks || trendData.stocks.length === 0) {
            return null;
        }

        // 收集所有日期
        const allDates = new Set();
        trendData.stocks.forEach(stock => {
            stock.data.forEach(d => allDates.add(d.date));
        });
        const sortedDates = Array.from(allDates).sort();

        // 为每只股票创建 dataset
        const colors = this.generateHighContrastColors(trendData.stocks.length, trendData.stocks);
        const datasets = trendData.stocks.map((stock, idx) => {
            const dataMap = {};
            stock.data.forEach(d => {
                dataMap[d.date] = d.volume || 0;
            });

            return {
                label: stock.stock_name,
                data: sortedDates.map(date => dataMap[date] ?? 0),
                backgroundColor: colors[idx] + '80',
                borderWidth: 0
            };
        });

        const chartInstance = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: sortedDates.map(d => d.substring(5)),
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) => `${ctx.dataset.label}: ${Charts.formatVolume(ctx.raw)}`
                        }
                    }
                },
                scales: {
                    x: { display: false },
                    y: {
                        beginAtZero: true,
                        ticks: {
                            font: { size: 9 },
                            callback: (v) => Charts.formatVolume(v)
                        },
                        grid: {
                            color: '#e9ecef'
                        }
                    }
                }
            }
        });

        this.volumeCharts[canvasId] = chartInstance;
        return chartInstance;
    },

    // 渲染相对强度历史曲线图
    renderRelativeStrengthTrendChart(trendData, adviceData, canvasId, onLineClick) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return null;

        // 销毁旧图表
        const existingChart = Chart.getChart(canvas);
        if (existingChart) {
            existingChart.destroy();
        }

        if (!trendData || !trendData.stocks || trendData.stocks.length < 2) {
            canvas.parentElement.innerHTML = '<div class="text-muted" style="padding: 20px; text-align: center;">暂无相对走势数据</div>';
            return null;
        }

        // 收集所有日期并计算每日组内平均
        const allDates = new Set();
        trendData.stocks.forEach(s => {
            if (s.data) s.data.forEach(d => allDates.add(d.date));
        });
        const sortedDates = Array.from(allDates).sort();

        // 计算每日组内平均涨跌幅
        const avgByDate = {};
        sortedDates.forEach(date => {
            const values = trendData.stocks
                .map(s => s.data?.find(d => d.date === date)?.change_pct)
                .filter(v => v !== undefined);
            avgByDate[date] = values.length > 0 ? values.reduce((a, b) => a + b, 0) / values.length : 0;
        });

        // 为每只股票计算历史差值
        const colors = this.generateHighContrastColors(trendData.stocks.length, trendData.stocks);
        const datasets = trendData.stocks.map((stock, idx) => {
            const diffData = sortedDates.map(date => {
                const d = stock.data?.find(x => x.date === date);
                if (!d || d.change_pct === undefined) return null;
                return d.change_pct - avgByDate[date];
            });

            return {
                label: stock.stock_name,
                data: diffData,
                borderColor: colors[idx],
                backgroundColor: colors[idx] + '20',
                fill: false,
                tension: 0.3,
                pointRadius: sortedDates.length > 20 ? 0 : 2,
                pointHoverRadius: 4,
                borderWidth: 2,
                _originalColor: colors[idx]
            };
        });

        // 零线插件
        const zeroLinePlugin = {
            id: 'zeroLineRS',
            beforeDraw(chart) {
                const ctx = chart.ctx;
                const yAxis = chart.scales.y;
                const xAxis = chart.scales.x;

                if (yAxis.min <= 0 && yAxis.max >= 0) {
                    const yPos = yAxis.getPixelForValue(0);
                    ctx.save();
                    ctx.strokeStyle = '#adb5bd';
                    ctx.lineWidth = 1;
                    ctx.setLineDash([5, 5]);
                    ctx.beginPath();
                    ctx.moveTo(xAxis.left, yPos);
                    ctx.lineTo(xAxis.right, yPos);
                    ctx.stroke();
                    ctx.restore();
                }
            }
        };

        // 末端标签插件
        const endLabelPlugin = {
            id: 'endLabelsRS',
            afterDraw(chart) {
                const ctx = chart.ctx;
                const chartArea = chart.chartArea;
                const datasets = chart.data.datasets;
                const minGap = 14;
                const labels = [];

                datasets.forEach((ds, i) => {
                    const meta = chart.getDatasetMeta(i);
                    if (meta.hidden) return;
                    if (!meta.data || meta.data.length === 0) return;

                    let lastPoint = null;
                    let lastValue = null;
                    for (let j = meta.data.length - 1; j >= 0; j--) {
                        if (ds.data[j] !== null && ds.data[j] !== undefined) {
                            lastPoint = meta.data[j];
                            lastValue = ds.data[j];
                            break;
                        }
                    }
                    if (!lastPoint) return;

                    const sign = lastValue >= 0 ? '+' : '';
                    labels.push({
                        index: i,
                        name: `${ds.label.slice(0, 4)}(${sign}${lastValue.toFixed(1)})`,
                        y: lastPoint.y,
                        color: ds._originalColor || ds.borderColor
                    });
                });

                if (labels.length === 0) return;

                labels.sort((a, b) => a.y - b.y);
                for (let i = 1; i < labels.length; i++) {
                    if (labels[i].y - labels[i - 1].y < minGap) {
                        labels[i].y = labels[i - 1].y + minGap;
                    }
                }

                const maxY = chartArea.bottom - 8;
                const minY = chartArea.top + 8;
                labels.forEach(l => {
                    l.y = Math.max(minY, Math.min(maxY, l.y));
                });

                const x = chartArea.right + 8;
                ctx.save();
                ctx.font = '11px sans-serif';
                ctx.textAlign = 'left';
                ctx.textBaseline = 'middle';

                labels.forEach(l => {
                    const meta = chart.getDatasetMeta(l.index);
                    ctx.fillStyle = meta.hidden ? '#999' : l.color;
                    ctx.globalAlpha = meta.hidden ? 0.5 : 1;
                    ctx.fillText(l.name, x, l.y);
                });

                ctx.restore();
            }
        };

        const chartInstance = new Chart(canvas, {
            type: 'line',
            data: {
                labels: sortedDates.map(d => d.substring(5)),
                datasets: datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                layout: {
                    padding: { right: 80 }
                },
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                onHover: (event, elements, chart) => {
                    if (elements.length > 0) {
                        const hoveredIndex = elements[0].datasetIndex;
                        chart.data.datasets.forEach((ds, i) => {
                            if (chart.getDatasetMeta(i).hidden) return;
                            ds.borderWidth = i === hoveredIndex ? 3 : 1.5;
                            ds.borderColor = i === hoveredIndex
                                ? ds._originalColor
                                : ds._originalColor + '4D';
                        });
                        chart.update('none');
                    } else {
                        chart.data.datasets.forEach((ds) => {
                            ds.borderWidth = 2;
                            ds.borderColor = ds._originalColor;
                        });
                        chart.update('none');
                    }
                },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: (items) => items.length > 0 ? sortedDates[items[0].dataIndex] : '',
                            label: (ctx) => {
                                const val = ctx.raw;
                                if (val === null) return null;
                                const sign = val >= 0 ? '+' : '';
                                return `${ctx.dataset.label}: ${sign}${val.toFixed(2)}%`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        display: true,
                        ticks: {
                            font: { size: 10 },
                            maxRotation: 0,
                            autoSkip: true,
                            maxTicksLimit: 10
                        },
                        grid: { display: false }
                    },
                    y: {
                        display: true,
                        ticks: {
                            font: { size: 10 },
                            callback: (v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`
                        },
                        grid: { color: '#e9ecef' }
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0 && onLineClick) {
                        const idx = elements[0].datasetIndex;
                        const stockName = datasets[idx].label;
                        onLineClick(stockName);
                    }
                }
            },
            plugins: [zeroLinePlugin, endLabelPlugin]
        });

        // 保存数据用于联动
        chartInstance._stockNames = trendData.stocks.map(s => s.stock_name);

        return chartInstance;
    },

    // 渲染相对强度条形图
    renderRelativeStrengthChart(trendData, adviceData, canvasId, onBarClick) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return null;

        // 销毁旧图表
        const existingChart = Chart.getChart(canvas);
        if (existingChart) {
            existingChart.destroy();
        }

        if (!adviceData || !adviceData.stocks || adviceData.stocks.length === 0) {
            canvas.parentElement.innerHTML = '<div class="text-muted" style="padding: 20px; text-align: center;">暂无相对走势数据</div>';
            return null;
        }

        // 计算分组平均涨跌幅
        const stocks = adviceData.stocks;
        const validStocks = stocks.filter(s => s.change_pct !== null && s.change_pct !== undefined);
        if (validStocks.length === 0) {
            canvas.parentElement.innerHTML = '<div class="text-muted" style="padding: 20px; text-align: center;">暂无相对走势数据</div>';
            return null;
        }

        const avgChange = validStocks.reduce((sum, s) => sum + s.change_pct, 0) / validStocks.length;

        // 计算相对强度并排序
        const relativeData = validStocks.map(s => ({
            name: s.name,
            code: s.code,
            change_pct: s.change_pct,
            relative_strength: s.change_pct - avgChange
        })).sort((a, b) => b.relative_strength - a.relative_strength);

        const labels = relativeData.map(d => d.name);
        const data = relativeData.map(d => d.relative_strength);
        const colors = data.map(v => v >= 0 ? '#22c55e' : '#ef4444');

        const chartInstance = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: colors,
                    borderWidth: 0,
                    barThickness: 16,
                    _relativeData: relativeData
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            title: (items) => items[0]?.label || '',
                            label: (ctx) => {
                                const rd = ctx.dataset._relativeData[ctx.dataIndex];
                                const changeSign = rd.change_pct >= 0 ? '+' : '';
                                const rsSign = rd.relative_strength >= 0 ? '+' : '';
                                return [
                                    `涨跌幅: ${changeSign}${rd.change_pct.toFixed(2)}%`,
                                    `相对强度: ${rsSign}${rd.relative_strength.toFixed(2)}%`
                                ];
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        position: 'top',
                        ticks: {
                            font: { size: 10 },
                            callback: (v) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}%`
                        },
                        grid: {
                            color: (ctx) => ctx.tick.value === 0 ? '#adb5bd' : '#e9ecef',
                            lineWidth: (ctx) => ctx.tick.value === 0 ? 2 : 1
                        }
                    },
                    y: {
                        ticks: {
                            font: { size: 11 }
                        },
                        grid: { display: false }
                    }
                },
                onClick: (event, elements) => {
                    if (elements.length > 0 && onBarClick) {
                        const idx = elements[0].index;
                        const stockName = relativeData[idx].name;
                        onBarClick(stockName);
                    }
                }
            }
        });

        // 保存相对强度数据用于联动
        chartInstance._relativeData = relativeData;

        return chartInstance;
    },
    // MACD副图
    renderMACDChart(technicalData, trendChart, canvasId = 'macdChart') {
        const wrapper = document.getElementById(canvasId.replace('Chart', 'ChartWrapper'));
        if (!wrapper) return null;

        if (this._macdChart) {
            this._macdChart.destroy();
            this._macdChart = null;
        }

        if (!technicalData || !trendChart) {
            wrapper.innerHTML = '';
            return null;
        }

        // 获取走势图的股票列表和labels
        const labels = trendChart.data.labels;
        const stockNames = trendChart.data.datasets.map(d => d.label);

        // 只取第一只股票的MACD数据（单股模式下清晰）
        const firstStock = Object.keys(technicalData)[0];
        if (!firstStock) { wrapper.innerHTML = ''; return null; }

        const macd = technicalData[firstStock]?.macd;
        if (!macd || !macd.history || macd.history.length === 0) {
            wrapper.innerHTML = '';
            return null;
        }

        // MACD历史数据对齐到图表尾部
        const history = macd.history;
        const histLen = Math.min(history.length, labels.length);
        const offset = labels.length - histLen;

        const difData = new Array(labels.length).fill(null);
        const deaData = new Array(labels.length).fill(null);
        const histData = new Array(labels.length).fill(null);
        const histColors = [];

        for (let i = 0; i < histLen; i++) {
            difData[offset + i] = history[i].dif;
            deaData[offset + i] = history[i].dea;
            histData[offset + i] = history[i].histogram;
        }
        for (let i = 0; i < labels.length; i++) {
            histColors.push(histData[i] !== null && histData[i] >= 0 ? 'rgba(220,53,69,0.6)' : 'rgba(40,167,69,0.6)');
        }

        wrapper.innerHTML = `<span class="tech-sub-chart-label">MACD · ${macd.signal}</span><canvas id="${canvasId}"></canvas>`;
        const canvas = document.getElementById(canvasId);

        this._macdChart = new Chart(canvas, {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    { type: 'bar', data: histData, backgroundColor: histColors, borderWidth: 0, order: 2 },
                    { type: 'line', label: 'DIF', data: difData, borderColor: '#2196F3', borderWidth: 1.2, pointRadius: 0, order: 1 },
                    { type: 'line', label: 'DEA', data: deaData, borderColor: '#FF9800', borderWidth: 1.2, pointRadius: 0, order: 1 },
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false }, tooltip: { mode: 'index', intersect: false } },
                scales: {
                    x: { display: false },
                    y: { ticks: { font: { size: 9 }, maxTicksLimit: 3 }, grid: { color: '#f0f0f0' } }
                }
            }
        });

        return this._macdChart;
    },

    // RSI副图
    renderRSIChart(technicalData, trendChart, canvasId = 'rsiChart') {
        const wrapper = document.getElementById(canvasId.replace('Chart', 'ChartWrapper'));
        if (!wrapper) return null;

        if (this._rsiChart) {
            this._rsiChart.destroy();
            this._rsiChart = null;
        }

        if (!technicalData || !trendChart) {
            wrapper.innerHTML = '';
            return null;
        }

        const labels = trendChart.data.labels;
        const firstStock = Object.keys(technicalData)[0];
        if (!firstStock) { wrapper.innerHTML = ''; return null; }

        const rsi = technicalData[firstStock]?.rsi;
        if (!rsi || !rsi.history || rsi.history.length === 0) {
            wrapper.innerHTML = '';
            return null;
        }

        const history = rsi.history;
        const histLen = Math.min(history.length, labels.length);
        const offset = labels.length - histLen;

        const rsi6Data = new Array(labels.length).fill(null);
        const rsi12Data = new Array(labels.length).fill(null);
        const rsi24Data = new Array(labels.length).fill(null);

        for (let i = 0; i < histLen; i++) {
            rsi6Data[offset + i] = history[i].rsi_6;
            rsi12Data[offset + i] = history[i].rsi_12;
            rsi24Data[offset + i] = history[i].rsi_24;
        }

        wrapper.innerHTML = `<span class="tech-sub-chart-label">RSI · ${rsi.status}</span><canvas id="${canvasId}"></canvas>`;
        const canvas = document.getElementById(canvasId);

        this._rsiChart = new Chart(canvas, {
            type: 'line',
            data: {
                labels,
                datasets: [
                    { label: 'RSI6', data: rsi6Data, borderColor: '#9C27B0', borderWidth: 1.2, pointRadius: 0 },
                    { label: 'RSI12', data: rsi12Data, borderColor: '#2196F3', borderWidth: 1, pointRadius: 0 },
                    { label: 'RSI24', data: rsi24Data, borderColor: '#FF9800', borderWidth: 1, pointRadius: 0 },
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: { mode: 'index', intersect: false },
                    // 超买超卖区域
                    annotation: undefined,
                },
                scales: {
                    x: { display: false },
                    y: {
                        min: 0, max: 100,
                        ticks: { font: { size: 9 }, stepSize: 30, callback: v => v === 70 ? '70' : v === 30 ? '30' : '' },
                        grid: {
                            color: (ctx) => {
                                if (ctx.tick.value === 70) return 'rgba(220,53,69,0.3)';
                                if (ctx.tick.value === 30) return 'rgba(40,167,69,0.3)';
                                return '#f0f0f0';
                            }
                        }
                    }
                }
            }
        });

        return this._rsiChart;
    },
};

// 导出
window.Charts = Charts;
