# 价值洼地页改用盯盘股（扁平化）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `/value-dip`（导航「价值洼地」）选股源从硬编码 `VALUE_DIP_SECTORS` 换成盯盘池 `WATCH_CODES`，去掉板块对比，页面变成一张扁平表。

**Architecture:** 数据层用 `WatchService.get_watch_list()` 取 12 只盯盘股，对其调一次 `get_trend_data(days=90)` 算逐股涨幅/高点回退（扁平，无板块聚合）。路由暴露扁平 `/api/stocks`。前端纯表格渲染。每日简报删掉板块洼地推送、保留高点回退推送。

**Tech Stack:** Flask、SQLAlchemy、原生 JS（Bootstrap 表格）、pytest。

## Global Constraints

- 响应中文；不写多余注释；不写 backup 文件。
- 所有 git/pytest 命令前加 `rtk`，链式 `&&` 中也要。
- 单测命令：`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest <path> -v`（env 赋值必须在 `rtk` 之前）。
- `git add` 与 `git commit` 放进**同一条** Bash 命令链，精确路径，勿 `git add -A`。
- 单测平铺放 `tests/test_*.py`。
- `WatchService.get_watch_list()` 返回 dict 键为 `stock_code` / `stock_name` / `market`（**不是** `code`/`name`）。

---

### Task 1: 数据层扁平化（`value_dip.py`）

把 `ValueDipService` 从板块聚合改为盯盘股扁平计算：新增 `get_watch_performance()`，改 `get_pullback_ranking()` 走扁平列表并输出 `market`，删除 `get_sector_performance()` / `detect_value_dips()`。`_calc_stock_changes` 保留逐股算法，去掉不再需要的 `trend_data` 字段。

**Files:**
- Modify: `app/services/value_dip.py`（整文件重写）
- Test: `tests/test_value_dip_flat.py`

**Interfaces:**
- Consumes: `WatchService.get_watch_list() -> list[dict]`（键 `stock_code`/`stock_name`/`market`）；`unified_stock_data_service.get_trend_data(codes, days) -> {'stocks': [{'stock_code', 'data': [{date, close, high, ...}]}], ...}`
- Produces:
  - `ValueDipService.get_watch_performance() -> list[dict]`，每项键：`code, name, market, price, change_7d, change_30d, change_90d, high_7d, high_30d, high_90d, pullback_7d, pullback_30d, pullback_90d`
  - `ValueDipService.get_pullback_ranking(days: int = 90) -> list[dict]`，每项键：`code, name, market, price, high, pullback_pct`

- [ ] **Step 1: 写失败测试**

新建 `tests/test_value_dip_flat.py`：

```python
from app.services.value_dip import ValueDipService


def _fake_trend(codes, days=90):
    # 造 30 天递减再回升的收盘价：高点在中段，末值低于高点 → 有回退
    def series(base):
        closes = [base + i for i in range(20)] + [base + 20 - j for j in range(10)]
        return [{'date': f'2026-06-{(i % 28) + 1:02d}', 'close': c, 'high': c}
                for i, c in enumerate(closes)]
    return {'stocks': [{'stock_code': c, 'stock_name': c, 'data': series(10 + idx)}
                       for idx, c in enumerate(codes)],
            'date_range': {}}


def _patch(monkeypatch, codes):
    watch = [{'stock_code': c, 'stock_name': f'N{c}', 'market': m}
             for c, m in codes]
    monkeypatch.setattr('app.services.value_dip.WatchService.get_watch_list',
                        staticmethod(lambda: watch))
    monkeypatch.setattr('app.services.value_dip.unified_stock_data_service.get_trend_data',
                        _fake_trend)


def test_get_watch_performance_flat_shape(monkeypatch):
    _patch(monkeypatch, [('300223', 'A'), ('2631.HK', 'HK'), ('000660.KS', 'KR')])
    rows = ValueDipService.get_watch_performance()
    assert [r['code'] for r in rows] == ['300223', '2631.HK', '000660.KS']
    r = rows[0]
    assert r['market'] == 'A'
    assert r['name'] == 'N300223'
    for k in ('price', 'change_7d', 'change_30d', 'change_90d',
              'high_90d', 'pullback_90d'):
        assert k in r
    # 无 trend_data 字段（纯表格不需要）
    assert 'trend_data' not in r


def test_pullback_ranking_has_market_and_sorted(monkeypatch):
    _patch(monkeypatch, [('300223', 'A'), ('2631.HK', 'HK')])
    ranking = ValueDipService.get_pullback_ranking(90)
    assert ranking, '应有回退数据'
    assert 'market' in ranking[0] and 'sector' not in ranking[0]
    pks = [s['pullback_pct'] for s in ranking]
    assert pks == sorted(pks)  # 回退最深在前


def test_sector_methods_removed():
    assert not hasattr(ValueDipService, 'get_sector_performance')
    assert not hasattr(ValueDipService, 'detect_value_dips')
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_value_dip_flat.py -v`
Expected: FAIL（`get_watch_performance` 不存在 / `sector` 仍在）

