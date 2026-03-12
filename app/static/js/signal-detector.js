/**
 * SignalDetector - 股票买卖点信号检测模块
 * 分析OHLC数据，识别各种技术形态，返回买卖点信号数组
 */

const SignalDetector = {
    /**
     * 主入口：检测所有信号
     * @param {Array} ohlcData - OHLC数据数组
     * @param {Object} thresholds - 预警阈值配置（可选）
     * @returns {Object} - {buySignals: Signal[], sellSignals: Signal[], alerts: Alert[]}
     */
    detectAll(ohlcData, thresholds = {}) {
        // 数据验证
        if (!ohlcData || !Array.isArray(ohlcData) || ohlcData.length === 0) {
            console.warn('[SignalDetector] 无效的OHLC数据');
            return { buySignals: [], sellSignals: [], alerts: [] };
        }

        // 检查最少需要的K线数量(双底/双顶需要至少20根K线)
        const minDataLength = 20;
        if (ohlcData.length < minDataLength) {
            console.warn(`[SignalDetector] 数据不足:需要至少${minDataLength}根K线,当前${ohlcData.length}根`);
        }

        const allSignals = [];
        const allAlerts = [];

        try {
            // 调用所有检测方法,捕获单个方法的错误
            const methods = [
                { name: '缩量突破', fn: () => this.detectVolumeBreakout(ohlcData), minData: 5 },
                { name: '突破新高', fn: () => this.detectNewHigh(ohlcData), minData: 60 },
                { name: '顶部巨量', fn: () => this.detectTopVolume(ohlcData, lookback = 20, highLookback = 60) {
        const signals = [];

        for (let i = lookback; i < ohlcData.length; i++) {
            const avgVolume = average(ohlcData.slice(i - lookback, i).map(d => d.volume));
            const volumeRatio = ohlcData[i].volume / avgVolume;

            // ?????????60???????????60????
            const startIdx = Math.max(0, i - highLookback + 1);
            const recentHigh = Math.max(...ohlcData.slice(startIdx, i + 1).map(d => d.high));
            const recentCloseHigh = Math.max(...ohlcData.slice(startIdx, i + 1).map(d => d.close));
            const currHigh = ohlcData[i].high;
            const currClose = ohlcData[i].close;
            const isNearTop = (recentCloseHigh > 0 && currClose >= recentCloseHigh * 0.90)
                || (recentHigh > 0 && currHigh >= recentHigh * 0.95);

            // ??????????????
            const prevClose = ohlcData[i - 1]?.close ?? 0;
            const currOpen = ohlcData[i].open ?? currClose;
            const isWeak = (currClose < currOpen) || (prevClose > 0 && currClose < prevClose);

            if (volumeRatio >= 2.5 && isNearTop && isWeak) {
                signals.push({
                    index: i,
                    type: "sell",
                    name: "????",
                    description: `????${lookback}????${volumeRatio.toFixed(1)}?????????`,
                    data: {
                        volumeRatio: volumeRatio,
                        recentHigh: recentHigh,
                        recentCloseHigh: recentCloseHigh,
                        currentHigh: currHigh,
                        currentClose: currClose
                    }
                });
            }
        }

        return signals;
    }
};

/**
 * 工具函数
 */

/**
 * 计算平均值
 * @param {Array} values - 数值数组
 * @returns {Number} - 平均值
 */
function average(values) {
    if (!values || values.length === 0) return 0;
    const sum = values.reduce((acc, val) => acc + val, 0);
    return sum / values.length;
}

/**
 * 计算移动平均线
 * @param {Array} data - OHLC数据数组
 * @param {Number} period - 周期（如5日、10日）
 * @returns {Array} - MA数值数组（前期不足的位置为null）
 */
function calculateMA(data, period) {
    const ma = [];
    for (let i = 0; i < data.length; i++) {
        if (i < period - 1) {
            ma.push(null);
            continue;
        }
        const sum = data.slice(i - period + 1, i + 1).reduce((acc, d) => acc + d.close, 0);
        ma.push(sum / period);
    }
    return ma;
}

/**
 * 查找局部最低点（用于双底形态识别）
 * @param {Array} data - OHLC数据数组
 * @param {Number} window - 窗口大小（左右各window个点）
 * @returns {Array} - 局部最低点的索引数组
 */
function findLocalMinima(data, window = 5) {
    const minima = [];
    for (let i = window; i < data.length - window; i++) {
        let isMinimum = true;
        // 检查左右window范围内是否是最低点
        for (let j = i - window; j <= i + window; j++) {
            if (j === i) continue;
            if (data[j].low < data[i].low) {
                isMinimum = false;
                break;
            }
        }
        if (isMinimum) {
            minima.push(i);
        }
    }
    return minima;
}

/**
 * 查找局部最高点（用于双顶形态识别）
 * @param {Array} data - OHLC数据数组
 * @param {Number} window - 窗口大小（左右各window个点）
 * @returns {Array} - 局部最高点的索引数组
 */
function findLocalMaxima(data, window = 5) {
    const maxima = [];
    for (let i = window; i < data.length - window; i++) {
        let isMaximum = true;
        // 检查左右window范围内是否是最高点
        for (let j = i - window; j <= i + window; j++) {
            if (j === i) continue;
            if (data[j].high > data[i].high) {
                isMaximum = false;
                break;
            }
        }
        if (isMaximum) {
            maxima.push(i);
        }
    }
    return maxima;
}

/**
 * Signal对象结构示例:
 * {
 *   index: 15,           // K线索引位置
 *   type: "buy",         // "buy" | "sell"
 *   name: "缩量突破",     // 信号名称
 *   description: "连续4天缩量下跌后放量上涨，放量倍数1.8倍",
 *   strength: "strong",  // "strong" | "medium" | "weak"（可选）
 *   data: {              // 附加数据（用于弹窗展示）
 *     shrinkDays: 4,
 *     volumeRatio: 1.8
 *   }
 * }
 */

/**
 * 计算 RSI（相对强弱指标）
 * @param {Array} data - OHLC 数据数组
 * @param {Number} period - 周期（默认14日）
 * @returns {Array} - RSI 数值数组（前期不足的位置为 null）
 */
function calculateRSI(data, period = 14) {
    const rsi = [];
    if (data.length < period + 1) {
        return data.map(() => null);
    }

    let gains = 0;
    let losses = 0;

    // 计算初始平均涨跌幅
    for (let i = 1; i <= period; i++) {
        const change = data[i].close - data[i - 1].close;
        if (change > 0) {
            gains += change;
        } else {
            losses -= change;
        }
        rsi.push(null);
    }

    let avgGain = gains / period;
    let avgLoss = losses / period;

    // 第一个有效 RSI 值
    const firstRSI = avgLoss === 0 ? 100 : 100 - (100 / (1 + avgGain / avgLoss));
    rsi.push(firstRSI);

    // 使用 Wilder 平滑方法计算后续 RSI
    for (let i = period + 1; i < data.length; i++) {
        const change = data[i].close - data[i - 1].close;
        const currentGain = change > 0 ? change : 0;
        const currentLoss = change < 0 ? -change : 0;

        avgGain = (avgGain * (period - 1) + currentGain) / period;
        avgLoss = (avgLoss * (period - 1) + currentLoss) / period;

        const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
        const currentRSI = avgLoss === 0 ? 100 : 100 - (100 / (1 + rs));
        rsi.push(currentRSI);
    }

    return rsi;
}

/**
 * 计算布林带
 * @param {Array} data - OHLC 数据数组
 * @param {Number} period - 周期（默认20日）
 * @param {Number} multiplier - 标准差倍数（默认2）
 * @returns {Object} - {middle: [], upper: [], lower: [], width: []}
 */
function calculateBollinger(data, period = 20, multiplier = 2) {
    const middle = [];
    const upper = [];
    const lower = [];
    const width = [];

    for (let i = 0; i < data.length; i++) {
        if (i < period - 1) {
            middle.push(null);
            upper.push(null);
            lower.push(null);
            width.push(null);
            continue;
        }

        const slice = data.slice(i - period + 1, i + 1);
        const closes = slice.map(d => d.close);
        const ma = closes.reduce((a, b) => a + b, 0) / period;

        const variance = closes.reduce((sum, val) => sum + Math.pow(val - ma, 2), 0) / period;
        const std = Math.sqrt(variance);

        middle.push(ma);
        upper.push(ma + multiplier * std);
        lower.push(ma - multiplier * std);
        width.push((2 * multiplier * std) / ma * 100);
    }

    return { middle, upper, lower, width };
}

/**
 * 计算 EMA（指数移动平均线）
 * @param {Array} values - 数值数组
 * @param {Number} period - 周期
 * @returns {Array} - EMA 数值数组
 */
function calculateEMA(values, period) {
    const ema = [];
    const multiplier = 2 / (period + 1);

    for (let i = 0; i < values.length; i++) {
        if (i < period - 1) {
            ema.push(null);
            continue;
        }

        if (i === period - 1) {
            const sma = values.slice(0, period).reduce((a, b) => a + b, 0) / period;
            ema.push(sma);
        } else {
            const prevEMA = ema[i - 1];
            const currentEMA = (values[i] - prevEMA) * multiplier + prevEMA;
            ema.push(currentEMA);
        }
    }

    return ema;
}

/**
 * 计算 MACD
 * @param {Array} data - OHLC 数据数组
 * @param {Number} fastPeriod - 快线周期（默认12）
 * @param {Number} slowPeriod - 慢线周期（默认26）
 * @param {Number} signalPeriod - 信号线周期（默认9）
 * @returns {Object} - {dif: [], dea: [], histogram: []}
 */
function calculateMACD(data, fastPeriod = 12, slowPeriod = 26, signalPeriod = 9) {
    const closes = data.map(d => d.close);
    const emaFast = calculateEMA(closes, fastPeriod);
    const emaSlow = calculateEMA(closes, slowPeriod);

    const dif = [];
    for (let i = 0; i < data.length; i++) {
        if (emaFast[i] === null || emaSlow[i] === null) {
            dif.push(null);
        } else {
            dif.push(emaFast[i] - emaSlow[i]);
        }
    }

    const validDif = dif.filter(v => v !== null);
    const dea = [];
    const difMultiplier = 2 / (signalPeriod + 1);
    let deaStartIdx = dif.findIndex(v => v !== null);

    for (let i = 0; i < data.length; i++) {
        if (i < deaStartIdx + signalPeriod - 1) {
            dea.push(null);
            continue;
        }

        if (i === deaStartIdx + signalPeriod - 1) {
            const smaDif = dif.slice(deaStartIdx, i + 1).reduce((a, b) => a + b, 0) / signalPeriod;
            dea.push(smaDif);
        } else if (dea[i - 1] !== null && dif[i] !== null) {
            const currentDEA = (dif[i] - dea[i - 1]) * difMultiplier + dea[i - 1];
            dea.push(currentDEA);
        } else {
            dea.push(null);
        }
    }

    const histogram = [];
    for (let i = 0; i < data.length; i++) {
        if (dif[i] === null || dea[i] === null) {
            histogram.push(null);
        } else {
            histogram.push((dif[i] - dea[i]) * 2);
        }
    }

    return { dif, dea, histogram };
}
