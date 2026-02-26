# 盯盘助手走势图 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在盯盘卡片内嵌入迷你走势图，支持分时/日K切换，叠加支撑位/阻力位/布林带标注。

**Architecture:** 后端新增分时数据获取接口（akshare A股分时 + yfinance 美股分时），复用现有两层缓存。前端用 ECharts 渲染迷你K线/分时图，叠加 markLine 标注。

**Tech Stack:** ECharts（已引入）、akshare（A股分时）、yfinance（美股分时）、现有缓存架构

---

### Task 1: 后端 — 新增分时数据获取方法

**Files:**
- Modify: `app/services/unified_stock_data.py`

**Step 1: 在 `UnifiedStockDataService` 类中新增 `get_intraday_data` 方法**

在 `get_trend_data` 方法之后添加：

```python
def get_intraday_data(self, stock_codes: list, interval: str = '1m',
                      force_refresh: bool = False) -> dict:
    """获取分时数据

    Args:
        stock_codes: 股票代码列表
        interval: 时间间隔 ('1m', '5m', '15m')
        force_refresh: 是否强制刷新

    Returns:
        {'stocks': [{stock_code, stock_name, data: [{time, price, volume, avg_price}]}]}
    """
    if not stock_codes:
        return {'stocks': []}

    cache_type = f'intraday_{interval}'
    results = []
    remaining_codes = list(stock_codes)

    # 内存缓存
    if not force_refresh:
        memory_cached = memory_cache.get_batch(remaining_codes, cache_type)
        for code, data in memory_cached.items():
            results.append(data)
        remaining_codes = [c for c in remaining_codes if c not in memory_cached]

    if not remaining_codes:
        return {'stocks': results}

    # DB缓存
    effective_dates = self._get_effective_cache_dates(remaining_codes)
    db_remaining = []
    for code in remaining_codes:
        cache_date = effective_dates.get(code, date.today())
        cached = UnifiedStockCache.get_cache(code, cache_type, cache_date)
        if cached and not force_refresh:
            # 分时缓存：交易时段1分钟TTL
            cache_age = (datetime.now() - cached.updated_at).total_seconds()
            market = MarketIdentifier.identify(code)
            is_open = TradingCalendarService.is_market_open(market or 'A')
            ttl = 60 if is_open else 28800  # 1分钟 / 8小时
            if cache_age < ttl:
                stock_data = cached.get_data()
                results.append(stock_data)
                memory_cache.set(code, cache_type, stock_data)
                continue
        db_remaining.append(code)

    # API获取
    if db_remaining:
        for code in db_remaining:
            try:
                data = self._fetch_intraday(code, interval)
                if data:
                    results.append(data)
                    cache_date = effective_dates.get(code, date.today())
                    memory_cache.set(code, cache_type, data)
                    UnifiedStockCache.save_cache(code, cache_type, cache_date, data)
            except Exception as e:
                logger.error(f"[数据服务.分时] {code} 获取失败: {e}")

    return {'stocks': results}

def _fetch_intraday(self, code: str, interval: str = '1m') -> dict:
    """从API获取分时数据"""
    market = MarketIdentifier.identify(code)

    if market == 'A':
        return self._fetch_intraday_a_share(code, interval)
    else:
        return self._fetch_intraday_yfinance(code, interval)

def _fetch_intraday_a_share(self, code: str, interval: str = '1m') -> dict:
    """A股分时数据 - 东方财富"""
    import akshare as ak

    # akshare 分时接口使用的间隔格式
    period_map = {'1m': '1', '5m': '5', '15m': '15'}
    ak_period = period_map.get(interval, '1')

    try:
        df = ak.stock_zh_a_hist_min_em(symbol=code, period=ak_period, adjust='qfq')
        if df is None or df.empty:
            return None

        # 只取今天的数据
        today_str = date.today().strftime('%Y-%m-%d')
        df['时间'] = pd.to_datetime(df['时间'])
        df = df[df['时间'].dt.strftime('%Y-%m-%d') == today_str]

        data_list = []
        for _, row in df.iterrows():
            data_list.append({
                'time': row['时间'].strftime('%H:%M'),
                'open': float(row['开盘']),
                'high': float(row['最高']),
                'low': float(row['最低']),
                'close': float(row['收盘']),
                'volume': int(row['成交量']),
            })

        return {
            'stock_code': code,
            'stock_name': '',
            'data': data_list,
        }
    except Exception as e:
        logger.error(f"[分时数据] A股 {code} 获取失败: {e}")
        return None

def _fetch_intraday_yfinance(self, code: str, interval: str = '1m') -> dict:
    """美股/港股分时数据 - yfinance"""
    import yfinance as yf

    yf_code = MarketIdentifier.to_yfinance(code)
    try:
        ticker = yf.Ticker(yf_code)
        df = ticker.history(period='1d', interval=interval)
        if df is None or df.empty:
            return None

        data_list = []
        for idx, row in df.iterrows():
            data_list.append({
                'time': idx.strftime('%H:%M'),
                'open': float(row['Open']),
                'high': float(row['High']),
                'low': float(row['Low']),
                'close': float(row['Close']),
                'volume': int(row['Volume']),
            })

        return {
            'stock_code': code,
            'stock_name': '',
            'data': data_list,
        }
    except Exception as e:
        logger.error(f"[分时数据] {code} yfinance获取失败: {e}")
        return None
```

