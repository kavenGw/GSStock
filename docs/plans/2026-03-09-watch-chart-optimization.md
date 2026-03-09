# 盯盘走势图优化 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 优化盯盘走势图坐标轴可读性、增强AI分析输出并以侧边栏展示、将首页操作建议整合到盯盘页面。

**Architecture:** 走势图布局从全宽改为 70/30 分栏（图表+AI侧边栏）。AI分析Prompt增强输出（信号+均线+价位区间），存储到 WatchAnalysis 新增字段。从 portfolio_advice.py 提取支撑/压力算法到独立工具函数供盯盘复用，然后删除首页操作建议模块。

**Tech Stack:** ECharts 5, Flask, SQLAlchemy, 智谱GLM

---

### Task 1: 走势图坐标轴优化

**Files:**
- Modify: `app/static/js/watch.js:683-712` (renderChart 的 chart.setOption)

**Step 1: 修改 ECharts grid 和 yAxis 配置**

在 `renderChart()` 方法中，将 grid 和 yAxis 配置改为：

```javascript
grid: { left: 10, right: 60, top: 8, bottom: 20, containLabel: true },
// ...
yAxis: {
    type: 'value',
    scale: true,
    splitLine: { lineStyle: { color: '#f0f0f0' } },
    axisLabel: {
        fontSize: 9,
        formatter: value => {
            if (value >= 10000) return (value / 10000).toFixed(1) + '万';
            if (value >= 1000) return value.toFixed(0);
            return value.toFixed(2);
        },
    },
},
```

**Step 2: 修改 xAxis 配置为半小时间隔**

```javascript
xAxis: {
    type: 'category',
    data: fullAxis,
    boundaryGap: false,
    axisLabel: {
        fontSize: 9,
        formatter: value => {
            const m = value.split(':')[1];
            return (m === '00' || m === '30') ? value : '';
        },
        interval: 0,
        showMinLabel: true,
        showMaxLabel: true,
    },
    axisTick: {
        alignWithLabel: true,
        interval: idx => {
            const t = fullAxis[idx];
            if (!t) return false;
            const m = t.split(':')[1];
            return m === '00' || m === '30';
        },
    },
    axisLine: { lineStyle: { color: '#ddd' } },
},
```

**Step 3: 同步更新 setOption 增量更新路径**

`renderChart()` 中已存在的 chart 增量更新（line 623-631）同样需确认 xAxis data 传入后轴标签不被覆盖——当前代码已传 `xAxis: { data: fullAxis }`，无需修改。

**Step 4: 验证**

启动 `python run.py`，打开盯盘页面确认：
- Y轴显示价格标签
- X轴仅在 :00 和 :30 显示时间标签

**Step 5: Commit**

```bash
git add app/static/js/watch.js
git commit -m "feat: 盯盘走势图坐标轴优化 — Y轴显示价格、X轴半小时间隔"
```

---

### Task 2: 提取支撑/压力算法到工具函数

**Files:**
- Create: `app/utils/support_resistance.py`
- Reference: `app/services/portfolio_advice.py:120-300` (提取逻辑)

**Step 1: 创建 `app/utils/support_resistance.py`**

从 `PortfolioAdviceService._calculate_moving_averages`、`_calculate_price_zones`、`_find_price_clusters` 提取核心算法：

