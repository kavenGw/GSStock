/**
 * 相对分析模块
 * 计算列表内品种的相对差值、排名和投资价值
 */
const RelativeAnalysis = {
    // 趋势分析配置
    TREND_CONFIG: {
        stableThreshold: 0.5,      // 差值变化率 < 0.5% 视为稳定
        neutralThreshold: 0.5,     // 相对差值 < 0.5% 视为中性
        lookbackDays: 5,           // 计算历史均值的回看天数
        significantThreshold: 1.0  // 显著趋势变化阈值（用于颜色标识）
    },

    /**
     * 计算单个品种的历史差值序列
     * @param {Object} stockTrendData - 单个股票的走势数据 { data: [{date, change_pct}] }
     * @param {Object} avgByDate - 按日期索引的组内平均涨跌幅 { 'YYYY-MM-DD': avgPct }
     * @returns {Array} 历史差值序列 [{ date, diff }]
     */
    calculateDiffHistory(stockTrendData, avgByDate) {
        if (!stockTrendData || !stockTrendData.data || !avgByDate) {
            return [];
        }
        return stockTrendData.data
            .map(d => {
                const avg = avgByDate[d.date];
                if (avg === undefined || d.change_pct === undefined) {
                    return null;
                }
                return { date: d.date, diff: d.change_pct - avg };
            })
            .filter(d => d !== null);
    },

    /**
     * 计算差值变化趋势（主入口）
     * @param {Array} stocks - 带有历史数据的股票列表
     * @param {Object} trendData - 走势数据 { stocks: [{ code, data: [{date, change_pct}] }] }
     * @returns {Array} 添加了趋势信息的列表
     */
    calculateTrend(stocks, trendData) {
        if (!stocks || stocks.length === 0) return stocks;

        // 单品种不计算趋势
        if (stocks.length <= 1 || !trendData || !trendData.stocks || trendData.stocks.length <= 1) {
            stocks.forEach(s => { s.trend = null; });
            return stocks;
        }

        // 1. 收集所有日期
        const allDates = new Set();
        trendData.stocks.forEach(s => {
            if (s.data) s.data.forEach(d => allDates.add(d.date));
        });
        const sortedDates = Array.from(allDates).sort();

        // 2. 计算每个日期的组内平均涨跌幅
        const avgByDate = {};
        sortedDates.forEach(date => {
            const values = trendData.stocks
                .map(s => s.data?.find(d => d.date === date)?.change_pct)
                .filter(v => v !== undefined);
            avgByDate[date] = values.length > 0 ? values.reduce((a, b) => a + b, 0) / values.length : 0;
        });

        // 3. 为每个品种计算趋势
        stocks.forEach(stock => {
            // 找到对应的走势数据
            const stockTrendData = trendData.stocks.find(s => s.code === stock.code);
            if (!stockTrendData) {
                stock.trend = null;
                return;
            }

            // 计算历史差值序列
            const diffHistory = this.calculateDiffHistory(stockTrendData, avgByDate);

            // 历史数据不足时不计算趋势
            if (diffHistory.length < 2) {
                stock.trend = null;
                return;
            }

            // 计算过去N日差值移动平均
            const lookback = Math.min(this.TREND_CONFIG.lookbackDays, diffHistory.length - 1);
            const recentDiffs = diffHistory.slice(-lookback - 1, -1);
            const diffMa = recentDiffs.length > 0
                ? recentDiffs.reduce((sum, d) => sum + d.diff, 0) / recentDiffs.length
                : 0;

            // 当前差值
            const currentDiff = diffHistory[diffHistory.length - 1].diff;

            // 差值变化率
            const diffChange = currentDiff - diffMa;

            // 判断趋势类型
            let trendType, arrow;
            if (diffChange > this.TREND_CONFIG.stableThreshold) {
                trendType = 'strengthening';
                arrow = '↑';
            } else if (diffChange < -this.TREND_CONFIG.stableThreshold) {
                trendType = 'weakening';
                arrow = '↓';
            } else {
                trendType = 'stable';
                arrow = '→';
            }

            stock.trend = {
                diff_history: diffHistory,
                diff_ma: diffMa,
                diff_change: diffChange,
                trend_type: trendType,
                arrow: arrow
            };
        });

        return stocks;
    },

    /**
     * 获取动态估值标签
     * @param {Object} stock - 单个股票（含趋势数据）
     * @returns {Object|null} { text, type, color, arrow }
     */
    getDynamicLabel(stock) {
        const diff = stock.relative_diff || 0;
        const trend = stock.trend;

        // 无趋势数据时不显示标签
        if (!trend) return null;

        const change = trend.diff_change || 0;

        // 中性判断：相对差值接近0
        if (Math.abs(diff) < this.TREND_CONFIG.neutralThreshold) {
            return { text: '中性', type: 'neutral', color: '#6c757d', arrow: '→' };
        }

        // 稳定判断：趋势变化幅度小
        if (Math.abs(change) < this.TREND_CONFIG.stableThreshold) {
            if (diff > 0) {
                return { text: '相对领先', type: 'leading', color: '#17a2b8', arrow: '→' };
            } else {
                return { text: '相对落后', type: 'lagging', color: '#ffc107', arrow: '→' };
            }
        }

        // 正差值（相对领先）
        if (diff > 0) {
            if (change > 0) {
                return { text: '相对高估', type: 'overvalued', color: '#dc3545', arrow: '↑' };
            } else {
                return { text: '回归中', type: 'reverting', color: '#28a745', arrow: '↓' };
            }
        }

        // 负差值（相对落后）
        if (diff < 0) {
            if (change < 0) {
                return { text: '相对低估', type: 'undervalued', color: '#28a745', arrow: '↓' };
            } else {
                return { text: '修复中', type: 'recovering', color: '#28a745', arrow: '↑' };
            }
        }

        return { text: '相对稳定', type: 'stable', color: '#6c757d', arrow: '→' };
    },

    /**
     * 计算列表平均涨跌幅
     * @param {Array} stocks - 股票列表
     * @returns {number} 平均涨跌幅
     */
    calculateAverage(stocks) {
        if (!stocks || stocks.length === 0) return 0;
        const sum = stocks.reduce((s, x) => s + (x.change_pct || 0), 0);
        return sum / stocks.length;
    },

    /**
     * 计算相对差值
     * @param {Array} stocks - 股票列表
     * @returns {Array} 添加了 relative_diff 字段的列表
     */
    calculateRelativeDiff(stocks) {
        if (!stocks || stocks.length === 0) return stocks;
        const avg = this.calculateAverage(stocks);
        stocks.forEach(s => {
            s.relative_diff = (s.change_pct || 0) - avg;
        });
        return stocks;
    },

    /**
     * 计算排名
     * @param {Array} stocks - 股票列表
     * @returns {Array} 添加了 rank 和 rank_num 字段的列表
     */
    calculateRanking(stocks) {
        if (!stocks || stocks.length === 0) return stocks;

        // 按涨跌幅降序排列计算排名
        const sorted = [...stocks].sort((a, b) => (b.change_pct || 0) - (a.change_pct || 0));
        const total = stocks.length;

        sorted.forEach((s, i) => {
            s.rank = `${i + 1}/${total}`;
            s.rank_num = i + 1;
        });

        return stocks;
    },

    /**
     * 计算投资价值
     * 公式：(100 - 估值评分) × 0.6 + 相对落后分 × 0.4
     * @param {Object} stock - 单个股票
     * @returns {number} 投资价值评分 0-100
     */
    calculateInvestmentValue(stock) {
        const valuationScore = stock.valuation?.valuation_score ?? 50;
        // 相对落后分：每落后1%得5分，上限50分
        const lagScore = Math.min(50, Math.max(0, -(stock.relative_diff || 0) * 5));
        return Math.round((100 - valuationScore) * 0.6 + lagScore * 0.4);
    },

    /**
     * 获取低估标签
     * @param {Object} stock - 单个股票
     * @param {number} total - 列表总数
     * @returns {string|null} 标签文本
     */
    getLabel(stock, total) {
        const isLast = stock.rank_num === total;
        const valuationScore = stock.valuation?.valuation_score ?? 100;
        const isLowValuation = valuationScore < 40;
        const isVeryLowValuation = valuationScore < 30;
        const isLagging = (stock.relative_diff || 0) < -2;

        if (isLast && isLowValuation) return '双重低估';
        if (isLast) return '相对低估';
        if (isVeryLowValuation) return '估值低估';
        if (isLagging) return '明显落后';
        return null;
    },

    /**
     * 检测短期回调
     * @param {Object} stock7d - 7日数据中的股票
     * @param {Object} stock30d - 30日数据中的股票
     * @returns {string|null} 标签文本
     */
    detectShortTermPullback(stock7d, stock30d) {
        if (!stock7d || !stock30d) return null;
        // 7日相对差值为负，但30日涨幅为正
        if ((stock7d.relative_diff || 0) < 0 && (stock30d.change_pct || 0) > 0) {
            return '短期回调';
        }
        return null;
    },

    /**
     * 筛选低估品种
     * @param {Array} stocks - 股票列表
     * @returns {Array} 筛选后的列表
     */
    filterUndervalued(stocks) {
        if (!stocks || stocks.length === 0) return stocks;
        return stocks.filter(s => {
            const valuationScore = s.valuation?.valuation_score ?? 100;
            return valuationScore < 40 || s.rank_num === stocks.length;
        });
    },

    /**
     * 排序
     * @param {Array} stocks - 股票列表
     * @param {string} field - 排序字段：change_pct/valuation/investment_value/relative_diff
     * @param {boolean} ascending - 升序
     * @returns {Array} 排序后的列表
     */
    sortBy(stocks, field, ascending = true) {
        if (!stocks || stocks.length === 0) return stocks;
        return [...stocks].sort((a, b) => {
            let va, vb;
            if (field === 'valuation') {
                va = a.valuation?.valuation_score ?? 100;
                vb = b.valuation?.valuation_score ?? 100;
            } else {
                va = a[field] ?? 0;
                vb = b[field] ?? 0;
            }
            return ascending ? va - vb : vb - va;
        });
    },

    /**
     * 综合计算入口
     * @param {Array} stocks - 股票列表
     * @returns {Array} 添加了所有相对分析字段的列表
     */
    calculate(stocks) {
        if (!stocks || stocks.length === 0) return stocks;

        // 单品种不计算相对差值
        if (stocks.length <= 1) {
            stocks.forEach(s => {
                s.relative_diff = 0;
                s.rank = '1/1';
                s.rank_num = 1;
                s.investment_value = this.calculateInvestmentValue(s);
                s.label = null;
            });
            return stocks;
        }

        // 1. 计算相对差值
        this.calculateRelativeDiff(stocks);

        // 2. 计算排名
        this.calculateRanking(stocks);

        // 3. 计算投资价值和标签
        const total = stocks.length;
        stocks.forEach(s => {
            s.investment_value = this.calculateInvestmentValue(s);
            s.label = this.getLabel(s, total);
        });

        return stocks;
    }
};

// 如果在Node环境下导出
if (typeof module !== 'undefined' && module.exports) {
    module.exports = RelativeAnalysis;
}
