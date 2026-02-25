# 盯盘助手实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现盯盘助手功能，支持多市场实时价格监控、AI 分析关键价位和波动阈值、超阈值 Slack 通知

**Architecture:** 基于现有策略插件系统实现。新建 `WatchList`/`WatchAnalysis` 两个 DB 模型存储盯盘列表和 AI 分析结果。`WatchAssistantStrategy` 继承 `Strategy` 基类，使用 `IntervalTrigger` 实现分钟级调度。前端新建 `/watch` 独立页面。

**Tech Stack:** Flask + SQLAlchemy + APScheduler IntervalTrigger + 智谱 GLM + Bootstrap 5 + 原生 JS

---

## Task 1: 数据模型 — WatchList + WatchAnalysis

**Files:**
- Create: `app/models/watch_list.py`
- Modify: `app/models/__init__.py`

**Step 1: 创建 WatchList 和 WatchAnalysis 模型**

在 `app/models/watch_list.py` 中：

```python
from datetime import datetime, date
from app.extensions import db


class WatchList(db.Model):
    __tablename__ = 'watch_list'
    id = db.Column(db.Integer, primary_key=True)
    stock_code = db.Column(db.String(20), nullable=False, unique=True)
    stock_name = db.Column(db.String(50))
    market = db.Column(db.String(10))
    added_at = db.Column(db.DateTime, default=datetime.utcnow)


class WatchAnalysis(db.Model):
    __tablename__ = 'watch_analysis'
    id = db.Column(db.Integer, primary_key=True)
    stock_code = db.Column(db.String(20), nullable=False)
    analysis_date = db.Column(db.Date, nullable=False)
    support_levels = db.Column(db.Text)
    resistance_levels = db.Column(db.Text)
    volatility_threshold = db.Column(db.Float)
    analysis_summary = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('stock_code', 'analysis_date', name='uq_watch_analysis_code_date'),
    )
```

**Step 2: 注册模型**

在 `app/models/__init__.py` 中添加 import：

```python
from app.models.watch_list import WatchList, WatchAnalysis
```

并添加到 `__all__` 列表。

**Step 3: 验证**

启动应用 `python run.py`，确认 `watch_list` 和 `watch_analysis` 表自动创建（`db.create_all()` 在 `create_app()` 中自动执行）。

**Step 4: Commit**

```bash
git add app/models/watch_list.py app/models/__init__.py
git commit -m "feat(watch): add WatchList and WatchAnalysis models"
```

---

## Task 2: 环境变量配置

**Files:**
- Modify: `app/config/notification_config.py`（或新建 `app/config/watch_config.py`，视现有配置组织方式）
- Modify: `.env.sample`
- Modify: `CLAUDE.md`（开发规范要求同步）
- Modify: `README.md`

**Step 1: 添加配置**

新建 `app/config/watch_config.py`：

```python
import os

WATCH_INTERVAL_MINUTES = int(os.environ.get('WATCH_INTERVAL_MINUTES', '1'))
```

**Step 2: 更新 .env.sample**

添加：

```
# 盯盘助手
WATCH_INTERVAL_MINUTES=1           # 盯盘刷新间隔（分钟）
```

**Step 3: 同步更新 CLAUDE.md 和 README.md**

在环境变量/配置相关章节添加 `WATCH_INTERVAL_MINUTES` 说明。

**Step 4: Commit**

```bash
git add app/config/watch_config.py .env.sample CLAUDE.md README.md
git commit -m "feat(watch): add WATCH_INTERVAL_MINUTES config"
```

---

## Task 3: LLM Prompt 模板

**Files:**
- Create: `app/llm/prompts/watch_analysis.py`
- Modify: `app/llm/router.py` (第9-14行 `TASK_LAYER_MAP`)

**Step 1: 创建 prompt 模板**

在 `app/llm/prompts/watch_analysis.py` 中：