```python
"""支撑/压力位计算工具"""
from statistics import mean


def calculate_moving_averages(closes: list) -> dict:
    result = {'ma5': None, 'ma10': None, 'ma20': None, 'ma60': None, 'trend': '数据不足'}
    if len(closes) < 5:
        return result

    ma5 = mean(closes[-5:])
    result['ma5'] = round(ma5, 2)

    if len(closes) >= 10:
        result['ma10'] = round(mean(closes[-10:]), 2)

    if len(closes) >= 20:
        ma20 = mean(closes[-20:])
        result['ma20'] = round(ma20, 2)

    if len(closes) >= 60:
        ma60 = mean(closes[-60:])
        result['ma60'] = round(ma60, 2)
        if ma5 > ma20 > ma60:
            result['trend'] = '多头排列'
        elif ma5 < ma20 < ma60:
            result['trend'] = '空头排列'
        elif ma5 > ma20 and ma20 < ma60:
            result['trend'] = '底部反转'
        elif ma5 < ma20 and ma20 > ma60:
            result['trend'] = '顶部回落'
        else:
            result['trend'] = '震荡整理'
    elif len(closes) >= 20:
        if ma5 > ma20:
            result['trend'] = '短期多头'
        else:
            result['trend'] = '短期空头'

    return result


def calculate_support_resistance(highs: list, lows: list, closes: list) -> dict:
    """计算支撑位和压力位

    Returns:
        {'support': [价格列表], 'resistance': [价格列表]}
    """
    if len(closes) < 20:
        return {'support': [], 'resistance': []}

    current_price = closes[-1]
    ma_info = calculate_moving_averages(closes)

    support_levels = []
    resistance_levels = []

    # 近20日最低/最高点
    recent_low = min(lows[-20:])
    recent_high = max(highs[-20:])
    support_levels.append((recent_low, 3))
    resistance_levels.append((recent_high, 3))

    # 均线支撑/压力
    for key, strength in [('ma20', 4), ('ma60', 5)]:
        val = ma_info.get(key)
        if val:
            if val < current_price:
                support_levels.append((val, strength))
            else:
                resistance_levels.append((val, strength))

    # 密集成交区
    price_min, price_max = min(closes[-20:]), max(closes[-20:])
    price_range = price_max - price_min
    if price_range > 0:
        bins = 10
        bin_size = price_range / bins
        counts = [0] * bins
        bin_prices = [0.0] * bins
        for p in closes[-20:]:
            idx = min(int((p - price_min) / bin_size), bins - 1)
            counts[idx] += 1
            bin_prices[idx] += p
        avg_count = len(closes[-20:]) / bins
        for i, count in enumerate(counts):
            if count > avg_count * 1.5:
                cluster_price = round(bin_prices[i] / count, 2)
                if abs(cluster_price - current_price) / current_price > 0.01:
                    if cluster_price < current_price:
                        support_levels.append((cluster_price, min(int(count / avg_count), 5)))
                    else:
                        resistance_levels.append((cluster_price, min(int(count / avg_count), 5)))

    # 按强度排序，取前3，只返回价格
    support_levels.sort(key=lambda x: x[1], reverse=True)
    resistance_levels.sort(key=lambda x: x[1], reverse=True)

    return {
        'support': [round(s[0], 2) for s in support_levels[:3]],
        'resistance': [round(r[0], 2) for r in resistance_levels[:3]],
    }
```

**Step 2: Commit**

```bash
git add app/utils/support_resistance.py
git commit -m "feat: 提取支撑/压力算法到 utils/support_resistance.py"
```

---

### Task 3: WatchAnalysis 模型扩展 + Service 更新

**Files:**
- Modify: `app/models/watch_list.py:16-30` (WatchAnalysis 模型)
- Modify: `app/services/watch_service.py:92-139` (save/read 方法)

**Step 1: 给 WatchAnalysis 增加字段**

```python
class WatchAnalysis(db.Model):
    # ... 现有字段保持不变 ...
    signal = db.Column(db.String(10))  # buy/sell/hold/watch
    analysis_detail = db.Column(db.Text)  # JSON: {ma_levels, price_range, signal_text}
```

**Step 2: 更新 save_analysis 方法签名和逻辑**

在 `watch_service.py` 中 `save_analysis` 增加 `signal` 和 `detail` 参数：

```python
@staticmethod
def save_analysis(stock_code: str, period: str, support_levels: list,
                  resistance_levels: list, summary: str,
                  signal: str = '', detail: dict = None):
    today = date.today()
    detail_json = json.dumps(detail, ensure_ascii=False) if detail else None
    existing = WatchAnalysis.query.filter_by(
        stock_code=stock_code, analysis_date=today, period=period
    ).first()
    if existing:
        existing.support_levels = json.dumps(support_levels)
        existing.resistance_levels = json.dumps(resistance_levels)
        existing.analysis_summary = summary
        existing.signal = signal
        existing.analysis_detail = detail_json
        db.session.commit()
        return
    try:
        analysis = WatchAnalysis(
            stock_code=stock_code, analysis_date=today, period=period,
            support_levels=json.dumps(support_levels),
            resistance_levels=json.dumps(resistance_levels),
            analysis_summary=summary,
            signal=signal,
            analysis_detail=detail_json,
        )
        db.session.add(analysis)
        db.session.commit()
    except Exception:
        db.session.rollback()
        existing = WatchAnalysis.query.filter_by(
            stock_code=stock_code, analysis_date=today, period=period
        ).first()
        if existing:
            existing.support_levels = json.dumps(support_levels)
            existing.resistance_levels = json.dumps(resistance_levels)
            existing.analysis_summary = summary
            existing.signal = signal
            existing.analysis_detail = detail_json
            db.session.commit()
```