- [ ] **Step 3: 重写 `app/services/value_dip.py`**

整文件替换为：

```python
"""价值洼地分析服务 — 盯盘股扁平涨幅 + 高点回退"""
import logging
from app.services.watch_service import WatchService
from app.services.unified_stock_data import unified_stock_data_service

logger = logging.getLogger(__name__)


class ValueDipService:

    @staticmethod
    def get_watch_performance() -> list:
        """盯盘股扁平涨幅明细：每只含 price / change_7d/30d/90d / high_* / pullback_* / market"""
        watch = WatchService.get_watch_list()
        codes = [w['stock_code'] for w in watch]
        name_map = {w['stock_code']: w['stock_name'] for w in watch}
        market_map = {w['stock_code']: w['market'] for w in watch}

        trend_result = unified_stock_data_service.get_trend_data(codes, days=90)
        trend_map = {}
        if trend_result and trend_result.get('stocks'):
            for stock in trend_result['stocks']:
                trend_map[stock['stock_code']] = stock.get('data', [])

        stocks = []
        for code in codes:
            data = trend_map.get(code, [])
            info = ValueDipService._calc_stock_changes(code, name_map.get(code, code), data)
            info['market'] = market_map.get(code)
            stocks.append(info)
        return stocks

    @staticmethod
    def get_pullback_ranking(days: int = 90) -> list:
        """获取所有盯盘股的高点回退排行（回退幅度从大到小）"""
        period_map = {7: '7d', 30: '30d', 90: '90d'}
        period_key = period_map.get(days, '90d')

        try:
            perf = ValueDipService.get_watch_performance()
        except Exception as e:
            logger.error(f'[价值洼地] 高点回退计算失败: {e}')
            return []

        stocks = []
        for s in perf:
            high = s.get(f'high_{period_key}')
            pullback = s.get(f'pullback_{period_key}')
            if high is not None and pullback is not None:
                stocks.append({
                    'code': s['code'],
                    'name': s['name'],
                    'market': s.get('market'),
                    'price': s['price'],
                    'high': high,
                    'pullback_pct': pullback,
                })
        stocks.sort(key=lambda x: x['pullback_pct'])
        return stocks

    @staticmethod
    def _calc_stock_changes(code: str, name: str, data: list) -> dict:
        """从走势数据计算单只股票的各周期涨幅与高点回退"""
        info = {
            'code': code,
            'name': name,
            'price': None,
            'change_7d': None,
            'change_30d': None,
            'change_90d': None,
        }
        if not data:
            return info

        last_close = data[-1].get('close')
        info['price'] = float(last_close) if last_close is not None else None

        for period_key, days in [('7d', 7), ('30d', 30), ('90d', len(data))]:
            if len(data) >= 2:
                idx = max(0, len(data) - days)
                base_price_raw = data[idx].get('close')
                current_price_raw = data[-1].get('close')
                if base_price_raw is not None and current_price_raw is not None:
                    base_price = float(base_price_raw)
                    current_price = float(current_price_raw)
                    if base_price > 0:
                        info[f'change_{period_key}'] = round(
                            (current_price - base_price) / base_price * 100, 2
                        )

        for period_key, period_days in [('7d', 7), ('30d', 30), ('90d', len(data))]:
            period_data = data[-period_days:] if period_days < len(data) else data
            highs = [float(d.get('high', d.get('close'))) for d in period_data
                     if d.get('high') is not None or d.get('close') is not None]
            if highs and info['price'] is not None:
                high_val = max(highs)
                info[f'high_{period_key}'] = round(high_val, 2)
                info[f'pullback_{period_key}'] = round(
                    (info['price'] - high_val) / high_val * 100, 2) if high_val > 0 else 0

        return info
```

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_value_dip_flat.py -v`
Expected: PASS（3 个测试全过）

- [ ] **Step 5: 提交**

```bash
git add app/services/value_dip.py tests/test_value_dip_flat.py && git commit -m "refactor(value-dip): 数据层扁平化，改用盯盘股、删板块/洼地方法"
```

---

### Task 2: 路由 `/api/stocks`（`value_dip.py` routes）

把 `/api/sectors` 改名 `/api/stocks` 返回扁平 `{stocks: [...]}`；`/api/pullback` 保留。

**Files:**
- Modify: `app/routes/value_dip.py`
- Test: `tests/test_value_dip_routes.py`

**Interfaces:**
- Consumes: `ValueDipService.get_watch_performance()`、`ValueDipService.get_pullback_ranking(days)`（Task 1）
- Produces: `GET /value-dip/api/stocks -> {'stocks': [...]}`；`GET /value-dip/api/pullback?days=N -> {'stocks': [...]}`

- [ ] **Step 1: 写失败测试**

新建 `tests/test_value_dip_routes.py`（用轻量 Flask app 直注 blueprint，避免 create_app 副作用）：

```python
from flask import Flask
from app.routes import value_dip_bp
from app.services.value_dip import ValueDipService


