# 盯盘助手 UI 重设计 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 重构盯盘助手页面，按市场分组显示股票，增加市场状态header、刷新倒计时、通知状态和关键点位信息。

**Architecture:** 后端新增 `/watch/market-status` 接口返回市场状态，扩展 `/watch/prices` 返回通知状态和分析数据。前端从卡片网格改为市场分组列表，增加全局倒计时和市场时间实时更新。

**Tech Stack:** Flask route, TradingCalendarService, watch.js, watch.html (Bootstrap 5)

---

### Task 1: 后端 — 新增 market-status 接口

**Files:**
- Modify: `app/routes/watch.py`

**Step 1: 在 `watch.py` 末尾添加 market-status 路由**

```python
@watch_bp.route('/market-status')
def market_status():
    """返回各市场的状态信息"""
    from app.services.trading_calendar import TradingCalendarService
    from datetime import time as dtime

    markets_config = {
        'A': {'name': 'A股', 'icon': '📊'},
        'US': {'name': '美股', 'icon': '🇺🇸'},
        'HK': {'name': '港股', 'icon': '🇭🇰'},
    }

    result = {}
    for market, config in markets_config.items():
        market_now = TradingCalendarService.get_market_now(market)
        tz_name = TradingCalendarService.MARKET_TIMEZONES.get(market, '')
        is_open = TradingCalendarService.is_market_open(market)
        is_lunch = False

        # A股午休判断
        if market == 'A' and TradingCalendarService.is_trading_day(market, market_now.date()):
            t = market_now.time()
            is_lunch = dtime(11, 30) <= t < dtime(13, 0)

        if is_open:
            status, status_text = 'trading', '交易中'
        elif is_lunch:
            status, status_text = 'lunch', '午休'
        elif TradingCalendarService.is_trading_day(market, market_now.date()):
            if TradingCalendarService.is_after_close(market, market_now):
                status, status_text = 'closed', '已收盘'
            else:
                status, status_text = 'pre_open', '未开盘'
        else:
            status, status_text = 'holiday', '休市'

        result[market] = {
            'name': config['name'],
            'icon': config['icon'],
            'timezone': tz_name,
            'time': market_now.strftime('%H:%M'),
            'status': status,
            'status_text': status_text,
        }

    return jsonify({'success': True, 'data': result})
```

**Step 2: 验证**

启动应用，浏览器访问 `http://127.0.0.1:5000/watch/market-status`，确认返回 JSON 包含 A/US/HK 市场信息。

**Step 3: Commit**

```bash
git add app/routes/watch.py
git commit -m "feat(watch): 新增 market-status 接口返回各市场状态"
```

---

### Task 2: 后端 — 扩展 prices 接口返回通知状态和分析数据

**Files:**
- Modify: `app/routes/watch.py`

**Step 1: 重写 prices 路由，合并返回通知状态和分析数据**

将现有 `prices()` 函数替换为：

```python
@watch_bp.route('/prices')
def prices():
    from app.services.unified_stock_data import unified_stock_data_service
    from app.strategies.registry import registry
    from datetime import datetime

    codes = WatchService.get_watch_codes()
    if not codes:
        return jsonify({'success': True, 'prices': []})

    result = unified_stock_data_service.get_realtime_prices(codes)
    prices_list = result.get('prices', [])

    # 获取分析数据
    analyses = WatchService.get_all_today_analyses()

    # 获取通知冷却状态
    strategy = registry.get('watch_assistant')
    cooldowns = {}
    if strategy:
        config = strategy.get_config()
        cooldown_minutes = config.get('notification_cooldown_minutes', 30)
        default_threshold = config.get('default_volatility_threshold', 0.02)
        now = datetime.now()
        for code in codes:
            last_notified = strategy._last_notified.get(code)
            remaining = 0
            if last_notified:
                elapsed = (now - last_notified).total_seconds()
                remaining = max(0, cooldown_minutes * 60 - elapsed)
            analysis = analyses.get(code, {})
            cooldowns[code] = {
                'cooldown_remaining': int(remaining),
                'threshold': analysis.get('volatility_threshold') or default_threshold,
                'support_levels': analysis.get('support_levels', []),
                'resistance_levels': analysis.get('resistance_levels', []),
                'summary': analysis.get('summary', ''),
            }

    # 合并到价格数据
    for p in prices_list:
        code = p.get('code', '')
        extra = cooldowns.get(code, {})
        p['notification'] = extra

    return jsonify({'success': True, 'prices': prices_list})
```