**Step 3: 更新读取方法返回新字段**

在 `get_today_analysis` 和 `get_all_today_analyses` 返回字典中增加 `signal` 和 `detail`：

```python
# 每个 period 的返回结构改为：
{
    'support_levels': [...],
    'resistance_levels': [...],
    'summary': '...',
    'signal': 'buy',
    'detail': { 'ma_levels': {...}, 'price_range': {...}, 'signal_text': '买入' },
    'created_at': '09:30',
}
```

**Step 4: 数据库迁移**

```bash
python -c "
from app import create_app, db
app = create_app()
with app.app_context():
    from sqlalchemy import text, inspect
    insp = inspect(db.engine)
    cols = [c['name'] for c in insp.get_columns('watch_analysis')]
    with db.engine.connect() as conn:
        if 'signal' not in cols:
            conn.execute(text('ALTER TABLE watch_analysis ADD COLUMN signal VARCHAR(10)'))
        if 'analysis_detail' not in cols:
            conn.execute(text('ALTER TABLE watch_analysis ADD COLUMN analysis_detail TEXT'))
        conn.commit()
    print('Migration done')
"
```

**Step 5: Commit**

```bash
git add app/models/watch_list.py app/services/watch_service.py
git commit -m "feat: WatchAnalysis 模型增加 signal/analysis_detail 字段"
```

---

### Task 4: AI 分析 Prompt 增强

**Files:**
- Modify: `app/llm/prompts/watch_analysis.py` (三个 prompt 函数)
- Modify: `app/routes/watch.py:81-173` (analyze 端点，传入60日数据，保存新字段)

**Step 1: 重写 `build_realtime_analysis_prompt`**

增加60日OHLC数据输入，输出扩展为信号+均线+价位区间：

```python
def build_realtime_analysis_prompt(stock_name: str, stock_code: str,
                                    intraday_data: list, current_price: float,
                                    ohlc_60d: list = None) -> str:
    data_lines = []
    for d in intraday_data[-60:]:
        data_lines.append(f"{d.get('time', '')}: {d.get('close', '')}")
    data_text = "\n".join(data_lines)

    ohlc_text = ""
    if ohlc_60d:
        ohlc_lines = []
        for d in ohlc_60d[-10:]:
            ohlc_lines.append(f"{d['date']}: O={d['open']} H={d['high']} L={d['low']} C={d['close']}")
        ohlc_text = f"\n\n近10日K线：\n" + "\n".join(ohlc_lines)

    return f"""分析 {stock_name}({stock_code}) 的当日走势，当前价格 {current_price}。

今日分时数据（最近60个点）：
{data_text}{ohlc_text}

请返回JSON（不要markdown代码块包裹）：
{{
  "support_levels": [支撑位1, 支撑位2],
  "resistance_levels": [阻力位1, 阻力位2],
  "signal": "buy或sell或hold或watch",
  "signal_text": "买入或卖出或持有或观望",
  "summary": "80字以内的走势解读和操作建议",
  "ma_levels": {{"ma5": 数值, "ma20": 数值, "ma60": 数值}},
  "price_range": {{"low": 建议买入下限, "high": 建议卖出上限}}
}}"""
```

**Step 2: 同样增强 `build_7d_analysis_prompt` 和 `build_30d_analysis_prompt`**

两者输出格式统一为与 realtime 相同的 JSON 结构（加 signal、ma_levels、price_range）。7d summary 改为80字，30d 保持100字。

**Step 3: 修改 analyze 端点**

在 `watch.py` analyze 路由中：
- 额外获取60日OHLC数据（所有period都获取，用于传给 prompt 和算法支撑/压力）
- 将60日数据传给 realtime prompt
- 解析 LLM 返回的新字段（signal, ma_levels, price_range）
- 调用 `WatchService.save_analysis` 时传入 signal 和 detail