def _client(monkeypatch):
    monkeypatch.setattr(ValueDipService, 'get_watch_performance',
                        staticmethod(lambda: [{'code': '300223', 'name': '北京君正',
                                               'market': 'A', 'price': 30.0,
                                               'change_7d': 1.0, 'change_30d': 2.0,
                                               'change_90d': 3.0, 'high_90d': 40.0,
                                               'pullback_90d': -25.0}]))
    monkeypatch.setattr(ValueDipService, 'get_pullback_ranking',
                        staticmethod(lambda days=90: [{'code': '300223', 'name': '北京君正',
                                                       'market': 'A', 'price': 30.0,
                                                       'high': 40.0, 'pullback_pct': -25.0}]))
    app = Flask(__name__)
    app.register_blueprint(value_dip_bp)
    return app.test_client()


def test_api_stocks_flat(monkeypatch):
    c = _client(monkeypatch)
    resp = c.get('/value-dip/api/stocks')
    assert resp.status_code == 200
    body = resp.get_json()
    assert 'stocks' in body
    assert body['stocks'][0]['market'] == 'A'


def test_api_sectors_route_removed(monkeypatch):
    c = _client(monkeypatch)
    assert c.get('/value-dip/api/sectors').status_code == 404


def test_api_pullback_still_works(monkeypatch):
    c = _client(monkeypatch)
    body = c.get('/value-dip/api/pullback?days=90').get_json()
    assert body['stocks'][0]['pullback_pct'] == -25.0
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_value_dip_routes.py -v`
Expected: FAIL（`/api/stocks` 404 / `/api/sectors` 仍 200）

- [ ] **Step 3: 改 `app/routes/value_dip.py`**

整文件替换为：

```python
import logging
from flask import render_template, jsonify, request
from app.routes import value_dip_bp
from app.services.value_dip import ValueDipService

logger = logging.getLogger(__name__)


@value_dip_bp.route('/')
def index():
    return render_template('value_dip.html')


@value_dip_bp.route('/api/stocks')
def stocks():
    try:
        data = ValueDipService.get_watch_performance()
        return jsonify({'stocks': data})
    except Exception as e:
        logger.error(f'[价值洼地] API 错误: {e}')
        return jsonify({'error': str(e)}), 500