**Step 2: 验证**

访问 `http://127.0.0.1:5000/watch/prices`，确认每个价格对象包含 `notification` 字段，内含 `cooldown_remaining`、`threshold`、`support_levels`、`resistance_levels`、`summary`。

**Step 3: Commit**

```bash
git add app/routes/watch.py
git commit -m "feat(watch): prices 接口合并返回通知状态和分析数据"
```

---

### Task 3: 前端 — 重写 watch.html 模板

**Files:**
- Modify: `app/templates/watch.html`

**Step 1: 替换整个 watch.html 内容**

```html
{% extends 'base.html' %}
{% block title %}盯盘助手{% endblock %}

{% block content %}
<!-- 页面标题 + 操作按钮 + 倒计时 -->
<div class="page-header mb-4">
    <div class="d-flex justify-content-between align-items-center">
        <div>
            <h4 class="mb-1"><i class="bi bi-eye"></i> 盯盘助手</h4>
            <small class="text-muted" id="watchStatus">加载中...</small>
        </div>
        <div class="d-flex align-items-center gap-2">
            <span class="badge bg-secondary" id="refreshCountdown" title="下次刷新倒计时">--s</span>
            <button class="btn btn-outline-primary btn-sm" id="btnAnalyze" onclick="Watch.triggerAnalysis()">
                <i class="bi bi-robot"></i> AI 分析
            </button>
            <button class="btn btn-primary btn-sm" data-bs-toggle="modal" data-bs-target="#addStockModal">
                <i class="bi bi-plus-lg"></i> 添加
            </button>
        </div>
    </div>
</div>

<!-- 骨架屏加载状态 -->
<div id="loadingState" class="py-3">
    <div class="mb-4">
        <div class="skeleton skeleton-text w-25 mb-3" style="height:24px;"></div>
        <div class="skeleton-card skeleton mb-2" style="height:80px;"></div>
        <div class="skeleton-card skeleton mb-2" style="height:80px;"></div>
    </div>
</div>

<!-- 空状态 -->
<div id="emptyState" class="text-center py-5 d-none">
    <i class="bi bi-eye-slash text-muted" style="font-size: 3rem;"></i>
    <p class="mt-3 text-muted">暂无盯盘股票</p>
    <button class="btn btn-primary btn-sm" data-bs-toggle="modal" data-bs-target="#addStockModal">
        <i class="bi bi-plus-lg"></i> 添加股票
    </button>
</div>

<!-- 市场分组列表 -->
<div id="watchGroups" class="d-none"></div>

<!-- 添加股票 Modal -->
<div class="modal fade" id="addStockModal" tabindex="-1">
    <div class="modal-dialog">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title"><i class="bi bi-plus-circle"></i> 添加盯盘股票</h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <div class="mb-3">
                    <input type="text" class="form-control" id="stockSearchInput"
                           placeholder="搜索股票代码或名称..." oninput="Watch.searchStocks(this.value)">
                </div>
                <div id="searchResults" class="list-group" style="max-height: 300px; overflow-y: auto;"></div>
            </div>
        </div>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script src="{{ url_for('static', filename='js/watch.js') }}"></script>
{% endblock %}
```

**Step 2: Commit**

```bash
git add app/templates/watch.html
git commit -m "feat(watch): 重写模板支持市场分组布局和倒计时"
```

---

### Task 4: 前端 — 重写 watch.js

**Files:**
- Modify: `app/static/js/watch.js`

**Step 1: 完整替换 watch.js**

