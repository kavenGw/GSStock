# 威科夫分析合并到股票详情页 - 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 移除威科夫独立页面，将威科夫分析功能整合到股票详情抽屉中，支持单股实时分析、回测和历史记录。

**Architecture:** 后端在 `stock_detail.py` 新增4个API端点（分析、回测、参考图、历史），前端在抽屉HTML中新增威科夫区块，在 `stock-detail.js` 中新增渲染和交互逻辑。然后删除威科夫独立页面的路由、模板和静态资源，并从导航栏和蓝图注册中移除引用。

**Tech Stack:** Flask, SQLAlchemy, JavaScript (原生), ECharts, Bootstrap 5

**Design doc:** `docs/plans/2026-02-15-wyckoff-merge-to-detail-design.md`

---

### Task 1: 新增后端 API 端点

**Files:**
- Modify: `app/routes/stock_detail.py`

**Step 1: 添加4个 API 端点到 stock_detail.py**

在文件末尾添加以下路由：

```python
# ====== 威科夫分析 API ======

@stock_detail_bp.route('/<code>/wyckoff/analyze', methods=['POST'])
def wyckoff_analyze(code):
    """单股威科夫实时分析"""
    from app.services.wyckoff import WyckoffAutoService
    from app.models.stock import Stock

    stock = Stock.query.filter_by(stock_code=code).first()
    stock_name = stock.stock_name if stock else ''

    try:
        result = WyckoffAutoService.analyze_single(code, stock_name)
        return jsonify(result)
    except Exception as e:
        logger.error(f"威科夫分析 {code} 失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@stock_detail_bp.route('/<code>/wyckoff/backtest', methods=['POST'])
def wyckoff_backtest(code):
    """单股回测验证"""
    from app.services.backtest import BacktestService

    data = request.get_json() or {}
    days = data.get('days', 180)

    try:
        service = BacktestService()
        wyckoff_result = service.backtest_wyckoff(code, days)
        signal_result = service.backtest_signals(code, days)
        return jsonify({'wyckoff': wyckoff_result, 'signals': signal_result})
    except Exception as e:
        logger.error(f"回测 {code} 失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@stock_detail_bp.route('/<code>/wyckoff/reference/<phase>')
def wyckoff_reference(code, phase):
    """获取阶段参考图"""
    from app.models.wyckoff import WyckoffReference

    ref = WyckoffReference.query.filter_by(phase=phase)\
        .order_by(WyckoffReference.created_at.desc()).first()
    if not ref:
        return jsonify({'found': False})
    return jsonify({'found': True, 'image_path': ref.image_path, 'description': ref.description})


@stock_detail_bp.route('/<code>/wyckoff/history')
def wyckoff_history(code):
    """该股票的威科夫历史分析记录"""
    from app.models.wyckoff import WyckoffAutoResult

    records = WyckoffAutoResult.query.filter_by(
        stock_code=code, status='success'
    ).order_by(WyckoffAutoResult.analysis_date.desc()).limit(20).all()

    return jsonify({'history': [r.to_dict() for r in records]})
```

**Step 2: 验证 Flask 启动无报错**

Run: `cd D:/Git/stock && python -c "from app import create_app; app = create_app(); print('OK')"`
Expected: OK

**Step 3: Commit**

```bash
git add app/routes/stock_detail.py
git commit -m "feat: 添加威科夫分析API到股票详情端点"
```

---

### Task 2: 新增抽屉 HTML 区块

**Files:**
- Modify: `app/templates/partials/stock_detail_drawer.html`

**Step 1: 在技术指标区和投资建议区之间插入威科夫区块**

在 `<!-- 3. 技术指标区 -->` 的 `</div>` 之后、`<!-- 4. 投资建议区 -->` 之前，插入：