@value_dip_bp.route('/api/pullback')
def pullback():
    try:
        days = request.args.get('days', 90, type=int)
        data = ValueDipService.get_pullback_ranking(days)
        return jsonify({'stocks': data})
    except Exception as e:
        logger.error(f'[价值洼地] 高点回退API错误: {e}')
        return jsonify({'error': str(e)}), 500
```

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_value_dip_routes.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add app/routes/value_dip.py tests/test_value_dip_routes.py && git commit -m "refactor(value-dip): 路由 /api/sectors 改 /api/stocks 扁平结构"
```

---

### Task 3: 每日简报删洼地推送、回退推送 sector→market

删除 `_push_value_dip_alert()` + `_format_value_dip_message()` 及第 42 行调用；`_format_pullback_message` 里 `s['sector']` 改 `s['market']`。

**Files:**
- Modify: `app/strategies/daily_briefing/__init__.py`
- Test: `tests/test_value_dip_briefing.py`

**Interfaces:**
- Consumes: `ValueDipService.get_pullback_ranking()`（Task 1）
- Produces: `DailyBriefingStrategy._format_pullback_message(stocks: list) -> str`（用 `market` 字段）

- [ ] **Step 1: 写失败测试**

新建 `tests/test_value_dip_briefing.py`：

```python
from app.strategies.daily_briefing import DailyBriefingStrategy


def test_pullback_message_uses_market():
    stocks = [{'code': '300223', 'name': '北京君正', 'market': 'A',
               'price': 30.0, 'high': 40.0, 'pullback_pct': -25.0}]
    msg = DailyBriefingStrategy._format_pullback_message(stocks)
    assert '北京君正' in msg and 'A' in msg and '-25.0%' in msg


def test_value_dip_push_removed():
    assert not hasattr(DailyBriefingStrategy, '_push_value_dip_alert')
    assert not hasattr(DailyBriefingStrategy, '_format_value_dip_message')
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_value_dip_briefing.py -v`
Expected: FAIL（`_push_value_dip_alert` 仍存在；`_format_pullback_message` 用 `sector` KeyError）

- [ ] **Step 3a: 删第 42 行调用**

删除 `app/strategies/daily_briefing/__init__.py:42` 这一行（保留第 43 行 `self._push_pullback_alert()`）：

```python
        self._push_value_dip_alert()
```

- [ ] **Step 3b: 删 `_push_value_dip_alert` 方法**

删除整段（原第 90–106 行，含 `@staticmethod` 装饰器）：

```python
    @staticmethod
    def _push_value_dip_alert():
        """检测价值洼地并推送 Slack 提醒"""
        from app.services.value_dip import ValueDipService
        from app.services.notification import NotificationService

        try:
            dips = ValueDipService.detect_value_dips()
            if not dips:
                logger.info('[每日简报] 无价值洼地')
                return

            message = DailyBriefingStrategy._format_value_dip_message(dips)
            NotificationService.send_slack(message, 'news_daily')
            logger.info(f'[每日简报] 价值洼地推送: {len(dips)} 条')
        except Exception as e:
            logger.error(f'[每日简报] 价值洼地推送失败: {e}')
```

- [ ] **Step 3c: 删 `_format_value_dip_message` 方法**

删除整段（原第 138–170 行，含 `@staticmethod` 装饰器），即 `def _format_value_dip_message(dips: list) -> str:` 整个方法体到 `return '\n'.join(lines).strip()`。

- [ ] **Step 3d: 改 `_format_pullback_message` 的 sector→market**

把（原第 132 行）：

```python
                f"  · {s['name']}（{s['sector']}）"
```

改为：