```python
SYSTEM_PROMPT = "你是专业的技术分析师，擅长识别关键支撑位、阻力位和波动特征。用简洁中文回答，数据以JSON格式返回。"


def build_watch_analysis_prompt(stock_name: str, stock_code: str, ohlc_data: list, current_price: float) -> str:
    data_lines = []
    for d in ohlc_data[-30:]:
        data_lines.append(f"{d['date']}: O={d['open']} H={d['high']} L={d['low']} C={d['close']} V={d.get('volume', 'N/A')}")
    data_text = "\n".join(data_lines)

    return f"""分析 {stock_name}({stock_code}) 的技术面，当前价格 {current_price}。

近30日K线数据：
{data_text}

请计算并返回JSON（不要markdown代码块包裹）：
{{
  "support_levels": [支撑位1, 支撑位2],
  "resistance_levels": [阻力位1, 阻力位2],
  "volatility_threshold": 基于近期波动率的合理日内监控阈值（小数，如0.02表示2%），
  "summary": "一句话分析要点"
}}"""
```

**Step 2: 注册 LLM 任务类型**

在 `app/llm/router.py` 的 `TASK_LAYER_MAP` 字典中添加：

```python
'watch_analysis': LLMLayer.FLASH,
```

用 FLASH 层（glm-4-flash）而非 PREMIUM，因为盯盘分析需要为每只股票单独调用，频率较高，控制成本。

**Step 3: Commit**

```bash
git add app/llm/prompts/watch_analysis.py app/llm/router.py
git commit -m "feat(watch): add watch analysis LLM prompt and task type"
```

---

## Task 4: 盯盘服务层 — WatchService

**Files:**
- Create: `app/services/watch_service.py`

**Step 1: 实现 WatchService**

```python
import json
import logging
from datetime import date, datetime

from app.extensions import db
from app.models.watch_list import WatchList, WatchAnalysis
from app.utils.market_identifier import MarketIdentifier

logger = logging.getLogger(__name__)


class WatchService:
    """盯盘助手服务"""

    @staticmethod
    def get_watch_list() -> list[dict]:
        """获取盯盘列表"""
        items = WatchList.query.order_by(WatchList.added_at.desc()).all()
        return [{'id': w.id, 'stock_code': w.stock_code, 'stock_name': w.stock_name,
                 'market': w.market, 'added_at': w.added_at.isoformat()} for w in items]

    @staticmethod
    def add_stock(stock_code: str, stock_name: str = '') -> dict:
        """添加股票到盯盘列表"""
        existing = WatchList.query.filter_by(stock_code=stock_code).first()
        if existing:
            return {'success': False, 'message': '该股票已在盯盘列表中'}

        market = MarketIdentifier.identify(stock_code) or 'A'
        item = WatchList(stock_code=stock_code, stock_name=stock_name, market=market)
        db.session.add(item)
        db.session.commit()
        return {'success': True, 'message': '添加成功'}

    @staticmethod
    def remove_stock(stock_code: str) -> dict:
        """从盯盘列表移除股票"""
        item = WatchList.query.filter_by(stock_code=stock_code).first()
        if not item:
            return {'success': False, 'message': '该股票不在盯盘列表中'}
        db.session.delete(item)
        db.session.commit()
        return {'success': True, 'message': '已移除'}

    @staticmethod
    def get_watch_codes() -> list[str]:
        """获取盯盘列表的股票代码"""
        items = WatchList.query.all()
        return [w.stock_code for w in items]

    @staticmethod
    def get_today_analysis(stock_code: str) -> dict | None:
        """获取今日AI分析结果"""
        today = date.today()
        analysis = WatchAnalysis.query.filter_by(
            stock_code=stock_code, analysis_date=today
        ).first()
        if not analysis:
            return None
        return {
            'stock_code': analysis.stock_code,
            'support_levels': json.loads(analysis.support_levels) if analysis.support_levels else [],
            'resistance_levels': json.loads(analysis.resistance_levels) if analysis.resistance_levels else [],
            'volatility_threshold': analysis.volatility_threshold,
            'summary': analysis.analysis_summary,
        }

    @staticmethod
    def save_analysis(stock_code: str, support_levels: list, resistance_levels: list,
                      volatility_threshold: float, summary: str):
        """保存AI分析结果"""
        today = date.today()
        existing = WatchAnalysis.query.filter_by(
            stock_code=stock_code, analysis_date=today
        ).first()
        if existing:
            existing.support_levels = json.dumps(support_levels)
            existing.resistance_levels = json.dumps(resistance_levels)
            existing.volatility_threshold = volatility_threshold
            existing.analysis_summary = summary
        else:
            analysis = WatchAnalysis(
                stock_code=stock_code, analysis_date=today,
                support_levels=json.dumps(support_levels),
                resistance_levels=json.dumps(resistance_levels),
                volatility_threshold=volatility_threshold,
                analysis_summary=summary,
            )
            db.session.add(analysis)
        db.session.commit()

    @staticmethod
    def get_all_today_analyses() -> dict:
        """获取所有盯盘股票的今日分析结果"""
        today = date.today()
        analyses = WatchAnalysis.query.filter_by(analysis_date=today).all()
        result = {}
        for a in analyses:
            result[a.stock_code] = {
                'support_levels': json.loads(a.support_levels) if a.support_levels else [],
                'resistance_levels': json.loads(a.resistance_levels) if a.resistance_levels else [],
                'volatility_threshold': a.volatility_threshold,
                'summary': a.analysis_summary,
            }
        return result
```