```html
            <!-- 4. 威科夫量价分析区 -->
            <div class="sd-section" id="sdWyckoffSection">
                <div class="sd-section-header">
                    <span class="sd-section-title">威科夫量价分析</span>
                    <div class="sd-wyckoff-btns">
                        <button class="sd-wk-btn" id="sdWkAnalyzeBtn">分析</button>
                        <button class="sd-wk-btn sd-wk-btn-secondary" id="sdWkBacktestBtn">回测</button>
                    </div>
                </div>
                <div id="sdWyckoffContent">
                    <div class="sd-skeleton-rows">
                        <div class="skeleton skeleton-text w-80"></div>
                        <div class="skeleton skeleton-text w-60"></div>
                    </div>
                </div>
                <!-- 回测结果（折叠） -->
                <div class="sd-wk-collapse d-none" id="sdWkBacktestResult"></div>
                <!-- 历史记录（折叠） -->
                <div class="sd-wk-collapse d-none" id="sdWkHistorySection">
                    <div class="sd-wk-history-title" id="sdWkHistoryToggle">
                        <i class="bi bi-clock-history"></i> 历史记录
                        <i class="bi bi-chevron-down sd-wk-toggle-icon"></i>
                    </div>
                    <div class="sd-wk-history-list d-none" id="sdWkHistoryList"></div>
                </div>
            </div>
```

将原来的 `<!-- 4. 投资建议区 -->` 注释改为 `<!-- 5. 投资建议区 -->`，`<!-- 5. AI分析区 -->` 改为 `<!-- 6. AI分析区 -->`。

**Step 2: Commit**

```bash
git add app/templates/partials/stock_detail_drawer.html
git commit -m "feat: 添加威科夫区块到详情抽屉HTML"
```

---

### Task 3: 新增威科夫区块 CSS 样式

**Files:**
- Modify: `app/static/css/stock-detail.css`

**Step 1: 在 `.sd-wyckoff-prices` 样式块后面追加威科夫区块样式**

```css
/* 威科夫分析按钮 */
.sd-wyckoff-btns {
    display: flex;
    gap: 6px;
}
.sd-wk-btn {
    padding: 3px 12px;
    border: 1px solid #6f42c1;
    color: #6f42c1;
    background: transparent;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s;
}
.sd-wk-btn:hover { background: #6f42c1; color: #fff; }
.sd-wk-btn:disabled { opacity: 0.5; cursor: wait; }
.sd-wk-btn-secondary {
    border-color: #6c757d;
    color: #6c757d;
}
.sd-wk-btn-secondary:hover { background: #6c757d; color: #fff; }

/* 威科夫分析结果 */
.sd-wk-result {
    padding: 10px 12px;
    background: #f8f7fc;
    border-radius: 6px;
    border: 1px solid #e8e0f0;
}
.sd-wk-result-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
    flex-wrap: wrap;
}
.sd-wk-phase-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 4px;
    font-weight: 600;
    font-size: 0.8rem;
    color: #fff;
}
.sd-wk-advice-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 3px;
    font-weight: 600;
    font-size: 0.75rem;
    color: #fff;
}
.sd-wk-ref-icon {
    cursor: pointer;
    color: #6f42c1;
    font-size: 0.85rem;
    opacity: 0.7;
    transition: opacity 0.15s;
}
.sd-wk-ref-icon:hover { opacity: 1; }
.sd-wk-events {
    display: flex;
    gap: 4px;
    flex-wrap: wrap;
    margin-bottom: 6px;
}
.sd-wk-event-tag {
    padding: 1px 8px;
    background: #e8e0f0;
    border-radius: 3px;
    font-size: 0.7rem;
    color: #6f42c1;
}
.sd-wk-prices {
    display: flex;
    gap: 16px;
    font-size: 0.75rem;
    color: #888;
    margin-bottom: 4px;
}
.sd-wk-time {
    font-size: 0.7rem;
    color: #aaa;
}

/* 威科夫折叠区 */
.sd-wk-collapse {
    margin-top: 10px;
    padding-top: 10px;
    border-top: 1px solid #eee;
}
.sd-wk-history-title {
    font-size: 0.8rem;
    font-weight: 600;
    color: #888;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 6px;
}
.sd-wk-toggle-icon {
    font-size: 0.65rem;
    transition: transform 0.2s;
    margin-left: auto;
}
.sd-wk-toggle-icon.open {
    transform: rotate(180deg);
}
.sd-wk-history-item {
    padding: 6px 10px;
    border: 1px solid #e8e0f0;
    border-radius: 4px;
    margin-top: 6px;
    font-size: 0.75rem;
    display: flex;
    align-items: center;
    gap: 8px;
}
.sd-wk-history-date {
    color: #888;
    font-size: 0.7rem;
    min-width: 80px;
}

/* 回测结果 */
.sd-wk-backtest {
    padding: 10px 12px;
    background: #f9f9f9;
    border-radius: 6px;
}
.sd-wk-backtest-title {
    font-size: 0.8rem;
    font-weight: 600;
    color: #666;
    margin-bottom: 8px;
}
.sd-wk-backtest-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 6px;
}
.sd-wk-backtest-item {
    display: flex;
    justify-content: space-between;
    padding: 4px 8px;
    background: #fff;
    border-radius: 3px;
    font-size: 0.75rem;
}
.sd-wk-backtest-label { color: #888; }
.sd-wk-backtest-value { font-weight: 600; }
```

