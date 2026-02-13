/**
 * 每日简报页面 - 渐进式加载
 */
class BriefingPage {
    static peData = null;
    static earningsData = null;
    static technicalData = null;
    static stocksRendered = false;
    static aiEnabled = false;

    static init() {
        this.bindAdviceEvents();
        this.bindAIEvents();
        this.checkAIStatus();

        document.getElementById('dataContent').classList.remove('d-none');
        document.getElementById('loadingState').classList.add('d-none');

        this.setLoadingPlaceholders();

        this.loadStocks();
        this.loadStocksPE();
        this.loadStocksEarnings();
        this.loadStocksTechnical();
        this.loadIndices();
        this.loadFutures();
        this.loadETF();
        this.loadSectors();
        this.loadEarningsAlerts();
    }

    static setLoadingPlaceholders() {
        if (window.Skeleton) {
            Skeleton.show('stocksContainer', 'card', 6);
            Skeleton.show('indicesContainer', 'card', 4);
            Skeleton.show('futuresContainer', 'card', 4);
            Skeleton.show('etfContainer', 'card', 4);
            Skeleton.show('sectorRatingsContainer', 'card', 3);
            Skeleton.show('cnSectorsContainer', 'table-row', 3);
            Skeleton.show('usSectorsContainer', 'table-row', 3);
        }
    }

