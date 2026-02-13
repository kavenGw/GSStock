/**
 * AlertPage - 预警页面控制器
 * 独立的预警中心页面，展示所有自选股的技术指标预警
 */

// 指标列配置（按分类组织）
const INDICATOR_COLUMNS = {
    trend: [
        { key: 'MA_BREAK_UP_5', label: 'MA5↑', tooltip: '突破5日线' },
        { key: 'MA_BREAK_DOWN_5', label: 'MA5↓', tooltip: '跌破5日线' },
        { key: 'MA_BREAK_UP_10', label: 'MA10↑', tooltip: '突破10日线' },
        { key: 'MA_BREAK_DOWN_10', label: 'MA10↓', tooltip: '跌破10日线' },
        { key: 'MA_BREAK_UP_20', label: 'MA20↑', tooltip: '突破20日线' },
        { key: 'MA_BREAK_DOWN_20', label: 'MA20↓', tooltip: '跌破20日线' },
        { key: 'MA_GOLDEN_CROSS', label: '金叉', tooltip: '均线金叉' },
        { key: 'MA_DEATH_CROSS', label: '死叉', tooltip: '均线死叉' }
    ],
    momentum: [
        { key: 'RSI_OVERBOUGHT', label: 'RSI↑', tooltip: 'RSI超买' },
        { key: 'RSI_OVERSOLD', label: 'RSI↓', tooltip: 'RSI超卖' },
        { key: 'MACD_GOLDEN_CROSS', label: 'MACD×', tooltip: 'MACD金叉' },
        { key: 'MACD_DEATH_CROSS', label: 'MACD÷', tooltip: 'MACD死叉' },
        { key: 'MACD_TOP_DIVERGENCE', label: '顶背离', tooltip: 'MACD顶背离' },
        { key: 'MACD_BOTTOM_DIVERGENCE', label: '底背离', tooltip: 'MACD底背离' }
    ],
    volatility: [
        { key: 'BOLLINGER_UPPER', label: 'BB↑', tooltip: '触及布林上轨' },
        { key: 'BOLLINGER_LOWER', label: 'BB↓', tooltip: '触及布林下轨' },
        { key: 'BOLLINGER_SQUEEZE', label: 'BB收', tooltip: '布林带收窄' }
    ],
    volume: [
        { key: 'VOLUME_SURGE', label: '放量', tooltip: '成交量放大' },
        { key: 'VOLUME_SHRINK', label: '缩量', tooltip: '成交量萎缩' },
        { key: 'VOLUME_PRICE_DIVERGENCE', label: '量背离', tooltip: '量价背离' }
    ]
};

// 合并指标配置（将成对的方向性指标合并为单一指标）
const MERGED_INDICATOR_CONFIG = {
    MA5: {
        upKey: 'MA_BREAK_UP_5',
        downKey: 'MA_BREAK_DOWN_5',
        label: 'MA5',
        category: 'trend',
        upColor: 'buy',
        downColor: 'sell'
    },
    MA10: {
        upKey: 'MA_BREAK_UP_10',
        downKey: 'MA_BREAK_DOWN_10',
        label: 'MA10',
        category: 'trend',
        upColor: 'buy',
        downColor: 'sell'
    },
    MA20: {
        upKey: 'MA_BREAK_UP_20',
        downKey: 'MA_BREAK_DOWN_20',
        label: 'MA20',
        category: 'trend',
        upColor: 'buy',
        downColor: 'sell'
    },
    RSI: {
        upKey: 'RSI_OVERBOUGHT',
        downKey: 'RSI_OVERSOLD',
        label: 'RSI',
        category: 'momentum',
        upColor: 'sell',
        downColor: 'buy'
    },
    BB: {
        upKey: 'BOLLINGER_UPPER',
        downKey: 'BOLLINGER_LOWER',
        label: 'BB',
        category: 'volatility',
        upColor: 'sell',
        downColor: 'buy'
    }
};

// 指标介绍数据
const INDICATOR_DESCRIPTIONS = {
    MA5: {
        name: 'MA5',
        fullName: '5日移动平均线',
        calculation: '最近5个交易日收盘价的算术平均值',
        signals: {
            up: { meaning: '突破5日均线', implication: '短期趋势转强，可能开启上涨' },
            down: { meaning: '跌破5日均线', implication: '短期趋势转弱，注意风险' }
        }
    },
    MA10: {
        name: 'MA10',
        fullName: '10日移动平均线',
        calculation: '最近10个交易日收盘价的算术平均值',
        signals: {
            up: { meaning: '突破10日均线', implication: '短期趋势确认，上涨动能增强' },
            down: { meaning: '跌破10日均线', implication: '短期趋势转弱，可能持续下跌' }
        }
    },
    MA20: {
        name: 'MA20',
        fullName: '20日移动平均线',
        calculation: '最近20个交易日收盘价的算术平均值',
        signals: {
            up: { meaning: '突破20日均线', implication: '中期趋势转强，上涨趋势确立' },
            down: { meaning: '跌破20日均线', implication: '中期趋势转弱，可能进入调整' }
        }
    },
    RSI: {
        name: 'RSI',
        fullName: '相对强弱指数 (Relative Strength Index)',
        calculation: 'RSI = 100 - 100/(1+RS)，RS为一定时期内平均涨幅与平均跌幅之比',
        signals: {
            up: { meaning: 'RSI超买（>70）', implication: '短期涨幅过大，可能面临回调压力' },
            down: { meaning: 'RSI超卖（<30）', implication: '短期跌幅过大，可能迎来反弹机会' }
        }
    },
    BB: {
        name: 'BB',
        fullName: '布林带 (Bollinger Bands)',
        calculation: '中轨为20日均线，上下轨为中轨±2倍标准差',
        signals: {
            up: { meaning: '触及布林上轨', implication: '价格处于超买区域，可能回调' },
            down: { meaning: '触及布林下轨', implication: '价格处于超卖区域，可能反弹' }
        }
    }
};