**Step 2: Commit**

```bash
git add app/static/css/stock-detail.css
git commit -m "feat: 添加威科夫区块CSS样式"
```

---

### Task 4: 新增前端 JavaScript 逻辑

**Files:**
- Modify: `app/static/js/stock-detail.js`

**Step 1: 在 `StockDetailDrawer` class 中添加威科夫相关方法**

1. 在 `init()` 方法中添加事件绑定（在 `sdAIBtn` 绑定后面）：

```javascript
document.getElementById('sdWkAnalyzeBtn')?.addEventListener('click', () => this.runWyckoffAnalysis());
document.getElementById('sdWkBacktestBtn')?.addEventListener('click', () => this.runWyckoffBacktest());
document.getElementById('sdWkHistoryToggle')?.addEventListener('click', () => this.toggleWyckoffHistory());
```

2. 在 `resetContent()` 方法中添加威科夫区块重置：

```javascript
document.getElementById('sdWyckoffContent').innerHTML = '<div class="sd-skeleton-rows"><div class="skeleton skeleton-text w-80"></div><div class="skeleton skeleton-text w-60"></div></div>';
document.getElementById('sdWkBacktestResult').classList.add('d-none');
document.getElementById('sdWkBacktestResult').innerHTML = '';
document.getElementById('sdWkHistorySection').classList.add('d-none');
document.getElementById('sdWkHistoryList').innerHTML = '';
document.getElementById('sdWkHistoryList').classList.add('d-none');
```

3. 在 `loadData()` 的 `renderTechnical` 调用后面修改：把 `this.renderTechnical(data.technical, data.wyckoff);` 改为 `this.renderTechnical(data.technical);` 并添加：

```javascript
this.renderWyckoff(data.wyckoff);
```

4. 修改 `renderTechnical(technical, wyckoff)` 方法签名为 `renderTechnical(technical)`，移除其中所有 wyckoff 相关代码（`if (wyckoff) {...}` 整个块）。

5. 在 AI 方法之前添加威科夫方法区块：