**Step 2: Commit**

```bash
git add app/services/unified_stock_data.py
git commit -m "feat(watch): 新增分时数据获取接口 get_intraday_data"
```

---

### Task 2: 后端 — 新增图表数据API端点

**Files:**
- Modify: `app/routes/watch.py`

**Step 1: 新增 `/watch/chart-data` 端点**

在 `watch.py` 文件末尾添加：

```python
@watch_bp.route('/chart-data')
def chart_data():
    """获取图表数据（分时/日K + 布林带 + 支撑阻力位）"""
    from app.services.unified_stock_data import unified_stock_data_service
    from app.services.technical_indicators import TechnicalIndicatorService

    code = request.args.get('code', '').strip()
    period = request.args.get('period', 'intraday')  # intraday, 7d, 30d, 90d

    if not code:
        return jsonify({'success': False, 'message': '缺少股票代码'})

    result = {'success': True, 'code': code, 'period': period}

    if period == 'intraday':
        # 分时数据
        intraday = unified_stock_data_service.get_intraday_data([code])
        stocks = intraday.get('stocks', [])
        result['data'] = stocks[0]['data'] if stocks else []
        result['chart_type'] = 'line'
    else:
        # 日K数据
        days_map = {'7d': 7, '30d': 30, '90d': 90}
        days = days_map.get(period, 30)
        # 布林带需要20天预热数据
        fetch_days = days + 20
        trend = unified_stock_data_service.get_trend_data([code], days=fetch_days)
        stocks = trend.get('stocks', [])
        ohlc_data = stocks[0]['data'] if stocks else []

        # 计算布林带（20日，2倍标准差）
        bollinger = []
        if len(ohlc_data) >= 20:
            closes = [d['close'] for d in ohlc_data]
            for i in range(len(closes)):
                if i < 19:
                    bollinger.append(None)
                    continue
                window = closes[i-19:i+1]
                ma = sum(window) / 20
                std = (sum((x - ma) ** 2 for x in window) / 20) ** 0.5
                bollinger.append({
                    'upper': round(ma + 2 * std, 2),
                    'middle': round(ma, 2),
                    'lower': round(ma - 2 * std, 2),
                })

        # 裁剪到请求天数（去掉预热部分）
        result['data'] = ohlc_data[-days:]
        result['bollinger'] = bollinger[-days:]
        result['chart_type'] = 'candlestick'

    # 支撑位/阻力位（从AI分析结果获取）
    analysis = WatchService.get_today_analysis(code)
    result['support_levels'] = analysis.get('support_levels', []) if analysis else []
    result['resistance_levels'] = analysis.get('resistance_levels', []) if analysis else []

    return jsonify(result)
```