    static bindAdviceEvents() {
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('advice-icon-btn')) {
                e.stopPropagation();
                const advice = e.target.dataset.advice;
                if (advice) this.showAdvicePopover(e.target, advice);
            }
        });
        document.addEventListener('click', (e) => {
            const popover = document.getElementById('advicePopover');
            if (popover && !popover.contains(e.target) && !e.target.classList.contains('advice-icon-btn')) {
                popover.remove();
            }
        });
    }

    static showAdvicePopover(target, advice) {
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

        const popoverRect = popover.getBoundingClientRect();
        let top = rect.bottom + 8;
        let left = rect.left - popoverRect.width / 2 + rect.width / 2;
        if (left < 10) left = 10;
        if (left + popoverRect.width > window.innerWidth - 10) left = window.innerWidth - popoverRect.width - 10;
        if (top + popoverRect.height > window.innerHeight - 10) top = rect.top - popoverRect.height - 8;

        popover.style.top = top + 'px';
        popover.style.left = left + 'px';
        popover.querySelector('.advice-popover-close').addEventListener('click', () => popover.remove());
    }

    static async checkAIStatus() {
        try {
            const resp = await fetch('/briefing/api/ai/status');
            const data = await resp.json();
            this.aiEnabled = data.enabled;
            if (this.aiEnabled) {
                document.querySelectorAll('.bc-ai').forEach(el => el.classList.remove('d-none'));
            }
        } catch (e) {
            console.error('检查AI状态失败:', e);
        }
    }

    static bindAIEvents() {
        document.addEventListener('click', (e) => {
            const btn = e.target.closest('.bc-ai-btn');
            if (!btn) return;
            e.stopPropagation();
            const container = btn.closest('.bc-ai');
            const code = container.dataset.code;
            const name = container.dataset.name;

            const existingResult = container.querySelector('.bc-ai-result');
            if (existingResult) {
                existingResult.remove();
                return;
            }

            this.fetchAIAnalysis(btn, container, code, name);
        });
    }

    static async fetchAIAnalysis(btn, container, code, name) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm" style="width:10px;height:10px"></span>';

        try {
            const resp = await fetch('/briefing/api/ai/analyze', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({stock_code: code, stock_name: name})
            });
            const result = await resp.json();
            if (result.error) throw new Error(result.error);
            this.renderAIResult(container, result);
        } catch (e) {
            console.error(`AI分析 ${code} 失败:`, e);
            const errDiv = document.createElement('div');
            errDiv.className = 'bc-ai-result';
            errDiv.innerHTML = `<span style="color:#dc3545">分析失败: ${e.message}</span>`;
            container.appendChild(errDiv);
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-robot"></i> AI';
        }
    }

    static renderAIResult(container, result) {
        container.querySelector('.bc-ai-result')?.remove();

        const signalMap = {
            'STRONG_BUY': {text: '强烈买入', bg: '#28a745'},
            'BUY': {text: '买入', bg: '#20c997'},
            'HOLD': {text: '持有', bg: '#ffc107'},
            'SELL': {text: '卖出', bg: '#fd7e14'},
            'STRONG_SELL': {text: '强烈卖出', bg: '#dc3545'}
        };
        const sig = signalMap[result.signal] || {text: result.signal || '--', bg: '#6c757d'};

        const analysis = result.analysis || {};
        const plan = result.action_plan || {};

        let html = `<div class="bc-ai-result">`;
        html += `<div style="margin-bottom:4px"><span class="bc-ai-signal" style="background:${sig.bg};color:#fff">${sig.text}</span>`;
        if (result.score !== undefined) html += ` <span style="font-weight:600">${result.score}分</span>`;
        if (result.from_cache) html += ` <span style="color:#aaa;font-size:0.6rem">缓存</span>`;
        html += `</div>`;

        if (result.conclusion) html += `<div style="margin-bottom:4px;font-weight:500">${result.conclusion}</div>`;

        const details = [];
        if (analysis.trend) details.push(`趋势: ${analysis.trend}`);
        if (analysis.volume) details.push(`量能: ${analysis.volume}`);
        if (analysis.risk) details.push(`风险: ${analysis.risk}`);
        if (details.length) html += `<div style="color:#666;margin-bottom:4px">${details.join(' | ')}</div>`;

        const planItems = [];
        if (plan.buy_price) planItems.push(`买入:${plan.buy_price}`);
        if (plan.stop_loss) planItems.push(`止损:${plan.stop_loss}`);
        if (plan.target_price) planItems.push(`目标:${plan.target_price}`);
        if (planItems.length) html += `<div style="color:#888">${planItems.join(' | ')}</div>`;
        if (plan.position_advice) html += `<div style="color:#888">${plan.position_advice}</div>`;

        html += `</div>`;
        container.insertAdjacentHTML('beforeend', html);
    }

    // ========== 数据加载 ==========

    static async loadStocks(force = false) {
        try {
            const url = '/briefing/api/stocks' + (force ? '?force=true' : '');
            const resp = await fetch(url);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            if (data.error) throw new Error(data.error);

            this.renderStocks(data);
            this.stocksRendered = true;
            // 应用已到达的PE/财报/技术指标数据
            this.applyPEData();
            this.applyEarningsData();
            this.applyTechnicalData();

            if (data.last_update) {
                document.getElementById('lastUpdate').textContent = `更新时间: ${data.last_update}`;
            }
        } catch (e) {
            console.error('加载股票数据失败:', e);
            document.getElementById('stocksContainer').innerHTML = `<div class="text-warning-dark">股票数据加载失败</div>`;
        }
    }

    static async loadStocksPE(force = false) {
        try {
            const url = '/briefing/api/stocks/pe' + (force ? '?force=true' : '');
            const resp = await fetch(url);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            if (data.error) throw new Error(data.error);

            this.peData = data;
            this.applyPEData();
        } catch (e) {
            console.error('加载PE数据失败:', e);
        }
    }

    static async loadStocksEarnings(force = false) {
        try {
            const url = '/briefing/api/stocks/earnings' + (force ? '?force=true' : '');
            const resp = await fetch(url);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            if (data.error) throw new Error(data.error);

            this.earningsData = data;
            this.applyEarningsData();
        } catch (e) {
            console.error('加载财报数据失败:', e);
        }
    }

    static async loadStocksTechnical(force = false) {
        try {
            const url = '/briefing/api/stocks/technical' + (force ? '?force=true' : '');
            const resp = await fetch(url);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            if (data.error) throw new Error(data.error);

            this.technicalData = data;
            this.applyTechnicalData();
        } catch (e) {
            console.error('加载技术指标失败:', e);
        }
    }

    static async loadIndices(force = false) {
        try {
            const url = '/briefing/api/indices' + (force ? '?force=true' : '');
            const resp = await fetch(url);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            if (data.error) throw new Error(data.error);
            this.renderIndices(data);
        } catch (e) {
            console.error('加载指数数据失败:', e);
            document.getElementById('indicesContainer').innerHTML = `<div class="text-warning-dark">指数数据加载失败</div>`;
        }
    }

    static async loadFutures(force = false) {
        try {
            const url = '/briefing/api/futures' + (force ? '?force=true' : '');
            const resp = await fetch(url);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            if (data.error) throw new Error(data.error);
            this.renderFutures(data);
        } catch (e) {
            console.error('加载期货数据失败:', e);
            document.getElementById('futuresContainer').innerHTML = `<div class="text-warning-dark">期货数据加载失败</div>`;
        }
    }

    static async loadETF(force = false) {
        try {
            const url = '/briefing/api/etf' + (force ? '?force=true' : '');
            const resp = await fetch(url);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            if (data.error) throw new Error(data.error);
            this.renderETFPremium(data);
        } catch (e) {
            console.error('加载ETF数据失败:', e);
            document.getElementById('etfContainer').innerHTML = `<div class="text-warning-dark">ETF数据加载失败</div>`;
        }
    }

    static async loadSectors(force = false) {
        try {
            const url = '/briefing/api/sectors' + (force ? '?force=true' : '');
            const resp = await fetch(url);
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            if (data.error) throw new Error(data.error);
            this.renderSectorRatings(data.sector_ratings);
            this.renderSectors(data.cn_sectors, data.us_sectors);
        } catch (e) {
            console.error('加载板块数据失败:', e);
            document.getElementById('sectorRatingsContainer').innerHTML = `<div class="text-warning-dark">板块数据加载失败</div>`;
            document.getElementById('cnSectorsContainer').innerHTML = `<div class="text-warning-dark">加载失败</div>`;
            document.getElementById('usSectorsContainer').innerHTML = `<div class="text-warning-dark">加载失败</div>`;
        }
    }

    static async loadEarningsAlerts() {
        try {
            const resp = await fetch('/briefing/api/earnings-alerts');
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            this.renderEarningsAlerts(data.earnings_alerts, data.has_alerts);
        } catch (e) {
            console.error('加载财报预警失败:', e);
        }
    }

    // ========== 刷新 ==========

    static async refresh() {
        const btn = document.getElementById('refreshBtn');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> 刷新中...';

        this.stocksRendered = false;
        this.peData = null;
        this.earningsData = null;
        this.technicalData = null;
        this.setLoadingPlaceholders();

        try {
            await Promise.all([
                this.loadStocks(true),
                this.loadStocksPE(true),
                this.loadStocksEarnings(true),
                this.loadStocksTechnical(true),
                this.loadIndices(true),
                this.loadFutures(true),
                this.loadETF(true),
                this.loadSectors(true),
                this.loadEarningsAlerts(),
            ]);
        } catch (e) {
            console.error('刷新失败:', e);
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-arrow-clockwise"></i> 刷新';
        }
    }

    // ========== 推送报告 ==========

    static async pushReport(btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> 推送中...';

        try {
            // 先检查推送状态
            const statusResp = await fetch('/briefing/api/notification/status');
            const status = await statusResp.json();

            if (!status.slack && !status.email) {
                alert('未配置推送渠道。请设置环境变量：\n- Slack: SLACK_WEBHOOK_URL\n- 邮件: SMTP_HOST, SMTP_USER, SMTP_PASSWORD, NOTIFY_EMAIL_TO');
                return;
            }

            const resp = await fetch('/briefing/api/notification/push', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({include_ai: false})
            });
            const result = await resp.json();

            const parts = [];
            if (result.slack !== undefined) parts.push(`Slack: ${result.slack ? '成功' : '失败'}`);
            if (result.email !== undefined) parts.push(`邮件: ${result.email ? '成功' : '失败'}`);
            alert('推送结果: ' + (parts.join(', ') || '无可用渠道'));
        } catch (e) {
            console.error('推送失败:', e);
            alert('推送请求失败');
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-send"></i> 推送';
        }
    }

    // ========== PE/财报异步填充 ==========

    static applyPEData() {
        if (!this.peData || !this.stocksRendered) return;
        for (const [code, pe] of Object.entries(this.peData)) {
            const el = document.querySelector(`.stock-pe[data-code="${code}"]`);
            if (!el) continue;
            if (pe.pe_status === 'loss') {
                el.innerHTML = '<span class="text-up">亏损</span>';
            } else if (pe.pe_ttm !== null && pe.pe_ttm !== undefined) {
                const cls = this.getPEStatusClass(pe.pe_status);
                el.innerHTML = `PE:<span class="${cls}">${pe.pe_ttm.toFixed(1)}</span>`;
            }
        }
    }

    static applyEarningsData() {
        if (!this.earningsData || !this.stocksRendered) return;
        for (const [code, earnings] of Object.entries(this.earningsData)) {
            const el = document.querySelector(`.stock-earnings[data-code="${code}"]`);
            if (!el) continue;
            if (!earnings.earnings_date) continue;
            if (earnings.days_until_earnings !== null && earnings.days_until_earnings < 0) continue;

            const daysUntil = earnings.days_until_earnings;
            const cls = this.getEarningsDateClass(daysUntil);
            let text;
            if (earnings.is_earnings_today) {
                text = '今日';
            } else if (daysUntil !== null && daysUntil <= 7) {
                text = `${daysUntil}天`;
            } else {
                text = earnings.earnings_date.slice(5);
            }
            el.innerHTML = `财报:<span class="${cls}">${text}</span>`;
        }
    }

    static applyTechnicalData() {
        if (!this.technicalData || !this.stocksRendered) return;
        for (const [code, tech] of Object.entries(this.technicalData)) {
            const el = document.querySelector(`.stock-technical[data-code="${code}"]`);
            if (!el) continue;

            const scoreBg = this.getScoreBg(tech.score);
            const macdCls = tech.macd_signal.includes('金叉') || tech.macd_signal === '多头' ? 'text-up' :
                           tech.macd_signal.includes('死叉') || tech.macd_signal === '空头' ? 'text-down' : 'text-flat';

            el.innerHTML = `<span class="bc-score-badge" style="background:${scoreBg}" title="${tech.signal_text}">${tech.score}</span>` +
                `<span class="bc-macd-tag ${macdCls}">${tech.macd_signal}</span>`;
        }
    }

    static getScoreBg(score) {
        if (score >= 80) return '#28a745';
        if (score >= 60) return '#20c997';
        if (score >= 40) return '#ffc107';
        if (score >= 20) return '#fd7e14';
        return '#dc3545';
    }

    // ========== 渲染方法 ==========

    static renderEarningsAlerts(alerts, hasAlerts) {
        const section = document.getElementById('earningsAlertSection');
        const container = document.getElementById('earningsAlertContainer');

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

    static renderStockCard(stock) {
        const changeClass = this.getChangeClassNew(stock.change_percent);
        const changeText = stock.change_percent !== null
            ? `${stock.change_percent > 0 ? '+' : ''}${stock.change_percent.toFixed(2)}%`
            : '--';
        const priceText = stock.close !== null ? stock.close.toFixed(2) : '--';

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
                    <div class="bc-technical" data-code="${stock.code}">
                        <span class="stock-technical" data-code="${stock.code}"></span>
                    </div>
                    <div class="bc-secondary">
                        ${stock.market !== 'A' ? `<span class="stock-pe" data-code="${stock.code}"></span>` : ''}
                        <span class="stock-earnings" data-code="${stock.code}"></span>
                    </div>
                    <div class="bc-ai ${this.aiEnabled ? '' : 'd-none'}" data-code="${stock.code}" data-name="${stock.name}">
                        <button class="bc-ai-btn" title="AI分析"><i class="bi bi-robot"></i> AI</button>
                    </div>
                `}
            </div>
        `;
    }

    static escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

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

    static renderSectors(cnSectors, usSectors) {
        const cnContainer = document.getElementById('cnSectorsContainer');
        const usContainer = document.getElementById('usSectorsContainer');

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

    // ========== 工具方法 ==========

    static getChangeClassNew(changePercent) {
        if (changePercent === null || changePercent === undefined) return 'text-flat';
        if (changePercent > 0) return 'text-up';
        if (changePercent < 0) return 'text-down';
        return 'text-flat';
    }

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

    static getEarningsDateClass(daysUntil) {
        if (daysUntil === null || daysUntil === undefined) return 'text-muted';
        if (daysUntil <= 3) return 'text-danger fw-bold';
        if (daysUntil <= 7) return 'text-warning';
        return 'text-info';
    }

    static getEarningsUrgencyBg(daysUntil) {
        if (daysUntil === null || daysUntil === undefined || daysUntil < 0) return '#6c757d';
        if (daysUntil <= 3) return '#dc3545';
        if (daysUntil <= 7) return '#ffc107';
        return '#17a2b8';
    }

    static getEarningsUrgencyText(daysUntil) {
        if (daysUntil === null || daysUntil === undefined || daysUntil < 0) return '';
        if (daysUntil === 0) return '今日发布';
        if (daysUntil === 1) return '明日发布';
        return `${daysUntil}天后`;
    }

    static getPremiumClass(premiumRate) {
        if (premiumRate === null || premiumRate === undefined) return '';
        if (premiumRate <= 3) return 'text-down';
        if (premiumRate >= 6) return 'text-up';
        return 'text-warning-dark';
    }

    static getSignalInfo(signal) {
        if (!signal) return null;
        switch (signal) {
            case 'buy': return { text: '买入', bg: '#28a745' };
            case 'sell': return { text: '卖出', bg: '#dc3545' };
            case 'normal': return { text: '正常', bg: '#ffc107' };
            default: return null;
        }
    }

    static getRatingClass(rating) {
        switch (rating) {
            case 'bullish': return 'rating-bullish';
            case 'neutral': return 'rating-neutral';
            case 'bearish': return 'rating-bearish';
            default: return 'rating-neutral';
        }
    }

    static getRatingText(rating) {
        switch (rating) {
            case 'bullish': return '看涨';
            case 'neutral': return '中性';
            case 'bearish': return '看跌';
            default: return '中性';
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    BriefingPage.init();
});