**Step 2: Commit**

```bash
git add app/services/watch_service.py
git commit -m "feat(watch): add WatchService for watch list CRUD and analysis storage"
```

---

## Task 5: 策略插件 — WatchAssistantStrategy

**Files:**
- Create: `app/strategies/watch_assistant/__init__.py`
- Create: `app/strategies/watch_assistant/config.yaml`

**Step 1: 创建策略配置**

`app/strategies/watch_assistant/config.yaml`：

```yaml
default_volatility_threshold: 0.02
notification_cooldown_minutes: 30
```

**Step 2: 实现策略插件**

`app/strategies/watch_assistant/__init__.py`：

```python
import json
import logging
from datetime import datetime

from app.strategies.base import Strategy, Signal
from app.services.trading_calendar import TradingCalendarService
from app.utils.market_identifier import MarketIdentifier

logger = logging.getLogger(__name__)


class WatchAssistantStrategy(Strategy):
    name = "watch_assistant"
    description = "盯盘助手 — 实时监控关注股票的价格波动"
    schedule = ""  # 不用 cron，由 SchedulerEngine 特殊处理为 IntervalTrigger
    needs_llm = True
    enabled = True

    def __init__(self):
        super().__init__()
        self._last_prices = {}
        self._last_notified = {}  # {stock_code: datetime} 通知冷却

    def scan(self) -> list[Signal]:
        from app.services.watch_service import WatchService
        from app.services.unified_stock_data import unified_stock_data_service

        watch_codes = WatchService.get_watch_codes()
        if not watch_codes:
            return []

        # 按市场分组，仅获取当前交易中的市场
        active_codes = []
        for code in watch_codes:
            market = MarketIdentifier.identify(code) or 'A'
            if TradingCalendarService.is_market_open(market):
                active_codes.append(code)

        if not active_codes:
            return []

        # 获取实时价格
        result = unified_stock_data_service.get_realtime_prices(active_codes)
        prices = result.get('prices', [])

        # 获取今日AI分析结果（波动阈值）
        analyses = WatchService.get_all_today_analyses()
        config = self.get_config()
        default_threshold = config.get('default_volatility_threshold', 0.02)
        cooldown = config.get('notification_cooldown_minutes', 30)

        signals = []
        for p in prices:
            code = p.get('code', '')
            current_price = p.get('price', 0)
            if not code or not current_price:
                continue

            last_price = self._last_prices.get(code)
            self._last_prices[code] = current_price

            if last_price is None:
                continue

            # 计算变化幅度
            change_pct = abs(current_price - last_price) / last_price
            analysis = analyses.get(code, {})
            threshold = analysis.get('volatility_threshold') or default_threshold

            if change_pct < threshold:
                continue

            # 通知冷却检查
            last_notify = self._last_notified.get(code)
            if last_notify and (datetime.now() - last_notify).total_seconds() < cooldown * 60:
                continue

            self._last_notified[code] = datetime.now()

            # 构建通知详情
            direction = "上涨" if current_price > last_price else "下跌"
            pct_display = (current_price - last_price) / last_price * 100
            detail_parts = [f"当前价: {current_price:.2f} | 变动: {pct_display:+.2f}%"]

            support = analysis.get('support_levels', [])
            resistance = analysis.get('resistance_levels', [])
            if support:
                nearest_support = min(support, key=lambda x: abs(x - current_price))
                dist = (current_price - nearest_support) / nearest_support * 100
                detail_parts.append(f"距支撑位 {nearest_support}: {dist:+.2f}%")
            if resistance:
                nearest_resist = min(resistance, key=lambda x: abs(x - current_price))
                dist = (current_price - nearest_resist) / nearest_resist * 100
                detail_parts.append(f"距阻力位 {nearest_resist}: {dist:+.2f}%")

            summary = analysis.get('summary', '')
            if summary:
                detail_parts.append(f"AI: {summary}")

            signals.append(Signal(
                strategy=self.name,
                priority="HIGH" if change_pct >= threshold * 2 else "MEDIUM",
                title=f"盯盘提醒 | {p.get('name', code)}({code}) {direction} {pct_display:+.2f}%",
                detail="\n".join(detail_parts),
                data={'stock_code': code, 'price': current_price, 'change_pct': pct_display},
            ))

        return signals
```

