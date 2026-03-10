# 九转信号分钟级走势 实施计划

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在盯盘助手分时图上标注1分钟级TD Sequential信号（1-9数字）

**Architecture:** 复用现有 `TDSequentialService.calculate()` 对分时OHLC数据计算，后端返回 `td_sequential_intraday` 字段，前端用 ECharts markPoint 渲染数字标注

**Tech Stack:** Python (Flask) / JavaScript (ECharts markPoint)

---

### Task 1: TDSequentialService 支持时间字段和价格

**Files:**
- Modify: `app/services/td_sequential.py`

- [ ] **Step 1: 修改 calculate() 方法**

当前 history 条目只记录 `date`。需要：
1. 同时提取 `time` 字段（分钟级数据用 `time`，日线用 `date`）
2. history 条目增加 `price` 字段（当前 close 价）

```python
@staticmethod
def calculate(ohlc_data: list) -> dict:
    if not ohlc_data or len(ohlc_data) < 5:
        return {'direction': None, 'count': 0, 'completed': False, 'history': []}

    closes = []
    time_keys = []
    for d in ohlc_data:
        close = d.get('close') or d.get('price') or 0
        if close <= 0:
            continue
        closes.append(close)
        time_keys.append(d.get('time') or d.get('date', ''))

    if len(closes) < 5:
        return {'direction': None, 'count': 0, 'completed': False, 'history': []}

    history = []
    buy_count = 0
    sell_count = 0

    for i in range(4, len(closes)):
        compare = closes[i - 4]

        if closes[i] < compare:
            buy_count += 1
            sell_count = 0
            direction = 'buy'
            count = buy_count
        elif closes[i] > compare:
            sell_count += 1
            buy_count = 0
            direction = 'sell'
            count = sell_count
        else:
            buy_count = 0
            sell_count = 0
            direction = None
            count = 0

        if count > 0:
            entry = {
                'direction': direction,
                'count': min(count, 9),
                'price': closes[i],
            }
            # 分钟级用 time，日线用 date
            tk = time_keys[i]
            if ':' in str(tk):
                entry['time'] = tk
            else:
                entry['date'] = tk
            history.append(entry)

        if buy_count >= 9:
            buy_count = 0
        if sell_count >= 9:
            sell_count = 0

    current_direction = None
    current_count = 0
    completed = False

    if history:
        last = history[-1]
        current_direction = last['direction']
        current_count = last['count']
        completed = current_count == 9

    return {
        'direction': current_direction,
        'count': current_count,
        'completed': completed,
        'history': history[-20:],
    }
```

- [ ] **Step 2: 验证**

启动应用，访问盯盘页面确认日线TD信号仍正常显示。

---

### Task 2: chart-data 接口返回分钟级TD信号

**Files:**
- Modify: `app/routes/watch.py`

- [ ] **Step 1: 在 period=intraday 分支中计算分钟级TD信号**

在 `chart_data()` 函数的 `if period == 'intraday':` 分支末尾（`result['prev_close'] = prev_close` 之后），添加分钟级TD计算：

```python
# 分钟级九转信号
from app.services.td_sequential import TDSequentialService
td_intraday = {'direction': None, 'count': 0, 'completed': False, 'history': []}
try:
    intraday_ohlc = stock_data.get('data', [])
    if len(intraday_ohlc) >= 5:
        td_intraday = TDSequentialService.calculate(intraday_ohlc)
except Exception as e:
    logger.debug(f"[盯盘] 分钟级九转信号计算失败 {code}: {e}")
result['td_sequential_intraday'] = td_intraday
```

注意：`all_data` 可能被 `last_timestamp` 过滤了，需要用完整的 `stock_data.get('data', [])` 计算。

- [ ] **Step 2: 验证**

请求 `/watch/chart-data?code=600519&period=intraday`，确认响应包含 `td_sequential_intraday` 字段。

---

### Task 3: 前端 markPoint 渲染分钟级TD信号

**Files:**
- Modify: `app/static/js/watch.js`

- [ ] **Step 1: loadChartData 中存储分钟级TD数据**

在 `loadChartData()` 方法中（约 line 205-207），增加对 `td_sequential_intraday` 的存储：

