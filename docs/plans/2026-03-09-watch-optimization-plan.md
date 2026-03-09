# 盯盘助手优化 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 优化盯盘助手：布局重构（图表全宽+下方双栏）、九转信号计算与展示、财报数据面板。

**Architecture:** 新增两个后端服务（td_sequential.py, earnings_service.py），修改 watch.py 路由附带九转和财报数据，重构 watch.html 模板布局和 watch.js 前端渲染逻辑。

**Tech Stack:** Flask, akshare（A股财报）, yfinance（美股/港股财报）, ECharts graphic API, SQLite 缓存

---

### Task 1: TD Sequential 服务

**Files:**
- Create: `app/services/td_sequential.py`

**Step 1: 创建 TD Sequential 计算服务**

```python
"""TD Sequential（九转序列）信号计算"""
import logging

logger = logging.getLogger(__name__)


class TDSequentialService:

    @staticmethod
    def calculate(ohlc_data: list) -> dict:
        """
        计算 TD Sequential 信号

        Args:
            ohlc_data: OHLC数据列表，每项包含 {date, close, ...}，按时间升序

        Returns:
            {
                direction: 'buy'|'sell'|None,  # 当前计数方向
                count: 0-9,                     # 当前计数
                completed: bool,                # 是否已完成9计数
                history: [{date, direction, count}, ...]  # 最近的计数历史
            }
        """
        if not ohlc_data or len(ohlc_data) < 5:
            return {'direction': None, 'count': 0, 'completed': False, 'history': []}

        closes = []
        dates = []
        for d in ohlc_data:
            close = d.get('close') or d.get('price') or 0
            if close <= 0:
                continue
            closes.append(close)
            dates.append(d.get('date', ''))

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
                history.append({
                    'date': dates[i],
                    'direction': direction,
                    'count': min(count, 9),
                })

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

**Step 2: commit**

```
feat: 添加 TD Sequential（九转序列）计算服务
```

---

### Task 2: 财报数据服务

**Files:**
- Create: `app/services/earnings_service.py`

**Step 1: 创建财报数据获取服务**

```python
"""财报数据服务 - 获取过去4个季度的营收、利润和季末股价"""
import logging
from datetime import date, datetime, timedelta

from app.utils.market_identifier import MarketIdentifier
from app.models.unified_cache import UnifiedStockCache

logger = logging.getLogger(__name__)