```javascript
const Watch = {
    refreshTimer: null,
    countdownTimer: null,
    marketTimeTimer: null,
    countdown: 60,
    REFRESH_INTERVAL: 60,
    analyses: {},
    searchDebounce: null,
    stocks: [],
    prices: [],
    marketStatus: {},

    async init() {
        await this.loadList();
        this.startAutoRefresh();
    },

    async loadList() {
        try {
            const [listResp, priceResp, marketResp] = await Promise.all([
                fetch('/watch/list'),
                fetch('/watch/prices'),
                fetch('/watch/market-status'),
            ]);
            const listData = await listResp.json();
            const priceData = await priceResp.json();
            const marketData = await marketResp.json();

            if (!listData.success) return;
            this.stocks = listData.data || [];
            this.prices = priceData.prices || [];
            this.marketStatus = marketData.data || {};

            if (this.stocks.length === 0) {
                this.showEmpty();
                return;
            }

            this.renderGroups();
            this.updateStatus(`${this.stocks.length} 只股票`);
        } catch (e) {
            console.error('[Watch] loadList failed:', e);
            this.updateStatus('加载失败');
        }
    },

    async refreshPrices() {
        try {
            const [priceResp, marketResp] = await Promise.all([
                fetch('/watch/prices'),
                fetch('/watch/market-status'),
            ]);
            const priceData = await priceResp.json();
            const marketData = await marketResp.json();
            if (!priceData.success) return;

            this.prices = priceData.prices || [];
            this.marketStatus = marketData.data || {};
            this.updatePrices();
            this.updateMarketHeaders();
        } catch (e) {
            console.error('[Watch] refreshPrices failed:', e);
        }
    },

    async triggerAnalysis(force = false) {
        const btn = document.getElementById('btnAnalyze');
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> 分析中...';

        try {
            const resp = await fetch('/watch/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ force }),
            });
            const data = await resp.json();
            if (data.success) {
                this.analyses = data.data || {};
                await this.refreshPrices();
            }
        } catch (e) {
            console.error('[Watch] triggerAnalysis failed:', e);
        } finally {
            btn.disabled = false;
            btn.innerHTML = '<i class="bi bi-robot"></i> AI 分析';
        }
    },

    async addStock(code, name) {
        try {
            const resp = await fetch('/watch/add', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ stock_code: code, stock_name: name }),
            });
            const data = await resp.json();
            if (data.success) {
                const modal = bootstrap.Modal.getInstance(document.getElementById('addStockModal'));
                if (modal) modal.hide();
                document.getElementById('stockSearchInput').value = '';
                document.getElementById('searchResults').innerHTML = '';
                await this.loadList();
                this.triggerAnalysis();
            } else {
                alert(data.message || '添加失败');
            }
        } catch (e) {
            console.error('[Watch] addStock failed:', e);
        }
    },

    async removeStock(code) {
        if (!confirm('确定移除该股票？')) return;
        try {
            const resp = await fetch(`/watch/remove/${code}`, { method: 'DELETE' });
            const data = await resp.json();
            if (data.success) {
                this.stocks = this.stocks.filter(s => s.stock_code !== code);
                this.prices = this.prices.filter(p => p.code !== code);
                if (this.stocks.length === 0) {
                    this.showEmpty();
                } else {
                    this.renderGroups();
                }
                this.updateStatus(`${this.stocks.length} 只股票`);
            }
        } catch (e) {
            console.error('[Watch] removeStock failed:', e);
        }
    },

    searchStocks(query) {
        clearTimeout(this.searchDebounce);
        this.searchDebounce = setTimeout(async () => {
            const container = document.getElementById('searchResults');
            if (!query.trim()) {
                container.innerHTML = '';
                return;
            }
            try {
                const resp = await fetch(`/watch/stocks/search?q=${encodeURIComponent(query)}`);
                const data = await resp.json();
                if (!data.success) return;

                const existingCodes = new Set(this.stocks.map(s => s.stock_code));
                container.innerHTML = (data.data || []).map(s => {
                    const added = existingCodes.has(s.stock_code);
                    return `<div class="list-group-item d-flex justify-content-between align-items-center">
                        <div>
                            <span class="fw-bold">${s.stock_name}</span>
                            <small class="text-muted ms-2">${s.stock_code}</small>
                        </div>
                        ${added
                            ? '<span class="badge bg-secondary">已添加</span>'
                            : `<button class="btn btn-sm btn-outline-primary" onclick="Watch.addStock('${s.stock_code}','${s.stock_name}')">添加</button>`
                        }
                    </div>`;
                }).join('');

                if ((data.data || []).length === 0) {
                    container.innerHTML = '<div class="list-group-item text-muted text-center">无匹配结果</div>';
                }
            } catch (e) {
                console.error('[Watch] searchStocks failed:', e);
            }
        }, 300);
    },

    // --- 渲染 ---

    renderGroups() {
        const pricesMap = {};
        this.prices.forEach(p => { pricesMap[p.code] = p; });

        // 按市场分组
        const groups = {};
        const marketOrder = ['A', 'US', 'HK'];
        this.stocks.forEach(stock => {
            const market = stock.market || 'A';
            if (!groups[market]) groups[market] = [];
            groups[market].push(stock);
        });

        const container = document.getElementById('watchGroups');
        let html = '';

        marketOrder.forEach(market => {
            const stocks = groups[market];
            if (!stocks || stocks.length === 0) return;

            const ms = this.marketStatus[market] || {};
            const statusIcon = this.getStatusIcon(ms.status);

            html += `<div class="mb-4" data-market-group="${market}">
                <div class="d-flex align-items-center mb-2 pb-2 border-bottom">
                    <span class="me-2">${ms.icon || ''}</span>
                    <strong class="me-2">${ms.name || market}</strong>
                    <span class="text-muted small me-2" data-market-time="${market}">${ms.time || '--:--'}</span>
                    <span class="badge ${this.getStatusBadgeClass(ms.status)}">${statusIcon} ${ms.status_text || '--'}</span>
                </div>
                <div class="list-group">
                    ${stocks.map(stock => this.renderStockRow(stock, pricesMap[stock.stock_code] || {})).join('')}
                </div>
            </div>`;
        });

        container.innerHTML = html;
        document.getElementById('loadingState').classList.add('d-none');
        document.getElementById('emptyState').classList.add('d-none');
        container.classList.remove('d-none');
    },

    renderStockRow(stock, price) {
        const code = stock.stock_code;
        const name = stock.stock_name || code;
        const market = stock.market || 'A';

        const currentPrice = price.price ?? null;
        const changePct = price.change_pct ?? null;
        const changeAmt = price.change ?? null;
        const notification = price.notification || {};

        const priceDisplay = currentPrice !== null ? this.formatPrice(currentPrice, market) : '--';
        const pctClass = changePct > 0 ? 'text-danger' : changePct < 0 ? 'text-success' : 'text-muted';
        const pctSign = changePct > 0 ? '+' : '';
        const pctDisplay = changePct !== null ? `${pctSign}${changePct.toFixed(2)}%` : '--';
        const amtSign = changeAmt > 0 ? '+' : '';
        const amtDisplay = changeAmt !== null ? `${amtSign}${changeAmt.toFixed(2)}` : '';

        // 支撑/阻力位
        const supports = (notification.support_levels || []);
        const resistances = (notification.resistance_levels || []);
        const levelsHtml = this.renderLevels(supports, resistances);

        // 通知状态
        const threshold = notification.threshold || 0.02;
        const cooldown = notification.cooldown_remaining || 0;
        const thresholdText = `阈值 ${(threshold * 100).toFixed(1)}%`;
        const cooldownText = cooldown > 0
            ? `<span class="text-warning">冷却中 剩${Math.ceil(cooldown / 60)}分</span>`
            : '<span class="text-success">就绪</span>';

        return `<div class="list-group-item" id="watch-row-${code}">
            <div class="d-flex justify-content-between align-items-start">
                <div class="flex-grow-1">
                    <div class="d-flex align-items-center mb-1">
                        <span class="fw-bold me-2">${name}</span>
                        <small class="text-muted me-3">${code}</small>
                        <span class="fs-5 fw-bold me-2" data-field="price" data-code="${code}">${priceDisplay}</span>
                        <span class="${pctClass} fw-bold me-1" data-field="change_pct" data-code="${code}">${pctDisplay}</span>
                        <span class="${pctClass} small" data-field="change" data-code="${code}">${amtDisplay}</span>
                    </div>
                    <div class="d-flex align-items-center small" data-field="extra" data-code="${code}">
                        ${levelsHtml}
                        <span class="text-muted mx-1">|</span>
                        <span class="text-muted me-1">${thresholdText}</span>
                        <span class="text-muted mx-1">|</span>
                        ${cooldownText}
                    </div>
                </div>
                <button class="btn btn-sm btn-link text-muted p-0 ms-2" onclick="Watch.removeStock('${code}')" title="移除">
                    <i class="bi bi-x-lg"></i>
                </button>
            </div>
        </div>`;
    },

    renderLevels(supports, resistances) {
        if (supports.length === 0 && resistances.length === 0) {
            return '<span class="text-muted">暂无点位</span>';
        }
        let parts = [];
        if (supports.length > 0) {
            parts.push(`<span class="text-success">支撑: ${supports.join(' / ')}</span>`);
        }
        if (resistances.length > 0) {
            parts.push(`<span class="text-danger">阻力: ${resistances.join(' / ')}</span>`);
        }
        return parts.join('<span class="text-muted mx-1">|</span>');
    },

    // --- 实时更新 ---

    updatePrices() {
        const pricesMap = {};
        this.prices.forEach(p => { pricesMap[p.code] = p; });

        this.stocks.forEach(stock => {
            const code = stock.stock_code;
            const market = stock.market || 'A';
            const p = pricesMap[code];
            if (!p) return;

            const notification = p.notification || {};

            // 价格
            const priceEl = document.querySelector(`[data-field="price"][data-code="${code}"]`);
            if (priceEl) priceEl.textContent = this.formatPrice(p.price, market);

            // 涨跌幅
            const pctClass = p.change_pct > 0 ? 'text-danger' : p.change_pct < 0 ? 'text-success' : 'text-muted';
            const pctSign = p.change_pct > 0 ? '+' : '';
            const pctEl = document.querySelector(`[data-field="change_pct"][data-code="${code}"]`);
            if (pctEl) {
                pctEl.textContent = `${pctSign}${p.change_pct.toFixed(2)}%`;
                pctEl.className = `${pctClass} fw-bold me-1`;
            }
            const amtEl = document.querySelector(`[data-field="change"][data-code="${code}"]`);
            const amtSign = p.change > 0 ? '+' : '';
            if (amtEl) {
                amtEl.textContent = `${amtSign}${p.change.toFixed(2)}`;
                amtEl.className = `${pctClass} small`;
            }

            // 通知状态 + 点位
            const extraEl = document.querySelector(`[data-field="extra"][data-code="${code}"]`);
            if (extraEl) {
                const supports = notification.support_levels || [];
                const resistances = notification.resistance_levels || [];
                const threshold = notification.threshold || 0.02;
                const cooldown = notification.cooldown_remaining || 0;
                const thresholdText = `阈值 ${(threshold * 100).toFixed(1)}%`;
                const cooldownText = cooldown > 0
                    ? `<span class="text-warning">冷却中 剩${Math.ceil(cooldown / 60)}分</span>`
                    : '<span class="text-success">就绪</span>';

                extraEl.innerHTML = `${this.renderLevels(supports, resistances)}
                    <span class="text-muted mx-1">|</span>
                    <span class="text-muted me-1">${thresholdText}</span>
                    <span class="text-muted mx-1">|</span>
                    ${cooldownText}`;
            }
        });
    },

    updateMarketHeaders() {
        Object.keys(this.marketStatus).forEach(market => {
            const ms = this.marketStatus[market];
            const group = document.querySelector(`[data-market-group="${market}"]`);
            if (!group) return;

            const timeEl = group.querySelector(`[data-market-time="${market}"]`);
            if (timeEl) timeEl.textContent = ms.time || '--:--';

            const badge = group.querySelector('.badge');
            if (badge) {
                badge.className = `badge ${this.getStatusBadgeClass(ms.status)}`;
                badge.innerHTML = `${this.getStatusIcon(ms.status)} ${ms.status_text || '--'}`;
            }
        });
    },

    // --- 倒计时与自动刷新 ---

    startAutoRefresh() {
        this.stopAutoRefresh();
        this.countdown = this.REFRESH_INTERVAL;
        this.updateCountdownDisplay();

        this.countdownTimer = setInterval(() => {
            this.countdown--;
            if (this.countdown <= 0) {
                this.countdown = this.REFRESH_INTERVAL;
                this.refreshPrices();
            }
            this.updateCountdownDisplay();
        }, 1000);
    },

    stopAutoRefresh() {
        if (this.countdownTimer) {
            clearInterval(this.countdownTimer);
            this.countdownTimer = null;
        }
    },

    updateCountdownDisplay() {
        const el = document.getElementById('refreshCountdown');
        if (el) el.textContent = `${this.countdown}s`;
    },

    // --- 工具函数 ---

    showEmpty() {
        document.getElementById('loadingState').classList.add('d-none');
        document.getElementById('watchGroups').classList.add('d-none');
        document.getElementById('emptyState').classList.remove('d-none');
        this.updateStatus('暂无盯盘股票');
    },

    updateStatus(text) {
        document.getElementById('watchStatus').textContent = text;
    },

    formatPrice(price, market) {
        const val = price.toFixed(2);
        if (market === 'US') return `$${val}`;
        if (market === 'HK') return `HK$${val}`;
        return `¥${val}`;
    },

    getStatusIcon(status) {
        const map = { trading: '🟢', lunch: '🟡', closed: '⚫', pre_open: '⚪', holiday: '⚫' };
        return map[status] || '⚫';
    },

    getStatusBadgeClass(status) {
        const map = {
            trading: 'bg-success bg-opacity-25 text-success',
            lunch: 'bg-warning bg-opacity-25 text-warning',
            closed: 'bg-secondary bg-opacity-25 text-secondary',
            pre_open: 'bg-info bg-opacity-25 text-info',
            holiday: 'bg-secondary bg-opacity-25 text-secondary',
        };
        return map[status] || 'bg-secondary';
    },
};

document.addEventListener('DOMContentLoaded', () => Watch.init());
```