需要在 `WatchService` 中新增 `get_today_analysis` 单股查询方法。

**Step 2: 在 `app/services/watch_service.py` 新增方法**

```python
@staticmethod
def get_today_analysis(stock_code):
    """获取单只股票今日分析"""
    from app.models.watch_list import WatchAnalysis
    from datetime import date
    analysis = WatchAnalysis.query.filter_by(
        stock_code=stock_code,
        analysis_date=date.today()
    ).first()
    if not analysis:
        return None
    return {
        'support_levels': analysis.support_levels or [],
        'resistance_levels': analysis.resistance_levels or [],
        'volatility_threshold': analysis.volatility_threshold,
        'summary': analysis.analysis_summary,
    }
```

**Step 3: Commit**

```bash
git add app/routes/watch.py app/services/watch_service.py
git commit -m "feat(watch): 新增图表数据API /watch/chart-data"
```

---

### Task 3: 前端 — 卡片内图表容器和切换按钮

**Files:**
- Modify: `app/static/js/watch.js` — `renderStockRow` 方法
- Modify: `app/templates/watch.html` — （可能无需改动，JS动态生成）

**Step 1: 修改 `renderStockRow` 添加图表容器**

在 `watch.js` 的 `renderStockRow` 方法中，`</div>` 闭合标签前添加图表区域：

```javascript
// 在现有卡片内容之后、闭合 </div> 之前添加
const chartHtml = `
    <div class="chart-section mt-2 d-none" id="chart-section-${code}">
        <div class="d-flex align-items-center mb-1">
            <div class="btn-group btn-group-sm" role="group">
                <button type="button" class="btn btn-outline-secondary btn-xs active" data-period="intraday" onclick="Watch.switchChartPeriod('${code}', 'intraday', this)">分时</button>
                <button type="button" class="btn btn-outline-secondary btn-xs" data-period="7d" onclick="Watch.switchChartPeriod('${code}', '7d', this)">7天</button>
                <button type="button" class="btn btn-outline-secondary btn-xs" data-period="30d" onclick="Watch.switchChartPeriod('${code}', '30d', this)">30天</button>
                <button type="button" class="btn btn-outline-secondary btn-xs" data-period="90d" onclick="Watch.switchChartPeriod('${code}', '90d', this)">90天</button>
            </div>
        </div>
        <div class="chart-container" id="chart-${code}" style="height: 160px;">
            <div class="skeleton skeleton-card" style="height: 100%;"></div>
        </div>
    </div>`;
```

**Step 2: 添加卡片点击展开/折叠逻辑**

在 `renderStockRow` 中给行添加点击事件，在 Watch 对象中新增：

```javascript
toggleChart(code) {
    const section = document.getElementById(`chart-section-${code}`);
    if (!section) return;

    const isHidden = section.classList.contains('d-none');
    if (isHidden) {
        section.classList.remove('d-none');
        // 首次展开时加载数据
        if (!this.chartInstances?.[code]) {
            this.loadChartData(code, 'intraday');
        }
    } else {
        section.classList.add('d-none');
    }
},
```

**Step 3: Commit**

```bash
git add app/static/js/watch.js
git commit -m "feat(watch): 卡片内图表容器和展开折叠逻辑"
```

---

### Task 4: 前端 — ECharts 图表渲染

**Files:**
- Modify: `app/static/js/watch.js`

**Step 1: 在 Watch 对象中添加图表相关属性和方法**