```python
# 在 codes 获取后，统一获取60日OHLC
trend_60d = unified_stock_data_service.get_trend_data(codes, days=60)
trend_60d_map = {s['stock_code']: s for s in trend_60d.get('stocks', [])}

# ... 循环内 ...
ohlc_60d = trend_60d_map.get(code, {}).get('data', [])

if period == 'realtime':
    prompt = build_realtime_analysis_prompt(stock_name, code, intraday_data, current_price, ohlc_60d)

# 解析后保存：
WatchService.save_analysis(
    stock_code=code, period=period,
    support_levels=parsed.get('support_levels', []),
    resistance_levels=parsed.get('resistance_levels', []),
    summary=parsed.get('summary', ''),
    signal=parsed.get('signal', ''),
    detail={
        'signal_text': parsed.get('signal_text', ''),
        'ma_levels': parsed.get('ma_levels', {}),
        'price_range': parsed.get('price_range', {}),
    },
)
```

**Step 4: Commit**

```bash
git add app/llm/prompts/watch_analysis.py app/routes/watch.py
git commit -m "feat: AI分析Prompt增强 — 输出操作信号+均线+建议价位区间"
```

---

### Task 5: 走势图布局改造 — 图表+AI侧边栏

**Files:**
- Modify: `app/templates/watch.html:6-15` (新增侧边栏CSS)
- Modify: `app/static/js/watch.js:463-514` (renderStockCard 加侧边栏结构)
- Modify: `app/static/js/watch.js:717-756` (renderAnalysisContent 改为侧边栏格式)

**Step 1: 在 watch.html 增加侧边栏样式**

在 `<style>` 块中新增：

```css
.chart-analysis-row {
    display: flex;
    gap: 0;
}
.chart-analysis-row .chart-side {
    flex: 7;
    min-width: 0;
}
.chart-analysis-row .analysis-sidebar {
    flex: 3;
    border-left: 1px solid #eee;
    max-height: 230px;
    overflow-y: auto;
    padding: 0.5rem;
    background: #fafbfc;
}
.analysis-sidebar .analysis-entry {
    padding: 0.4rem 0;
    border-bottom: 1px solid #f0f0f0;
    font-size: 0.78rem;
}
.analysis-sidebar .analysis-entry:last-child {
    border-bottom: none;
}
.analysis-entry .entry-time {
    font-size: 0.7rem;
    color: #999;
    margin-right: 0.3rem;
}
.analysis-entry .entry-signal {
    display: inline-block;
    padding: 0 0.4rem;
    border-radius: 3px;
    font-size: 0.7rem;
    font-weight: 600;
}
.entry-signal.signal-buy { background: #dcfce7; color: #16a34a; }
.entry-signal.signal-sell { background: #fef2f2; color: #dc2626; }
.entry-signal.signal-hold { background: #fef9c3; color: #ca8a04; }
.entry-signal.signal-watch { background: #f3f4f6; color: #6b7280; }
.analysis-entry .entry-summary {
    margin-top: 0.2rem;
    color: #374151;
    line-height: 1.4;
}
.analysis-entry .entry-detail {
    margin-top: 0.15rem;
    font-size: 0.72rem;
    color: #6b7280;
}
```

**Step 2: 修改 renderStockCard 布局**

将现有的 chart-container 和 analysis-section 改为横向排列：

```javascript
// 替换 renderStockCard 中 chart-container 和 analysis-section 部分
// 原来:
//   <div class="chart-container" id="chart-${code}">...</div>
//   <div class="analysis-section" id="analysis-${code}">...</div>
// 改为:
`<div class="chart-analysis-row">
    <div class="chart-side">
        <div class="chart-container" id="chart-${code}">
            <div class="skeleton skeleton-card" style="height:100%;"></div>
        </div>
    </div>
    <div class="analysis-sidebar" id="analysis-sidebar-${code}">
        <div class="text-muted small text-center py-3">等待AI分析...</div>
    </div>
</div>
<div class="analysis-section" id="analysis-${code}">
    <ul class="nav nav-tabs analysis-tab mb-2" role="tablist">
        <!-- 保持 realtime/7d/30d tab 不变 -->
    </ul>
    <div class="analysis-content" id="analysis-content-${code}">
        <span class="text-muted small">点击「AI 分析」获取分析结果</span>
    </div>
</div>`
```