**Step 3: Commit**

```bash
git add app/strategies/watch_assistant/__init__.py app/strategies/watch_assistant/config.yaml
git commit -m "feat(watch): add WatchAssistantStrategy plugin"
```

---

## Task 6: 调度引擎适配 IntervalTrigger

**Files:**
- Modify: `app/scheduler/engine.py`

**Step 1: 修改 init_app() 支持 IntervalTrigger**

在 `SchedulerEngine.init_app()` 中，遍历 `registry.active` 时，为 `watch_assistant` 策略使用 `IntervalTrigger`：

```python
from apscheduler.triggers.interval import IntervalTrigger
from app.config.watch_config import WATCH_INTERVAL_MINUTES

# 在 for strategy in registry.active 循环内：
if strategy.name == 'watch_assistant':
    trigger = IntervalTrigger(minutes=WATCH_INTERVAL_MINUTES)
elif not strategy.schedule:
    continue
else:
    trigger = CronTrigger.from_crontab(strategy.schedule)
```

其余逻辑（`add_job`、`_run_strategy`）不变。

**Step 2: Commit**

```bash
git add app/scheduler/engine.py
git commit -m "feat(watch): support IntervalTrigger for watch_assistant in SchedulerEngine"
```

---

## Task 7: 路由 — /watch API 和页面

**Files:**
- Modify: `app/routes/__init__.py` (添加 watch_bp Blueprint 声明)
- Create: `app/routes/watch.py`
- Modify: `app/__init__.py` (注册 Blueprint)

**Step 1: 声明 Blueprint**

在 `app/routes/__init__.py` 中添加：

```python
watch_bp = Blueprint('watch', __name__, url_prefix='/watch')
```

末尾 import 处添加：

```python
from app.routes import watch
```

**Step 2: 注册 Blueprint**

在 `app/__init__.py` 的 `register_blueprint` 区块中添加：

```python
from app.routes import watch_bp
app.register_blueprint(watch_bp)
```

**Step 3: 实现路由**

`app/routes/watch.py`：