```javascript
// 在 Watch 对象顶部添加
chartInstances: {},
chartPeriods: {},

// 加载图表数据
async loadChartData(code, period) {
    const container = document.getElementById(`chart-${code}`);
    if (!container) return;

    // 骨架屏
    container.innerHTML = '<div class="skeleton skeleton-card" style="height: 100%;"></div>';

    try {
        const resp = await fetch(`/watch/chart-data?code=${encodeURIComponent(code)}&period=${period}`);
        const result = await resp.json();
        if (!result.success || !result.data?.length) {
            container.innerHTML = '<div class="text-muted text-center small py-4">暂无数据</div>';
            return;
        }
        this.chartPeriods[code] = period;
        this.renderChart(code, result);
    } catch (e) {
        console.error(`[Watch] chart load failed for ${code}:`, e);
        container.innerHTML = '<div class="text-muted text-center small py-4">加载失败</div>';
    }
},

// 切换周期
switchChartPeriod(code, period, btn) {
    // 更新按钮状态
    const group = btn.parentElement;
    group.querySelectorAll('.btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');

    this.loadChartData(code, period);
},

// 渲染ECharts图表
renderChart(code, result) {
    const container = document.getElementById(`chart-${code}`);
    container.innerHTML = '';

    // 销毁旧实例
    if (this.chartInstances[code]) {
        this.chartInstances[code].dispose();
    }

    const chart = echarts.init(container);
    this.chartInstances[code] = chart;

    const option = result.chart_type === 'line'
        ? this.buildIntradayOption(result)
        : this.buildCandlestickOption(result);

    chart.setOption(option);

    // 响应式
    new ResizeObserver(() => chart.resize()).observe(container);
},

// 分时图配置
buildIntradayOption(result) {
    const data = result.data;
    const times = data.map(d => d.time);
    const prices = data.map(d => d.close);
    const support = result.support_levels || [];
    const resistance = result.resistance_levels || [];

    const markLines = [];
    support.forEach(level => {
        markLines.push({
            yAxis: level,
            lineStyle: { color: '#28a745', type: 'dashed', width: 1 },
            label: { formatter: String(level), position: 'end', fontSize: 9, color: '#28a745' },
        });
    });
    resistance.forEach(level => {
        markLines.push({
            yAxis: level,
            lineStyle: { color: '#dc3545', type: 'dashed', width: 1 },
            label: { formatter: String(level), position: 'end', fontSize: 9, color: '#dc3545' },
        });
    });

    return {
        grid: { left: 8, right: 55, top: 8, bottom: 20, containLabel: false },
        tooltip: {
            trigger: 'axis',
            formatter: params => {
                const p = params[0];
                return `${p.axisValue}<br/>¥${p.value.toFixed(2)}`;
            },
        },
        xAxis: {
            type: 'category',
            data: times,
            axisLabel: { fontSize: 9, interval: Math.floor(times.length / 4) },
            axisLine: { lineStyle: { color: '#ddd' } },
        },
        yAxis: {
            type: 'value',
            scale: true,
            splitLine: { lineStyle: { color: '#f0f0f0' } },
            axisLabel: { fontSize: 9 },
        },
        series: [{
            type: 'line',
            data: prices,
            smooth: true,
            symbol: 'none',
            lineStyle: { width: 1.5, color: '#1890ff' },
            areaStyle: { color: 'rgba(24,144,255,0.08)' },
            markLine: markLines.length > 0 ? {
                silent: true,
                symbol: 'none',
                data: markLines,
            } : undefined,
        }],
    };
},

// K线图配置
buildCandlestickOption(result) {
    const data = result.data;
    const bollinger = result.bollinger || [];
    const support = result.support_levels || [];
    const resistance = result.resistance_levels || [];

    const dates = data.map(d => d.date);
    // ECharts candlestick: [open, close, low, high]
    const ohlc = data.map(d => [d.open, d.close, d.low, d.high]);

    const markLines = [];
    support.forEach(level => {
        markLines.push({
            yAxis: level,
            lineStyle: { color: '#28a745', type: 'dashed', width: 1 },
            label: { formatter: String(level), position: 'end', fontSize: 9, color: '#28a745' },
        });
    });
    resistance.forEach(level => {
        markLines.push({
            yAxis: level,
            lineStyle: { color: '#dc3545', type: 'dashed', width: 1 },
            label: { formatter: String(level), position: 'end', fontSize: 9, color: '#dc3545' },
        });
    });

    const series = [
        {
            type: 'candlestick',
            data: ohlc,
            itemStyle: {
                color: '#ef5350',        // 涨（红）
                color0: '#26a69a',       // 跌（绿）
                borderColor: '#ef5350',
                borderColor0: '#26a69a',
            },
            markLine: markLines.length > 0 ? {
                silent: true,
                symbol: 'none',
                data: markLines,
            } : undefined,
        },
    ];

    // 布林带
    const bbUpper = bollinger.map(b => b ? b.upper : null);
    const bbMiddle = bollinger.map(b => b ? b.middle : null);
    const bbLower = bollinger.map(b => b ? b.lower : null);

    if (bollinger.some(b => b !== null)) {
        series.push(
            { type: 'line', data: bbUpper, smooth: true, symbol: 'none', lineStyle: { width: 1, color: 'rgba(150,150,150,0.5)', type: 'dotted' }, z: 0 },
            { type: 'line', data: bbMiddle, smooth: true, symbol: 'none', lineStyle: { width: 1, color: 'rgba(150,150,150,0.7)' }, z: 0 },
            { type: 'line', data: bbLower, smooth: true, symbol: 'none', lineStyle: { width: 1, color: 'rgba(150,150,150,0.5)', type: 'dotted' }, z: 0 },
        );
    }

    return {
        grid: { left: 8, right: 55, top: 8, bottom: 20, containLabel: false },
        tooltip: {
            trigger: 'axis',
            formatter: params => {
                const candle = params.find(p => p.seriesType === 'candlestick');
                if (!candle) return '';
                const [open, close, low, high] = candle.value;
                return `${candle.axisValue}<br/>开:${open} 高:${high}<br/>低:${low} 收:${close}`;
            },
        },
        xAxis: {
            type: 'category',
            data: dates,
            axisLabel: { fontSize: 9, interval: Math.floor(dates.length / 4) },
            axisLine: { lineStyle: { color: '#ddd' } },
        },
        yAxis: {
            type: 'value',
            scale: true,
            splitLine: { lineStyle: { color: '#f0f0f0' } },
            axisLabel: { fontSize: 9 },
        },
        series,
    };
},
```

