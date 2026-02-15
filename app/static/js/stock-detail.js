/**
 * 股票详情抽屉组件
 */
class StockDetailDrawer {
    static currentCode = null;
    static currentName = null;
    static abortController = null;
    static chart = null;
    static aiHistoryData = [];
    static currentDays = 60;

    static init() {
        document.getElementById('sdClose')?.addEventListener('click', () => this.close());

        document.getElementById('stockDetailOverlay')?.addEventListener('click', (e) => {
            if (e.target.id === 'stockDetailOverlay') this.close();
        });

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') this.close();
        });

        document.getElementById('sdPeriodBtns')?.addEventListener('click', (e) => {
            const btn = e.target.closest('.sd-period-btn');
            if (!btn || btn.classList.contains('active')) return;
            document.querySelectorAll('.sd-period-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const days = parseInt(btn.dataset.days);
            this.currentDays = days;
            this.loadOHLC(this.currentCode, days);
        });

        document.getElementById('sdAIBtn')?.addEventListener('click', () => this.runAIAnalysis());
    }

    static open(code, name) {
        if (this.currentCode === code && document.getElementById('stockDetailOverlay').style.display !== 'none') {
            return;
        }

        if (this.abortController) {
            this.abortController.abort();
        }
        this.abortController = new AbortController();

        this.currentCode = code;
        this.currentName = name;
        this.currentDays = 60;

        document.getElementById('sdTitle').textContent = name || code;
        document.getElementById('sdCode').textContent = code;
        document.getElementById('sdMarket').textContent = '';

        this.resetContent();

        document.querySelectorAll('.sd-period-btn').forEach(b => {
            b.classList.toggle('active', b.dataset.days === '60');
        });

        const overlay = document.getElementById('stockDetailOverlay');
        overlay.style.display = '';
        document.body.style.overflow = 'hidden';
        requestAnimationFrame(() => {
            overlay.classList.add('active');
        });

        this.loadData(code);
    }

    static close() {
        const overlay = document.getElementById('stockDetailOverlay');
        if (!overlay || overlay.style.display === 'none') return;

        overlay.classList.remove('active');
        document.body.style.overflow = '';

        setTimeout(() => {
            overlay.style.display = 'none';
            if (this.chart) {
                this.chart.dispose();
                this.chart = null;
            }
        }, 300);

        if (this.abortController) {
            this.abortController.abort();
            this.abortController = null;
        }

        this.currentCode = null;
        this.currentName = null;
    }

    static resetContent() {
        document.getElementById('sdPrice').textContent = '--';
        document.getElementById('sdPrice').className = 'sd-current-price';
        document.getElementById('sdChange').textContent = '';
        document.getElementById('sdChangePct').textContent = '';
        document.getElementById('sdVolume').textContent = '';
        document.getElementById('sdPosition').classList.add('d-none');

        document.getElementById('sdChartContainer').innerHTML = '<div class="sd-chart-skeleton"><div class="skeleton skeleton-chart"></div></div>';

        document.getElementById('sdTechnicalContent').innerHTML = '<div class="sd-skeleton-rows"><div class="skeleton skeleton-text w-80"></div><div class="skeleton skeleton-text w-60"></div></div>';

        document.getElementById('sdAdviceSection').classList.add('d-none');
        document.getElementById('sdAISection').classList.add('d-none');
        document.getElementById('sdAIResult').innerHTML = '';
        document.getElementById('sdAIHistoryList').innerHTML = '';
    }

    static async loadData(code) {
        try {
            const resp = await fetch(`/api/stock-detail/${encodeURIComponent(code)}`, {
                signal: this.abortController?.signal
            });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            if (data.error) throw new Error(data.error);

            if (this.currentCode !== code) return;

            this.renderBasic(data.basic);
            this.renderPosition(data.position, data.basic?.price);
            this.renderChart(data.ohlc);
            this.renderTechnical(data.technical, data.wyckoff);
            this.renderAdvice(data.advice);
            this.renderAISection(data.ai_enabled, code);

        } catch (e) {
            if (e.name === 'AbortError') return;
            console.error('加载股票详情失败:', e);
            if (this.currentCode === code) {
                document.getElementById('sdTechnicalContent').innerHTML = `
                    <div class="sd-error">
                        <div>加载失败: ${e.message}</div>
                        <button class="sd-error-btn" onclick="StockDetailDrawer.loadData('${code}')">重试</button>
                    </div>`;
            }
        }
    }

    // ====== 渲染方法 ======

    static renderBasic(basic) {
        if (!basic) return;

        document.getElementById('sdMarket').textContent = basic.market || '';

        const price = basic.price;
        const change = basic.change;
        const changePct = basic.change_pct;

        const colorClass = changePct > 0 ? 'sd-text-up' : changePct < 0 ? 'sd-text-down' : 'sd-text-flat';

        document.getElementById('sdPrice').textContent = price !== null && price !== undefined ? price.toFixed(2) : '--';
        document.getElementById('sdPrice').className = `sd-current-price ${colorClass}`;

        if (change !== null && change !== undefined) {
            const sign = change > 0 ? '+' : '';
            document.getElementById('sdChange').textContent = `${sign}${change.toFixed(2)}`;
            document.getElementById('sdChange').className = `sd-change ${colorClass}`;
        }

        if (changePct !== null && changePct !== undefined) {
            const sign = changePct > 0 ? '+' : '';
            document.getElementById('sdChangePct').textContent = `${sign}${changePct.toFixed(2)}%`;
            document.getElementById('sdChangePct').className = `sd-change-pct ${colorClass}`;
        }

        if (basic.volume) {
            const vol = basic.volume >= 10000 ? (basic.volume / 10000).toFixed(1) + '万' : basic.volume;
            document.getElementById('sdVolume').textContent = `成交量: ${vol}`;
        }
    }

    static renderPosition(position, currentPrice) {
        const el = document.getElementById('sdPosition');
        if (!position) {
            el.classList.add('d-none');
            return;
        }

        el.classList.remove('d-none');
        document.getElementById('sdPosQuantity').textContent = position.quantity;
        document.getElementById('sdPosCost').textContent = position.cost_price?.toFixed(2) || '--';

        const profit = position.profit;
        const profitPct = position.profit_pct;
        if (profit !== null && profit !== undefined) {
            const sign = profit > 0 ? '+' : '';
            const cls = profit > 0 ? 'sd-text-up' : profit < 0 ? 'sd-text-down' : 'sd-text-flat';
            const pctText = profitPct !== null && profitPct !== undefined ? ` (${sign}${profitPct.toFixed(2)}%)` : '';
            document.getElementById('sdPosProfit').innerHTML = `<span class="${cls}">${sign}${profit.toFixed(2)}${pctText}</span>`;
        }
    }

    static renderChart(ohlc) {
        const container = document.getElementById('sdChartContainer');
        if (!ohlc || ohlc.length === 0) {
            container.innerHTML = '<div style="text-align:center;color:#aaa;padding:40px 0">暂无走势数据</div>';
            return;
        }

        container.innerHTML = '';

        if (typeof echarts === 'undefined') {
            container.innerHTML = '<div style="text-align:center;color:#aaa;padding:40px 0">图表库未加载</div>';
            return;
        }

        if (this.chart) {
            this.chart.dispose();
        }
        this.chart = echarts.init(container);

        const dates = ohlc.map(d => d.date);
        const ohlcData = ohlc.map(d => [d.open, d.close, d.low, d.high]);
        const volumes = ohlc.map(d => d.volume || 0);
        const colors = ohlc.map(d => d.close >= d.open ? '#dc3545' : '#28a745');

        const option = {
            animation: false,
            grid: [
                { left: 50, right: 10, top: 10, height: '60%' },
                { left: 50, right: 10, top: '76%', height: '18%' }
            ],
            xAxis: [
                {
                    type: 'category', data: dates,
                    gridIndex: 0,
                    axisLabel: { show: false },
                    axisTick: { show: false },
                    axisLine: { lineStyle: { color: '#eee' } }
                },
                {
                    type: 'category', data: dates,
                    gridIndex: 1,
                    axisLabel: { fontSize: 10, color: '#aaa', rotate: 0, interval: Math.floor(dates.length / 4) },
                    axisTick: { show: false },
                    axisLine: { lineStyle: { color: '#eee' } }
                }
            ],
            yAxis: [
                {
                    gridIndex: 0,
                    scale: true,
                    splitLine: { lineStyle: { color: '#f5f5f5' } },
                    axisLabel: { fontSize: 10, color: '#aaa' }
                },
                {
                    gridIndex: 1,
                    scale: true,
                    splitLine: { show: false },
                    axisLabel: { show: false },
                    axisTick: { show: false }
                }
            ],
            series: [
                {
                    type: 'candlestick',
                    xAxisIndex: 0, yAxisIndex: 0,
                    data: ohlcData,
                    itemStyle: {
                        color: '#dc3545',
                        color0: '#28a745',
                        borderColor: '#dc3545',
                        borderColor0: '#28a745'
                    }
                },
                {
                    type: 'bar',
                    xAxisIndex: 1, yAxisIndex: 1,
                    data: volumes.map((v, i) => ({
                        value: v,
                        itemStyle: { color: colors[i], opacity: 0.5 }
                    })),
                    barWidth: '60%'
                }
            ],
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'cross' },
                formatter: function(params) {
                    if (!params || !params[0]) return '';
                    const d = params[0];
                    const idx = d.dataIndex;
                    const item = ohlc[idx];
                    if (!item) return '';
                    return `${item.date}<br/>
                        开: ${item.open?.toFixed(2) || '--'}<br/>
                        高: ${item.high?.toFixed(2) || '--'}<br/>
                        低: ${item.low?.toFixed(2) || '--'}<br/>
                        收: ${item.close?.toFixed(2) || '--'}<br/>
                        量: ${(item.volume || 0).toLocaleString()}`;
                }
            },
            dataZoom: [
                {
                    type: 'inside',
                    xAxisIndex: [0, 1],
                    start: 50, end: 100
                }
            ]
        };

        this.chart.setOption(option);

        const resizeObserver = new ResizeObserver(() => {
            this.chart?.resize();
        });
        resizeObserver.observe(container);
    }

    static async loadOHLC(code, days) {
        const container = document.getElementById('sdChartContainer');
        container.innerHTML = '<div class="sd-chart-skeleton"><div class="skeleton skeleton-chart"></div></div>';

        try {
            const resp = await fetch(`/api/stock-detail/${encodeURIComponent(code)}/ohlc?days=${days}`, {
                signal: this.abortController?.signal
            });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            const data = await resp.json();
            if (this.currentCode !== code) return;
            this.renderChart(data.ohlc);
        } catch (e) {
            if (e.name === 'AbortError') return;
            console.error('加载走势数据失败:', e);
            container.innerHTML = '<div style="text-align:center;color:#dc3545;padding:40px 0">加载失败</div>';
        }
    }

    static renderTechnical(technical, wyckoff) {
        const content = document.getElementById('sdTechnicalContent');

        if (!technical && !wyckoff) {
            content.innerHTML = '<div style="color:#aaa;font-size:0.8rem">暂无技术分析</div>';
            return;
        }

        let html = '';

        if (technical) {
            const scoreBg = this.getScoreBg(technical.score);
            html += `<div class="sd-tech-grid">`;
            html += `<div class="sd-tech-item"><span class="sd-tech-label">综合评分</span><span class="sd-tech-value" style="color:#fff;background:${scoreBg};padding:1px 8px;border-radius:3px">${technical.score}</span></div>`;

            if (technical.signal_text) {
                html += `<div class="sd-tech-item"><span class="sd-tech-label">信号</span><span class="sd-tech-value">${technical.signal_text}</span></div>`;
            }
            if (technical.macd_signal) {
                const macdCls = technical.macd_signal.includes('金叉') || technical.macd_signal === '多头' ? 'sd-text-up' :
                               technical.macd_signal.includes('死叉') || technical.macd_signal === '空头' ? 'sd-text-down' : 'sd-text-flat';
                html += `<div class="sd-tech-item"><span class="sd-tech-label">MACD</span><span class="sd-tech-value ${macdCls}">${technical.macd_signal}</span></div>`;
            }
            if (technical.rsi_6 !== undefined) {
                const rsiCls = technical.rsi_6 > 70 ? 'sd-text-up' : technical.rsi_6 < 30 ? 'sd-text-down' : '';
                html += `<div class="sd-tech-item"><span class="sd-tech-label">RSI(6)</span><span class="sd-tech-value ${rsiCls}">${technical.rsi_6?.toFixed(1) || '--'}</span></div>`;
            }
            if (technical.trend_state) {
                const trendText = {'uptrend':'上升趋势','downtrend':'下降趋势','sideways':'横盘整理'}[technical.trend_state] || technical.trend_state;
                const trendCls = technical.trend_state === 'uptrend' ? 'sd-text-up' : technical.trend_state === 'downtrend' ? 'sd-text-down' : 'sd-text-flat';
                html += `<div class="sd-tech-item"><span class="sd-tech-label">趋势</span><span class="sd-tech-value ${trendCls}">${trendText}</span></div>`;
            }
            html += `</div>`;
        }

        if (wyckoff) {
            const phaseMap = {
                'accumulation': '吸筹阶段', 'markup': '上涨阶段',
                'distribution': '派发阶段', 'markdown': '下跌阶段',
                'reaccumulation': '再吸筹', 'redistribution': '再派发'
            };
            const phaseName = phaseMap[wyckoff.phase] || wyckoff.phase || '未知';

            html += `<div class="sd-wyckoff">`;
            html += `<div class="sd-wyckoff-phase">威科夫: ${phaseName}</div>`;
            if (wyckoff.advice) {
                html += `<div class="sd-wyckoff-advice">${wyckoff.advice}</div>`;
            }
            if (wyckoff.support_price || wyckoff.resistance_price) {
                html += `<div class="sd-wyckoff-prices">`;
                if (wyckoff.support_price) html += `<span>支撑: ${wyckoff.support_price.toFixed(2)}</span>`;
                if (wyckoff.resistance_price) html += `<span>阻力: ${wyckoff.resistance_price.toFixed(2)}</span>`;
                html += `</div>`;
            }
            html += `</div>`;
        }

        content.innerHTML = html;
    }

    static renderAdvice(advice) {
        const section = document.getElementById('sdAdviceSection');
        if (!advice) {
            section.classList.add('d-none');
            return;
        }
        section.classList.remove('d-none');
        document.getElementById('sdAdviceContent').textContent = advice;
    }

    static renderAISection(aiEnabled, code) {
        const section = document.getElementById('sdAISection');
        if (!aiEnabled) {
            section.classList.add('d-none');
            return;
        }
        section.classList.remove('d-none');

        const btn = document.getElementById('sdAIBtn');
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-robot"></i> AI 智能分析';

        this.loadAIHistory(code);
    }

    // ====== AI 方法 ======

    static async loadAIHistory(code) {
        const container = document.getElementById('sdAIHistoryList');
        container.innerHTML = '<div class="sd-ai-history-empty">加载中...</div>';

        try {
            const resp = await fetch(`/api/stock-detail/ai/history?stock_code=${encodeURIComponent(code)}`, {
                signal: this.abortController?.signal
            });
            const data = await resp.json();
            if (data.error) throw new Error(data.error);
            if (this.currentCode !== code) return;

            this.aiHistoryData = data.history || [];
            this.renderAIHistory(this.aiHistoryData);
        } catch (e) {
            if (e.name === 'AbortError') return;
            console.error('加载AI历史失败:', e);
            container.innerHTML = '<div class="sd-ai-history-empty">加载历史记录失败</div>';
        }
    }

    static renderAIHistory(history) {
        const container = document.getElementById('sdAIHistoryList');
        if (!history || history.length === 0) {
            container.innerHTML = '<div class="sd-ai-history-empty">暂无历史分析记录</div>';
            return;
        }

        const signalMap = {
            'STRONG_BUY': {text: '强烈买入', bg: '#28a745'},
            'BUY': {text: '买入', bg: '#20c997'},
            'HOLD': {text: '持有', bg: '#ffc107'},
            'SELL': {text: '卖出', bg: '#fd7e14'},
            'STRONG_SELL': {text: '强烈卖出', bg: '#dc3545'}
        };

        container.innerHTML = history.map((item, idx) => {
            const sig = signalMap[item.signal] || {text: item.signal || '--', bg: '#6c757d'};
            return `
                <div class="sd-ai-history-item" onclick="StockDetailDrawer.showHistoryDetail(${idx})">
                    <div class="sd-ai-history-item-header">
                        <span class="sd-ai-history-date">${item.date}</span>
                        <span class="sd-ai-history-signal" style="background:${sig.bg}">${sig.text}</span>
                    </div>
                    <div class="sd-ai-history-conclusion">${item.conclusion || '--'}</div>
                </div>`;
        }).join('');
    }

    static showHistoryDetail(idx) {
        if (!this.aiHistoryData || !this.aiHistoryData[idx]) return;
        this.renderAIResultPanel(this.aiHistoryData[idx], true);
    }

    static async runAIAnalysis() {
        if (!this.currentCode) return;
        const btn = document.getElementById('sdAIBtn');

        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> 分析中...';

        try {
            const resp = await fetch('/api/stock-detail/ai/analyze', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    stock_code: this.currentCode,
                    stock_name: this.currentName,
                    force: true
                }),
                signal: this.abortController?.signal
            });
            const result = await resp.json();
            if (result.error) throw new Error(result.error);

            this.renderAIResultPanel(result);
            this.loadAIHistory(this.currentCode);
        } catch (e) {
            if (e.name === 'AbortError') return;
            console.error('AI分析失败:', e);
            document.getElementById('sdAIResult').innerHTML = `<div class="sd-ai-result" style="color:#dc3545">分析失败: ${e.message}</div>`;
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-robot"></i> AI 智能分析';
        }
    }

    static renderAIResultPanel(result, isHistory = false) {
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

        let html = `<div class="sd-ai-result">`;
        if (isHistory && result.date) {
            html += `<div style="color:#888;font-size:0.7rem;margin-bottom:6px">${result.date} 的分析</div>`;
        }
        html += `<div class="sd-ai-header">`;
        html += `<span class="sd-ai-signal" style="background:${sig.bg}">${sig.text}</span>`;
        if (result.score !== undefined) html += `<span class="sd-ai-score">${result.score}分</span>`;
        html += `</div>`;

        if (result.conclusion) html += `<div class="sd-ai-conclusion">${result.conclusion}</div>`;

        const details = [];
        if (analysis.trend) details.push(`趋势: ${analysis.trend}`);
        if (analysis.volume) details.push(`量能: ${analysis.volume}`);
        if (analysis.risk) details.push(`风险: ${analysis.risk}`);
        if (details.length) html += `<div class="sd-ai-details">${details.join('<br>')}</div>`;

        const planItems = [];
        if (plan.buy_price) planItems.push(`买入价: ${plan.buy_price}`);
        if (plan.stop_loss) planItems.push(`止损价: ${plan.stop_loss}`);
        if (plan.target_price) planItems.push(`目标价: ${plan.target_price}`);
        if (planItems.length) html += `<div class="sd-ai-plan">${planItems.join(' | ')}</div>`;
        if (plan.position_advice) html += `<div class="sd-ai-plan">${plan.position_advice}</div>`;

        html += `</div>`;
        document.getElementById('sdAIResult').innerHTML = html;
    }

    // ====== 工具方法 ======

    static getScoreBg(score) {
        if (score >= 80) return '#28a745';
        if (score >= 60) return '#20c997';
        if (score >= 40) return '#ffc107';
        if (score >= 20) return '#fd7e14';
        return '#dc3545';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    StockDetailDrawer.init();
});