**Step 2: 验证**

启动应用访问 `http://127.0.0.1:5000/watch`，确认：
- 股票按市场分组显示
- 市场 header 显示时间和交易状态
- 每只股票显示支撑/阻力位和通知状态
- 页面顶部倒计时从60递减，归零后自动刷新

**Step 3: Commit**

```bash
git add app/static/js/watch.js app/templates/watch.html
git commit -m "feat(watch): 重写前端实现市场分组、倒计时和通知状态显示"
```

---

### Task 5: 集成验证与修复

**Step 1: 端到端验证清单**

1. 页面加载：骨架屏 → 市场分组列表
2. 市场 header：图标 + 名称 + 时间 + 状态指示灯
3. 股票行：名称 + 代码 + 价格 + 涨跌 + 支撑/阻力 + 阈值 + 冷却状态
4. 倒计时：60→0 递减，归零后刷新价格和市场状态
5. 添加/移除股票：正常工作，列表自动更新
6. AI 分析：触发后支撑/阻力位更新到股票行
7. 空列表：显示空状态提示

**Step 2: 修复发现的问题**

**Step 3: Final commit**

```bash
git add -A
git commit -m "feat(watch): 盯盘助手 UI 重设计完成 — 市场分组 + 倒计时 + 通知状态"
```
