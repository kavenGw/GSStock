/**
 * AlertEngine - 预警引擎模块
 * 基于 SignalDetector 的信号检测，提供预警配置、评估和 UI 渲染
 */

// 预警类型定义（18种）
const ALERT_TYPES = {
    // 均线跌破（3种）
    MA_BREAK_DOWN_5: { level: 'medium', category: 'trend', label: '跌破5日线', signal: 'sell' },
    MA_BREAK_DOWN_10: { level: 'medium', category: 'trend', label: '跌破10日线', signal: 'sell' },
    MA_BREAK_DOWN_20: { level: 'high', category: 'trend', label: '跌破20日线', signal: 'sell' },
    // 均线突破（3种）
    MA_BREAK_UP_5: { level: 'medium', category: 'trend', label: '突破5日线', signal: 'buy' },
    MA_BREAK_UP_10: { level: 'medium', category: 'trend', label: '突破10日线', signal: 'buy' },
    MA_BREAK_UP_20: { level: 'high', category: 'trend', label: '突破20日线', signal: 'buy' },
    // 均线交叉（2种）
    MA_GOLDEN_CROSS: { level: 'high', category: 'trend', label: '均线金叉', signal: 'buy' },
    MA_DEATH_CROSS: { level: 'high', category: 'trend', label: '均线死叉', signal: 'sell' },

    // MACD相关（4种）
    MACD_GOLDEN_CROSS: { level: 'high', category: 'momentum', label: 'MACD金叉', signal: 'buy' },
    MACD_DEATH_CROSS: { level: 'high', category: 'momentum', label: 'MACD死叉', signal: 'sell' },
    MACD_TOP_DIVERGENCE: { level: 'high', category: 'momentum', label: 'MACD顶背离', signal: 'sell' },
    MACD_BOTTOM_DIVERGENCE: { level: 'high', category: 'momentum', label: 'MACD底背离', signal: 'buy' },

    // RSI相关（2种）
    RSI_OVERBOUGHT: { level: 'medium', category: 'momentum', label: 'RSI超买', signal: 'sell' },
    RSI_OVERSOLD: { level: 'medium', category: 'momentum', label: 'RSI超卖', signal: 'buy' },

    // 布林带相关（3种）
    BOLLINGER_UPPER: { level: 'low', category: 'volatility', label: '触及布林上轨', signal: 'sell' },
    BOLLINGER_LOWER: { level: 'low', category: 'volatility', label: '触及布林下轨', signal: 'buy' },
    BOLLINGER_SQUEEZE: { level: 'medium', category: 'volatility', label: '布林带收窄', signal: 'neutral' },

    // 成交量相关（3种）
    VOLUME_SURGE: { level: 'medium', category: 'volume', label: '放量', signal: 'neutral' },
    VOLUME_SHRINK: { level: 'low', category: 'volume', label: '缩量', signal: 'neutral' },
    VOLUME_PRICE_DIVERGENCE: { level: 'high', category: 'volume', label: '量价背离', signal: 'sell' }
};

// 默认配置
const DEFAULT_CONFIG = {
    enabledCategories: [],
    thresholds: {
        rsiOverbought: 70,
        rsiOversold: 30,
        volumeRatio: 2.0,
        volumeShrinkRatio: 0.5,
        bollingerWidth: 2
    },
    disabledTypes: [],
    version: 1
};

const STORAGE_KEY = 'alert_config';