```javascript
// ====== 威科夫方法 ======

static PHASE_MAP = {
    'accumulation': {text: '吸筹', bg: '#28a745'},
    'markup': {text: '上涨', bg: '#0d6efd'},
    'distribution': {text: '派发', bg: '#fd7e14'},
    'markdown': {text: '下跌', bg: '#dc3545'},
    'reaccumulation': {text: '再吸筹', bg: '#20c997'},
    'redistribution': {text: '再派发', bg: '#e83e8c'},
};

static ADVICE_MAP = {
    'buy': {text: '买入', bg: '#28a745'},
    'hold': {text: '持有', bg: '#0d6efd'},
    'sell': {text: '卖出', bg: '#dc3545'},
    'watch': {text: '观望', bg: '#6c757d'},
};

static EVENT_MAP = {
    'spring': '弹簧效应',
    'shakeout': '震仓',
    'breakout': '突破',
    'utad': '上冲回落',
    'test': '测试',
    'sos': '强势信号',
    'lpsy': '最后供给点',
    'creek': '小溪',
};

static renderWyckoff(wyckoff) {
    const content = document.getElementById('sdWyckoffContent');

    if (!wyckoff) {
        content.innerHTML = '<div style="color:#aaa;font-size:0.8rem">暂无分析数据，点击"分析"开始</div>';
        document.getElementById('sdWkHistorySection').classList.add('d-none');
        return;
    }

    const phase = this.PHASE_MAP[wyckoff.phase] || {text: wyckoff.phase || '未知', bg: '#6c757d'};
    const advice = this.ADVICE_MAP[wyckoff.advice] || {text: wyckoff.advice || '--', bg: '#6c757d'};
    const events = wyckoff.events || [];

    let html = '<div class="sd-wk-result">';

    // 阶段 + 参考图图标 + 建议
    html += '<div class="sd-wk-result-header">';
    html += `<span class="sd-wk-phase-badge" style="background:${phase.bg}">${phase.text}</span>`;
    html += `<i class="bi bi-image sd-wk-ref-icon" title="查看参考图" onclick="StockDetailDrawer.showReference('${wyckoff.phase}')"></i>`;
    html += `<span class="sd-wk-advice-badge" style="background:${advice.bg}">${advice.text}</span>`;
    html += '</div>';

    // 事件标签
    if (events.length) {
        html += '<div class="sd-wk-events">';
        events.forEach(e => {
            const name = this.EVENT_MAP[e] || e;
            html += `<span class="sd-wk-event-tag">${name}</span>`;
        });
        html += '</div>';
    }

    // 支撑/阻力
    if (wyckoff.support_price || wyckoff.resistance_price) {
        html += '<div class="sd-wk-prices">';
        if (wyckoff.support_price) html += `<span>支撑: ${wyckoff.support_price.toFixed(2)}</span>`;
        if (wyckoff.resistance_price) html += `<span>阻力: ${wyckoff.resistance_price.toFixed(2)}</span>`;
        html += '</div>';
    }

    // 分析时间
    if (wyckoff.analysis_date) {
        html += `<div class="sd-wk-time">分析: ${wyckoff.analysis_date}</div>`;
    }

    html += '</div>';
    content.innerHTML = html;

    // 显示历史记录区域并加载
    document.getElementById('sdWkHistorySection').classList.remove('d-none');
    this.loadWyckoffHistory(this.currentCode);
}

static async runWyckoffAnalysis() {
    if (!this.currentCode) return;
    const btn = document.getElementById('sdWkAnalyzeBtn');
    const content = document.getElementById('sdWyckoffContent');

    btn.disabled = true;
    btn.textContent = '分析中...';

    try {
        const resp = await fetch(`/api/stock-detail/${encodeURIComponent(this.currentCode)}/wyckoff/analyze`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            signal: this.abortController?.signal
        });
        const result = await resp.json();
        if (result.error) throw new Error(result.error);
        if (result.status === 'failed') throw new Error(result.error_msg || '分析失败');

        if (this.currentCode) {
            this.renderWyckoff(result);
        }
    } catch (e) {
        if (e.name === 'AbortError') return;
        console.error('威科夫分析失败:', e);
        content.innerHTML = `<div style="color:#dc3545;font-size:0.8rem">分析失败: ${e.message}</div>`;
    } finally {
        btn.disabled = false;
        btn.textContent = '分析';
    }
}

static async runWyckoffBacktest() {
    if (!this.currentCode) return;
    const btn = document.getElementById('sdWkBacktestBtn');
    const container = document.getElementById('sdWkBacktestResult');

    btn.disabled = true;
    btn.textContent = '回测中...';
    container.classList.remove('d-none');
    container.innerHTML = '<div style="color:#888;font-size:0.8rem;text-align:center;padding:8px">回测中...</div>';

    try {
        const resp = await fetch(`/api/stock-detail/${encodeURIComponent(this.currentCode)}/wyckoff/backtest`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({days: 180}),
            signal: this.abortController?.signal
        });
        const data = await resp.json();
        if (data.error) throw new Error(data.error);

        this.renderBacktest(data);
    } catch (e) {
        if (e.name === 'AbortError') return;
        console.error('回测失败:', e);
        container.innerHTML = `<div style="color:#dc3545;font-size:0.8rem;padding:8px">回测失败: ${e.message}</div>`;
    } finally {
        btn.disabled = false;
        btn.textContent = '回测';
    }
}

static renderBacktest(data) {
    const container = document.getElementById('sdWkBacktestResult');
    const w = data.wyckoff || {};
    const s = data.signals || {};

    let html = '<div class="sd-wk-backtest">';
    html += '<div class="sd-wk-backtest-title">回测验证结果</div>';
    html += '<div class="sd-wk-backtest-grid">';

    // 威科夫阶段准确率
    if (w.accuracy) {
        for (const [days, acc] of Object.entries(w.accuracy)) {
            if (acc !== null) {
                html += `<div class="sd-wk-backtest-item"><span class="sd-wk-backtest-label">${days}日准确率</span><span class="sd-wk-backtest-value">${acc}%</span></div>`;
            }
        }
    }

    // 信号胜率
    if (s.buy && s.buy.win_rates) {
        const wr10 = s.buy.win_rates[10];
        if (wr10 !== undefined) {
            html += `<div class="sd-wk-backtest-item"><span class="sd-wk-backtest-label">买入信号胜率</span><span class="sd-wk-backtest-value">${wr10}%</span></div>`;
        }
    }
    if (s.sell && s.sell.win_rates) {
        const wr10 = s.sell.win_rates[10];
        if (wr10 !== undefined) {
            html += `<div class="sd-wk-backtest-item"><span class="sd-wk-backtest-label">卖出信号胜率</span><span class="sd-wk-backtest-value">${wr10}%</span></div>`;
        }
    }

    if (w.total === 0 && s.total === 0) {
        html += '<div class="sd-wk-backtest-item" style="grid-column:1/-1"><span class="sd-wk-backtest-label">暂无足够历史数据</span></div>';
    }

    html += '</div></div>';
    container.innerHTML = html;
}

static async loadWyckoffHistory(code) {
    const list = document.getElementById('sdWkHistoryList');

    try {
        const resp = await fetch(`/api/stock-detail/${encodeURIComponent(code)}/wyckoff/history`, {
            signal: this.abortController?.signal
        });
        const data = await resp.json();
        if (this.currentCode !== code) return;

        const history = data.history || [];
        if (history.length === 0) {
            document.getElementById('sdWkHistorySection').classList.add('d-none');
            return;
        }

        list.innerHTML = history.slice(0, 10).map(item => {
            const phase = this.PHASE_MAP[item.phase] || {text: item.phase, bg: '#6c757d'};
            const advice = this.ADVICE_MAP[item.advice] || {text: item.advice, bg: '#6c757d'};
            return `<div class="sd-wk-history-item">
                <span class="sd-wk-history-date">${item.analysis_date}</span>
                <span class="sd-wk-phase-badge" style="background:${phase.bg};font-size:0.7rem;padding:1px 6px">${phase.text}</span>
                <span class="sd-wk-advice-badge" style="background:${advice.bg};font-size:0.65rem;padding:1px 6px">${advice.text}</span>
            </div>`;
        }).join('');
    } catch (e) {
        if (e.name === 'AbortError') return;
        console.error('加载威科夫历史失败:', e);
    }
}

static toggleWyckoffHistory() {
    const list = document.getElementById('sdWkHistoryList');
    const icon = document.querySelector('.sd-wk-toggle-icon');
    list.classList.toggle('d-none');
    icon?.classList.toggle('open');
}

static async showReference(phase) {
    if (!this.currentCode) return;

    try {
        const resp = await fetch(`/api/stock-detail/${encodeURIComponent(this.currentCode)}/wyckoff/reference/${phase}`);
        const data = await resp.json();

        if (!data.found) {
            alert('暂无该阶段的参考图');
            return;
        }

        // 简单弹窗显示参考图
        const modal = document.createElement('div');
        modal.style.cssText = 'position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.7);z-index:1100;display:flex;align-items:center;justify-content:center;cursor:pointer';
        modal.onclick = () => modal.remove();

        const img = document.createElement('img');
        img.src = `/api/stock-detail/${encodeURIComponent(this.currentCode)}/wyckoff/image/${encodeURIComponent(data.image_path)}`;
        img.style.cssText = 'max-width:90%;max-height:90%;border-radius:8px;box-shadow:0 4px 24px rgba(0,0,0,0.3)';
        modal.appendChild(img);

        document.body.appendChild(modal);
    } catch (e) {
        console.error('加载参考图失败:', e);
    }
}
```