```python
import json
import logging
from flask import render_template, request, jsonify

from app.routes import watch_bp
from app.services.watch_service import WatchService
from app.models.stock import Stock

logger = logging.getLogger(__name__)


@watch_bp.route('/')
def index():
    return render_template('watch.html')


@watch_bp.route('/list')
def watch_list():
    items = WatchService.get_watch_list()
    return jsonify({'success': True, 'data': items})


@watch_bp.route('/add', methods=['POST'])
def add_stock():
    data = request.get_json()
    code = data.get('stock_code', '').strip()
    name = data.get('stock_name', '').strip()
    if not code:
        return jsonify({'success': False, 'message': '股票代码不能为空'})
    result = WatchService.add_stock(code, name)
    return jsonify(result)


@watch_bp.route('/remove/<stock_code>', methods=['DELETE'])
def remove_stock(stock_code):
    result = WatchService.remove_stock(stock_code)
    return jsonify(result)


@watch_bp.route('/prices')
def prices():
    from app.services.unified_stock_data import unified_stock_data_service
    codes = WatchService.get_watch_codes()
    if not codes:
        return jsonify({'success': True, 'prices': []})
    result = unified_stock_data_service.get_realtime_prices(codes)
    return jsonify({'success': True, 'prices': result.get('prices', [])})


@watch_bp.route('/analyze', methods=['POST'])
def analyze():
    """触发AI分析（每日首次自动，也可手动触发）"""
    from app.services.unified_stock_data import unified_stock_data_service
    from app.llm.router import llm_router
    from app.llm.prompts.watch_analysis import SYSTEM_PROMPT, build_watch_analysis_prompt

    data = request.get_json() or {}
    force = data.get('force', False)

    codes = WatchService.get_watch_codes()
    if not codes:
        return jsonify({'success': True, 'data': {}, 'message': '盯盘列表为空'})

    # 检查今日是否已有分析
    existing = WatchService.get_all_today_analyses()
    if not force:
        uncalculated = [c for c in codes if c not in existing]
    else:
        uncalculated = codes

    if not uncalculated:
        return jsonify({'success': True, 'data': existing, 'message': '使用今日缓存'})

    # 获取走势数据
    trend_result = unified_stock_data_service.get_trend_data(uncalculated, days=30)
    stocks_data = {s['stock_code']: s for s in trend_result.get('stocks', [])}

    # 获取实时价格
    price_result = unified_stock_data_service.get_realtime_prices(uncalculated)
    prices_map = {p['code']: p for p in price_result.get('prices', [])}

    provider = llm_router.route('watch_analysis')
    results = {}
    for code in uncalculated:
        stock = stocks_data.get(code, {})
        price_info = prices_map.get(code, {})
        ohlc = stock.get('data', [])
        current_price = price_info.get('price', 0)
        stock_name = stock.get('stock_name', '') or price_info.get('name', code)

        if not ohlc or not current_price or not provider:
            continue

        try:
            prompt = build_watch_analysis_prompt(stock_name, code, ohlc, current_price)
            response = provider.chat([
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': prompt},
            ])
            parsed = json.loads(response)
            WatchService.save_analysis(
                stock_code=code,
                support_levels=parsed.get('support_levels', []),
                resistance_levels=parsed.get('resistance_levels', []),
                volatility_threshold=parsed.get('volatility_threshold', 0.02),
                summary=parsed.get('summary', ''),
            )
            results[code] = parsed
        except Exception as e:
            logger.error(f"[盯盘AI] {code} 分析失败: {e}")

    # 合并已有分析
    all_analyses = WatchService.get_all_today_analyses()
    return jsonify({'success': True, 'data': all_analyses})


@watch_bp.route('/analysis')
def get_analysis():
    """获取AI分析结果"""
    analyses = WatchService.get_all_today_analyses()
    return jsonify({'success': True, 'data': analyses})


@watch_bp.route('/stocks/search')
def search_stocks():
    """搜索可添加的股票（从Stock表）"""
    q = request.args.get('q', '').strip()
    if not q:
        stocks = Stock.query.limit(50).all()
    else:
        stocks = Stock.query.filter(
            (Stock.stock_code.contains(q)) | (Stock.stock_name.contains(q))
        ).limit(50).all()
    return jsonify({'success': True, 'data': [
        {'stock_code': s.stock_code, 'stock_name': s.stock_name} for s in stocks
    ]})
```

**Step 4: Commit**

```bash
git add app/routes/__init__.py app/routes/watch.py app/__init__.py
git commit -m "feat(watch): add /watch routes and API endpoints"
```