// 预警类型定义
const ALERT_TYPES = {
    MA_BREAK_DOWN_5: { level: 'medium', category: 'trend', label: '跌破5日线', signal: 'sell' },
    MA_BREAK_DOWN_10: { level: 'medium', category: 'trend', label: '跌破10日线', signal: 'sell' },
    MA_BREAK_DOWN_20: { level: 'high', category: 'trend', label: '跌破20日线', signal: 'sell' },
    MA_BREAK_UP_5: { level: 'medium', category: 'trend', label: '突破5日线', signal: 'buy' },
    MA_BREAK_UP_10: { level: 'medium', category: 'trend', label: '突破10日线', signal: 'buy' },
    MA_BREAK_UP_20: { level: 'high', category: 'trend', label: '突破20日线', signal: 'buy' },
    MA_GOLDEN_CROSS: { level: 'high', category: 'trend', label: '均线金叉', signal: 'buy' },
    MA_DEATH_CROSS: { level: 'high', category: 'trend', label: '均线死叉', signal: 'sell' },
    MACD_GOLDEN_CROSS: { level: 'high', category: 'momentum', label: 'MACD金叉', signal: 'buy' },
    MACD_DEATH_CROSS: { level: 'high', category: 'momentum', label: 'MACD死叉', signal: 'sell' },
    MACD_TOP_DIVERGENCE: { level: 'high', category: 'momentum', label: 'MACD顶背离', signal: 'sell' },
    MACD_BOTTOM_DIVERGENCE: { level: 'high', category: 'momentum', label: 'MACD底背离', signal: 'buy' },
    RSI_OVERBOUGHT: { level: 'medium', category: 'momentum', label: 'RSI超买', signal: 'sell' },
    RSI_OVERSOLD: { level: 'medium', category: 'momentum', label: 'RSI超卖', signal: 'buy' },
    BOLLINGER_UPPER: { level: 'low', category: 'volatility', label: '触及布林上轨', signal: 'sell' },
    BOLLINGER_LOWER: { level: 'low', category: 'volatility', label: '触及布林下轨', signal: 'buy' },
    BOLLINGER_SQUEEZE: { level: 'medium', category: 'volatility', label: '布林带收窄', signal: 'neutral' },
    VOLUME_SURGE: { level: 'medium', category: 'volume', label: '放量', signal: 'neutral' },
    VOLUME_SHRINK: { level: 'low', category: 'volume', label: '缩量', signal: 'neutral' },
    VOLUME_PRICE_DIVERGENCE: { level: 'high', category: 'volume', label: '量价背离', signal: 'sell' }
};

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
    viewMode: 'card'
};

const STORAGE_KEY = 'alert_config';