```python
                f"  · {s['name']}（{s['market']}）"
```

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_value_dip_briefing.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add app/strategies/daily_briefing/__init__.py tests/test_value_dip_briefing.py && git commit -m "refactor(briefing): 删板块洼地推送，高点回退推送 sector→market"
```

---

### Task 4: 前端纯表格（`value_dip.html` + `value_dip.js`）

页面重写为单张扁平表：列 `股票(名+代码) | 市场 | 现价 | 7d | 30d | 90d | 高点回退`，顶部 7d/30d/90d 周期切换控制「高点回退」列取哪个周期，默认按高点回退升序。删除板块卡片 / 对比图 / 个股走势图。

**Files:**
- Modify: `app/templates/value_dip.html`（整文件重写）
- Modify: `app/static/js/value_dip.js`（整文件重写）

**Interfaces:**
- Consumes: `GET /value-dip/api/stocks`（Task 2）

- [ ] **Step 1: 重写 `app/templates/value_dip.html`**

整文件替换为：

```html
{% extends "base.html" %}
{% block title %}价值洼地{% endblock %}

{% block content %}
<div class="d-flex justify-content-between align-items-center mb-3">
    <h4 class="mb-0">价值洼地</h4>
    <div class="btn-group btn-group-sm" id="period-toggle">
        <button type="button" class="btn btn-outline-primary" data-period="7d">7天</button>
        <button type="button" class="btn btn-primary" data-period="30d">30天</button>
        <button type="button" class="btn btn-outline-primary" data-period="90d">90天</button>
    </div>
</div>

<div class="card">
    <div class="card-body p-0">
        <table class="table table-hover table-sm mb-0 align-middle">
            <thead>
                <tr>
                    <th>股票</th>
                    <th>市场</th>
                    <th class="text-end">现价</th>
                    <th class="text-end">7d</th>
                    <th class="text-end">30d</th>
                    <th class="text-end">90d</th>
                    <th class="text-end" id="pullback-th">30日高点回退</th>
                </tr>
            </thead>
            <tbody id="stock-body">
                <tr><td colspan="7" class="text-center text-muted py-3">加载中...</td></tr>
            </tbody>
        </table>
    </div>
</div>
{% endblock %}

{% block extra_js %}
<script src="{{ url_for('static', filename='js/value_dip.js') }}"></script>
{% endblock %}
```

- [ ] **Step 2: 重写 `app/static/js/value_dip.js`**

整文件替换为：

```javascript
(function() {
    let stocks = [];
    let currentPeriod = '30d';

    document.addEventListener('DOMContentLoaded', () => {
        loadStocks();
        document.getElementById('period-toggle').addEventListener('click', e => {
            const btn = e.target.closest('[data-period]');
            if (!btn) return;
            currentPeriod = btn.dataset.period;
            document.querySelectorAll('#period-toggle .btn').forEach(b => {
                b.classList.toggle('btn-primary', b.dataset.period === currentPeriod);
                b.classList.toggle('btn-outline-primary', b.dataset.period !== currentPeriod);
            });
            render();
        });
    });

    async function loadStocks() {
        try {
            const resp = await fetch('/value-dip/api/stocks');
            const data = await resp.json();
            stocks = data.stocks || [];
            render();
        } catch (e) {
            console.error('加载盯盘股数据失败:', e);
        }
    }

    function fmtChange(v) {
        if (v === null || v === undefined) return '<span class="text-muted">N/A</span>';
        const cls = v >= 0 ? 'text-success' : 'text-danger';
        return `<span class="${cls}">${v >= 0 ? '+' : ''}${v}%</span>`;
    }

    function fmtPullback(v) {
        if (v === null || v === undefined) return '<span class="text-muted">N/A</span>';
        const cls = v < -10 ? 'text-danger fw-bold' : v < -5 ? 'text-danger' : 'text-muted';
        return `<span class="${cls}">${v}%</span>`;
    }

    function esc(s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[c]));
    }

    function render() {
        const tbody = document.getElementById('stock-body');
        const th = document.getElementById('pullback-th');
        const days = { '7d': 7, '30d': 30, '90d': 90 }[currentPeriod];
        if (th) th.textContent = `${days}日高点回退`;

        const pbKey = 'pullback_' + currentPeriod;
        const sorted = [...stocks].sort((a, b) => {
            const av = a[pbKey], bv = b[pbKey];
            if (av === null || av === undefined) return 1;
            if (bv === null || bv === undefined) return -1;
            return av - bv;
        });

        if (!sorted.length) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted py-3">暂无数据</td></tr>';
            return;
        }

        tbody.innerHTML = sorted.map(s => `
            <tr>
                <td>${esc(s.name)}<span class="text-muted small ms-1">${esc(s.code)}</span></td>
                <td>${esc(s.market || '')}</td>
                <td class="text-end">${s.price == null ? '—' : s.price}</td>
                <td class="text-end">${fmtChange(s.change_7d)}</td>
                <td class="text-end">${fmtChange(s.change_30d)}</td>
                <td class="text-end">${fmtChange(s.change_90d)}</td>
                <td class="text-end">${fmtPullback(s[pbKey])}</td>
            </tr>
        `).join('');
    }
})();
```

- [ ] **Step 3: 页面冒烟（route 200 + 无 JS 报错）**

启动应用（`python run.py`），浏览器开 `http://127.0.0.1:5000/value-dip`，确认：
- 表格渲染 12 只盯盘股
- 周期切换 7d/30d/90d 时「高点回退」列表头与数值随之变化、行重新按回退升序排
- 浏览器 console 无报错