class EarningsService:

    CACHE_TYPE = 'earnings'
    CACHE_TTL_DAYS = 7

    @classmethod
    def get_earnings(cls, stock_code: str) -> list[dict]:
        """
        获取过去4个季度的财报数据 + 季末股价

        Returns:
            [
                {
                    quarter: "Q4'25",
                    revenue: 32500000000,    # 营收（原始值）
                    profit: 15800000000,     # 净利润（原始值）
                    price_high: 1850.0,      # 季末最高价
                    price_low: 1680.0,       # 季末最低价
                    price_close: 1800.0,     # 季末收盘价
                    price_avg: 1765.0,       # 季末均价
                },
                ...
            ]
        """
        cached = cls._get_cache(stock_code)
        if cached is not None:
            return cached

        market = MarketIdentifier.identify(stock_code)
        try:
            if market == 'A':
                financials = cls._fetch_a_share(stock_code)
            elif market in ('US', 'HK'):
                financials = cls._fetch_yfinance(stock_code)
            else:
                financials = []
        except Exception as e:
            logger.warning(f'[财报] {stock_code} 获取失败: {e}')
            financials = []

        if financials:
            financials = cls._attach_quarter_prices(stock_code, financials)

        cls._set_cache(stock_code, financials)
        return financials

    @classmethod
    def _fetch_a_share(cls, stock_code: str) -> list[dict]:
        """A股财报数据（akshare）"""
        import akshare as ak

        result = []
        try:
            # 利润表
            df = ak.stock_financial_benefit_lja(symbol=stock_code)
            if df is None or df.empty:
                return []

            # 取最近4个季度（按报告期降序）
            df = df.sort_values('REPORT_DATE', ascending=False).head(4)

            for _, row in df.iterrows():
                report_date = str(row.get('REPORT_DATE', ''))[:10]
                quarter_label = cls._date_to_quarter_label(report_date)

                revenue = row.get('TOTAL_OPERATE_INCOME') or row.get('OPERATE_INCOME') or 0
                profit = row.get('NETPROFIT') or row.get('NET_PROFIT') or 0

                result.append({
                    'quarter': quarter_label,
                    'report_date': report_date,
                    'revenue': float(revenue) if revenue else 0,
                    'profit': float(profit) if profit else 0,
                })
        except Exception as e:
            logger.warning(f'[财报] A股 {stock_code} akshare获取失败: {e}')

        return result

    @classmethod
    def _fetch_yfinance(cls, stock_code: str) -> list[dict]:
        """美股/港股财报数据（yfinance）"""
        import yfinance as yf

        result = []
        try:
            yf_code = MarketIdentifier.to_yfinance(stock_code)
            ticker = yf.Ticker(yf_code)
            financials = ticker.quarterly_financials

            if financials is None or financials.empty:
                return []

            # 列是日期，行是指标，取最近4个季度
            cols = list(financials.columns)[:4]

            for col_date in cols:
                col = financials[col_date]
                report_date = col_date.strftime('%Y-%m-%d') if hasattr(col_date, 'strftime') else str(col_date)[:10]
                quarter_label = cls._date_to_quarter_label(report_date)

                revenue = 0
                for key in ['Total Revenue', 'Operating Revenue']:
                    if key in col.index and col[key] and not (isinstance(col[key], float) and col[key] != col[key]):
                        revenue = float(col[key])
                        break

                profit = 0
                for key in ['Net Income', 'Net Income Common Stockholders']:
                    if key in col.index and col[key] and not (isinstance(col[key], float) and col[key] != col[key]):
                        profit = float(col[key])
                        break

                result.append({
                    'quarter': quarter_label,
                    'report_date': report_date,
                    'revenue': revenue,
                    'profit': profit,
                })
        except Exception as e:
            logger.warning(f'[财报] yfinance {stock_code} 获取失败: {e}')

        return result

    @classmethod
    def _attach_quarter_prices(cls, stock_code: str, financials: list) -> list:
        """附加季末股价数据"""
        from app.services.unified_stock_data import unified_stock_data_service

        try:
            trend = unified_stock_data_service.get_trend_data([stock_code], days=400)
            stocks = trend.get('stocks', [])
            ohlc_data = stocks[0]['data'] if stocks else []
        except Exception as e:
            logger.warning(f'[财报] {stock_code} 获取OHLC失败: {e}')
            ohlc_data = []

        if not ohlc_data:
            for item in financials:
                item.update({'price_high': None, 'price_low': None, 'price_close': None, 'price_avg': None})
            return financials

        for item in financials:
            report_date = item.get('report_date', '')
            quarter_end = cls._get_quarter_end_date(report_date)
            prices = cls._get_quarter_prices(ohlc_data, quarter_end)
            item.update(prices)

        return financials

    @classmethod
    def _get_quarter_prices(cls, ohlc_data: list, quarter_end: str) -> dict:
        """从OHLC数据中提取某季度的股价区间"""
        if not quarter_end or not ohlc_data:
            return {'price_high': None, 'price_low': None, 'price_close': None, 'price_avg': None}

        try:
            end_date = datetime.strptime(quarter_end, '%Y-%m-%d').date()
            start_date = end_date - timedelta(days=95)

            quarter_data = [
                d for d in ohlc_data
                if start_date <= datetime.strptime(d['date'], '%Y-%m-%d').date() <= end_date
            ]

            if not quarter_data:
                return {'price_high': None, 'price_low': None, 'price_close': None, 'price_avg': None}

            highs = [d['high'] for d in quarter_data]
            lows = [d['low'] for d in quarter_data]
            last_close = quarter_data[-1]['close']

            return {
                'price_high': round(max(highs), 2),
                'price_low': round(min(lows), 2),
                'price_close': round(last_close, 2),
                'price_avg': round((max(highs) + min(lows)) / 2, 2),
            }
        except Exception as e:
            logger.debug(f'[财报] 季末股价计算失败: {e}')
            return {'price_high': None, 'price_low': None, 'price_close': None, 'price_avg': None}

    @staticmethod
    def _get_quarter_end_date(report_date: str) -> str:
        """从报告日期推断季度末日期"""
        try:
            dt = datetime.strptime(report_date[:10], '%Y-%m-%d')
            month = dt.month
            year = dt.year
            # 季度末月份: 3, 6, 9, 12
            quarter_end_months = {1: 3, 2: 3, 3: 3, 4: 6, 5: 6, 6: 6,
                                  7: 9, 8: 9, 9: 9, 10: 12, 11: 12, 12: 12}
            end_month = quarter_end_months[month]
            if end_month == 12:
                end_date = date(year, 12, 31)
            elif end_month == 3:
                end_date = date(year, 3, 31)
            elif end_month == 6:
                end_date = date(year, 6, 30)
            elif end_month == 9:
                end_date = date(year, 9, 30)
            return end_date.isoformat()
        except Exception:
            return ''

    @staticmethod
    def _date_to_quarter_label(report_date: str) -> str:
        """日期转季度标签：如 2025-12-31 → Q4'25"""
        try:
            dt = datetime.strptime(report_date[:10], '%Y-%m-%d')
            q = (dt.month - 1) // 3 + 1
            return f"Q{q}'{str(dt.year)[2:]}"
        except Exception:
            return report_date[:7]

    @classmethod
    def _get_cache(cls, stock_code: str) -> list | None:
        """从DB缓存读取"""
        try:
            cached = UnifiedStockCache.get_cached_data(stock_code, cls.CACHE_TYPE)
            if cached is None:
                return None
            # 检查TTL
            cache_obj = UnifiedStockCache.query.filter_by(
                stock_code=stock_code, cache_type=cls.CACHE_TYPE
            ).order_by(UnifiedStockCache.updated_at.desc()).first()
            if cache_obj and cache_obj.updated_at:
                age = (datetime.now() - cache_obj.updated_at).days
                if age <= cls.CACHE_TTL_DAYS:
                    return cached
            return None
        except Exception:
            return None

    @classmethod
    def _set_cache(cls, stock_code: str, data: list) -> None:
        """写入DB缓存"""
        try:
            UnifiedStockCache.set_cached_data(stock_code, cls.CACHE_TYPE, data)
        except Exception as e:
            logger.debug(f'[财报] 缓存写入失败 {stock_code}: {e}')