**Step 3: 新增 renderAnalysisSidebar 方法**

渲染右侧侧边栏的AI分析历史记录：

```javascript
renderAnalysisSidebar(code) {
    const sidebar = document.getElementById(`analysis-sidebar-${code}`);
    if (!sidebar) return;

    const codeAnalysis = this.analyses[code] || {};
    const realtimeData = codeAnalysis['realtime'];

    if (!realtimeData) {
        sidebar.innerHTML = '<div class="text-muted small text-center py-3">等待AI分析...</div>';
        return;
    }

    const signal = realtimeData.signal || 'watch';
    const signalText = realtimeData.detail?.signal_text || '观望';
    const summary = realtimeData.summary || '';
    const detail = realtimeData.detail || {};
    const maLevels = detail.ma_levels || {};
    const priceRange = detail.price_range || {};
    const createdAt = realtimeData.created_at || '';

    let detailHtml = '';
    if (maLevels.ma5 || maLevels.ma20 || maLevels.ma60) {
        const parts = [];
        if (maLevels.ma5) parts.push(`MA5:${maLevels.ma5}`);
        if (maLevels.ma20) parts.push(`MA20:${maLevels.ma20}`);
        if (maLevels.ma60) parts.push(`MA60:${maLevels.ma60}`);
        detailHtml += `<div class="entry-detail">${parts.join(' ')}</div>`;
    }
    if (priceRange.low || priceRange.high) {
        detailHtml += `<div class="entry-detail">建议区间: ${priceRange.low || '?'} - ${priceRange.high || '?'}</div>`;
    }

    // 实时分析条目
    let html = `<div class="analysis-entry">
        <span class="entry-time">${createdAt}</span>
        <span class="entry-signal signal-${signal}">${signalText}</span>
        <div class="entry-summary">${summary}</div>
        ${detailHtml}
    </div>`;

    // 7d/30d 分析也展示（如有）
    for (const p of ['7d', '30d']) {
        const pData = codeAnalysis[p];
        if (!pData) continue;
        const pSignal = pData.signal || 'watch';
        const pSignalText = pData.detail?.signal_text || (p === '7d' ? '7日' : '30日');
        html += `<div class="analysis-entry">
            <span class="entry-time">${p}</span>
            <span class="entry-signal signal-${pSignal}">${pSignalText}</span>
            <div class="entry-summary">${pData.summary || ''}</div>
        </div>`;
    }

    sidebar.innerHTML = html;
},
```

**Step 4: 在 updateAllAnalysisPanels 中调用 renderAnalysisSidebar**

```javascript
updateAllAnalysisPanels() {
    this.stocks.forEach(stock => {
        const code = stock.stock_code;
        this.renderAnalysisSidebar(code);
        // 保留现有 tab 内容更新
        const section = document.getElementById(`analysis-${code}`);
        if (!section) return;
        const activeBtn = section.querySelector('.nav-link.active');
        const activePeriod = activeBtn ? activeBtn.dataset.period : 'realtime';
        this.renderAnalysisContent(code, activePeriod);
    });
},
```

**Step 5: 更新 renderAnalysisContent 显示新字段**

在现有的 `renderAnalysisContent` 中增加 signal 和 detail 显示：

```javascript
renderAnalysisContent(code, period) {
    const el = document.getElementById(`analysis-content-${code}`);
    if (!el) return;

    const codeAnalysis = this.analyses[code] || {};
    const periodData = codeAnalysis[period];

    if (!periodData) {
        el.innerHTML = '<span class="text-muted small">暂无分析数据</span>';
        return;
    }

    const supports = periodData.support_levels || [];
    const resistances = periodData.resistance_levels || [];
    const summary = periodData.summary || '';
    const signal = periodData.signal || '';
    const detail = periodData.detail || {};

    let html = '';
    if (signal) {
        const signalText = detail.signal_text || signal;
        html += `<span class="entry-signal signal-${signal} me-2">${signalText}</span>`;
    }
    if (summary) html += `<span class="small">${summary}</span>`;
    html += '<div class="mt-1">';
    if (supports.length > 0) html += `<span class="text-success small me-2">支撑: ${supports.join(' / ')}</span>`;
    if (resistances.length > 0) html += `<span class="text-danger small">阻力: ${resistances.join(' / ')}</span>`;
    html += '</div>';
    el.innerHTML = html || '<span class="text-muted small">暂无分析数据</span>';
},
```