---

## Task 8: 前端页面 — watch.html + watch.js

**Files:**
- Create: `app/templates/watch.html`
- Create: `app/static/js/watch.js`

**Step 1: 创建 HTML 模板**

`app/templates/watch.html` — 继承 `base.html`，包含：
- 顶部操作栏：添加按钮 + AI分析按钮
- 盯盘卡片列表区域（骨架屏加载）
- 添加股票 Modal（搜索 + 选择）

关键布局结构：

```html
{% extends "base.html" %}
{% block title %}盯盘助手{% endblock %}
{% block content %}
<div class="container mt-3">
    <div class="d-flex justify-content-between align-items-center mb-3">
        <h4 class="mb-0"><i class="bi bi-eye"></i> 盯盘助手</h4>
        <div>
            <button class="btn btn-sm btn-outline-primary" onclick="Watch.triggerAnalysis()">
                <i class="bi bi-robot"></i> AI 分析
            </button>
            <button class="btn btn-sm btn-primary" data-bs-toggle="modal" data-bs-target="#addStockModal">
                <i class="bi bi-plus-lg"></i> 添加
            </button>
        </div>
    </div>
    <div id="watchCards" class="row g-3">
        <!-- 动态渲染 -->
    </div>
</div>

<!-- 添加股票 Modal -->
<div class="modal fade" id="addStockModal">
    <!-- 搜索框 + 股票列表 -->
</div>
{% endblock %}

{% block extra_js %}
<script src="{{ url_for('static', filename='js/watch.js') }}"></script>
{% endblock %}
```

**Step 2: 创建 JS**

`app/static/js/watch.js` — 核心功能：
- `Watch.init()` — 页面加载时获取盯盘列表 + 触发AI分析 + 启动定时刷新
- `Watch.loadList()` — GET /watch/list → 渲染卡片
- `Watch.refreshPrices()` — GET /watch/prices → 更新价格数据
- `Watch.triggerAnalysis(force)` — POST /watch/analyze → 更新AI分析
- `Watch.addStock(code, name)` — POST /watch/add
- `Watch.removeStock(code)` — DELETE /watch/remove/{code}
- `Watch.searchStocks(query)` — GET /watch/stocks/search
- `Watch.startAutoRefresh()` — setInterval 定时刷新
- `Watch.renderCard(stock)` — 单个股票卡片渲染
- 每张卡片显示：股票名/代码、市场标签、实时价格/涨跌幅、支撑位/阻力位、波动阈值、AI摘要、市场状态

**Step 3: Commit**

```bash
git add app/templates/watch.html app/static/js/watch.js
git commit -m "feat(watch): add watch assistant frontend page and JS"
```

---

## Task 9: 导航栏集成

**Files:**
- Modify: `app/templates/base.html` (第24-27行导航栏区域)

**Step 1: 添加导航链接**

在 `base.html` 导航栏中（第25-27行之间），添加盯盘助手链接：

```html
<a class="nav-link" href="{{ url_for('watch.index') }}">盯盘助手</a>
```

放在"预警"和"走势看板"之间。

**Step 2: Commit**

```bash
git add app/templates/base.html
git commit -m "feat(watch): add watch assistant to navbar"
```

---

## Task 10: 集成验证

**Step 1: 完整启动测试**

```bash
python run.py
```

验证：
1. 应用正常启动，无报错
2. 导航栏出现"盯盘助手"链接
3. `/watch` 页面正常加载
4. 添加股票到盯盘列表功能正常
5. AI 分析按钮触发正常
6. 价格实时刷新正常
7. 删除股票功能正常

**Step 2: 调度验证**

查看日志确认：
- `WatchAssistantStrategy` 被 `SchedulerEngine` 正确注册为 IntervalTrigger
- 在交易时段内按配置间隔执行 `scan()`
- 非交易时段跳过执行

**Step 3: 通知验证**

手动测试或等待价格波动超过阈值，确认 Slack 收到通知。

**Step 4: Final Commit**

如有修复，提交最终修正。