```

**Step 2: commit**

```
feat: 添加财报数据服务（A股+美股+港股季度财报+季末股价）
```

---

### Task 3: 后端路由修改

**Files:**
- Modify: `app/routes/watch.py` — chart-data 接口附带 td_sequential，新增 earnings 接口

**Step 1: 在 chart-data 接口中附带九转信号数据**

在 `chart_data()` 函数中，在返回 `jsonify(result)` 之前，添加九转信号计算：

```python
# 在算法支撑/压力计算之后、return jsonify(result) 之前添加：

# 九转序列信号（基于30日K线数据）
from app.services.td_sequential import TDSequentialService
td_result = {'direction': None, 'count': 0, 'completed': False, 'history': []}
try:
    td_trend = unified_stock_data_service.get_trend_data([code], days=30)
    td_stocks = td_trend.get('stocks', [])
    if td_stocks and td_stocks[0].get('data'):
        td_result = TDSequentialService.calculate(td_stocks[0]['data'])
except Exception as e:
    logger.debug(f"[盯盘] 九转信号计算失败 {code}: {e}")
result['td_sequential'] = td_result
```

**Step 2: 新增财报数据接口**

在 watch.py 底部新增：

```python
@watch_bp.route('/earnings')
def earnings():
    from app.services.earnings_service import EarningsService

    code = request.args.get('code', '').strip()
    if not code:
        return jsonify({'success': False, 'message': '缺少股票代码'})

    data = EarningsService.get_earnings(code)
    return jsonify({'success': True, 'data': data})
