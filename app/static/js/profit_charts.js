// 收益统计图表

/**
 * 渲染累计收益曲线
 * @param {string} canvasId - Canvas 元素 ID
 * @param {Array} cumulativeProfits - 数据数组 [{date, cumulative}]
 * @param {Object} options - 可选配置
 * @returns {Chart|null} Chart 实例或 null
 */
function renderCumulativeLine(canvasId, cumulativeProfits, options = {}) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return null;

    if (!cumulativeProfits || cumulativeProfits.length === 0) {
        return null;
    }

    const showFullDate = options.showFullDate || false;
    const labels = cumulativeProfits.map(d => showFullDate ? d.date : d.date.slice(5));
    const data = cumulativeProfits.map(d => d.cumulative);

    // 渐变填充：根据最终值决定颜色
    const ctx = canvas.getContext('2d');
    const gradient = ctx.createLinearGradient(0, 0, 0, canvas.height);
    const lastValue = data[data.length - 1];
    if (lastValue >= 0) {
        gradient.addColorStop(0, 'rgba(72, 187, 120, 0.3)');
        gradient.addColorStop(1, 'rgba(72, 187, 120, 0.05)');
    } else {
        gradient.addColorStop(0, 'rgba(229, 62, 62, 0.3)');
        gradient.addColorStop(1, 'rgba(229, 62, 62, 0.05)');
    }

    return new Chart(canvas, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: '累计盈亏',
                data: data,
                borderColor: lastValue >= 0 ? '#48bb78' : '#e53e3e',
                backgroundColor: gradient,
                fill: true,
                tension: 0.3,
                pointRadius: data.length > 15 ? 0 : 3,
                pointHoverRadius: 5
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: options.maintainAspectRatio !== undefined ? options.maintainAspectRatio : false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const value = context.raw;
                            const sign = value >= 0 ? '+' : '';
                            return `累计: ${sign}${value.toFixed(2)}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    display: true,
                    ticks: { font: { size: 10 }, maxRotation: 45, minRotation: 45 },
                    grid: { display: false }
                },
                y: {
                    display: true,
                    ticks: { font: { size: 10 } },
                    grid: {
                        color: function(context) {
                            if (context.tick.value === 0) {
                                return 'rgba(0, 0, 0, 0.3)';
                            }
                            return '#e2e8f0';
                        }
                    }
                }
            }
        }
    });
}

/**
 * 渲染每日盈亏柱状图
 * @param {string} canvasId - Canvas 元素 ID
 * @param {Array} dailyProfits - 数据数组 [{date, daily_profit, daily_profit_pct}]
 * @param {Object} options - 可选配置
 * @returns {Chart|null} Chart 实例或 null
 */
function renderDailyProfitBar(canvasId, dailyProfits, options = {}) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return null;

    if (!dailyProfits || dailyProfits.length === 0) {
        return null;
    }

    const showFullDate = options.showFullDate || false;
    const labels = dailyProfits.map(d => showFullDate ? d.date : d.date.slice(5));
    const profits = dailyProfits.map(d => d.daily_profit);
    const colors = profits.map(p => p >= 0 ? '#48bb78' : '#e53e3e');

    return new Chart(canvas, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: '每日盈亏',
                data: profits,
                backgroundColor: colors,
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: options.maintainAspectRatio !== undefined ? options.maintainAspectRatio : false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const idx = context.dataIndex;
                            const value = context.raw;
                            const sign = value >= 0 ? '+' : '';
                            const pct = dailyProfits[idx].daily_profit_pct;
                            if (pct !== undefined) {
                                return `盈亏: ${sign}${value.toFixed(2)} (${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%)`;
                            }
                            return `${sign}${value.toFixed(2)}`;
                        }
                    }
                }
            },
            scales: {
                x: {
                    display: true,
                    ticks: { font: { size: 10 }, maxRotation: 45, minRotation: 45 },
                    grid: { display: false }
                },
                y: {
                    display: true,
                    beginAtZero: true,
                    ticks: { font: { size: 10 } },
                    grid: {
                        color: function(context) {
                            if (context.tick.value === 0) {
                                return 'rgba(0, 0, 0, 0.3)';
                            }
                            return '#e2e8f0';
                        }
                    }
                }
            }
        }
    });
}

document.addEventListener('DOMContentLoaded', function() {
    // 每日收益页面图表
    if (window.profitData) {
        initDailyProfitCharts(window.profitData, window.byStockData, window.byCategoryData);
    }

    // 整体收益页面图表
    if (window.dailyData && window.tradeData) {
        initOverallProfitCharts(window.dailyData, window.tradeData, window.byStockData, window.byCategoryData);
    }
});

function initDailyProfitCharts(data, byStockData, byCategoryData) {
    if (!data.daily_profits || data.daily_profits.length === 0) return;

    // 每日盈亏柱状图 - 使用共享函数
    renderDailyProfitBar('dailyProfitChart', data.daily_profits, { showFullDate: true, maintainAspectRatio: true });

    // 累计盈亏曲线 - 使用共享函数
    if (data.cumulative_profits && data.cumulative_profits.length > 0) {
        renderCumulativeLine('cumulativeProfitChart', data.cumulative_profits, { showFullDate: true, maintainAspectRatio: true });
    }

    // 按股票盈亏分布
    renderProfitBarChart('profitByStockChart', byStockData?.by_stock, 'stock_name', 'total_profit');

    // 按分类盈亏分布
    renderProfitBarChart('profitByCategoryChart', byCategoryData?.by_category, 'category', 'total_profit');
}

function initOverallProfitCharts(dailyData, tradeData, byStockData, byCategoryData) {
    // 累计盈亏走势
    const cumulativeCtx = document.getElementById('overallCumulativeChart');
    if (cumulativeCtx) {
        const datasets = [];

        // 每日累计盈亏（浮动）
        if (dailyData.cumulative_profits && dailyData.cumulative_profits.length > 0) {
            datasets.push({
                label: '浮动累计盈亏',
                data: dailyData.cumulative_profits.map(d => ({
                    x: d.date,
                    y: d.cumulative
                })),
                borderColor: 'rgba(54, 162, 235, 1)',
                backgroundColor: 'rgba(54, 162, 235, 0.1)',
                fill: false,
                tension: 0.3
            });
        }

        // 已实现累计盈亏
        if (tradeData.cumulative_profit && tradeData.cumulative_profit.length > 0) {
            datasets.push({
                label: '已实现累计盈亏',
                data: tradeData.cumulative_profit.map(d => ({
                    x: d.date,
                    y: d.cumulative
                })),
                borderColor: 'rgba(40, 167, 69, 1)',
                backgroundColor: 'rgba(40, 167, 69, 0.1)',
                fill: false,
                tension: 0.3
            });
        }

        if (datasets.length > 0) {
            new Chart(cumulativeCtx, {
                type: 'line',
                data: { datasets: datasets },
                options: {
                    responsive: true,
                    plugins: {
                        tooltip: {
                            callbacks: {
                                label: function(context) {
                                    return `${context.dataset.label}: ${context.raw.y >= 0 ? '+' : ''}${context.raw.y.toFixed(2)}`;
                                }
                            }
                        }
                    },
                    scales: {
                        x: {
                            type: 'category',
                            labels: [...new Set([
                                ...(dailyData.cumulative_profits || []).map(d => d.date),
                                ...(tradeData.cumulative_profit || []).map(d => d.date)
                            ])].sort()
                        },
                        y: {
                            grid: {
                                color: function(context) {
                                    if (context.tick.value === 0) {
                                        return 'rgba(0, 0, 0, 0.3)';
                                    }
                                    return 'rgba(0, 0, 0, 0.1)';
                                }
                            }
                        }
                    }
                }
            });
        }
    }

    // 浮动盈亏 - 按股票
    renderProfitBarChart('floatingByStockChart', byStockData?.by_stock, 'stock_name', 'total_profit');

    // 浮动盈亏 - 按分类
    renderProfitBarChart('floatingByCategoryChart', byCategoryData?.by_category, 'category', 'total_profit');

    // 已实现盈亏 - 按股票
    renderProfitBarChart('profitDistributionChart', tradeData?.profit_distribution, 'stock_name', 'profit');

    // 已实现盈亏 - 按分类
    renderProfitBarChart('realizedByCategoryChart', tradeData?.by_category, 'category', 'total_profit');
}

function renderProfitBarChart(canvasId, dataArray, labelKey, valueKey) {
    const ctx = document.getElementById(canvasId);
    if (!ctx || !dataArray || dataArray.length === 0) return null;

    const labels = dataArray.map(d => d[labelKey] || d.stock_code || '未知');
    const profits = dataArray.map(d => d[valueKey]);
    const colors = profits.map(p => p >= 0 ? '#48bb78' : '#e53e3e');

    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: '盈亏',
                data: profits,
                backgroundColor: colors,
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `盈亏: ${context.raw >= 0 ? '+' : ''}${context.raw.toFixed(2)}`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: function(context) {
                            if (context.tick.value === 0) {
                                return 'rgba(0, 0, 0, 0.3)';
                            }
                            return 'rgba(0, 0, 0, 0.1)';
                        }
                    }
                }
            }
        }
    });
}

// 导出共享函数
window.ProfitCharts = {
    renderDailyProfitBar,
    renderCumulativeLine,
    renderProfitBarChart
};