**Step 6: Commit**

```bash
git add app/templates/watch.html app/static/js/watch.js
git commit -m "feat: 盯盘走势图布局改造 — 70/30分栏+AI分析侧边栏"
```

---

### Task 6: 移除首页操作建议模块

**Files:**
- Modify: `app/templates/index.html:162-177, 215-456` (删除 advice 模块和 AdviceManager)
- Modify: `app/routes/main.py:8, 139-170` (删除 import 和 API 端点)
- Modify: `app/static/css/index.css:267-376+` (删除 advice 相关 CSS)
- Delete: `app/services/portfolio_advice.py`

**Step 1: 删除 index.html 中的操作建议模块**

删除 `<!-- 模块5: 持仓操作建议 -->` 整个 div（line 162-177）。

删除 `<script>` 中的 AdviceManager 对象定义（line 215-456 中的 AdviceManager 及其调用 `AdviceManager.loadAdvice()`）。

**Step 2: 删除 main.py 中的 API 端点**

删除 `from app.services.portfolio_advice import PortfolioAdviceBatchService` import。

删除 `@main_bp.route('/api/portfolio-advice')` 整个函数（line 139-170）。

**Step 3: 删除 index.css 中的 advice 样式**

删除 `/* ========== 持仓操作建议模块 ========== */` 下方所有 advice 相关 CSS（约 line 267-376，以及 line 530-571 中的 advice 响应式样式）。

**Step 4: 删除 portfolio_advice.py**

```bash
rm app/services/portfolio_advice.py
```

**Step 5: Commit**

```bash
git add -u app/services/portfolio_advice.py app/templates/index.html app/routes/main.py app/static/css/index.css
git commit -m "feat: 移除首页持仓操作建议模块，功能已整合到盯盘页面"
```

---

### Task 7: 盯盘走势图整合算法支撑/压力线

**Files:**
- Modify: `app/routes/watch.py:267-373` (chart-data 端点，用算法计算支撑/压力)

**Step 1: 在 chart-data 端点中使用算法支撑/压力**

修改 `chart_data()` 路由，当 period 为 intraday 时，额外获取60日OHLC用算法计算支撑/压力：

```python
# 在 chart-data 路由中，替换现有的 analysis_data 读取逻辑：
from app.utils.support_resistance import calculate_support_resistance

# 算法支撑/压力（60日OHLC）
algo_sr = {'support': [], 'resistance': []}
try:
    trend_60d = unified_stock_data_service.get_trend_data([code], days=60)
    stocks_60d = trend_60d.get('stocks', [])
    if stocks_60d and stocks_60d[0].get('data') and len(stocks_60d[0]['data']) >= 20:
        ohlc = stocks_60d[0]['data']
        highs = [d['high'] for d in ohlc]
        lows = [d['low'] for d in ohlc]
        closes = [d['close'] for d in ohlc]
        algo_sr = calculate_support_resistance(highs, lows, closes)
except Exception as e:
    logger.debug(f"[盯盘] 算法支撑/压力计算失败 {code}: {e}")

# AI分析的支撑/压力
analysis_data = WatchService.get_today_analysis(code)
ai_supports = []
ai_resistances = []
if analysis_data and isinstance(analysis_data, dict):
    for p_data in analysis_data.values():
        if isinstance(p_data, dict):
            ai_supports.extend(p_data.get('support_levels', []))
            ai_resistances.extend(p_data.get('resistance_levels', []))

# 合并去重
result['support_levels'] = sorted(set(algo_sr['support'] + ai_supports))
result['resistance_levels'] = sorted(set(algo_sr['resistance'] + ai_resistances))
```

**Step 2: Commit**

```bash
git add app/routes/watch.py
git commit -m "feat: 盯盘走势图整合算法+AI双重支撑/压力线"
```

---

### 执行顺序

Task 1 → Task 2 → Task 3 → Task 4 → Task 5 → Task 6 → Task 7

依赖关系：
- Task 3 依赖 Task 2（model 字段）
- Task 4 依赖 Task 3（新字段读写）
- Task 5 依赖 Task 4（侧边栏需要新字段数据）
- Task 7 依赖 Task 2（算法工具函数）
- Task 1 和 Task 6 相互独立