**Step 2: 验证无语法错误**

在浏览器中打开页面，检查控制台无 JavaScript 错误。

**Step 3: Commit**

```bash
git add app/static/js/stock-detail.js
git commit -m "feat: 添加威科夫分析交互逻辑到详情抽屉JS"
```

---

### Task 5: 添加参考图 serve 路由

**Files:**
- Modify: `app/routes/stock_detail.py`

**Step 1: 添加图片访问路由**

在 stock_detail.py 的末尾添加：

```python
@stock_detail_bp.route('/<code>/wyckoff/image/<path:filepath>')
def wyckoff_image(code, filepath):
    """参考图文件访问"""
    from flask import send_file
    import os
    if not os.path.exists(filepath):
        return jsonify({'error': '文件不存在'}), 404
    return send_file(filepath)
```

**Step 2: Commit**

```bash
git add app/routes/stock_detail.py
git commit -m "feat: 添加威科夫参考图serve路由"
```

---

### Task 6: 移除威科夫独立页面

**Files:**
- Delete: `app/routes/wyckoff.py`
- Delete: `app/templates/wyckoff_auto.html`
- Delete: `app/templates/wyckoff_reference.html`
- Delete: `app/templates/wyckoff_analysis.html`
- Delete: `app/static/js/wyckoff.js`
- Delete: `app/static/css/wyckoff.css`
- Modify: `app/routes/__init__.py` — 移除 `wyckoff_bp` 定义和 `wyckoff` import
- Modify: `app/__init__.py` — 移除 `wyckoff_bp` 的 import 和 `register_blueprint`
- Modify: `app/templates/base.html` — 移除导航栏中的"威科夫分析"链接