```

**Step 3: commit**

```
feat: watch 路由增加九转信号和财报数据接口
```

---

### Task 4: 模板布局重构

**Files:**
- Modify: `app/templates/watch.html`

**Step 1: 重构 CSS 样式**

删除 `.chart-analysis-row`、`.analysis-sidebar` 相关所有样式，替换为新布局样式：

```css
.chart-container { height: 200px; border-radius: 4px; background: #fafafa; }
.analysis-tab .nav-link { padding: 0.25rem 0.75rem; font-size: 0.8rem; }
.analysis-tab .nav-link.active { font-weight: 600; }
.analysis-content { font-size: 0.85rem; min-height: 40px; }
.bottom-panel { display: flex; gap: 12px; }
.bottom-panel .panel-left,
.bottom-panel .panel-right { flex: 1; min-width: 0; }
.panel-right table { font-size: 0.78rem; }
.panel-right th { font-weight: 600; color: #6b7280; }
.td-badge {
    display: inline-block;
    padding: 0 0.5rem;
    border-radius: 3px;
    font-size: 0.72rem;
    font-weight: 700;
}
.td-badge-buy { background: #dcfce7; color: #16a34a; }
.td-badge-sell { background: #fef2f2; color: #dc2626; }
.td-badge-warn { animation: td-pulse 1s ease-in-out infinite; }
@keyframes td-pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }
.earnings-table td, .earnings-table th { padding: 0.25rem 0.4rem; white-space: nowrap; }
```

模板 HTML 不变（卡片结构由 JS 动态生成）。

**Step 2: commit**

```
refactor: watch.html 样式重构，删除右侧栏样式，新增底部双栏+九转徽章样式
```

---

### Task 5: 前端 JS 重构

**Files:**
- Modify: `app/static/js/watch.js`

**Step 1: 在 Watch 对象中添加新的数据容器**

```javascript
// 在 Watch 对象属性中新增：
tdSequential: {},   // {code: {direction, count, completed, history}}
earnings: {},       // {code: [{quarter, revenue, profit, price_high, ...}]}
```

同步更新 `WatchCache.snapshot()` 和 `WatchCache.restore()` 包含 `tdSequential` 和 `earnings`。

**Step 2: 重构 renderStockCard 方法**

新的卡片结构：

```javascript
renderStockCard(stock, pricesMap) {
    const code = stock.stock_code;
    const name = stock.stock_name || code;
    const market = stock.market || 'A';
    const p = pricesMap[code] || {};

    const priceDisplay = p.price != null ? this.formatPrice(p.price, market) : '--';
    const pctClass = p.change_pct > 0 ? 'price-up' : p.change_pct < 0 ? 'price-down' : 'price-flat';
    const pctSign = p.change_pct > 0 ? '+' : '';
    const pctDisplay = p.change_pct != null ? `${pctSign}${p.change_pct.toFixed(2)}%` : '--';
    const changeDisplay = p.change != null ? `${p.change > 0 ? '+' : ''}${p.change.toFixed(2)}` : '';

    // 九转徽章
    const td = this.tdSequential[code] || {};
    let tdBadgeHtml = '';
    if (td.direction && td.count > 0) {
        const tdClass = td.direction === 'buy' ? 'td-badge-buy' : 'td-badge-sell';
        const warn = td.count >= 7 ? ' td-badge-warn' : '';
        const check = td.completed ? ' ✓' : '';
        const label = td.direction === 'buy' ? '买' : '卖';
        tdBadgeHtml = `<span class="td-badge ${tdClass}${warn}">${label}${td.count}${check}</span>`;
    }

    return `<div class="card stock-card mb-3" id="card-${code}">
        <div class="card-body">
            <div class="d-flex justify-content-between align-items-center mb-2">
                <div class="d-flex align-items-center gap-2">
                    <span class="fw-bold fs-6">${name}</span>
                    <small class="text-muted">${code}</small>
                    ${tdBadgeHtml}
                </div>
                <div class="d-flex align-items-center gap-3">
                    <div class="text-end">
                        <span class="fs-5 fw-bold" data-field="price" data-code="${code}">${priceDisplay}</span>
                        <span class="${pctClass} fw-bold ms-2" data-field="change_pct" data-code="${code}">${pctDisplay}</span>
                        <span class="${pctClass} small ms-1" data-field="change" data-code="${code}">${changeDisplay}</span>
                    </div>
                    <button class="btn btn-sm btn-link text-muted p-0" onclick="Watch.removeStock('${code}')" title="移除">
                        <i class="bi bi-x-lg"></i>
                    </button>
                </div>
            </div>
            <div class="chart-container mb-2" id="chart-${code}">
                <div class="skeleton skeleton-card" style="height:100%;"></div>
            </div>
            <div class="bottom-panel">
                <div class="panel-left">
                    <ul class="nav nav-tabs analysis-tab mb-2" role="tablist">
                        <li class="nav-item"><button class="nav-link active" data-period="realtime" onclick="Watch.switchAnalysisTab('${code}','realtime',this)">实时</button></li>
                        <li class="nav-item"><button class="nav-link" data-period="7d" onclick="Watch.switchAnalysisTab('${code}','7d',this)">7天</button></li>
                        <li class="nav-item"><button class="nav-link" data-period="30d" onclick="Watch.switchAnalysisTab('${code}','30d',this)">30天</button></li>
                    </ul>
                    <div class="analysis-content" id="analysis-content-${code}">
                        <span class="text-muted small">等待分析数据...</span>
                    </div>
                </div>
                <div class="panel-right">
                    <div class="small fw-bold text-muted mb-1">财报数据</div>
                    <div id="earnings-${code}">
                        <span class="text-muted small">加载中...</span>
                    </div>
                </div>
            </div>
        </div>
    </div>`;
},
```

**Step 3: 图表中添加九转浮动标注**

在 `renderChart` 方法中，初始化 chart 后，添加 ECharts `graphic` 元素：

```javascript
// 在 chart.setOption({...}) 之后添加九转浮动标注：
const td = this.tdSequential[code] || {};
if (td.direction && td.count > 0) {
    const label = td.direction === 'buy' ? 'TD买入' : 'TD卖出';
    const color = td.direction === 'buy' ? '#16a34a' : '#dc2626';
    const check = td.completed ? ' ✓' : '';
    chart.setOption({
        graphic: [{
            type: 'group',
            left: 15,
            bottom: 25,
            children: [{
                type: 'rect',
                shape: { width: 90, height: 22, r: 3 },
                style: { fill: 'rgba(255,255,255,0.85)', stroke: color, lineWidth: 1 },
            }, {
                type: 'text',
                style: {
                    text: `${label} ${td.count}/9${check}`,
                    x: 8, y: 4,
                    fill: color,
                    font: 'bold 11px sans-serif',
                },
            }],
        }],
    });
} else {
    chart.setOption({ graphic: [] });
}
```

对于已存在的 chart 实例更新分支（`if (this.chartInstances[code])`），也要附带更新 graphic。

**Step 4: 添加财报加载和渲染方法**

```javascript
async loadEarnings(code) {
    try {
        const resp = await fetch(`/watch/earnings?code=${encodeURIComponent(code)}`);
        const data = await resp.json();
        if (data.success) {
            this.earnings[code] = data.data || [];
            this.renderEarnings(code);
        }
    } catch (e) {
        console.error(`[Watch] earnings load failed ${code}:`, e);
    }
},

renderEarnings(code) {
    const el = document.getElementById(`earnings-${code}`);
    if (!el) return;
    const items = this.earnings[code] || [];
    if (items.length === 0) {
        el.innerHTML = '<span class="text-muted small">暂无财报数据</span>';
        return;
    }
    let html = `<table class="table table-sm table-borderless earnings-table mb-0">
        <thead><tr><th>季度</th><th>营收</th><th>利润</th><th>股价区间</th></tr></thead><tbody>`;
    for (const item of items) {
        const rev = this._formatLargeNumber(item.revenue);
        const prof = this._formatLargeNumber(item.profit);
        let priceRange = '--';
        if (item.price_high != null && item.price_low != null) {
            priceRange = `${item.price_low}-${item.price_high}`;
        }
        html += `<tr><td>${item.quarter}</td><td>${rev}</td><td>${prof}</td><td>${priceRange}</td></tr>`;
    }
    html += '</tbody></table>';
    el.innerHTML = html;
},

_formatLargeNumber(num) {
    if (num == null || num === 0) return '--';
    const abs = Math.abs(num);
    const sign = num < 0 ? '-' : '';
    if (abs >= 1e12) return sign + (abs / 1e12).toFixed(1) + 'T';
    if (abs >= 1e9) return sign + (abs / 1e9).toFixed(1) + 'B';
    if (abs >= 1e8) return sign + (abs / 1e8).toFixed(1) + '亿';
    if (abs >= 1e4) return sign + (abs / 1e4).toFixed(0) + '万';
    return sign + abs.toFixed(0);
},
```

**Step 5: 集成到数据流**

1. `loadChartData` 中保存 `td_sequential` 数据：
```javascript
// 在 this.chartMeta[code] = {...} 之后添加：
if (result.td_sequential) {
    this.tdSequential[code] = result.td_sequential;
}
```

2. `loadAllCharts` 完成后加载所有财报：
```javascript
// 在 loadAllCharts 末尾，或 loadList 中 await this.loadAllCharts() 之后：
this.stocks.forEach(s => this.loadEarnings(s.stock_code));
```

3. 删除 `renderAnalysisSidebar` 方法和所有 `analysis-sidebar` 相关引用。

4. `updateAllAnalysisPanels` 中删除 `this.renderAnalysisSidebar(code)` 调用。

**Step 6: 更新缓存快照/恢复**

```javascript
// WatchCache.snapshot 中新增：
tdSequential: watch.tdSequential,
earnings: watch.earnings,

// WatchCache.restore 中新增：
watch.tdSequential = cache.tdSequential || {};
watch.earnings = cache.earnings || {};
```

**Step 7: commit**

```
feat: 盯盘助手前端重构 — 全宽图表+下方双栏+九转信号+财报面板
```

---

### Task 6: 集成验证

**Step 1: 启动应用，手动验证**

```bash
python run.py
```

访问 http://127.0.0.1:5000/watch，验证：
- [ ] 图表占满卡片宽度
- [ ] 右侧 AI 分析边栏已移除
- [ ] 下方左栏显示 AI 分析（标签页切换正常）
- [ ] 下方右栏显示财报表格
- [ ] 标题行显示九转徽章
- [ ] 图表左下角显示九转浮动标注
- [ ] 实时刷新不报错

**Step 2: commit（如有修复）**

```
fix: 盯盘助手优化集成修复
```