```javascript
if (result.td_sequential) {
    this.tdSequential[code] = result.td_sequential;
}
// 新增
if (result.td_sequential_intraday) {
    this.tdSequentialIntraday = this.tdSequentialIntraday || {};
    this.tdSequentialIntraday[code] = result.td_sequential_intraday;
}
```

- [ ] **Step 2: Watch 对象添加 tdSequentialIntraday 属性**

在 Watch 对象的属性声明中（约 line 80）添加：

```javascript
tdSequentialIntraday: {},
```

- [ ] **Step 3: WatchCache 快照和恢复**

`snapshot()` 中添加：
```javascript
tdSequentialIntraday: watch.tdSequentialIntraday,
```

`restore()` 中添加：
```javascript
watch.tdSequentialIntraday = cache.tdSequentialIntraday || {};
```

- [ ] **Step 4: renderChart 中添加 markPoint**

在 `renderChart()` 方法中，构建 `seriesList` 的第一个 series（主分时线）时，添加 `markPoint` 配置。

在 `const seriesList = [{...}]` 构建之前，准备 markPoint 数据：

```javascript
// 分钟级TD信号 markPoint
const tdIntraday = (this.tdSequentialIntraday || {})[code] || {};
const tdHistory = tdIntraday.history || [];
const tdMarkData = [];
if (tdHistory.length > 0 && fullAxis.length > 0) {
    for (const h of tdHistory) {
        const idx = fullAxis.indexOf(h.time);
        if (idx === -1) continue;
        const isBuy = h.direction === 'buy';
        tdMarkData.push({
            coord: [idx, h.price],
            value: h.count,
            symbol: h.count === 9 ? 'circle' : 'none',
            symbolSize: h.count === 9 ? 16 : 1,
            itemStyle: h.count === 9 ? {
                color: isBuy ? 'rgba(22,163,74,0.2)' : 'rgba(220,38,38,0.2)',
                borderColor: isBuy ? '#16a34a' : '#dc2626',
                borderWidth: 1,
            } : undefined,
            label: {
                show: true,
                formatter: String(h.count),
                position: isBuy ? 'bottom' : 'top',
                color: isBuy ? '#16a34a' : '#dc2626',
                fontSize: 11,
                fontWeight: h.count >= 7 ? 'bold' : 'normal',
                offset: isBuy ? [0, 4] : [0, -4],
            },
        });
    }
}
```

然后在主 series 中加入 markPoint：

```javascript
const seriesList = [{
    type: 'line',
    data: prices,
    smooth: true,
    symbol: 'none',
    connectNulls: false,
    lineStyle: { width: 1.5, color: '#1890ff' },
    areaStyle: { color: 'rgba(24,144,255,0.08)' },
    markLine: markLines.length > 0 ? { silent: true, symbol: 'none', data: markLines } : undefined,
    markPoint: tdMarkData.length > 0 ? { silent: true, data: tdMarkData } : undefined,
}];
```

- [ ] **Step 5: 增量更新时也刷新 markPoint**

在 `renderChart()` 中已有图表实例时的更新分支（约 line 614-623），也需要更新 markPoint：

```javascript
if (this.chartInstances[code]) {
    const tdIntraday2 = (this.tdSequentialIntraday || {})[code] || {};
    const tdHistory2 = tdIntraday2.history || [];
    const tdMarkData2 = [];
    // ... 同 Step 4 的 markPoint 构建逻辑 ...

    const seriesUpdate = [{
        data: prices,
        markPoint: tdMarkData2.length > 0 ? { silent: true, data: tdMarkData2 } : undefined,
    }];
    if (prevPrices.length > 0) seriesUpdate.push({ data: prevPrices });
    this.chartInstances[code].setOption({
        xAxis: { data: fullAxis },
        series: seriesUpdate,
    });
    this._renderTDGraphic(code, this.chartInstances[code]);
    return;
}
```

为避免代码重复，将 markPoint 数据构建提取为辅助方法 `_buildTDIntradayMarkPoints(code, fullAxis)`。

- [ ] **Step 6: 验证**

访问盯盘页面，确认分时图上出现1-9数字标注：
- 绿色数字在线下方（买入信号）
- 红色数字在线上方（卖出信号）
- 数字7/8/9加粗
- 数字9有背景圆圈

---

### Task 4: 提交

- [ ] **Step 1: 确认所有功能正常**
- [ ] **Step 2: 提交代码**