**Step 1: 删除文件**

```bash
cd D:/Git/stock
rm app/routes/wyckoff.py
rm app/templates/wyckoff_auto.html
rm app/templates/wyckoff_reference.html
rm app/templates/wyckoff_analysis.html
rm app/static/js/wyckoff.js
rm app/static/css/wyckoff.css
```

**Step 2: 修改 `app/routes/__init__.py`**

移除行:
```python
wyckoff_bp = Blueprint('wyckoff', __name__, url_prefix='/wyckoff')
```

从末尾 import 行中移除 `wyckoff`：
```python
from app.routes import main, position, advice, category, trade, stock, daily_record, profit, rebalance, heavy_metals, preload, alert, briefing, strategy, stock_detail
```

**Step 3: 修改 `app/__init__.py`**

从 import 行中移除 `wyckoff_bp`：
```python
from app.routes import main_bp, position_bp, advice_bp, category_bp, trade_bp, stock_bp, daily_record_bp, profit_bp, rebalance_bp, heavy_metals_bp, preload_bp, alert_bp, briefing_bp, strategy_bp, stock_detail_bp
```

移除：
```python
app.register_blueprint(wyckoff_bp)
```

**Step 4: 修改 `app/templates/base.html`**

移除第27行：
```html
<a class="nav-link" href="{{ url_for('wyckoff.auto_index') }}">威科夫分析</a>
```

**Step 5: 验证启动**

Run: `cd D:/Git/stock && python -c "from app import create_app; app = create_app(); print('OK')"`
Expected: OK

**Step 6: Commit**

```bash
git add -A
git commit -m "refactor: 移除威科夫独立页面，功能已合并到股票详情抽屉"
```

---

### Task 7: 清理旧 CSS 中 wyckoff 样式

**Files:**
- Modify: `app/static/css/stock-detail.css`

**Step 1: 移除旧的 `.sd-wyckoff` 相关样式**

删除 stock-detail.css 中以下样式块（已被 Task 3 的新样式取代）：

```css
/* 威科夫分析 */
.sd-wyckoff { ... }
.sd-wyckoff-phase { ... }
.sd-wyckoff-advice { ... }
.sd-wyckoff-prices { ... }
```

**Step 2: Commit**

```bash
git add app/static/css/stock-detail.css
git commit -m "cleanup: 移除旧的威科夫内联样式"
```

---

### Task 8: 端到端验证

**Step 1: 启动应用**

```bash
cd D:/Git/stock && python run.py
```

**Step 2: 手动验证**

1. 打开 http://127.0.0.1:5000
2. 确认导航栏没有"威科夫分析"链接
3. 点击任意股票打开详情抽屉
4. 确认技术分析区下方有"威科夫量价分析"区块
5. 点击"分析"按钮，观察 loading 状态和结果渲染
6. 点击"回测"按钮，确认回测结果折叠展示
7. 确认历史记录列表显示和折叠正常
8. 访问 /wyckoff/auto 确认返回 404

**Step 3: 最终 commit（如有修复）**