- [ ] **Step 4: 提交**

```bash
git add app/templates/value_dip.html app/static/js/value_dip.js && git commit -m "feat(value-dip): 前端改纯扁平表格（盯盘股，去图表）"
```

---

### Task 5: 清理 `VALUE_DIP_SECTORS` + 全量验证

删除 `app/config/stock_codes.py` 的 `VALUE_DIP_SECTORS`，全仓 grep 确认无残留引用，跑全量 pytest。

**Files:**
- Modify: `app/config/stock_codes.py`

- [ ] **Step 1: 删 `VALUE_DIP_SECTORS`**

删除 `app/config/stock_codes.py` 第 73–95 行（`# 价值洼地板块配置` 注释 + 整个 `VALUE_DIP_SECTORS = {...}` 字典）。

- [ ] **Step 2: grep 确认无残留**

Run: `grep -rn "VALUE_DIP_SECTORS\|detect_value_dips\|get_sector_performance\|_push_value_dip_alert\|_format_value_dip_message\|api/sectors" app/ tests/`
Expected: 无输出（全部清除）

- [ ] **Step 3: 跑本特性全部测试**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_value_dip_flat.py tests/test_value_dip_routes.py tests/test_value_dip_briefing.py -v`
Expected: 全 PASS

- [ ] **Step 4: 跑全量 pytest 查无新增报错**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ > .omc/_pytest_out.txt 2>&1; grep -E "passed|failed|error|ModuleNotFoundError|AttributeError" .omc/_pytest_out.txt | tail -20`
Expected: 无新增 failed / ModuleNotFoundError / AttributeError（沿用 dev-environment.md：crawl4ai 进度条走 stdout，结果写文件再 grep）

- [ ] **Step 5: 提交**

```bash
git add app/config/stock_codes.py && git commit -m "chore(value-dip): 删除不再使用的 VALUE_DIP_SECTORS"
```

---

## Self-Review 结果

**Spec coverage**：
- 数据层扁平 + 删板块/洼地方法 → Task 1 ✓
- 路由 `/api/sectors`→`/api/stocks` → Task 2 ✓
- 删板块洼地推送、回退 sector→market → Task 3 ✓
- 前端纯表格、去图表 → Task 4 ✓
- 删 `VALUE_DIP_SECTORS` + 验证 → Task 5 ✓

**Placeholder scan**：无 TBD / 模糊步骤，所有代码步骤含完整代码。

**Type consistency**：`get_watch_performance()` 产出键（`code/name/market/price/change_*/high_*/pullback_*`）在 Task 2 路由测试、Task 4 前端消费处一致；`get_pullback_ranking()` 产出 `market`（非 `sector`）在 Task 3 `_format_pullback_message` 消费处一致；`WatchService.get_watch_list()` 键 `stock_code/stock_name/market` 在 Task 1 实现与测试一致。
