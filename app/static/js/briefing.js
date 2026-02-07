/**
 * 每日简报页面
 */
class BriefingPage {
    static data = null;

    /**
     * 初始化页面
     */
    static init() {
        this.loadData();
        this.bindAdviceEvents();
    }

    /**
     * 绑定投资建议按钮事件
     */
    static bindAdviceEvents() {
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('advice-icon-btn')) {
                e.stopPropagation();
                const advice = e.target.dataset.advice;
                if (advice) {
                    this.showAdvicePopover(e.target, advice);
                }
            }
        });

        // 点击其他地方关闭 popover
        document.addEventListener('click', (e) => {
            const popover = document.getElementById('advicePopover');
            if (popover && !popover.contains(e.target) && !e.target.classList.contains('advice-icon-btn')) {
                popover.remove();
            }
        });
    }

    /**
     * 显示投资建议 Popover
     */
    static showAdvicePopover(target, advice) {
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
        popover.querySelector('.advice-popover-close').addEventListener('click', () => {
            popover.remove();
        });
    }

    /**
     * 加载数据
     */
    static async loadData() {
        this.showLoading(true);
        this.showError(false);

        try {
            const response = await fetch('/briefing/api/data');
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const data = await response.json();

            if (data.error) {
                throw new Error(data.error);
            }

            this.data = data;
            this.render();
            this.showLoading(false);
            document.getElementById('dataContent').classList.remove('d-none');
        } catch (error) {
            console.error('加载数据失败:', error);
            this.showLoading(false);
            this.showError(true, error.message);
        }
    }

    /**
     * 刷新数据
     */
    static async refresh() {
        const btn = document.getElementById('refreshBtn');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> 刷新中...';

        try {
            const response = await fetch('/briefing/api/refresh', { method: 'POST' });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}`);
            }
            const data = await response.json();

            if (data.error) {
                throw new Error(data.error);
            }

            this.data = data;
            this.render();
        } catch (error) {
            console.error('刷新失败:', error);
            alert('刷新失败: ' + error.message);
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> 刷新';
        }
    }

    /**
     * 渲染所有数据
     */
    static render() {
        if (!this.data) return;

        this.renderEarningsAlerts(this.data.earnings_alerts, this.data.has_earnings_alerts);
        this.renderStocks(this.data.stocks);
        this.renderIndices(this.data.indices);
        this.renderFutures(this.data.futures);
        this.renderETFPremium(this.data.etf_premium);
        this.renderSectorRatings(this.data.sector_ratings);
        this.renderSectors(this.data.cn_sectors, this.data.us_sectors);

        if (this.data.last_update) {
            document.getElementById('lastUpdate').textContent = `更新时间: ${this.data.last_update}`;
        }
    }

    /**
     * 渲染财报预警
     */
    static renderEarningsAlerts(alerts, hasAlerts) {
        const section = document.getElementById('earningsAlertSection');
        const container = document.getElementById('earningsAlertContainer');

        // 过滤掉负数（已过期）的财报
        const validAlerts = (alerts || []).filter(a => a.days_until !== null && a.days_until >= 0);

        if (!hasAlerts || validAlerts.length === 0) {
            section.classList.add('d-none');
            return;
        }

        section.classList.remove('d-none');
        container.innerHTML = validAlerts.map(alert => {
            const urgencyBg = this.getEarningsUrgencyBg(alert.days_until);
            const urgencyText = this.getEarningsUrgencyText(alert.days_until);

            return `
                <div class="earnings-alert-item">
                    <div>
                        <span style="font-weight:600">${alert.stock_name}</span>
                        <span class="bc-code" style="margin-left:6px">${alert.stock_code}</span>
                    </div>
                    <div>
                        <span class="bc-badge" style="background:${urgencyBg};margin-right:6px">${urgencyText}</span>
                        <span style="color:#888">${alert.earnings_date}</span>
                    </div>
                </div>
            `;
        }).join('');
    }

    /**
     * 获取财报紧急程度背景色
     */
    static getEarningsUrgencyBg(daysUntil) {
        if (daysUntil === null || daysUntil === undefined || daysUntil < 0) return '#6c757d';
        if (daysUntil <= 3) return '#dc3545';
        if (daysUntil <= 7) return '#ffc107';
        return '#17a2b8';
    }

    /**
     * 获取财报紧急程度文本
     */
    static getEarningsUrgencyText(daysUntil) {
        if (daysUntil === null || daysUntil === undefined || daysUntil < 0) return '';
        if (daysUntil === 0) return '今日发布';
        if (daysUntil === 1) return '明日发布';
        return `${daysUntil}天后`;
    }

    /**
     * 渲染股票卡片（按分类分组）
     */
    static renderStocks(stocksData) {
        const container = document.getElementById('stocksContainer');
        if (!stocksData || !stocksData.categories || stocksData.categories.length === 0) {
            container.innerHTML = '<div class="text-muted">暂无数据</div>';
            return;
        }

        let html = '';
        for (const category of stocksData.categories) {
            const stocks = stocksData.stocks[category.key] || [];
            if (stocks.length === 0) continue;

            html += `<div class="category-title">${category.name}</div>`;
            html += stocks.map(stock => this.renderStockCard(stock)).join('');
        }

        container.innerHTML = html || '<div class="text-muted">暂无数据</div>';
    }

    /**
     * 渲染单个股票卡片
     */
    static renderStockCard(stock) {
        const changeClass = this.getChangeClassNew(stock.change_percent);
        const changeText = stock.change_percent !== null
            ? `${stock.change_percent > 0 ? '+' : ''}${stock.change_percent.toFixed(2)}%`
            : '--';
        const priceText = stock.close !== null ? stock.close.toFixed(2) : '--';

        // 次要信息
        const secondaryInfo = this.renderStockSecondary(stock);

        // 投资建议按钮
        const adviceBtn = stock.investment_advice
            ? `<i class="bi bi-journal-text advice-icon-btn" data-advice="${this.escapeHtml(stock.investment_advice)}" title="查看投资建议"></i>`
            : '';

        return `
            <div class="briefing-card ${stock.error ? 'has-error' : ''}">
                <div class="bc-header">
                    <div>
                        <div class="bc-name">${stock.name}</div>
                        <div class="bc-code">${stock.code}</div>
                    </div>
                    <div class="bc-header-right">
                        ${adviceBtn}
                        <span class="bc-badge">${stock.market}</span>
                    </div>
                </div>
                ${stock.error ? `<div class="text-warning-dark" style="font-size:0.75rem">${stock.error}</div>` : `
                    <div class="bc-price">${priceText}</div>
                    <div class="bc-change ${changeClass}">${changeText}</div>
                    <div class="bc-secondary">${secondaryInfo}</div>
                `}
            </div>
        `;
    }

    /**
     * HTML 转义
     */
    static escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    /**
     * 渲染股票次要信息（PE + 财报）
     */
    static renderStockSecondary(stock) {
        const parts = [];

        // PE 信息
        if (stock.pe_status === 'loss') {
            parts.push('<span class="text-up">亏损</span>');
        } else if (stock.pe_ttm !== null) {
            const peClass = this.getPEStatusClass(stock.pe_status);
            parts.push(`PE:<span class="${peClass}">${stock.pe_ttm.toFixed(1)}</span>`);
        }

        // 财报信息（负数不显示）
        if (stock.earnings_date && (stock.days_until_earnings === null || stock.days_until_earnings >= 0)) {
            const daysUntil = stock.days_until_earnings;
            const dateClass = this.getEarningsDateClass(daysUntil);
            let text;
            if (stock.is_earnings_today) {
                text = '今日';
            } else if (daysUntil !== null && daysUntil <= 7) {
                text = `${daysUntil}天`;
            } else {
                text = stock.earnings_date.slice(5);
            }
            parts.push(`财报:<span class="${dateClass}">${text}</span>`);
        }

        return parts.join(' ');
    }

    /**
     * 获取财报日期样式类
     */
    static getEarningsDateClass(daysUntil) {
        if (daysUntil === null || daysUntil === undefined) return 'text-muted';
        if (daysUntil <= 3) return 'text-danger fw-bold';
        if (daysUntil <= 7) return 'text-warning';
        return 'text-info';
    }

    /**
     * 获取PE状态样式类
     */
    static getPEStatusClass(status) {
        switch (status) {
            case 'low': return 'text-success';
            case 'normal': return '';
            case 'high': return 'text-warning';
            case 'very_high':
            case 'loss': return 'text-danger';
            default: return 'text-muted';
        }
    }

    /**
     * 渲染指数卡片（按地区分组）
     */
    static renderIndices(indicesData) {
        const container = document.getElementById('indicesContainer');
        if (!indicesData || !indicesData.regions || indicesData.regions.length === 0) {
            container.innerHTML = '<div class="text-muted">暂无数据</div>';
            return;
        }

        let html = '';
        for (const region of indicesData.regions) {
            const indices = indicesData.indices[region.key] || [];
            if (indices.length === 0) continue;

            html += `<div class="category-title">${region.name}</div>`;
            html += indices.map(index => this.renderIndexCard(index)).join('');
        }

        container.innerHTML = html || '<div class="text-muted">暂无数据</div>';
    }

    /**
     * 渲染单个指数卡片
     */
    static renderIndexCard(index) {
        const changeClass = this.getChangeClassNew(index.change_percent);
        const changeText = index.change_percent !== null
            ? `${index.change_percent > 0 ? '+' : ''}${index.change_percent.toFixed(2)}%`
            : '--';
        const priceText = index.close !== null ? index.close.toFixed(2) : '--';

        return `
            <div class="briefing-card ${index.error ? 'has-error' : ''}" style="text-align:center">
                <div class="bc-name">${index.name}</div>
                ${index.error ? `<div class="text-warning-dark" style="font-size:0.75rem">${index.error}</div>` : `
                    <div class="bc-price">${priceText}</div>
                    <div class="bc-change ${changeClass}">${changeText}</div>
                `}
            </div>
        `;
    }

    /**
     * 渲染期货卡片
     */
    static renderFutures(futures) {
        const container = document.getElementById('futuresContainer');
        if (!futures || futures.length === 0) {
            container.innerHTML = '<div class="text-muted">暂无数据</div>';
            return;
        }

        container.innerHTML = futures.map(item => {
            const changeClass = this.getChangeClassNew(item.change_percent);
            const changeText = item.change_percent !== null
                ? `${item.change_percent > 0 ? '+' : ''}${item.change_percent.toFixed(2)}%`
                : '--';
            const priceText = item.close !== null ? item.close.toFixed(2) : '--';

            return `
                <div class="briefing-card ${item.error ? 'has-error' : ''}" style="text-align:center">
                    <div class="bc-name">${item.name}</div>
                    ${item.error ? `<div class="text-warning-dark" style="font-size:0.75rem">${item.error}</div>` : `
                        <div class="bc-price">${priceText}</div>
                        <div class="bc-change ${changeClass}">${changeText}</div>
                    `}
                </div>
            `;
        }).join('');
    }

    /**
     * 渲染ETF溢价卡片
     */
    static renderETFPremium(etfs) {
        const container = document.getElementById('etfContainer');
        if (!etfs || etfs.length === 0) {
            container.innerHTML = '<div class="text-muted">暂无数据</div>';
            return;
        }

        container.innerHTML = etfs.map(etf => {
            const signalInfo = this.getSignalInfo(etf.signal);
            const premiumText = etf.premium_rate !== null
                ? `${etf.premium_rate > 0 ? '+' : ''}${etf.premium_rate.toFixed(2)}%`
                : '--';
            const signalBadge = signalInfo ? `<span class="bc-badge" style="background:${signalInfo.bg}">${signalInfo.text}</span>` : '';

            return `
                <div class="briefing-card etf-card ${etf.error ? 'has-error' : ''}">
                    <div class="bc-header">
                        <div>
                            <div class="bc-name">${etf.name}</div>
                            <div class="bc-code">${etf.code}</div>
                        </div>
                        ${signalBadge}
                    </div>
                    ${etf.error ? `<div class="text-warning-dark" style="font-size:0.75rem">${etf.error}</div>` : `
                        <div class="bc-row">
                            <span><span class="bc-row-label">价格</span> ${etf.price !== null ? etf.price.toFixed(3) : '--'}</span>
                            <span><span class="bc-row-label">净值</span> ${etf.nav !== null ? etf.nav.toFixed(3) : '--'}</span>
                            <span><span class="bc-row-label">溢价</span> <span class="${this.getPremiumClass(etf.premium_rate)}">${premiumText}</span></span>
                        </div>
                    `}
                </div>
            `;
        }).join('');
    }

    /**
     * 渲染板块评级
     */
    static renderSectorRatings(ratings) {
        const container = document.getElementById('sectorRatingsContainer');
        if (!ratings || Object.keys(ratings).length === 0) {
            container.innerHTML = '<div class="text-muted">暂无数据</div>';
            return;
        }

        let html = '';
        for (const [sectorId, data] of Object.entries(ratings)) {
            const ratingClass = this.getRatingClass(data.rating);
            const ratingText = this.getRatingText(data.rating);

            // 构建股票涨跌详情
            const stocksDetail = data.stocks
                .filter(s => s.change_pct !== null)
                .map(s => {
                    const changeClass = this.getChangeClassNew(s.change_pct);
                    const sign = s.change_pct > 0 ? '+' : '';
                    return `<span class="${changeClass}">${s.code} ${sign}${s.change_pct.toFixed(2)}%</span>`;
                })
                .join(' | ');

            html += `
                <div class="rating-card">
                    <div class="rating-card-header">
                        <span class="rating-sector-name">${data.name}</span>
                        <span class="rating-badge ${ratingClass}">${ratingText}</span>
                    </div>
                    <div class="rating-stocks">${stocksDetail}</div>
                    <div class="rating-detail">
                        综合评分: ${data.score} | 平均涨幅: ${data.details.avg_change > 0 ? '+' : ''}${data.details.avg_change}% | ${data.details.consistency}
                    </div>
                </div>
            `;
        }

        container.innerHTML = html;
    }

    /**
     * 获取评级样式类
     */
    static getRatingClass(rating) {
        switch (rating) {
            case 'bullish': return 'rating-bullish';
            case 'neutral': return 'rating-neutral';
            case 'bearish': return 'rating-bearish';
            default: return 'rating-neutral';
        }
    }

    /**
     * 获取评级文本
     */
    static getRatingText(rating) {
        switch (rating) {
            case 'bullish': return '看涨';
            case 'neutral': return '中性';
            case 'bearish': return '看跌';
            default: return '中性';
        }
    }

    /**
     * 渲染板块涨幅
     */
    static renderSectors(cnSectors, usSectors) {
        const cnContainer = document.getElementById('cnSectorsContainer');
        const usContainer = document.getElementById('usSectorsContainer');

        // 渲染A股板块
        if (!cnSectors || cnSectors.length === 0) {
            cnContainer.innerHTML = '<div class="text-muted">暂无数据</div>';
        } else {
            cnContainer.innerHTML = cnSectors.map(sector => {
                const changeClass = this.getChangeClassNew(sector.change_percent);
                const changeText = sector.change_percent !== null
                    ? `${sector.change_percent > 0 ? '+' : ''}${sector.change_percent.toFixed(2)}%`
                    : '--';

                return `
                    <div class="sector-item">
                        <div>
                            <span>${sector.name}</span>
                            <span class="sector-leader">${sector.leader || ''}</span>
                        </div>
                        <span class="${changeClass}">${changeText}</span>
                    </div>
                `;
            }).join('');
        }

        // 渲染美股板块
        if (!usSectors || usSectors.length === 0) {
            usContainer.innerHTML = '<div class="text-muted">暂无数据</div>';
        } else {
            usContainer.innerHTML = usSectors.map(sector => {
                const changeClass = this.getChangeClassNew(sector.change_percent);
                const changeText = sector.change_percent !== null
                    ? `${sector.change_percent > 0 ? '+' : ''}${sector.change_percent.toFixed(2)}%`
                    : '--';

                return `
                    <div class="sector-item">
                        <span>${sector.name}</span>
                        <span class="${changeClass}">${changeText}</span>
                    </div>
                `;
            }).join('');
        }
    }

    /**
     * 获取涨跌颜色类
     */
    static getChangeClassNew(changePercent) {
        if (changePercent === null || changePercent === undefined) return 'text-flat';
        if (changePercent > 0) return 'text-up';
        if (changePercent < 0) return 'text-down';
        return 'text-flat';
    }

    /**
     * 获取溢价率颜色类
     */
    static getPremiumClass(premiumRate) {
        if (premiumRate === null || premiumRate === undefined) return '';
        if (premiumRate <= 3) return 'text-down';
        if (premiumRate >= 6) return 'text-up';
        return 'text-warning-dark';
    }

    /**
     * 获取信号信息
     */
    static getSignalInfo(signal) {
        if (!signal) return null;
        switch (signal) {
            case 'buy':
                return { text: '买入', bg: '#28a745' };
            case 'sell':
                return { text: '卖出', bg: '#dc3545' };
            case 'normal':
                return { text: '正常', bg: '#ffc107' };
            default:
                return null;
        }
    }

    /**
     * 显示/隐藏加载状态
     */
    static showLoading(show) {
        document.getElementById('loadingState').classList.toggle('d-none', !show);
    }

    /**
     * 显示/隐藏错误状态
     */
    static showError(show, message = '') {
        const errorState = document.getElementById('errorState');
        const errorMessage = document.getElementById('errorMessage');
        errorState.classList.toggle('d-none', !show);
        if (message) {
            errorMessage.textContent = message;
        }
    }
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => {
    BriefingPage.init();
});