const AlertEngine = {
    // 配置对象
    config: {
        enabledCategories: new Set(),
        thresholds: {},
        disabledTypes: new Set()
    },

    // 预警缓存
    alertCache: {
        lastUpdate: 0,
        alerts: {},
        summary: {
            high: 0,
            medium: 0,
            low: 0,
            byCategory: {}
        }
    },

    /**
     * 初始化预警引擎
     */
    init() {
        this.loadConfig();
        console.log('[AlertEngine] 初始化完成');
    },

    /**
     * 从 localStorage 加载配置
     */
    loadConfig() {
        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            if (stored) {
                const parsed = JSON.parse(stored);
                this.config.enabledCategories = new Set(parsed.enabledCategories || []);
                this.config.thresholds = { ...DEFAULT_CONFIG.thresholds, ...parsed.thresholds };
                this.config.disabledTypes = new Set(parsed.disabledTypes || []);
            } else {
                this.config.enabledCategories = new Set(DEFAULT_CONFIG.enabledCategories);
                this.config.thresholds = { ...DEFAULT_CONFIG.thresholds };
                this.config.disabledTypes = new Set(DEFAULT_CONFIG.disabledTypes);
            }
        } catch (e) {
            console.warn('[AlertEngine] 加载配置失败，使用默认配置:', e);
            this.config.enabledCategories = new Set(DEFAULT_CONFIG.enabledCategories);
            this.config.thresholds = { ...DEFAULT_CONFIG.thresholds };
            this.config.disabledTypes = new Set(DEFAULT_CONFIG.disabledTypes);
        }
    },

    /**
     * 保存配置到 localStorage
     */
    saveConfig() {
        try {
            const toStore = {
                enabledCategories: Array.from(this.config.enabledCategories),
                thresholds: this.config.thresholds,
                disabledTypes: Array.from(this.config.disabledTypes),
                version: DEFAULT_CONFIG.version
            };
            localStorage.setItem(STORAGE_KEY, JSON.stringify(toStore));
        } catch (e) {
            console.warn('[AlertEngine] 保存配置失败:', e);
        }
    },

    /**
     * 更新阈值配置
     * @param {Object} newThresholds - 新的阈值配置
     */
    updateThresholds(newThresholds) {
        this.config.thresholds = { ...this.config.thresholds, ...newThresholds };
        this.saveConfig();
    },

    /**
     * 切换预警类型启用状态
     * @param {string} alertType - 预警类型
     */
    toggleAlertType(alertType) {
        if (this.config.disabledTypes.has(alertType)) {
            this.config.disabledTypes.delete(alertType);
        } else {
            this.config.disabledTypes.add(alertType);
        }
        this.saveConfig();
    },

    /**
     * 检查预警类型是否启用
     * @param {string} alertType - 预警类型
     * @returns {boolean}
     */
    isAlertTypeEnabled(alertType) {
        return !this.config.disabledTypes.has(alertType);
    },

    /**
     * 切换分类预警开关
     * @param {number|string} categoryId - 分类ID
     * @returns {boolean} - 切换后的状态（true=开启）
     */
    toggleCategory(categoryId) {
        const id = Number(categoryId);
        if (this.config.enabledCategories.has(id)) {
            this.config.enabledCategories.delete(id);
            this.saveConfig();
            return false;
        } else {
            this.config.enabledCategories.add(id);
            this.saveConfig();
            return true;
        }
    },

    /**
     * 检查分类预警是否启用
     * @param {number|string} categoryId - 分类ID
     * @returns {boolean}
     */
    isCategoryEnabled(categoryId) {
        return this.config.enabledCategories.has(Number(categoryId));
    },

    /**
     * 获取所有启用预警的分类ID
     * @returns {number[]}
     */
    getEnabledCategories() {
        return Array.from(this.config.enabledCategories);
    },

    /**
     * 评估股票预警
     * @param {Array} stocks - 股票列表 [{code, name, categoryId, ...}]
     * @param {Object} ohlcDataMap - OHLC 数据映射 {stockCode: ohlcData[]}
     * @returns {Object} - {alerts: {stockCode: Alert[]}, summary: {high, medium, low, byCategory}}
     */
    evaluate(stocks, ohlcDataMap) {
        const alerts = {};
        const summary = {
            high: 0,
            medium: 0,
            low: 0,
            byCategory: {}
        };

        if (!stocks || stocks.length === 0) {
            return { alerts, summary };
        }

        const enabledCategories = this.getEnabledCategories();
        if (enabledCategories.length === 0) {
            return { alerts, summary };
        }

        stocks.forEach(stock => {
            const categoryId = Number(stock.categoryId || stock.category_id || 0);

            if (!this.isCategoryEnabled(categoryId)) {
                return;
            }

            const ohlcData = ohlcDataMap[stock.code];
            if (!ohlcData || ohlcData.length < 20) {
                return;
            }

            try {
                const result = SignalDetector.detectAll(ohlcData, this.config.thresholds);
                const stockAlerts = [];

                if (result.alerts && result.alerts.length > 0) {
                    result.alerts.forEach(alert => {
                        if (!this.isAlertTypeEnabled(alert.alertType)) {
                            return;
                        }

                        const typeInfo = ALERT_TYPES[alert.alertType] || { level: 'low' };
                        const fullAlert = {
                            ...alert,
                            stockCode: stock.code,
                            stockName: stock.name,
                            level: typeInfo.level,
                            category: typeInfo.category,
                            timestamp: Date.now()
                        };

                        stockAlerts.push(fullAlert);

                        // 更新汇总计数
                        summary[typeInfo.level]++;
                        summary.byCategory[categoryId] = (summary.byCategory[categoryId] || 0) + 1;
                    });
                }

                if (stockAlerts.length > 0) {
                    alerts[stock.code] = stockAlerts;
                }
            } catch (e) {
                console.warn(`[AlertEngine] 评估股票 ${stock.code} 失败:`, e);
            }
        });

        // 更新缓存
        this.alertCache = {
            lastUpdate: Date.now(),
            alerts,
            summary
        };

        console.log(`[AlertEngine] 评估完成: 高${summary.high} 中${summary.medium} 低${summary.low}`);
        return { alerts, summary };
    },

    /**
     * 获取指定股票的预警
     * @param {string} stockCode - 股票代码
     * @returns {Array} - 预警数组
     */
    getStockAlerts(stockCode) {
        return this.alertCache.alerts[stockCode] || [];
    },

    /**
     * 获取所有预警（扁平化）
     * @returns {Array} - 所有预警数组
     */
    getAllAlerts() {
        const all = [];
        Object.values(this.alertCache.alerts).forEach(stockAlerts => {
            all.push(...stockAlerts);
        });
        return all;
    },

    /**
     * 按级别获取预警
     * @param {string} level - 级别 (high/medium/low)
     * @returns {Array}
     */
    getAlertsByLevel(level) {
        return this.getAllAlerts().filter(a => a.level === level);
    },

    /**
     * 渲染预警汇总面板
     */
    renderSummaryPanel() {
        const panel = document.getElementById('alertSummaryPanel');
        if (!panel) return;

        const summary = this.alertCache.summary;
        const totalAlerts = summary.high + summary.medium + summary.low;

        if (totalAlerts === 0) {
            panel.classList.add('d-none');
            return;
        }

        panel.classList.remove('d-none');

        // 更新各级别计数
        ['high', 'medium', 'low'].forEach(level => {
            const group = panel.querySelector(`.alert-group[data-level="${level}"]`);
            if (group) {
                const countBadge = group.querySelector('.alert-count');
                if (countBadge) {
                    countBadge.textContent = summary[level];
                }

                const itemsContainer = group.querySelector('.alert-items');
                if (itemsContainer) {
                    const alerts = this.getAlertsByLevel(level);
                    itemsContainer.innerHTML = alerts.map(alert => `
                        <div class="alert-item ${level}-level" data-stock-code="${alert.stockCode}" title="${alert.description}">
                            <span class="stock-name">${alert.stockName}</span>
                            <span class="alert-type">${alert.name}</span>
                        </div>
                    `).join('');
                }
            }
        });
    },

    /**
     * 渲染分类徽章（预警计数）
     */
    renderCategoryBadges() {
        const tabs = document.querySelectorAll('.category-tab');
        const byCategory = this.alertCache.summary.byCategory;

        tabs.forEach(tab => {
            const categoryId = Number(tab.dataset.id);
            let badge = tab.querySelector('.alert-count');

            const count = byCategory[categoryId] || 0;

            if (count > 0) {
                if (!badge) {
                    badge = document.createElement('span');
                    badge.className = 'alert-count badge bg-danger';
                    tab.appendChild(badge);
                }
                badge.textContent = count;
                badge.classList.remove('d-none');
            } else if (badge) {
                badge.classList.add('d-none');
            }
        });
    },

    /**
     * 渲染股票预警图标
     * @param {string} stockCode - 股票代码
     * @returns {string} - HTML 字符串
     */
    getStockAlertIcon(stockCode) {
        const alerts = this.getStockAlerts(stockCode);
        if (alerts.length === 0) return '';

        // 决定显示颜色（优先级：sell > buy > neutral）
        let signalClass = 'neutral-signal';
        let icon = 'bi-exclamation-circle-fill';

        const hasSell = alerts.some(a => a.type === 'sell');
        const hasBuy = alerts.some(a => a.type === 'buy');

        if (hasSell) {
            signalClass = 'sell-signal';
            icon = 'bi-exclamation-triangle-fill';
        } else if (hasBuy) {
            signalClass = 'buy-signal';
            icon = 'bi-check-circle-fill';
        }

        return `
            <span class="alert-indicator ${signalClass}" data-stock-code="${stockCode}" title="点击查看${alerts.length}个预警">
                <i class="bi ${icon}"></i>
                ${alerts.length > 1 ? `<span class="alert-badge">${alerts.length}</span>` : ''}
            </span>
        `;
    },

    /**
     * 显示预警详情弹窗
     * @param {string} stockCode - 股票代码
     */
    showAlertDetail(stockCode) {
        const alerts = this.getStockAlerts(stockCode);
        if (alerts.length === 0) return;

        const modal = document.getElementById('signalModal');
        if (!modal) return;

        const typeLabel = alerts[0].type === 'sell' ? '卖出信号' : alerts[0].type === 'buy' ? '买入信号' : '预警信号';
        const typeBadge = modal.querySelector('.signal-type-badge');
        typeBadge.textContent = `${alerts[0].stockName} - ${typeLabel}`;
        typeBadge.className = `signal-type-badge ${alerts[0].type === 'sell' ? 'sell' : alerts[0].type === 'buy' ? 'buy' : ''}`;

        const signalList = modal.querySelector('.signal-list');
        signalList.innerHTML = alerts.map(alert => `
            <div class="signal-item">
                <div class="signal-name">${alert.name}</div>
                <div class="signal-description">${alert.description}</div>
            </div>
        `).join('');

        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
    },

    /**
     * 显示设置弹窗
     */
    showSettingsModal() {
        const modal = document.getElementById('alertSettingsModal');
        if (!modal) return;

        // 填充当前配置值
        const thresholds = this.config.thresholds;

        document.getElementById('rsiOverboughtRange').value = thresholds.rsiOverbought;
        document.getElementById('rsiOverboughtValue').textContent = thresholds.rsiOverbought;

        document.getElementById('rsiOversoldRange').value = thresholds.rsiOversold;
        document.getElementById('rsiOversoldValue').textContent = thresholds.rsiOversold;

        document.getElementById('volumeRatioRange').value = thresholds.volumeRatio;
        document.getElementById('volumeRatioValue').textContent = thresholds.volumeRatio.toFixed(1);

        // 生成预警类型复选框
        const checkboxContainer = document.getElementById('alertTypeCheckboxes');
        checkboxContainer.innerHTML = Object.entries(ALERT_TYPES).map(([type, info]) => `
            <div class="form-check">
                <input class="form-check-input" type="checkbox" id="alert_${type}" value="${type}"
                    ${this.isAlertTypeEnabled(type) ? 'checked' : ''}>
                <label class="form-check-label" for="alert_${type}">${info.label}</label>
            </div>
        `).join('');

        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
    },

    /**
     * 保存设置
     */
    saveSettings() {
        // 保存阈值
        const newThresholds = {
            rsiOverbought: parseInt(document.getElementById('rsiOverboughtRange').value),
            rsiOversold: parseInt(document.getElementById('rsiOversoldRange').value),
            volumeRatio: parseFloat(document.getElementById('volumeRatioRange').value)
        };
        this.config.thresholds = { ...this.config.thresholds, ...newThresholds };

        // 保存预警类型启用状态
        this.config.disabledTypes = new Set();
        Object.keys(ALERT_TYPES).forEach(type => {
            const checkbox = document.getElementById(`alert_${type}`);
            if (checkbox && !checkbox.checked) {
                this.config.disabledTypes.add(type);
            }
        });

        this.saveConfig();

        // 关闭弹窗
        const modal = bootstrap.Modal.getInstance(document.getElementById('alertSettingsModal'));
        if (modal) modal.hide();

        // 触发预警重新计算
        if (typeof triggerAlertRefresh === 'function') {
            triggerAlertRefresh();
        }
    },

    /**
     * 滚动到指定股票并高亮
     * @param {string} stockCode - 股票代码
     */
    scrollToStock(stockCode) {
        // 先尝试精确匹配
        let stockItem = document.querySelector(`.stock-item[data-code="${stockCode}"]`);

        // 如果没找到，可能需要处理一些格式转换
        if (!stockItem && stockCode) {
            const allItems = document.querySelectorAll('.stock-item[data-code]');
            for (const item of allItems) {
                if (item.dataset.code === stockCode || item.dataset.code.includes(stockCode)) {
                    stockItem = item;
                    break;
                }
            }
        }

        if (!stockItem) {
            console.warn(`[AlertEngine] 未找到股票项: ${stockCode}`);
            return;
        }

        stockItem.scrollIntoView({ behavior: 'smooth', block: 'center' });
        stockItem.classList.add('alert-highlight');

        setTimeout(() => {
            stockItem.classList.remove('alert-highlight');
        }, 2000);
    },

    /**
     * 绑定事件
     */
    bindEvents() {
        // 预警项点击 -> 滚动定位
        document.addEventListener('click', (e) => {
            const alertItem = e.target.closest('.alert-item');
            if (alertItem) {
                const stockCode = alertItem.dataset.stockCode;
                if (stockCode) {
                    this.scrollToStock(stockCode);
                }
            }

            const alertIndicator = e.target.closest('.alert-indicator');
            if (alertIndicator) {
                e.stopPropagation();
                const stockCode = alertIndicator.dataset.stockCode;
                if (stockCode) {
                    this.showAlertDetail(stockCode);
                }
            }
        });

        // 设置弹窗滑块变化
        ['rsiOverbought', 'rsiOversold', 'volumeRatio'].forEach(id => {
            const range = document.getElementById(`${id}Range`);
            const value = document.getElementById(`${id}Value`);
            if (range && value) {
                range.addEventListener('input', () => {
                    value.textContent = id === 'volumeRatio' ? parseFloat(range.value).toFixed(1) : range.value;
                });
            }
        });
    }
};