**Step 2: Commit**

```bash
git add app/static/js/watch.js
git commit -m "feat(watch): ECharts迷你走势图渲染（分时+K线+布林带+支撑阻力位）"
```

---

### Task 5: 集成和样式调优

**Files:**
- Modify: `app/static/js/watch.js` — 卡片点击事件绑定
- Modify: `app/templates/watch.html` — 可能的CSS微调

**Step 1: 在 `renderStockRow` 中集成图表容器和点击事件**

确保 `renderStockRow` 返回的HTML包含图表容器，点击股票名/代码区域展开图表。添加小箭头图标提示可展开。

**Step 2: 添加必要的CSS**

在 watch.html 或内联样式中：

```css
.btn-xs {
    padding: 0.1rem 0.4rem;
    font-size: 0.7rem;
}
.chart-container {
    border-radius: 4px;
    background: #fafafa;
}
```

**Step 3: 处理图表实例销毁**

当卡片被移除或列表重新渲染时，销毁对应的 ECharts 实例，防止内存泄漏：

```javascript
// 在 renderGroups 开头添加
Object.values(this.chartInstances).forEach(chart => chart.dispose());
this.chartInstances = {};
```

**Step 4: Commit**

```bash
git add app/static/js/watch.js app/templates/watch.html
git commit -m "feat(watch): 走势图集成完成 — 样式+生命周期管理"
```
