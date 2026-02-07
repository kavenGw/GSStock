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
                { name: '顶部巨量', fn: () => this.detectTopVolume(ohlcData), minData: 20 },
                { name: '均线突破', fn: () => this.detectMA5Cross(ohlcData), minData: 5 },
                { name: '双底形态', fn: () => this.detectDoubleBottom(ohlcData), minData: 20 },
                { name: '双顶形态', fn: () => this.detectDoubleTop(ohlcData), minData: 20 }
            ];

            methods.forEach(method => {
                if (ohlcData.length < method.minData) {
                    console.warn(`[SignalDetector] 跳过${method.name}检测:数据不足(需要${method.minData}根)`);
                    return;
                }

                try {
                    const signals = method.fn();
                    if (signals && Array.isArray(signals)) {
                        allSignals.push(...signals);
                    }
                } catch (error) {
                    console.error(`[SignalDetector] ${method.name}检测失败:`, error);
                }
            });

            // 预警检测方法
            const alertMethods = [
                { name: 'RSI', fn: () => this.detectRSI(ohlcData, thresholds), minData: 15 },
                { name: '布林带', fn: () => this.detectBollinger(ohlcData, thresholds), minData: 20 },
                { name: '成交量', fn: () => this.detectVolumeAnomaly(ohlcData, thresholds), minData: 6 },
                { name: '均线', fn: () => this.detectMABreak(ohlcData), minData: 21 },
                { name: 'MACD', fn: () => this.detectMACD(ohlcData), minData: 36 }
            ];

            alertMethods.forEach(method => {
                if (ohlcData.length < method.minData) {
                    return;
                }

                try {
                    const alerts = method.fn();
                    if (alerts && Array.isArray(alerts)) {
                        allAlerts.push(...alerts);
                    }
                } catch (error) {
                    console.error(`[SignalDetector] ${method.name}预警检测失败:`, error);
                }
            });

            // 按K线索引排序
            allSignals.sort((a, b) => a.index - b.index);

            // 分离买点和卖点信号
            const buySignals = allSignals.filter(s => s.type === "buy");
            const sellSignals = allSignals.filter(s => s.type === "sell");

            console.log(`[SignalDetector] 检测完成:买点${buySignals.length}个,卖点${sellSignals.length}个,预警${allAlerts.length}个`);

            return { buySignals, sellSignals, alerts: allAlerts };
        } catch (error) {
            console.error('[SignalDetector] detectAll执行失败:', error);
            return { buySignals: [], sellSignals: [], alerts: [] };
        }
    },

    /**
     * 缩量突破信号检测
     * @param {Array} ohlcData - OHLC数据数组
     * @returns {Array} - 买点信号数组
     */
    detectVolumeBreakout(ohlcData) {
        const signals = [];

        for (let i = 4; i < ohlcData.length; i++) {
            // 检查前3天是否缩量下跌
            let shrinking = true;
            let shrinkDays = 0;

            for (let j = i - 3; j < i; j++) {
                if (ohlcData[j].volume >= ohlcData[j-1].volume || ohlcData[j].close >= ohlcData[j-1].close) {
                    shrinking = false;
                    break;
                }
                shrinkDays++;
            }

            if (shrinking && shrinkDays >= 3) {
                // 检查当日是否放量上涨
                const avgVolume = average(ohlcData.slice(i-3, i).map(d => d.volume));
                const volumeRatio = ohlcData[i].volume / avgVolume;

                if (volumeRatio >= 1.5 && ohlcData[i].close > ohlcData[i-1].close) {
                    signals.push({
                        index: i,
                        type: "buy",
                        name: "缩量突破",
                        description: `连续${shrinkDays}天缩量下跌后放量上涨，放量倍数${volumeRatio.toFixed(1)}倍`,
                        data: {
                            shrinkDays: shrinkDays,
                            volumeRatio: volumeRatio
                        }
                    });
                }
            }
        }

        return signals;
    },

    /**
     * 突破历史新高信号检测
     * @param {Array} ohlcData - OHLC数据数组
     * @param {Number} lookback - 回看天数（默认60日）
     * @returns {Array} - 买点信号数组
     */
    detectNewHigh(ohlcData, lookback = 60) {
        const signals = [];

        for (let i = lookback; i < ohlcData.length; i++) {
            const historicalHigh = Math.max(...ohlcData.slice(i - lookback, i).map(d => d.high));

            if (ohlcData[i].close > historicalHigh) {
                signals.push({
                    index: i,
                    type: "buy",
                    name: "突破历史新高",
                    description: `突破${lookback}日新高，前高${historicalHigh.toFixed(2)}，现价${ohlcData[i].close.toFixed(2)}`,
                    data: {
                        lookbackDays: lookback,
                        previousHigh: historicalHigh,
                        currentPrice: ohlcData[i].close
                    }
                });
            }
        }

        return signals;
    },

    /**
     * 顶部巨量信号检测
     * @param {Array} ohlcData - OHLC数据数组
     * @param {Number} lookback - 回看天数（默认20日）
     * @returns {Array} - 卖点信号数组
     */
    detectTopVolume(ohlcData, lookback = 20) {
        const signals = [];

        for (let i = lookback; i < ohlcData.length; i++) {
            const avgVolume = average(ohlcData.slice(i - lookback, i).map(d => d.volume));
            const volumeRatio = ohlcData[i].volume / avgVolume;

            // 检查是否在近期高位（价格在近20日高点附近5%以内）
            const recentHigh = Math.max(...ohlcData.slice(i - lookback, i + 1).map(d => d.high));
            const isNearTop = ohlcData[i].high >= recentHigh * 0.95;

            if (volumeRatio >= 3 && isNearTop) {
                signals.push({
                    index: i,
                    type: "sell",
                    name: "顶部巨量",
                    description: `成交量为${lookback}日均量的${volumeRatio.toFixed(1)}倍，处于近期高位`,
                    data: {
                        volumeRatio: volumeRatio,
                        recentHigh: recentHigh,
                        currentHigh: ohlcData[i].high
                    }
                });
            }
        }

        return signals;
    },

    /**
     * 均线突破/跌破信号检测
     * @param {Array} ohlcData - OHLC数据数组
     * @returns {Array} - 买点/卖点信号数组
     */
    detectMA5Cross(ohlcData) {
        const signals = [];
        const ma5 = calculateMA(ohlcData, 5);

        for (let i = 1; i < ohlcData.length; i++) {
            if (!ma5[i] || !ma5[i-1]) continue;

            const prevAboveMA = ohlcData[i-1].close > ma5[i-1];
            const currAboveMA = ohlcData[i].close > ma5[i];

            if (!prevAboveMA && currAboveMA) {
                signals.push({
                    index: i,
                    type: "buy",
                    name: "突破5日均线",
                    description: `股价从${ohlcData[i-1].close.toFixed(2)}突破至${ohlcData[i].close.toFixed(2)}，均线值${ma5[i].toFixed(2)}`,
                    data: {
                        previousClose: ohlcData[i-1].close,
                        currentClose: ohlcData[i].close,
                        ma5Value: ma5[i]
                    }
                });
            } else if (prevAboveMA && !currAboveMA) {
                signals.push({
                    index: i,
                    type: "sell",
                    name: "跌破5日均线",
                    description: `股价从${ohlcData[i-1].close.toFixed(2)}跌至${ohlcData[i].close.toFixed(2)}，均线值${ma5[i].toFixed(2)}`,
                    data: {
                        previousClose: ohlcData[i-1].close,
                        currentClose: ohlcData[i].close,
                        ma5Value: ma5[i]
                    }
                });
            }
        }

        return signals;
    },

    /**
     * 双底形态信号检测
     * @param {Array} ohlcData - OHLC数据数组
     * @param {Number} tolerance - 价格误差容忍度（默认0.03即3%）
     * @returns {Array} - 买点信号数组
     */
    detectDoubleBottom(ohlcData, tolerance = 0.03) {
        const signals = [];
        const lows = findLocalMinima(ohlcData, 5);

        for (let i = 1; i < lows.length; i++) {
            const first = lows[i-1];
            const second = lows[i];

            // 检查两个底部价格是否接近（误差3%以内）
            const priceDiff = Math.abs(ohlcData[first].low - ohlcData[second].low) / ohlcData[first].low;
            if (priceDiff > tolerance) continue;

            // 找中间的反弹高点（颈线）
            const middleHigh = Math.max(...ohlcData.slice(first, second + 1).map(d => d.high));
            const necklineIndex = ohlcData.slice(first, second + 1).findIndex(d => d.high === middleHigh) + first;

            // 检查突破颈线
            for (let j = second + 1; j < Math.min(second + 10, ohlcData.length); j++) {
                if (ohlcData[j].close > middleHigh) {
                    const vol1 = ohlcData[first].volume;
                    const vol2 = ohlcData[second].volume;
                    const volumeNote = vol2 < vol1 ? "，缩量确认" : "";

                    signals.push({
                        index: j,
                        type: "buy",
                        name: "双底形态",
                        description: `W底形成，底部${ohlcData[first].low.toFixed(2)}/${ohlcData[second].low.toFixed(2)}，颈线${middleHigh.toFixed(2)}${volumeNote}`,
                        data: {
                            firstBottom: ohlcData[first].low,
                            secondBottom: ohlcData[second].low,
                            neckline: middleHigh,
                            volumeConfirmed: vol2 < vol1
                        }
                    });
                    break;
                }
            }
        }

        return signals;
    },

    /**
     * RSI 超买超卖预警检测
     * @param {Array} ohlcData - OHLC数据数组
     * @param {Object} thresholds - 阈值配置 {rsiOverbought, rsiOversold}
     * @returns {Array} - 预警信号数组
     */
    detectRSI(ohlcData, thresholds = { rsiOverbought: 70, rsiOversold: 30 }) {
        const alerts = [];
        const rsi = calculateRSI(ohlcData, 14);
        const lastIdx = ohlcData.length - 1;

        if (lastIdx < 0 || rsi[lastIdx] === null) return alerts;

        const currentRSI = rsi[lastIdx];

        if (currentRSI >= thresholds.rsiOverbought) {
            alerts.push({
                index: lastIdx,
                alertType: 'RSI_OVERBOUGHT',
                type: 'sell',
                name: 'RSI超买',
                description: `RSI达到${currentRSI.toFixed(1)}，超买阈值${thresholds.rsiOverbought}`,
                data: {
                    rsiValue: currentRSI,
                    threshold: thresholds.rsiOverbought
                }
            });
        }

        if (currentRSI <= thresholds.rsiOversold) {
            alerts.push({
                index: lastIdx,
                alertType: 'RSI_OVERSOLD',
                type: 'buy',
                name: 'RSI超卖',
                description: `RSI达到${currentRSI.toFixed(1)}，超卖阈值${thresholds.rsiOversold}`,
                data: {
                    rsiValue: currentRSI,
                    threshold: thresholds.rsiOversold
                }
            });
        }

        return alerts;
    },

    /**
     * 布林带预警检测
     * @param {Array} ohlcData - OHLC数据数组
     * @param {Object} thresholds - 阈值配置 {bollingerWidth}
     * @returns {Array} - 预警信号数组
     */
    detectBollinger(ohlcData, thresholds = { bollingerWidth: 2 }) {
        const alerts = [];
        const bollinger = calculateBollinger(ohlcData, 20, thresholds.bollingerWidth);
        const lastIdx = ohlcData.length - 1;

        if (lastIdx < 19 || bollinger.upper[lastIdx] === null) return alerts;

        const currentPrice = ohlcData[lastIdx].close;
        const upperBand = bollinger.upper[lastIdx];
        const lowerBand = bollinger.lower[lastIdx];
        const currentWidth = bollinger.width[lastIdx];

        // 触及/突破上轨
        if (currentPrice >= upperBand * 0.98) {
            alerts.push({
                index: lastIdx,
                alertType: 'BOLLINGER_UPPER',
                type: 'sell',
                name: '触及布林上轨',
                description: `当前价${currentPrice.toFixed(2)}接近/超过上轨${upperBand.toFixed(2)}`,
                data: {
                    price: currentPrice,
                    upperBand: upperBand
                }
            });
        }

        // 触及/跌破下轨
        if (currentPrice <= lowerBand * 1.02) {
            alerts.push({
                index: lastIdx,
                alertType: 'BOLLINGER_LOWER',
                type: 'buy',
                name: '触及布林下轨',
                description: `当前价${currentPrice.toFixed(2)}接近/跌破下轨${lowerBand.toFixed(2)}`,
                data: {
                    price: currentPrice,
                    lowerBand: lowerBand
                }
            });
        }

        // 布林带收窄（宽度低于历史平均的50%）
        const recentWidths = bollinger.width.slice(-20).filter(w => w !== null);
        if (recentWidths.length >= 10) {
            const avgWidth = recentWidths.reduce((a, b) => a + b, 0) / recentWidths.length;
            if (currentWidth < avgWidth * 0.5) {
                alerts.push({
                    index: lastIdx,
                    alertType: 'BOLLINGER_SQUEEZE',
                    type: 'neutral',
                    name: '布林带收窄',
                    description: `布林带宽度${currentWidth.toFixed(2)}%低于平均${avgWidth.toFixed(2)}%的50%，可能变盘`,
                    data: {
                        currentWidth: currentWidth,
                        avgWidth: avgWidth
                    }
                });
            }
        }

        return alerts;
    },

    /**
     * MACD 预警检测
     * @param {Array} ohlcData - OHLC数据数组
     * @returns {Array} - 预警信号数组
     */
    detectMACD(ohlcData) {
        const alerts = [];
        const lastIdx = ohlcData.length - 1;

        if (lastIdx < 35) return alerts;

        const macd = calculateMACD(ohlcData);

        // 金叉/死叉检测
        if (macd.dif[lastIdx] !== null && macd.dea[lastIdx] !== null &&
            macd.dif[lastIdx - 1] !== null && macd.dea[lastIdx - 1] !== null) {

            const prevAbove = macd.dif[lastIdx - 1] > macd.dea[lastIdx - 1];
            const currAbove = macd.dif[lastIdx] > macd.dea[lastIdx];

            if (!prevAbove && currAbove) {
                alerts.push({
                    index: lastIdx,
                    alertType: 'MACD_GOLDEN_CROSS',
                    type: 'buy',
                    name: 'MACD金叉',
                    description: `DIF(${macd.dif[lastIdx].toFixed(3)})上穿DEA(${macd.dea[lastIdx].toFixed(3)})`,
                    data: { dif: macd.dif[lastIdx], dea: macd.dea[lastIdx] }
                });
            } else if (prevAbove && !currAbove) {
                alerts.push({
                    index: lastIdx,
                    alertType: 'MACD_DEATH_CROSS',
                    type: 'sell',
                    name: 'MACD死叉',
                    description: `DIF(${macd.dif[lastIdx].toFixed(3)})下穿DEA(${macd.dea[lastIdx].toFixed(3)})`,
                    data: { dif: macd.dif[lastIdx], dea: macd.dea[lastIdx] }
                });
            }
        }

        // 背离检测（近20日内）
        if (lastIdx >= 40) {
            const lookback = 20;
            const recentData = ohlcData.slice(-lookback);
            const recentDif = macd.dif.slice(-lookback);
            const recentPrices = recentData.map(d => d.close);

            const priceHigh = Math.max(...recentPrices);
            const priceLow = Math.min(...recentPrices);
            const validDif = recentDif.filter(d => d !== null);
            const difHigh = Math.max(...validDif);
            const difLow = Math.min(...validDif);

            const currentPrice = ohlcData[lastIdx].close;
            const currentDif = macd.dif[lastIdx];

            // 顶背离：价格接近新高但DIF没有新高
            if (currentPrice >= priceHigh * 0.98 && currentDif < difHigh * 0.8 && currentDif > 0) {
                alerts.push({
                    index: lastIdx,
                    alertType: 'MACD_TOP_DIVERGENCE',
                    type: 'sell',
                    name: 'MACD顶背离',
                    description: `价格接近${lookback}日高点，但MACD未创新高`,
                    data: { price: currentPrice, priceHigh, dif: currentDif, difHigh }
                });
            }

            // 底背离：价格接近新低但DIF没有新低
            if (currentPrice <= priceLow * 1.02 && currentDif > difLow * 0.8 && currentDif < 0) {
                alerts.push({
                    index: lastIdx,
                    alertType: 'MACD_BOTTOM_DIVERGENCE',
                    type: 'buy',
                    name: 'MACD底背离',
                    description: `价格接近${lookback}日低点，但MACD未创新低`,
                    data: { price: currentPrice, priceLow, dif: currentDif, difLow }
                });
            }
        }

        return alerts;
    },

    /**
     * 均线突破/跌破预警检测
     * @param {Array} ohlcData - OHLC数据数组
     * @returns {Array} - 预警信号数组
     */
    detectMABreak(ohlcData) {
        const alerts = [];
        const lastIdx = ohlcData.length - 1;

        if (lastIdx < 20) return alerts;

        const ma5 = calculateMA(ohlcData, 5);
        const ma10 = calculateMA(ohlcData, 10);
        const ma20 = calculateMA(ohlcData, 20);

        const currentPrice = ohlcData[lastIdx].close;
        const prevPrice = ohlcData[lastIdx - 1].close;

        // 检测5日线
        if (ma5[lastIdx] && ma5[lastIdx - 1]) {
            if (prevPrice >= ma5[lastIdx - 1] && currentPrice < ma5[lastIdx]) {
                alerts.push({
                    index: lastIdx,
                    alertType: 'MA_BREAK_DOWN_5',
                    type: 'sell',
                    name: '跌破5日线',
                    description: `股价${currentPrice.toFixed(2)}跌破5日均线${ma5[lastIdx].toFixed(2)}`,
                    data: { price: currentPrice, maValue: ma5[lastIdx] }
                });
            } else if (prevPrice <= ma5[lastIdx - 1] && currentPrice > ma5[lastIdx]) {
                alerts.push({
                    index: lastIdx,
                    alertType: 'MA_BREAK_UP_5',
                    type: 'buy',
                    name: '突破5日线',
                    description: `股价${currentPrice.toFixed(2)}突破5日均线${ma5[lastIdx].toFixed(2)}`,
                    data: { price: currentPrice, maValue: ma5[lastIdx] }
                });
            }
        }

        // 检测10日线
        if (ma10[lastIdx] && ma10[lastIdx - 1]) {
            if (prevPrice >= ma10[lastIdx - 1] && currentPrice < ma10[lastIdx]) {
                alerts.push({
                    index: lastIdx,
                    alertType: 'MA_BREAK_DOWN_10',
                    type: 'sell',
                    name: '跌破10日线',
                    description: `股价${currentPrice.toFixed(2)}跌破10日均线${ma10[lastIdx].toFixed(2)}`,
                    data: { price: currentPrice, maValue: ma10[lastIdx] }
                });
            } else if (prevPrice <= ma10[lastIdx - 1] && currentPrice > ma10[lastIdx]) {
                alerts.push({
                    index: lastIdx,
                    alertType: 'MA_BREAK_UP_10',
                    type: 'buy',
                    name: '突破10日线',
                    description: `股价${currentPrice.toFixed(2)}突破10日均线${ma10[lastIdx].toFixed(2)}`,
                    data: { price: currentPrice, maValue: ma10[lastIdx] }
                });
            }
        }

        // 检测20日线
        if (ma20[lastIdx] && ma20[lastIdx - 1]) {
            if (prevPrice >= ma20[lastIdx - 1] && currentPrice < ma20[lastIdx]) {
                alerts.push({
                    index: lastIdx,
                    alertType: 'MA_BREAK_DOWN_20',
                    type: 'sell',
                    name: '跌破20日线',
                    description: `股价${currentPrice.toFixed(2)}跌破20日均线${ma20[lastIdx].toFixed(2)}`,
                    data: { price: currentPrice, maValue: ma20[lastIdx] }
                });
            } else if (prevPrice <= ma20[lastIdx - 1] && currentPrice > ma20[lastIdx]) {
                alerts.push({
                    index: lastIdx,
                    alertType: 'MA_BREAK_UP_20',
                    type: 'buy',
                    name: '突破20日线',
                    description: `股价${currentPrice.toFixed(2)}突破20日均线${ma20[lastIdx].toFixed(2)}`,
                    data: { price: currentPrice, maValue: ma20[lastIdx] }
                });
            }
        }

        // 检测均线金叉/死叉（5日线与10日线）
        if (ma5[lastIdx] && ma5[lastIdx - 1] && ma10[lastIdx] && ma10[lastIdx - 1]) {
            const prevAbove = ma5[lastIdx - 1] > ma10[lastIdx - 1];
            const currAbove = ma5[lastIdx] > ma10[lastIdx];

            if (!prevAbove && currAbove) {
                alerts.push({
                    index: lastIdx,
                    alertType: 'MA_GOLDEN_CROSS',
                    type: 'buy',
                    name: '均线金叉',
                    description: `5日均线${ma5[lastIdx].toFixed(2)}上穿10日均线${ma10[lastIdx].toFixed(2)}`,
                    data: { ma5: ma5[lastIdx], ma10: ma10[lastIdx] }
                });
            } else if (prevAbove && !currAbove) {
                alerts.push({
                    index: lastIdx,
                    alertType: 'MA_DEATH_CROSS',
                    type: 'sell',
                    name: '均线死叉',
                    description: `5日均线${ma5[lastIdx].toFixed(2)}下穿10日均线${ma10[lastIdx].toFixed(2)}`,
                    data: { ma5: ma5[lastIdx], ma10: ma10[lastIdx] }
                });
            }
        }

        return alerts;
    },

    /**
     * 成交量异常预警检测
     * @param {Array} ohlcData - OHLC数据数组
     * @param {Object} thresholds - 阈值配置 {volumeRatio, volumeShrinkRatio}
     * @returns {Array} - 预警信号数组
     */
    detectVolumeAnomaly(ohlcData, thresholds = { volumeRatio: 2.0, volumeShrinkRatio: 0.5 }) {
        const alerts = [];
        const lastIdx = ohlcData.length - 1;

        if (lastIdx < 5) return alerts;

        // 计算5日均量
        const recentVolumes = ohlcData.slice(-6, -1).map(d => d.volume);
        const avgVolume = recentVolumes.reduce((a, b) => a + b, 0) / 5;
        const currentVolume = ohlcData[lastIdx].volume;
        const volumeRatio = currentVolume / avgVolume;

        // 放量检测
        if (volumeRatio >= thresholds.volumeRatio) {
            alerts.push({
                index: lastIdx,
                alertType: 'VOLUME_SURGE',
                type: 'neutral',
                name: '放量',
                description: `成交量为5日均量的${volumeRatio.toFixed(1)}倍`,
                data: {
                    currentVolume: currentVolume,
                    avgVolume: avgVolume,
                    ratio: volumeRatio
                }
            });
        }

        // 缩量检测
        if (volumeRatio <= thresholds.volumeShrinkRatio) {
            alerts.push({
                index: lastIdx,
                alertType: 'VOLUME_SHRINK',
                type: 'neutral',
                name: '缩量',
                description: `成交量仅为5日均量的${(volumeRatio * 100).toFixed(0)}%`,
                data: {
                    currentVolume: currentVolume,
                    avgVolume: avgVolume,
                    ratio: volumeRatio
                }
            });
        }

        // 量价背离检测（价格新高但成交量萎缩）
        if (lastIdx >= 20) {
            const recentPrices = ohlcData.slice(-20);
            const maxPrice = Math.max(...recentPrices.map(d => d.high));
            const currentPrice = ohlcData[lastIdx].close;

            // 价格接近或创新高
            if (currentPrice >= maxPrice * 0.98) {
                // 但成交量低于平均
                const recentVolumeAvg = average(recentPrices.slice(0, -1).map(d => d.volume));
                if (currentVolume < recentVolumeAvg * 0.8) {
                    alerts.push({
                        index: lastIdx,
                        alertType: 'VOLUME_PRICE_DIVERGENCE',
                        type: 'sell',
                        name: '量价背离',
                        description: `价格接近20日高点${maxPrice.toFixed(2)}，但成交量萎缩`,
                        data: {
                            currentPrice: currentPrice,
                            maxPrice: maxPrice,
                            currentVolume: currentVolume,
                            avgVolume: recentVolumeAvg
                        }
                    });
                }
            }
        }

        return alerts;
    },

    /**
     * 双顶形态信号检测
     * @param {Array} ohlcData - OHLC数据数组
     * @param {Number} tolerance - 价格误差容忍度（默认0.03即3%）
     * @returns {Array} - 卖点信号数组
     */
    detectDoubleTop(ohlcData, tolerance = 0.03) {
        const signals = [];
        const highs = findLocalMaxima(ohlcData, 5);

        for (let i = 1; i < highs.length; i++) {
            const first = highs[i-1];
            const second = highs[i];

            // 检查两个顶部价格是否接近（误差3%以内）
            const priceDiff = Math.abs(ohlcData[first].high - ohlcData[second].high) / ohlcData[first].high;
            if (priceDiff > tolerance) continue;

            // 找中间的回调低点（颈线）
            const middleLow = Math.min(...ohlcData.slice(first, second + 1).map(d => d.low));

            // 检查跌破颈线
            for (let j = second + 1; j < Math.min(second + 10, ohlcData.length); j++) {
                if (ohlcData[j].close < middleLow) {
                    const vol1 = ohlcData[first].volume;
                    const vol2 = ohlcData[second].volume;
                    const volumeNote = vol2 < vol1 ? "，量能背离" : "";

                    signals.push({
                        index: j,
                        type: "sell",
                        name: "双顶形态",
                        description: `M头形成，顶部${ohlcData[first].high.toFixed(2)}/${ohlcData[second].high.toFixed(2)}，颈线${middleLow.toFixed(2)}${volumeNote}`,
                        data: {
                            firstTop: ohlcData[first].high,
                            secondTop: ohlcData[second].high,
                            neckline: middleLow,
                            volumeDivergence: vol2 < vol1
                        }
                    });
                    break;
                }
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