const AlertPage = {
    // 数据缓存
    data: {
        stocks: [],
        ohlcData: {},
        categories: [],
        alerts: {},
        summary: { high: 0, medium: 0, low: 0 },
        earningsData: {},
        signalCache: new Map()
    },

    // 配置
    config: {
        enabledCategories: new Set(),
        thresholds: {},
        disabledTypes: new Set(),
        viewMode: 'card'
    },

    // 当前过滤条件
    filter: {
        signalType: 'all'
    },

    /**
     * 初始化
     */
    init() {
        this.loadConfig();
        this.initViewState();
        this.bindEvents();
        this.loadData();
    },

    /**
     * 初始化视图状态
     */
    initViewState() {
        const viewMode = this.config.viewMode;
        document.querySelectorAll('#viewSwitcher .view-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.view === viewMode);
        });
    },

    /**
     * 加载配置
     */
    loadConfig() {
        try {
            const stored = localStorage.getItem(STORAGE_KEY);
            if (stored) {
                const parsed = JSON.parse(stored);
                this.config.enabledCategories = new Set(parsed.enabledCategories || []);
                this.config.thresholds = { ...DEFAULT_CONFIG.thresholds, ...parsed.thresholds };
                this.config.disabledTypes = new Set(parsed.disabledTypes || []);
                this.config.viewMode = parsed.viewMode || DEFAULT_CONFIG.viewMode;
            } else {
                this.config.enabledCategories = new Set(DEFAULT_CONFIG.enabledCategories);
                this.config.thresholds = { ...DEFAULT_CONFIG.thresholds };
                this.config.disabledTypes = new Set(DEFAULT_CONFIG.disabledTypes);
                this.config.viewMode = DEFAULT_CONFIG.viewMode;
            }
        } catch (e) {
            console.warn('[AlertPage] 加载配置失败:', e);
            this.config.enabledCategories = new Set();
            this.config.thresholds = { ...DEFAULT_CONFIG.thresholds };
            this.config.disabledTypes = new Set();
            this.config.viewMode = DEFAULT_CONFIG.viewMode;
        }
    },

    /**
     * 保存配置
     */
    saveConfig() {
        try {
            const toStore = {
                enabledCategories: Array.from(this.config.enabledCategories),
                thresholds: this.config.thresholds,
                disabledTypes: Array.from(this.config.disabledTypes),
                viewMode: this.config.viewMode
            };
            localStorage.setItem(STORAGE_KEY, JSON.stringify(toStore));
        } catch (e) {
            console.warn('[AlertPage] 保存配置失败:', e);
        }
    },

    /**
     * 切换视图
     */
    switchView(viewType) {
        if (viewType !== 'card' && viewType !== 'list') return;
        this.config.viewMode = viewType;
        this.saveConfig();

        // 更新按钮状态
        document.querySelectorAll('#viewSwitcher .view-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.view === viewType);
        });

        this.render();
    },

    /**
     * 获取当前视图
     */
    getCurrentView() {
        return this.config.viewMode;
    },

    /**
     * 获取可见指标列（过滤掉 disabledTypes）
     */
    getVisibleIndicatorColumns() {
        const result = {};
        for (const [category, columns] of Object.entries(INDICATOR_COLUMNS)) {
            const visible = columns.filter(col => !this.config.disabledTypes.has(col.key));
            if (visible.length > 0) {
                result[category] = visible;
            }
        }
        return result;
    },

    /**
     * 获取合并后的指标列配置（用于列表视图）
     */
    getMergedIndicatorColumns() {
        const result = { trend: [], momentum: [], volatility: [] };

        for (const [key, config] of Object.entries(MERGED_INDICATOR_CONFIG)) {
            const upDisabled = this.config.disabledTypes.has(config.upKey);
            const downDisabled = this.config.disabledTypes.has(config.downKey);

            if (upDisabled && downDisabled) continue;

            result[config.category].push({
                key: key,
                label: config.label,
                upKey: config.upKey,
                downKey: config.downKey,
                upColor: config.upColor,
                downColor: config.downColor
            });
        }

        // 添加非合并指标
        const nonMergedIndicators = {
            trend: ['MA_GOLDEN_CROSS', 'MA_DEATH_CROSS'],
            momentum: ['MACD_GOLDEN_CROSS', 'MACD_DEATH_CROSS', 'MACD_TOP_DIVERGENCE', 'MACD_BOTTOM_DIVERGENCE'],
            volatility: ['BOLLINGER_SQUEEZE'],
            volume: ['VOLUME_SURGE', 'VOLUME_SHRINK', 'VOLUME_PRICE_DIVERGENCE']
        };

        for (const [category, keys] of Object.entries(nonMergedIndicators)) {
            if (!result[category]) result[category] = [];
            for (const key of keys) {
                if (this.config.disabledTypes.has(key)) continue;
                const col = Object.values(INDICATOR_COLUMNS).flat().find(c => c.key === key);
                if (col) {
                    result[category].push({ key: col.key, label: col.label, tooltip: col.tooltip, merged: false });
                }
            }
        }

        // 移除空分类
        for (const category of Object.keys(result)) {
            if (result[category].length === 0) delete result[category];
        }

        return result;
    },

    /**
     * 获取股票的指标状态
     */
    getStockIndicatorStates(stockCode) {
        const stockAlerts = this.data.alerts[stockCode] || [];
        const ohlcData = this.data.ohlcData[stockCode];
        const hasData = ohlcData && ohlcData.length >= 20;

        const states = {};

        // 遍历所有指标
        for (const columns of Object.values(INDICATOR_COLUMNS)) {
            for (const col of columns) {
                if (!hasData) {
                    states[col.key] = { triggered: false, type: null, value: null, error: true };
                    continue;
                }

                // 查找该指标是否被触发
                const alert = stockAlerts.find(a => a.alertType === col.key);
                if (alert) {
                    states[col.key] = {
                        triggered: true,
                        type: alert.type,
                        value: alert.description || null,
                        error: false
                    };
                } else {
                    states[col.key] = { triggered: false, type: null, value: null, error: false };
                }
            }
        }

        return states;
    },

    /**
     * 获取合并指标的状态
     */
    getStockMergedState(stockCode, mergedKey) {
        const config = MERGED_INDICATOR_CONFIG[mergedKey];
        if (!config) {
            return { direction: 'neutral', colorClass: 'inactive', symbol: '—', triggered: false, description: null };
        }

        const stockAlerts = this.data.alerts[stockCode] || [];
        const ohlcData = this.data.ohlcData[stockCode];
        const hasData = ohlcData && ohlcData.length >= 20;

        if (!hasData) {
            return { direction: 'neutral', colorClass: 'inactive', symbol: '—', triggered: false, description: null, error: true };
        }

        const upAlert = stockAlerts.find(a => a.alertType === config.upKey);
        const downAlert = stockAlerts.find(a => a.alertType === config.downKey);

        // 同时触发上下信号时返回中性状态
        if (upAlert && downAlert) {
            return { direction: 'neutral', colorClass: 'inactive', symbol: '—', triggered: false, description: null };
        }

        if (upAlert) {
            return {
                direction: 'up',
                colorClass: config.upColor,
                symbol: '↑',
                triggered: true,
                description: upAlert.description || null
            };
        }

        if (downAlert) {
            return {
                direction: 'down',
                colorClass: config.downColor,
                symbol: '↓',
                triggered: true,
                description: downAlert.description || null
            };
        }

        return { direction: 'neutral', colorClass: 'inactive', symbol: '—', triggered: false, description: null };
    },

    /**
     * 绑定事件
     */
    bindEvents() {
        // 视图切换
        document.getElementById('viewSwitcher')?.addEventListener('click', (e) => {
            const btn = e.target.closest('.view-btn');
            if (!btn || btn.classList.contains('active')) return;
            this.switchView(btn.dataset.view);
        });

        // 信号类型过滤
        document.getElementById('signalFilter')?.addEventListener('click', (e) => {
            const btn = e.target.closest('.filter-btn');
            if (!btn) return;

            document.querySelectorAll('#signalFilter .filter-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');

            this.filter.signalType = btn.dataset.type;
            this.render();
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

        // 指标标签点击事件（事件委托）
        document.getElementById('stockListContent')?.addEventListener('click', (e) => {
            const indicatorTag = e.target.closest('.indicator-tag[data-indicator]');
            if (!indicatorTag) return;

            e.stopPropagation();
            const mergedKey = indicatorTag.dataset.indicator;
            const direction = indicatorTag.dataset.direction;

            // 获取当前状态
            const row = indicatorTag.closest('tr');
            const stockCode = row?.querySelector('.stock-code-cell')?.textContent;
            let currentState = null;
            if (stockCode && mergedKey) {
                currentState = this.getStockMergedState(stockCode, mergedKey);
            }

            this.showIndicatorPopover(e, mergedKey, currentState);
        });

        // Popover 关闭按钮
        document.getElementById('popoverClose')?.addEventListener('click', () => {
            this.hideIndicatorPopover();
        });

        // 点击外部关闭 Popover
        document.addEventListener('click', (e) => {
            const popover = document.getElementById('indicatorPopover');
            if (!popover || popover.style.display === 'none') return;

            // 如果点击的是 Popover 内部，不关闭
            if (popover.contains(e.target)) return;

            // 如果点击的是指标标签，由上面的事件处理，不在这里关闭
            if (e.target.closest('.indicator-tag[data-indicator]')) return;

            this.hideIndicatorPopover();
        });
    },

    /**
     * 加载数据（两阶段：快速首屏 + 异步补充）
     */
    async loadData() {
        this.showLoading(true);

        try {
            // 阶段1：快速路径 - 60天OHLC + 已缓存信号 + 投资建议
            const enabledIds = Array.from(this.config.enabledCategories).join(',');
            const url = enabledIds ? `/alert/api/data?categories=${enabledIds}` : '/alert/api/data';
            const response = await fetch(url);
            const data = await response.json();

            this.data.stocks = data.stocks || [];
            this.data.ohlcData = data.ohlc_data || {};
            this.data.categories = data.categories || [];
            this.data.earningsData = {};

            this.renderCategoryToggles();
            this.computeAllSignals();
            this.evaluateAlerts();
            this.render();

            // 阶段2：异步并行加载（不阻塞首屏）
            const stockCodes = this.data.stocks.map(s => s.code);
            if (stockCodes.length > 0) {
                this.loadSignalRefresh(stockCodes);
                this.loadEarningsData(stockCodes);
            }
            this.loadSignalWinRates();
        } catch (e) {
            console.error('[AlertPage] 加载数据失败:', e);
            this.showEmpty();
        } finally {
            this.showLoading(false);
        }
    },

    /**
     * 异步刷新信号缓存（后台静默，不更新UI）
     */
    async loadSignalRefresh(stockCodes) {
        try {
            await fetch('/alert/api/signals/refresh', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ stock_codes: stockCodes })
            });
        } catch (e) {
            console.warn('[AlertPage] 信号刷新失败:', e);
        }
    },

    /**
     * 异步加载财报/PE数据，到达后增量更新卡片
     */
    async loadEarningsData(stockCodes) {
        try {
            const response = await fetch(`/alert/api/earnings?codes=${stockCodes.join(',')}`);
            const earningsData = await response.json();
            if (earningsData.error) return;

            this.data.earningsData = earningsData;
            this.updateEarningsDisplay();
        } catch (e) {
            console.warn('[AlertPage] 财报数据加载失败:', e);
        }
    },

    /**
     * 增量更新卡片中的财报区域（避免全量re-render）
     */
    updateEarningsDisplay() {
        document.querySelectorAll('.alert-card[data-stock-code]').forEach(card => {
            const stockCode = card.dataset.stockCode;
            const html = this.renderEarningsInfo(stockCode);
            const existing = card.querySelector('.earnings-info');
            if (existing) {
                existing.outerHTML = html;
            } else if (html) {
                card.insertAdjacentHTML('beforeend', html);
            }
        });
    },

    /**
     * 渲染分类 Toggle 开关
     */
    renderCategoryToggles() {
        const container = document.getElementById('categoryToggleFilter');
        if (!container || !this.data.categories) return;

        container.innerHTML = this.data.categories.map(cat => {
            const isOn = this.config.enabledCategories.has(cat.id);
            return `
                <div class="category-toggle ${isOn ? 'is-on' : ''}" data-id="${cat.id}">
                    <span class="toggle-label">${cat.name}</span>
                    <label class="toggle-switch">
                        <input type="checkbox" ${isOn ? 'checked' : ''}>
                        <span class="toggle-slider"></span>
                    </label>
                </div>
            `;
        }).join('');

        this.bindToggleEvents();
    },

    /**
     * 绑定 Toggle 事件
     */
    bindToggleEvents() {
        const container = document.getElementById('categoryToggleFilter');
        if (!container) return;

        container.querySelectorAll('.category-toggle input[type="checkbox"]').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const toggle = e.target.closest('.category-toggle');
                const catId = Number(toggle.dataset.id);

                if (e.target.checked) {
                    this.config.enabledCategories.add(catId);
                    toggle.classList.add('is-on');
                } else {
                    this.config.enabledCategories.delete(catId);
                    toggle.classList.remove('is-on');
                }

                this.saveConfig();
                this.evaluateAlerts();
                this.render();
            });
        });
    },

    /**
     * 计算所有股票的信号并缓存（仅在OHLC数据变化或阈值变化时调用）
     */
    computeAllSignals() {
        this.data.signalCache.clear();

        this.data.stocks.forEach(stock => {
            const ohlcData = this.data.ohlcData[stock.code];
            if (!ohlcData || ohlcData.length < 20) return;

            try {
                const result = SignalDetector.detectAll(ohlcData, this.config.thresholds);
                if (result.alerts && result.alerts.length > 0) {
                    const fullAlerts = result.alerts.map(alert => {
                        const typeInfo = ALERT_TYPES[alert.alertType] || { level: 'low' };
                        return {
                            ...alert,
                            stockCode: stock.code,
                            stockName: stock.name,
                            categoryId: stock.categoryId,
                            categoryName: stock.categoryName,
                            level: typeInfo.level,
                            category: typeInfo.category,
                            timestamp: Date.now()
                        };
                    });
                    this.data.signalCache.set(stock.code, fullAlerts);
                }
            } catch (e) {
                console.warn(`[AlertPage] 计算股票 ${stock.code} 信号失败:`, e);
            }
        });

        console.log(`[AlertPage] 信号计算完成: ${this.data.signalCache.size} 只股票有信号`);
    },

    /**
     * 从缓存过滤预警（Toggle切换/信号过滤时调用，无需重新计算）
     */
    evaluateAlerts() {
        const alerts = {};
        const summary = { high: 0, medium: 0, low: 0 };

        if (this.config.enabledCategories.size === 0) {
            this.data.alerts = alerts;
            this.data.summary = summary;
            return;
        }

        this.data.stocks.forEach(stock => {
            const categoryId = Number(stock.categoryId || 0);
            if (!this.config.enabledCategories.has(categoryId)) return;

            const cached = this.data.signalCache.get(stock.code);
            if (!cached) return;

            const stockAlerts = cached.filter(alert => !this.config.disabledTypes.has(alert.alertType));
            stockAlerts.forEach(a => summary[a.level]++);

            if (stockAlerts.length > 0) {
                alerts[stock.code] = stockAlerts;
            }
        });

        this.data.alerts = alerts;
        this.data.summary = summary;
    },

    /**
     * 加载信号胜率数据
     */
    async loadSignalWinRates() {
        try {
            const response = await fetch('/alert/api/backtest/win-rates');
            const data = await response.json();
            this.data.signalWinRates = data || {};
            // 重新渲染以显示胜率
            this.render();
        } catch (e) {
            console.warn('[AlertPage] 加载信号胜率失败:', e);
            this.data.signalWinRates = {};
        }
    },

    /**
     * 获取所有预警（扁平化）
     */
    getAllAlerts() {
        const all = [];
        Object.values(this.data.alerts).forEach(stockAlerts => {
            all.push(...stockAlerts);
        });
        return all;
    },

    /**
     * 按条件过滤预警
     */
    getFilteredAlerts() {
        let alerts = this.getAllAlerts();

        // 信号类型过滤
        if (this.filter.signalType !== 'all') {
            alerts = alerts.filter(a => a.type === this.filter.signalType);
        }

        return alerts;
    },

    // 虚拟滚动状态
    virtual: {
        items: [],
        rowHeight: 44,
        headerHeight: 36,
        bufferSize: 5,
        collapsedCategories: new Set(),
        scrollHandler: null
    },

    /**
     * 构建虚拟滚动数据列表
     */
    buildVirtualItems() {
        const items = [];
        const mergedColumns = this.getMergedIndicatorColumns();
        this.virtual.cachedMergedColumns = mergedColumns;

        for (const cat of this.data.categories) {
            if (!this.config.enabledCategories.has(cat.id)) continue;

            // 收集该分类下有信号的股票
            const stocks = [];
            for (const stock of this.data.stocks) {
                const catId = Number(stock.categoryId || 0);
                if (catId !== cat.id) continue;

                const stockAlerts = this.data.alerts[stock.code] || [];
                let filteredAlerts = stockAlerts;
                if (this.filter.signalType !== 'all') {
                    filteredAlerts = stockAlerts.filter(a => a.type === this.filter.signalType);
                }
                if (filteredAlerts.length === 0) continue;

                stocks.push({ ...stock, alerts: filteredAlerts });
            }

            if (stocks.length === 0) continue;

            items.push({
                type: 'header',
                category: cat,
                stockCount: stocks.length,
                height: this.virtual.headerHeight
            });

            if (!this.virtual.collapsedCategories.has(cat.id)) {
                for (const stock of stocks) {
                    items.push({
                        type: 'row',
                        stock,
                        mergedColumns,
                        height: this.virtual.rowHeight
                    });
                }
            }
        }

        this.virtual.items = items;
    },

    /**
     * 渲染固定表头
     */
    renderFixedHeader() {
        const headerRow = document.getElementById('virtualHeaderRow');
        if (!headerRow) return;

        const mergedColumns = this.getMergedIndicatorColumns();
        let cells = '<th class="stock-info-cell">股票</th>';
        for (const [, columns] of Object.entries(mergedColumns)) {
            for (const col of columns) {
                const tooltip = col.tooltip || (INDICATOR_DESCRIPTIONS[col.key]?.fullName || col.label);
                cells += `<th class="indicator-cell" title="${tooltip}">${col.label}</th>`;
            }
        }
        headerRow.innerHTML = cells;
    },

    /**
     * 渲染股票列表视图（虚拟滚动）
     */
    renderStockListView() {
        const container = document.getElementById('stockListContent');
        const emptyEl = document.getElementById('stockListEmpty');
        const viewport = document.getElementById('virtualScrollViewport');
        const scrollContainer = document.querySelector('.virtual-scroll-container');
        if (!container) return;

        if (this.config.enabledCategories.size === 0) {
            container.innerHTML = '';
            scrollContainer?.classList.add('d-none');
            emptyEl?.classList.remove('d-none');
            return;
        }

        emptyEl?.classList.add('d-none');
        scrollContainer?.classList.remove('d-none');

        this.renderFixedHeader();
        this.buildVirtualItems();

        if (this.virtual.items.length === 0) {
            container.innerHTML = '';
            scrollContainer?.classList.add('d-none');
            emptyEl?.classList.remove('d-none');
            return;
        }

        // 计算总高度
        const totalHeight = this.virtual.items.reduce((sum, item) => sum + item.height, 0);

        // 绑定滚动事件（只绑定一次）
        if (!this.virtual.scrollHandler) {
            this.virtual.scrollHandler = () => {
                this.onVirtualScroll();
                // 同步表头横向滚动
                const header = document.getElementById('virtualScrollHeader');
                if (header) header.scrollLeft = viewport.scrollLeft;
            };
            viewport.addEventListener('scroll', this.virtual.scrollHandler);
        }

        // 设置spacer总高度（初始渲染后由 onVirtualScroll 精确调整）
        document.getElementById('virtualSpacerTop').style.height = '0px';
        document.getElementById('virtualSpacerBottom').style.height = totalHeight + 'px';

        // 触发首次渲染
        this.onVirtualScroll();
    },

    /**
     * 虚拟滚动事件处理
     */
    onVirtualScroll() {
        const viewport = document.getElementById('virtualScrollViewport');
        const container = document.getElementById('stockListContent');
        if (!viewport || !container) return;

        const scrollTop = viewport.scrollTop;
        const viewportHeight = viewport.clientHeight;
        const items = this.virtual.items;
        const buffer = this.virtual.bufferSize;

        if (items.length === 0) {
            container.innerHTML = '';
            return;
        }

        // 二分查找 startIndex
        let startIndex = this.findStartIndex(scrollTop);
        startIndex = Math.max(0, startIndex - buffer);

        // 找 endIndex
        let endIndex = startIndex;
        let accHeight = this.getOffsetForIndex(startIndex);
        while (endIndex < items.length && accHeight < scrollTop + viewportHeight) {
            accHeight += items[endIndex].height;
            endIndex++;
        }
        endIndex = Math.min(items.length, endIndex + buffer);

        // 渲染可见项
        const html = [];
        const mergedColumns = this.virtual.cachedMergedColumns;

        for (let i = startIndex; i < endIndex; i++) {
            const item = items[i];
            if (item.type === 'header') {
                const collapsed = this.virtual.collapsedCategories.has(item.category.id);
                html.push(`
                    <div class="virtual-category-header ${collapsed ? 'collapsed' : ''}" data-category-id="${item.category.id}">
                        <div class="category-title">
                            <i class="bi bi-chevron-down"></i>
                            <span>${item.category.name}</span>
                        </div>
                        <span class="category-count">${item.stockCount} 只</span>
                    </div>
                `);
            } else {
                html.push(`<table class="stock-table"><tbody>${this.renderStockRow(item.stock, mergedColumns)}</tbody></table>`);
            }
        }

        container.innerHTML = html.join('');

        // 设置 spacer
        const topOffset = this.getOffsetForIndex(startIndex);
        const bottomOffset = this.getTotalHeight() - this.getOffsetForIndex(endIndex);

        document.getElementById('virtualSpacerTop').style.height = topOffset + 'px';
        document.getElementById('virtualSpacerBottom').style.height = Math.max(0, bottomOffset) + 'px';

        // 绑定分类折叠事件
        container.querySelectorAll('.virtual-category-header').forEach(header => {
            header.addEventListener('click', () => {
                const catId = Number(header.dataset.categoryId);
                if (this.virtual.collapsedCategories.has(catId)) {
                    this.virtual.collapsedCategories.delete(catId);
                } else {
                    this.virtual.collapsedCategories.add(catId);
                }
                this.buildVirtualItems();
                this.onVirtualScroll();
            });
        });
    },

    /**
     * 二分查找：scrollTop 对应的起始 item index
     */
    findStartIndex(scrollTop) {
        const items = this.virtual.items;
        let low = 0, high = items.length - 1;

        while (low <= high) {
            const mid = (low + high) >>> 1;
            const midOffset = this.getOffsetForIndex(mid);

            if (midOffset <= scrollTop) {
                low = mid + 1;
            } else {
                high = mid - 1;
            }
        }

        return Math.max(0, high);
    },

    /**
     * 获取指定 index 的累积偏移量
     */
    getOffsetForIndex(index) {
        let offset = 0;
        for (let i = 0; i < index && i < this.virtual.items.length; i++) {
            offset += this.virtual.items[i].height;
        }
        return offset;
    },

    /**
     * 获取所有项的总高度
     */
    getTotalHeight() {
        return this.virtual.items.reduce((sum, item) => sum + item.height, 0);
    },

    /**
     * 渲染股票行
     */
    renderStockRow(stock, mergedColumns) {
        const states = this.getStockIndicatorStates(stock.code);

        let cells = `
            <td class="stock-info-cell">
                <div class="stock-name-cell" title="${stock.name}">${stock.name}</div>
                <div class="stock-code-cell">${stock.code}</div>
            </td>
        `;

        for (const [, columns] of Object.entries(mergedColumns)) {
            for (const col of columns) {
                if (col.merged === false) {
                    // 非合并指标，使用原有渲染方式
                    const state = states[col.key];
                    cells += `<td class="indicator-cell">${this.renderIndicatorTag(col, state)}</td>`;
                } else {
                    // 合并指标，使用新的渲染方式
                    const mergedState = this.getStockMergedState(stock.code, col.key);
                    cells += `<td class="indicator-cell">${this.renderMergedIndicatorTag(col.key, mergedState)}</td>`;
                }
            }
        }

        return `<tr>${cells}</tr>`;
    },

    /**
     * 渲染指标标签
     */
    renderIndicatorTag(col, state) {
        if (state.error) {
            return `<span class="indicator-tag error" title="数据不足">-</span>`;
        }

        if (state.triggered) {
            const tooltip = state.value || col.tooltip;
            return `<span class="indicator-tag ${state.type}" title="${tooltip}">${col.label}</span>`;
        }

        return `<span class="indicator-tag inactive" title="${col.tooltip}">${col.label}</span>`;
    },

    /**
     * 渲染合并指标标签（带箭头）
     */
    renderMergedIndicatorTag(mergedKey, state) {
        const desc = INDICATOR_DESCRIPTIONS[mergedKey];
        const tooltip = state.description || (desc ? desc.fullName : mergedKey);

        if (state.error) {
            return `<span class="indicator-tag clickable error" data-indicator="${mergedKey}" title="数据不足">-</span>`;
        }

        return `<span class="indicator-tag clickable ${state.colorClass}" data-indicator="${mergedKey}" data-direction="${state.direction}" title="${tooltip}">${state.symbol}</span>`;
    },

    /**
     * 显示指标介绍 Popover
     */
    showIndicatorPopover(event, mergedKey, currentState) {
        const popover = document.getElementById('indicatorPopover');
        if (!popover) return;

        const desc = INDICATOR_DESCRIPTIONS[mergedKey];

        // 填充内容
        document.getElementById('popoverTitle').textContent = desc?.name || mergedKey;
        document.getElementById('popoverSubtitle').textContent = desc?.fullName || '';
        document.getElementById('popoverCalculation').textContent = desc?.calculation || '暂无介绍信息';

        // 填充信号说明
        const signalsContainer = document.getElementById('popoverSignals');
        if (desc?.signals) {
            signalsContainer.innerHTML = `
                <div class="indicator-popover-signal">
                    <span class="indicator-popover-signal-icon up">↑</span>
                    <div class="indicator-popover-signal-text">
                        <div class="indicator-popover-signal-meaning">${desc.signals.up.meaning}</div>
                        <div class="indicator-popover-signal-implication">${desc.signals.up.implication}</div>
                    </div>
                </div>
                <div class="indicator-popover-signal">
                    <span class="indicator-popover-signal-icon down">↓</span>
                    <div class="indicator-popover-signal-text">
                        <div class="indicator-popover-signal-meaning">${desc.signals.down.meaning}</div>
                        <div class="indicator-popover-signal-implication">${desc.signals.down.implication}</div>
                    </div>
                </div>
            `;
        } else {
            signalsContainer.textContent = '暂无信号说明';
        }

        // 填充当前状态
        const footer = document.getElementById('popoverFooter');
        const currentStateEl = document.getElementById('popoverCurrentState');
        if (currentState && currentState.triggered) {
            footer.style.display = 'block';
            currentStateEl.textContent = currentState.description || '已触发信号';
            currentStateEl.className = 'indicator-popover-current-value triggered';
        } else {
            footer.style.display = 'block';
            currentStateEl.textContent = '未触发';
            currentStateEl.className = 'indicator-popover-current-value not-triggered';
        }

        // 计算位置
        const target = event.target;
        const rect = target.getBoundingClientRect();
        const popoverRect = { width: 300, height: 280 };

        let top = rect.bottom + 8;
        let left = rect.left + rect.width / 2 - popoverRect.width / 2;

        // 检查是否超出视口底部
        const viewportHeight = window.innerHeight;
        const viewportWidth = window.innerWidth;
        let arrowBottom = false;

        if (top + popoverRect.height > viewportHeight - 10) {
            top = rect.top - popoverRect.height - 8;
            arrowBottom = true;
        }

        // 检查水平边界
        if (left < 10) left = 10;
        if (left + popoverRect.width > viewportWidth - 10) {
            left = viewportWidth - popoverRect.width - 10;
        }

        // 设置位置和箭头方向
        popover.style.top = `${top}px`;
        popover.style.left = `${left}px`;
        popover.classList.toggle('arrow-bottom', arrowBottom);

        // 调整箭头水平位置
        const arrow = popover.querySelector('.indicator-popover-arrow');
        const arrowLeft = rect.left + rect.width / 2 - left;
        arrow.style.left = `${Math.max(16, Math.min(arrowLeft, popoverRect.width - 16))}px`;
        arrow.style.marginLeft = '0';

        // 显示 Popover
        popover.style.display = 'block';
    },

    /**
     * 隐藏指标介绍 Popover
     */
    hideIndicatorPopover() {
        const popover = document.getElementById('indicatorPopover');
        if (popover) {
            popover.style.display = 'none';
        }
    },

    /**
     * 统一渲染入口
     */
    render() {
        const viewMode = this.getCurrentView();

        // 控制视图显示/隐藏
        const alertCardView = document.getElementById('alertCardView');
        const stockListView = document.getElementById('stockListView');
        const emptyState = document.getElementById('emptyState');

        if (viewMode === 'list') {
            alertCardView?.classList.add('d-none');
            emptyState?.classList.add('d-none');
            stockListView?.classList.remove('d-none');
            this.renderStockListView();
        } else {
            stockListView?.classList.add('d-none');
            this.renderCardView();
        }
    },

    /**
     * 渲染卡片视图（按板块分组）
     */
    renderCardView() {
        const container = document.getElementById('alertCardContent');
        const cardView = document.getElementById('alertCardView');
        const emptyState = document.getElementById('emptyState');
        if (!container) return;

        // 检查是否有启用的分类
        if (this.config.enabledCategories.size === 0) {
            container.innerHTML = '';
            cardView?.classList.add('d-none');
            emptyState?.classList.remove('d-none');
            return;
        }

        // 按板块分组股票和预警
        const categoryData = {};
        for (const cat of this.data.categories) {
            if (!this.config.enabledCategories.has(cat.id)) continue;
            categoryData[cat.id] = {
                id: cat.id,
                name: cat.name,
                stocks: []
            };
        }

        // 分配股票到各板块
        for (const stock of this.data.stocks) {
            const catId = Number(stock.categoryId || 0);
            if (!categoryData[catId]) continue;

            const stockAlerts = this.data.alerts[stock.code] || [];
            // 应用信号类型过滤
            let filteredAlerts = stockAlerts;
            if (this.filter.signalType !== 'all') {
                filteredAlerts = stockAlerts.filter(a => a.type === this.filter.signalType);
            }

            // 只显示有信号的股票卡片
            if (filteredAlerts.length === 0) continue;

            categoryData[catId].stocks.push({
                ...stock,
                alerts: filteredAlerts
            });
        }

        // 渲染各板块
        const html = [];
        for (const cat of this.data.categories) {
            if (!categoryData[cat.id]) continue;
            const data = categoryData[cat.id];
            html.push(this.renderCategoryCardSection(data));
        }

        if (html.length === 0) {
            container.innerHTML = '';
            cardView?.classList.add('d-none');
            emptyState?.classList.remove('d-none');
            return;
        }

        emptyState?.classList.add('d-none');
        cardView?.classList.remove('d-none');
        container.innerHTML = html.join('');

        // 绑定板块折叠事件
        container.querySelectorAll('.category-card-header').forEach(header => {
            header.addEventListener('click', () => {
                header.closest('.category-card-section').classList.toggle('collapsed');
            });
        });
    },

    /**
     * 获取股票的主要信号类型（根据预警数量判断）
     */
    getStockSignalType(alerts) {
        if (!alerts || alerts.length === 0) return null;

        let buyCount = 0, sellCount = 0;
        alerts.forEach(a => {
            if (a.type === 'buy') buyCount++;
            else if (a.type === 'sell') sellCount++;
        });

        if (buyCount > 0 && sellCount === 0) return 'buy';
        if (sellCount > 0 && buyCount === 0) return 'sell';
        if (buyCount > 0 && sellCount > 0) return 'mixed';
        return 'neutral';
    },

    /**
     * 获取优先级排序权重（用于排序）
     */
    getLevelWeight(level) {
        const weights = { high: 3, medium: 2, low: 1 };
        return weights[level] || 0;
    },

    /**
     * 按优先级排序股票
     */
    sortStocksByPriority(stocks) {
        return stocks.slice().sort((a, b) => {
            const levelA = this.getHighestAlertLevel(a.alerts);
            const levelB = this.getHighestAlertLevel(b.alerts);
            const weightA = this.getLevelWeight(levelA);
            const weightB = this.getLevelWeight(levelB);

            // 优先级高的排前面
            if (weightB !== weightA) return weightB - weightA;

            // 同优先级，预警数量多的排前面
            return (b.alerts?.length || 0) - (a.alerts?.length || 0);
        });
    },

    /**
     * 渲染板块卡片区块
     */
    renderCategoryCardSection(categoryData) {
        const { id, name, stocks } = categoryData;

        // 统计该板块的预警数量
        let alertCount = 0;
        stocks.forEach(s => { alertCount += s.alerts.length; });

        // 按优先级排序股票
        const sortedStocks = this.sortStocksByPriority(stocks);

        // 生成股票卡片
        const cardsHtml = sortedStocks.map(stock => this.renderStockCard(stock)).join('');

        return `
            <div class="category-card-section" data-category-id="${id}">
                <div class="category-card-header">
                    <div class="category-card-title">
                        <i class="bi bi-chevron-down"></i>
                        <span>${name}</span>
                    </div>
                    <div class="category-card-stats">
                        <span class="stock-count">${stocks.length} 只股票</span>
                        ${alertCount > 0 ? `<span class="alert-count">${alertCount} 个预警</span>` : ''}
                    </div>
                </div>
                <div class="category-card-body">
                    <div class="alert-grid">
                        ${cardsHtml || '<div class="category-empty-msg">该板块暂无股票</div>'}
                    </div>
                </div>
            </div>
        `;
    },

    /**
     * 获取信号类型标签
     */
    getSignalTypeLabel(signalType) {
        const labels = { buy: '买入', sell: '卖出', mixed: '混合', neutral: '中性' };
        return labels[signalType] || '';
    },

    /**
     * 渲染单个股票卡片
     */
    renderStockCard(stock) {
        const alerts = stock.alerts || [];
        const highestLevel = this.getHighestAlertLevel(alerts);
        const signalType = this.getStockSignalType(alerts);

        // 预警标签（含信号胜率）
        const winRates = this.data.signalWinRates || {};
        const alertTags = alerts.slice(0, 3).map(alert => {
            const wr = winRates[alert.name];
            const wrBadge = wr && wr.total >= 3
                ? `<span class="win-rate-badge" title="历史胜率(${wr.wins}/${wr.total})">${Math.round(wr.win_rate * 100)}%</span>`
                : '';
            return `<span class="alert-tag ${alert.type}" title="${alert.description}">${alert.name}${wrBadge}</span>`;
        }).join('');

        const moreCount = alerts.length > 3 ? `<span class="alert-tag more">+${alerts.length - 3}</span>` : '';

        // 信号类型和优先级标签
        let badgesHtml = '';
        if (alerts.length > 0 && signalType) {
            const signalClass = signalType === 'mixed' ? 'mixed' : signalType;
            const levelLabel = this.getLevelLabel(highestLevel);
            badgesHtml = `
                <div class="card-badges">
                    <span class="signal-type-badge ${signalClass}">${this.getSignalTypeLabel(signalType)}</span>
                    ${highestLevel ? `<span class="priority-badge ${highestLevel}">${levelLabel}</span>` : ''}
                </div>
            `;
        }

        // 投资建议按钮
        const adviceBtn = stock.investment_advice
            ? `<i class="bi bi-journal-text advice-icon-btn" data-advice="${this.escapeHtml(stock.investment_advice)}" title="查看投资建议" onclick="event.stopPropagation(); AlertPage.showAdvicePopover(this, '${this.escapeHtml(stock.investment_advice).replace(/'/g, "\\'")}')"></i>`
            : '';

        return `
            <div class="alert-card ${highestLevel ? 'has-alert level-' + highestLevel : ''}"
                 data-stock-code="${stock.code}"
                 onclick="AlertPage.showDetail('${stock.code}')">
                <div class="alert-card-header">
                    <div class="stock-info">
                        <div class="stock-name">${stock.name} ${adviceBtn}</div>
                        <div class="stock-code">${stock.code}</div>
                    </div>
                    ${badgesHtml}
                </div>
                ${alerts.length > 0 ? `
                <div class="alert-card-body">
                    <div class="alert-tags">${alertTags}${moreCount}</div>
                </div>
                ` : ''}
                ${this.renderEarningsInfo(stock.code)}
            </div>
        `;
    },

    /**
     * HTML 转义
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    },

    /**
     * 显示投资建议 Popover
     */
    showAdvicePopover(target, advice) {
        // 移除已有的 popover
        const existing = document.getElementById('advicePopover');
        if (existing) existing.remove();

        const rect = target.getBoundingClientRect();
        const popover = document.createElement('div');
        popover.id = 'advicePopover';
        popover.className = 'advice-popover';
        popover.innerHTML = `
            <div class="advice-popover-header">
                <span>投资建议</span>
                <button class="advice-popover-close">&times;</button>
            </div>
            <div class="advice-popover-body">${advice}</div>
        `;

        document.body.appendChild(popover);

        // 计算位置
        const popoverRect = popover.getBoundingClientRect();
        let top = rect.bottom + 8;
        let left = rect.left - popoverRect.width / 2 + rect.width / 2;

        // 边界检查
        if (left < 10) left = 10;
        if (left + popoverRect.width > window.innerWidth - 10) {
            left = window.innerWidth - popoverRect.width - 10;
        }
        if (top + popoverRect.height > window.innerHeight - 10) {
            top = rect.top - popoverRect.height - 8;
        }

        popover.style.top = top + 'px';
        popover.style.left = left + 'px';

        // 关闭按钮事件
        popover.querySelector('.advice-popover-close').addEventListener('click', (e) => {
            e.stopPropagation();
            popover.remove();
        });

        // 点击其他地方关闭
        setTimeout(() => {
            document.addEventListener('click', function closePopover(e) {
                if (!popover.contains(e.target)) {
                    popover.remove();
                    document.removeEventListener('click', closePopover);
                }
            });
        }, 10);
    },

    /**
     * 获取最高预警级别
     */
    getHighestAlertLevel(alerts) {
        if (!alerts || alerts.length === 0) return null;
        const levels = ['high', 'medium', 'low'];
        for (const level of levels) {
            if (alerts.some(a => a.level === level)) return level;
        }
        return null;
    },

    /**
     * 获取级别标签
     */
    getLevelLabel(level) {
        const labels = { high: '高', medium: '中', low: '低' };
        return labels[level] || '';
    },

    /**
     * 渲染财报信息
     */
    renderEarningsInfo(stockCode) {
        const earningsData = this.data.earningsData[stockCode];
        if (!earningsData) {
            return '';
        }

        const market = earningsData.market || 'unknown';
        const nextDate = earningsData.next_earnings_date;
        const daysUntil = earningsData.days_until_next;

        // A股不显示财报日期和PE
        if (market === 'A') return '';

        // 财报日期（负数已过期不显示）
        let earningsDateHtml = '';
        if (nextDate && (daysUntil === null || daysUntil >= 0)) {
            let dateClass = 'bg-secondary';
            let dateText = nextDate;
            if (earningsData.is_today) {
                dateClass = 'bg-danger text-white';
                dateText = '今日发布';
            } else if (daysUntil !== null && daysUntil <= 7) {
                dateClass = 'bg-warning text-dark';
                dateText = `${nextDate} (${daysUntil}天后)`;
            }
            earningsDateHtml = `
                <div class="d-flex justify-content-between align-items-center small">
                    <span class="text-muted">下次财报</span>
                    <span class="badge ${dateClass}">${dateText}</span>
                </div>
            `;
        }

        const peDisplay = earningsData.pe_display || '暂无数据';
        const peStatus = earningsData.pe_status || 'na';
        const peClassMap = {
            'low': 'bg-success',
            'normal': 'bg-secondary',
            'high': 'bg-warning',
            'very_high': 'bg-danger',
            'loss': 'bg-dark text-white',
            'na': 'bg-light text-muted'
        };
        const peClass = peClassMap[peStatus] || 'bg-secondary';

        return `
            <div class="earnings-info mt-2 pt-2 border-top">
                ${earningsDateHtml}
                <div class="d-flex justify-content-between align-items-center small${earningsDateHtml ? ' mt-1' : ''}">
                    <span class="text-muted">市盈率(TTM)</span>
                    <span class="badge ${peClass}">${peDisplay}</span>
                </div>
            </div>
        `;
    },

    /**
     * 获取信号标签
     */
    getSignalLabel(type) {
        switch (type) {
            case 'buy': return '买入';
            case 'sell': return '卖出';
            default: return '中性';
        }
    },

    /**
     * 显示详情弹窗
     */
    showDetail(stockCode) {
        const stockAlerts = this.data.alerts[stockCode] || [];
        if (stockAlerts.length === 0) return;

        const modal = document.getElementById('alertDetailModal');
        const stock = this.data.stocks.find(s => s.code === stockCode);

        document.getElementById('detailStockName').textContent = stock?.name || stockCode;
        document.getElementById('detailStockCode').textContent = stockCode;

        const container = document.getElementById('detailAlerts');
        container.innerHTML = stockAlerts.map(alert => `
            <div class="detail-alert-item ${alert.level}">
                <div class="detail-alert-name">${alert.name}</div>
                <div class="detail-alert-desc">${alert.description}</div>
            </div>
        `).join('');

        new bootstrap.Modal(modal).show();
    },

    /**
     * 显示设置弹窗
     */
    showSettings() {
        const modal = document.getElementById('alertSettingsModal');

        // 填充阈值
        const thresholds = this.config.thresholds;
        document.getElementById('rsiOverboughtRange').value = thresholds.rsiOverbought;
        document.getElementById('rsiOverboughtValue').textContent = thresholds.rsiOverbought;
        document.getElementById('rsiOversoldRange').value = thresholds.rsiOversold;
        document.getElementById('rsiOversoldValue').textContent = thresholds.rsiOversold;
        document.getElementById('volumeRatioRange').value = thresholds.volumeRatio;
        document.getElementById('volumeRatioValue').textContent = thresholds.volumeRatio.toFixed(1);

        // 填充预警类型复选框
        const typeContainer = document.getElementById('alertTypeCheckboxes');
        typeContainer.innerHTML = Object.entries(ALERT_TYPES).map(([type, info]) => `
            <div class="form-check">
                <input class="form-check-input" type="checkbox" id="type_${type}" value="${type}"
                    ${!this.config.disabledTypes.has(type) ? 'checked' : ''}>
                <label class="form-check-label" for="type_${type}">${info.label}</label>
            </div>
        `).join('');

        new bootstrap.Modal(modal).show();
    },

    /**
     * 保存设置
     */
    saveSettings() {
        // 保存阈值
        this.config.thresholds = {
            ...this.config.thresholds,
            rsiOverbought: parseInt(document.getElementById('rsiOverboughtRange').value),
            rsiOversold: parseInt(document.getElementById('rsiOversoldRange').value),
            volumeRatio: parseFloat(document.getElementById('volumeRatioRange').value)
        };

        // 保存禁用的预警类型
        this.config.disabledTypes = new Set();
        Object.keys(ALERT_TYPES).forEach(type => {
            const checkbox = document.getElementById(`type_${type}`);
            if (checkbox && !checkbox.checked) {
                this.config.disabledTypes.add(type);
            }
        });

        this.saveConfig();

        // 关闭弹窗
        const modal = bootstrap.Modal.getInstance(document.getElementById('alertSettingsModal'));
        if (modal) modal.hide();

        // 阈值变化需重新计算信号
        this.computeAllSignals();
        this.evaluateAlerts();
        this.render();
    },

    /**
     * 刷新数据
     */
    refresh() {
        this.loadData();
    },

    /**
     * 显示加载状态
     */
    showLoading(show) {
        document.getElementById('loadingState').classList.toggle('d-none', !show);
        if (show) {
            document.getElementById('alertCardView')?.classList.add('d-none');
            document.getElementById('stockListView')?.classList.add('d-none');
            document.getElementById('emptyState')?.classList.add('d-none');
        }
    },

    /**
     * 显示空状态
     */
    showEmpty() {
        document.getElementById('alertCardView')?.classList.add('d-none');
        document.getElementById('stockListView')?.classList.add('d-none');
        document.getElementById('emptyState')?.classList.remove('d-none');
    }
};

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    AlertPage.init();
});
