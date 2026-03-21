# 财报估值页面实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 创建独立的财报估值页面，展示股票季度财报与动态PE/PS估值，支持板块过滤和排序。

**Architecture:** 每日调度策略预计算所有股票的市值+季度财报数据写入 `earnings_snapshot` 快照表，前端页面直接读取快照秒开。页面通过板块Toggle开关过滤，两个Tab分别展示利润估值和营收估值视图。

**Tech Stack:** Flask Blueprint + SQLAlchemy + akshare/yfinance + Bootstrap 5 + 原生JS

**Spec:** `docs/superpowers/specs/2026-03-21-earnings-valuation-page-design.md`

---

### Task 1: EarningsSnapshot 数据模型

**Files:**
- Create: `app/models/earnings_snapshot.py`
- Modify: `app/models/__init__.py` — 导入新模型

- [ ] **Step 1: 创建 EarningsSnapshot 模型**

`app/models/earnings_snapshot.py`:

```python
from datetime import datetime, date
from app import db


class EarningsSnapshot(db.Model):
    """财报估值快照 — 每日预计算"""
    __tablename__ = 'earnings_snapshot'
    __table_args__ = (
        db.UniqueConstraint('stock_code', 'snapshot_date', name='uq_earnings_snapshot'),
        db.Index('idx_earnings_snapshot_date', 'snapshot_date'),
    )

    id = db.Column(db.Integer, primary_key=True)
    stock_code = db.Column(db.String(20), nullable=False)
    stock_name = db.Column(db.String(50))
    market_cap = db.Column(db.Float)

    q1_revenue = db.Column(db.Float)
    q2_revenue = db.Column(db.Float)
    q3_revenue = db.Column(db.Float)
    q4_revenue = db.Column(db.Float)
    q1_profit = db.Column(db.Float)
    q2_profit = db.Column(db.Float)
    q3_profit = db.Column(db.Float)
    q4_profit = db.Column(db.Float)

    q1_label = db.Column(db.String(10))
    q2_label = db.Column(db.String(10))
    q3_label = db.Column(db.String(10))
    q4_label = db.Column(db.String(10))

    pe_dynamic = db.Column(db.Float)
    ps_dynamic = db.Column(db.Float)

    snapshot_date = db.Column(db.Date, nullable=False, default=date.today)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'stock_code': self.stock_code,
            'stock_name': self.stock_name,
            'market_cap': self.market_cap,
            'quarters': [self.q1_label, self.q2_label, self.q3_label, self.q4_label],
            'revenue': [self.q1_revenue, self.q2_revenue, self.q3_revenue, self.q4_revenue],
            'profit': [self.q1_profit, self.q2_profit, self.q3_profit, self.q4_profit],
            'pe_dynamic': self.pe_dynamic,
            'ps_dynamic': self.ps_dynamic,
            'updated_at': self.updated_at.strftime('%Y-%m-%d %H:%M') if self.updated_at else None,
        }
```

- [ ] **Step 2: 在 models/__init__.py 中导入**

在 `app/models/__init__.py` 的导入列表中添加 `EarningsSnapshot`。

- [ ] **Step 3: 在 app/__init__.py 中注册模型**

在 `app/__init__.py:229` 的 `from app.models import ...` 行中添加 `EarningsSnapshot`。

- [ ] **Step 4: 验证表创建**

启动应用确认表自动创建无报错：
```bash
python -c "from app import create_app; app = create_app(); app.app_context().push(); from app.models.earnings_snapshot import EarningsSnapshot; print('OK')"
```

- [ ] **Step 5: Commit**

```bash
git add app/models/earnings_snapshot.py app/models/__init__.py app/__init__.py
git commit -m "feat: 添加 EarningsSnapshot 数据模型"
```

---

### Task 2: MarketCapService 市值获取服务

**Files:**
- Create: `app/services/market_cap_service.py`

- [ ] **Step 1: 创建 MarketCapService**

`app/services/market_cap_service.py`:

```python
import logging
from app.utils.market_identifier import MarketIdentifier

logger = logging.getLogger(__name__)


class MarketCapService:
    """获取股票市值"""

    @classmethod
    def get_market_caps(cls, stock_codes: list) -> dict:
        """批量获取市值，返回 {code: market_cap_float}，失败返回 None"""
        result = {}
        a_share_codes = []
        foreign_codes = []

        for code in stock_codes:
            if MarketIdentifier.is_a_share(code):
                a_share_codes.append(code)
            else:
                foreign_codes.append(code)

        # A股批量获取
        for code in a_share_codes:
            try:
                result[code] = cls._get_a_share_market_cap(code)
            except Exception as e:
                logger.warning(f"[市值] A股 {code} 获取失败: {e}")
                result[code] = None

        # 美股/港股逐个获取
        for code in foreign_codes:
            try:
                result[code] = cls._get_foreign_market_cap(code)
            except Exception as e:
                logger.warning(f"[市值] {code} 获取失败: {e}")
                result[code] = None

        return result

    @classmethod
    def _get_a_share_market_cap(cls, code: str) -> float | None:
        """A股市值 — akshare"""
        import akshare as ak
        info = ak.stock_individual_info_em(symbol=code)
        for _, row in info.iterrows():
            if row['item'] == '总市值':
                return float(row['value'])
        return None

    @classmethod
    def _get_foreign_market_cap(cls, code: str) -> float | None:
        """美股/港股市值 — yfinance"""
        import yfinance as yf
        yf_code = MarketIdentifier.to_yfinance(code)
        ticker = yf.Ticker(yf_code)
        info = ticker.info
        return info.get('marketCap')
```

- [ ] **Step 2: 验证**

```bash
python -c "from app.services.market_cap_service import MarketCapService; print(MarketCapService.get_market_caps(['600519']))"
```

- [ ] **Step 3: Commit**

```bash
git add app/services/market_cap_service.py
git commit -m "feat: 添加 MarketCapService 市值获取服务"
```

---

### Task 3: EarningsSnapshot 调度策略

**Files:**
- Create: `app/strategies/earnings_snapshot/__init__.py`
- Create: `app/strategies/earnings_snapshot/config.yaml`

- [ ] **Step 1: 创建策略目录和配置**

`app/strategies/earnings_snapshot/config.yaml`:

```yaml
schedule: "0 8 * * 1-5"
```

- [ ] **Step 2: 创建策略类**

`app/strategies/earnings_snapshot/__init__.py`:

```python
import logging
import re
from datetime import date, datetime, timedelta

from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)


class EarningsSnapshotStrategy(Strategy):
    name = "earnings_snapshot"
    description = "每日财报估值快照预计算"
    schedule = "0 8 * * 1-5"
    needs_llm = False

    def scan(self) -> list[Signal]:
        from flask import current_app
        from app.models import db
        from app.models.stock import Stock
        from app.models.earnings_snapshot import EarningsSnapshot
        from app.services.market_cap_service import MarketCapService
        from app.services.earnings_service import QuarterlyEarningsService
        from app.utils.market_identifier import MarketIdentifier

        today = date.today()
        all_stocks = Stock.query.all()
        codes = [s.stock_code for s in all_stocks if not MarketIdentifier.is_etf(s.stock_code)]
        stock_names = {s.stock_code: s.stock_name for s in all_stocks}

        logger.info(f"[财报快照] 开始计算 {len(codes)} 只股票")

        # 批量获取市值
        market_caps = MarketCapService.get_market_caps(codes)

        success_count = 0
        fail_count = 0

        # 季度标签格式转换: "Q3'25" → "2025Q3"
        def convert_label(label):
            m = re.match(r"Q(\d)'(\d{2})", label or '')
            if m:
                return f"20{m.group(2)}Q{m.group(1)}"
            return label

        for code in codes:
            try:
                cap = market_caps.get(code)
                earnings = QuarterlyEarningsService.get_earnings(code)

                if not earnings:
                    logger.debug(f"[财报快照] {code} 无财报数据，跳过")
                    fail_count += 1
                    continue

                # Q1=最近, Q4=最早（earnings已按时间倒序）
                q_data = []
                for i, e in enumerate(earnings[:4]):
                    q_data.append({
                        'revenue': e.get('revenue'),
                        'profit': e.get('profit'),
                        'label': convert_label(e.get('quarter')),
                    })
                # 补齐不足4个季度
                while len(q_data) < 4:
                    q_data.append({'revenue': None, 'profit': None, 'label': None})

                # 计算动态估值
                q1_profit = q_data[0]['profit']
                q1_revenue = q_data[0]['revenue']
                pe = None
                ps = None
                if cap and q1_profit and q1_profit > 0:
                    pe = round(cap / (q1_profit * 4), 1)
                if cap and q1_revenue and q1_revenue > 0:
                    ps = round(cap / (q1_revenue * 4), 1)

                # Upsert
                snapshot = EarningsSnapshot.query.filter_by(
                    stock_code=code, snapshot_date=today
                ).first()
                if not snapshot:
                    snapshot = EarningsSnapshot(stock_code=code, snapshot_date=today)
                    db.session.add(snapshot)

                snapshot.stock_name = stock_names.get(code, '')
                snapshot.market_cap = cap
                snapshot.q1_revenue = q_data[0]['revenue']
                snapshot.q2_revenue = q_data[1]['revenue']
                snapshot.q3_revenue = q_data[2]['revenue']
                snapshot.q4_revenue = q_data[3]['revenue']
                snapshot.q1_profit = q_data[0]['profit']
                snapshot.q2_profit = q_data[1]['profit']
                snapshot.q3_profit = q_data[2]['profit']
                snapshot.q4_profit = q_data[3]['profit']
                snapshot.q1_label = q_data[0]['label']
                snapshot.q2_label = q_data[1]['label']
                snapshot.q3_label = q_data[2]['label']
                snapshot.q4_label = q_data[3]['label']
                snapshot.pe_dynamic = pe
                snapshot.ps_dynamic = ps
                snapshot.updated_at = datetime.utcnow()

                db.session.commit()
                success_count += 1

            except Exception as e:
                db.session.rollback()
                logger.error(f"[财报快照] {code} 处理失败: {e}")
                fail_count += 1

        # 清理7天前的快照
        cutoff = today - timedelta(days=7)
        deleted = EarningsSnapshot.query.filter(
            EarningsSnapshot.snapshot_date < cutoff
        ).delete()
        db.session.commit()
        if deleted:
            logger.info(f"[财报快照] 清理 {deleted} 条过期快照")

        logger.info(f"[财报快照] 完成: 成功 {success_count}, 失败 {fail_count}")
        return [Signal(
            strategy=self.name,
            priority="LOW",
            title="财报快照更新完成",
            detail=f"成功 {success_count} 只, 失败 {fail_count} 只",
            data={'success': success_count, 'fail': fail_count}
        )]
```

- [ ] **Step 3: 验证策略注册**

```bash
python -c "from app import create_app; app = create_app(); app.app_context().push(); from app.strategies.registry import registry; s = registry.get('earnings_snapshot'); print(s.name, s.schedule)"
```

- [ ] **Step 4: Commit**

```bash
git add app/strategies/earnings_snapshot/
git commit -m "feat: 添加财报快照每日预计算策略"
```

---

### Task 4: 后端路由

**Files:**
- Create: `app/routes/earnings_page.py`
- Modify: `app/routes/__init__.py` — 声明 Blueprint
- Modify: `app/__init__.py` — 注册 Blueprint

- [ ] **Step 1: 在 routes/__init__.py 声明 Blueprint**

在 `app/routes/__init__.py:18`（`news_bp` 之后）添加：

```python
earnings_page_bp = Blueprint('earnings_page', __name__, url_prefix='/earnings')
```

在末尾 import 行追加 `earnings_page`。

- [ ] **Step 2: 创建路由文件**

`app/routes/earnings_page.py`:

```python
import logging
from datetime import date
from threading import Thread

from flask import render_template, request, jsonify, current_app

from app.routes import earnings_page_bp
from app.models import db
from app.models.earnings_snapshot import EarningsSnapshot
from app.models.category import Category, StockCategory
from app.models.stock import Stock
from app.utils.market_identifier import MarketIdentifier

logger = logging.getLogger(__name__)


def _get_categories_with_position():
    """获取所有顶级分类，标记哪些有持仓"""
    from app.models.position import Position
    categories = Category.query.filter_by(parent_id=None).all()

    # 当前持仓的股票代码
    latest_date = db.session.query(db.func.max(Position.date)).scalar()
    held_codes = set()
    if latest_date:
        positions = Position.query.filter_by(date=latest_date).all()
        held_codes = {p.stock_code for p in positions if p.quantity and p.quantity > 0}

    # 各分类的股票代码
    all_sc = StockCategory.query.all()
    cat_codes = {}
    for sc in all_sc:
        cat_id = sc.category_id
        if cat_id:
            cat_codes.setdefault(cat_id, set()).add(sc.stock_code)

    result = []
    for cat in categories:
        cat_ids = [cat.id] + [c.id for c in cat.children]
        codes = set()
        for cid in cat_ids:
            codes |= cat_codes.get(cid, set())

        a_share_codes = {c for c in codes if MarketIdentifier.is_a_share(c)}
        has_position = bool(codes & held_codes)

        result.append({
            'id': cat.id,
            'name': cat.name,
            'count': len(a_share_codes | {c for c in codes if not MarketIdentifier.is_a_share(c)}),
            'has_position': has_position,
        })

    return result


@earnings_page_bp.route('/')
def index():
    categories = _get_categories_with_position()
    return render_template('earnings_page.html', categories=categories)


@earnings_page_bp.route('/api/data')
def get_data():
    cat_ids_str = request.args.get('categories', '')
    sort_field = request.args.get('sort', 'pe_dynamic')
    order = request.args.get('order', 'asc')

    if sort_field not in ('pe_dynamic', 'ps_dynamic'):
        sort_field = 'pe_dynamic'

    # 解析板块ID
    cat_ids = []
    if cat_ids_str:
        cat_ids = [int(x) for x in cat_ids_str.split(',') if x.strip().isdigit()]

    # 查快照：优先今天，否则最近一天
    today = date.today()
    snapshot_date = db.session.query(db.func.max(EarningsSnapshot.snapshot_date)).filter(
        EarningsSnapshot.snapshot_date <= today
    ).scalar()

    if not snapshot_date:
        return jsonify({'categories': [], 'stocks': [], 'snapshot_date': None, 'is_today': False})

    # 按板块过滤股票代码
    filtered_codes = None
    if cat_ids:
        # 包含子分类
        all_cat_ids = list(cat_ids)
        for cid in cat_ids:
            cat = Category.query.get(cid)
            if cat:
                all_cat_ids.extend([c.id for c in cat.children])

        scs = StockCategory.query.filter(StockCategory.category_id.in_(all_cat_ids)).all()
        filtered_codes = {sc.stock_code for sc in scs}

    # 查询快照
    query = EarningsSnapshot.query.filter_by(snapshot_date=snapshot_date)
    if filtered_codes is not None:
        query = query.filter(EarningsSnapshot.stock_code.in_(filtered_codes))

    # 排序（NULL 排最后）
    sort_col = getattr(EarningsSnapshot, sort_field)
    if order == 'desc':
        query = query.order_by(db.case((sort_col.is_(None), 1), else_=0), sort_col.desc())
    else:
        query = query.order_by(db.case((sort_col.is_(None), 1), else_=0), sort_col.asc())

    snapshots = query.all()

    # 分类列表
    categories = _get_categories_with_position()

    return jsonify({
        'categories': categories,
        'stocks': [s.to_dict() for s in snapshots],
        'snapshot_date': snapshot_date.isoformat(),
        'is_today': snapshot_date == today,
    })


@earnings_page_bp.route('/api/refresh', methods=['POST'])
def refresh():
    """异步触发快照重新计算"""
    app = current_app._get_current_object()

    def _run():
        with app.app_context():
            from app.strategies.earnings_snapshot import EarningsSnapshotStrategy
            strategy = EarningsSnapshotStrategy()
            strategy.scan()

    Thread(target=_run, daemon=True).start()
    return jsonify({'message': '正在刷新，请稍后刷新页面查看'}), 202
```

- [ ] **Step 3: 在 app/__init__.py 注册 Blueprint**

在 `app/__init__.py:210` 的 import 行添加 `earnings_page_bp`，在 `app.register_blueprint(news_bp)` 后添加：

```python
app.register_blueprint(earnings_page_bp)
```

- [ ] **Step 4: 验证路由**

```bash
python -c "from app import create_app; app = create_app(); print([r.rule for r in app.url_map.iter_rules() if '/earnings' in r.rule])"
```

预期输出包含 `/earnings/`, `/earnings/api/data`, `/earnings/api/refresh`。

- [ ] **Step 5: Commit**

```bash
git add app/routes/earnings_page.py app/routes/__init__.py app/__init__.py
git commit -m "feat: 添加财报估值页面路由"
```

---

### Task 5: 前端页面模板

**Files:**
- Create: `app/templates/earnings_page.html`

- [ ] **Step 1: 创建页面模板**

`app/templates/earnings_page.html`（参考 `alert.html` 结构）：

```html
{% extends 'base.html' %}

{% block title %}财报估值{% endblock %}

{% block extra_css %}
<link rel="stylesheet" href="{{ url_for('static', filename='css/earnings-page.css') }}">
{% endblock %}

{% block content %}
<div class="page-header mb-4">
    <div class="d-flex justify-content-between align-items-center">
        <div>
            <h4 class="mb-1"><i class="bi bi-bar-chart-line"></i> 财报估值</h4>
            <small class="text-muted" id="snapshotInfo">加载中...</small>
        </div>
        <div class="header-actions">
            <button class="btn btn-outline-primary btn-sm" id="refreshBtn">
                <i class="bi bi-arrow-clockwise"></i> 刷新数据
            </button>
        </div>
    </div>
</div>

<!-- 板块过滤 -->
<div class="filter-section mb-3">
    <div class="filter-group">
        <label class="filter-label">板块筛选</label>
        <div class="category-toggle-group" id="categoryToggleFilter"></div>
    </div>
</div>

<!-- Tab 切换 -->
<div class="earnings-tabs mb-3">
    <button class="tab-btn active" data-tab="profit" id="tabProfit">按利润估值</button>
    <button class="tab-btn" data-tab="revenue" id="tabRevenue">按营收估值</button>
</div>

<!-- 骨架屏 -->
<div id="loadingState" class="py-3">
    <table class="table earnings-table">
        <thead>
            <tr>
                <th>代码</th><th>名称</th><th>市值</th>
                <th>Q1</th><th>Q2</th><th>Q3</th><th>Q4</th><th>估值比</th>
            </tr>
        </thead>
        <tbody>
            {% for _ in range(8) %}
            <tr>
                {% for _ in range(8) %}
                <td><div class="skeleton skeleton-text"></div></td>
                {% endfor %}
            </tr>
            {% endfor %}
        </tbody>
    </table>
</div>

<!-- 空状态 -->
<div id="emptyState" class="text-center py-5 d-none">
    <i class="bi bi-inbox text-muted" style="font-size: 3rem;"></i>
    <p class="mt-3 text-muted">暂无数据，请点击"刷新数据"生成快照</p>
</div>

<!-- 数据表格 -->
<div id="dataContainer" class="d-none">
    <table class="table earnings-table" id="earningsTable">
        <thead>
            <tr id="tableHeader"></tr>
        </thead>
        <tbody id="tableBody"></tbody>
    </table>
</div>

<script>
    const INITIAL_CATEGORIES = {{ categories | tojson }};
</script>
{% endblock %}

{% block extra_js %}
<script src="{{ url_for('static', filename='js/earnings-page.js') }}"></script>
{% endblock %}
```

- [ ] **Step 2: Commit**

```bash
git add app/templates/earnings_page.html
git commit -m "feat: 添加财报估值页面模板"
```

---

### Task 6: 前端 CSS 样式

**Files:**
- Create: `app/static/css/earnings-page.css`

- [ ] **Step 1: 创建样式文件**

`app/static/css/earnings-page.css`：

复用预警中心的 Toggle 样式（`.category-toggle-group`, `.category-toggle`, `.toggle-switch`, `.toggle-slider`），参考 `alert.css:111-180`。新增：

```css
/* Tab 切换 */
.earnings-tabs {
    display: flex;
    gap: 0;
    border-bottom: 2px solid #e5e7eb;
}

.tab-btn {
    padding: 0.5rem 1.5rem;
    border: none;
    background: none;
    color: #6b7280;
    font-size: 0.875rem;
    cursor: pointer;
    border-bottom: 2px solid transparent;
    margin-bottom: -2px;
    transition: all 0.2s;
}

.tab-btn.active {
    color: #3b82f6;
    border-bottom-color: #3b82f6;
    font-weight: 600;
}

.tab-btn:hover:not(.active) {
    color: #374151;
}

/* 表格 */
.earnings-table {
    width: 100%;
    font-size: 0.8125rem;
}

.earnings-table th {
    font-weight: 600;
    color: #6b7280;
    border-bottom: 1px solid #e5e7eb;
    padding: 0.5rem 0.75rem;
    white-space: nowrap;
    cursor: pointer;
    user-select: none;
}

.earnings-table th:hover {
    color: #374151;
}

.earnings-table th.sorted {
    color: #3b82f6;
}

.earnings-table th .sort-icon {
    margin-left: 4px;
    font-size: 0.75rem;
}

.earnings-table td {
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid #f3f4f6;
    white-space: nowrap;
}

.earnings-table td.stock-code {
    font-family: monospace;
    color: #6b7280;
}

.earnings-table td.stock-name {
    font-weight: 500;
}

.earnings-table td.number {
    text-align: right;
    font-variant-numeric: tabular-nums;
}

.earnings-table td.valuation {
    text-align: right;
    font-weight: 600;
    color: #3b82f6;
}

.earnings-table td.loss {
    color: #ef4444;
    font-weight: normal;
}

/* 板块 Toggle — 复用 alert.css 模式 */
.category-toggle-group {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
}

.category-toggle {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.375rem 0.75rem;
    background: #fff;
    border: 1px solid #e5e7eb;
    border-radius: 20px;
    transition: border-color 0.2s;
}

.category-toggle.is-on {
    border-color: #3b82f6;
}

.category-toggle .toggle-label {
    font-size: 0.8125rem;
    color: #4b5563;
    user-select: none;
}

.category-toggle.is-on .toggle-label {
    color: #1f2937;
}

.toggle-switch {
    position: relative;
    display: inline-block;
    width: 36px;
    height: 20px;
}

.toggle-switch input {
    opacity: 0;
    width: 0;
    height: 0;
}

.toggle-slider {
    position: absolute;
    cursor: pointer;
    top: 0; left: 0; right: 0; bottom: 0;
    background-color: #d1d5db;
    border-radius: 20px;
    transition: background-color 0.2s;
}

.toggle-slider:before {
    position: absolute;
    content: "";
    height: 16px;
    width: 16px;
    left: 2px;
    bottom: 2px;
    background-color: #fff;
    border-radius: 50%;
    transition: transform 0.2s;
}

.toggle-switch input:checked + .toggle-slider {
    background-color: #3b82f6;
}

.toggle-switch input:checked + .toggle-slider:before {
    transform: translateX(16px);
}

/* 骨架屏 */
.skeleton {
    background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
    background-size: 200% 100%;
    animation: shimmer 1.5s infinite;
    border-radius: 4px;
    height: 1rem;
}

@keyframes shimmer {
    0% { background-position: 200% 0; }
    100% { background-position: -200% 0; }
}

/* 筛选区 */
.filter-section {
    padding: 0.75rem 0;
}

.filter-label {
    font-size: 0.75rem;
    color: #9ca3af;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.5rem;
    display: block;
}

/* 刷新提示 */
.refresh-toast {
    position: fixed;
    top: 1rem;
    right: 1rem;
    padding: 0.75rem 1.5rem;
    background: #3b82f6;
    color: #fff;
    border-radius: 8px;
    font-size: 0.875rem;
    z-index: 9999;
    animation: fadeIn 0.3s;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(-10px); }
    to { opacity: 1; transform: translateY(0); }
}
```

- [ ] **Step 2: Commit**

```bash
git add app/static/css/earnings-page.css
git commit -m "feat: 添加财报估值页面样式"
```

---

### Task 7: 前端 JavaScript

**Files:**
- Create: `app/static/js/earnings-page.js`

- [ ] **Step 1: 创建 EarningsPage JS**

`app/static/js/earnings-page.js`:

```javascript
const EarningsPage = {
    data: { categories: [], stocks: [] },
    config: {
        enabledCategories: new Set(),
        activeTab: 'profit',  // 'profit' | 'revenue'
        sortField: 'pe_dynamic',
        sortOrder: 'asc',
    },

    init() {
        this.loadConfig();
        this.initCategories();
        this.bindEvents();
        this.fetchData();
    },

    // --- 配置持久化 ---
    loadConfig() {
        try {
            const saved = JSON.parse(localStorage.getItem('earningsPageConfig'));
            if (saved) {
                this.config.enabledCategories = new Set(saved.enabledCategories || []);
                this.config.activeTab = saved.activeTab || 'profit';
            }
        } catch (e) { /* ignore */ }
    },

    saveConfig() {
        localStorage.setItem('earningsPageConfig', JSON.stringify({
            enabledCategories: [...this.config.enabledCategories],
            activeTab: this.config.activeTab,
        }));
    },

    // --- 板块 Toggle ---
    initCategories() {
        const cats = typeof INITIAL_CATEGORIES !== 'undefined' ? INITIAL_CATEGORIES : [];
        this.data.categories = cats;

        // 首次访问：默认启用有持仓的板块
        if (this.config.enabledCategories.size === 0) {
            cats.forEach(c => {
                if (c.has_position) this.config.enabledCategories.add(c.id);
            });
            this.saveConfig();
        }

        this.renderToggles();
    },

    renderToggles() {
        const container = document.getElementById('categoryToggleFilter');
        if (!container) return;

        container.innerHTML = this.data.categories.map(cat => {
            const isOn = this.config.enabledCategories.has(cat.id);
            return `
                <div class="category-toggle ${isOn ? 'is-on' : ''}" data-id="${cat.id}">
                    <span class="toggle-label">${cat.name} (${cat.count})</span>
                    <label class="toggle-switch">
                        <input type="checkbox" ${isOn ? 'checked' : ''}>
                        <span class="toggle-slider"></span>
                    </label>
                </div>
            `;
        }).join('');

        container.querySelectorAll('.category-toggle input[type="checkbox"]').forEach(cb => {
            cb.addEventListener('change', (e) => {
                const toggle = e.target.closest('.category-toggle');
                const catId = Number(toggle.dataset.id);
                if (e.target.checked) {
                    this.config.enabledCategories.add(catId);
                    toggle.classList.add('is-on');
                } else {
                    this.config.enabledCategories.delete(catId);
                    toggle.classList.remove('is-on');
                }
                this.saveConfig();
                this.fetchData();
            });
        });
    },

    // --- Tab 切换 ---
    bindEvents() {
        document.getElementById('tabProfit')?.addEventListener('click', () => this.switchTab('profit'));
        document.getElementById('tabRevenue')?.addEventListener('click', () => this.switchTab('revenue'));
        document.getElementById('refreshBtn')?.addEventListener('click', () => this.refresh());
    },

    switchTab(tab) {
        this.config.activeTab = tab;
        this.config.sortField = tab === 'profit' ? 'pe_dynamic' : 'ps_dynamic';
        this.config.sortOrder = 'asc';

        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.getElementById(tab === 'profit' ? 'tabProfit' : 'tabRevenue')?.classList.add('active');

        this.saveConfig();
        this.renderTable();
    },

    // --- 数据获取 ---
    async fetchData() {
        const catIds = [...this.config.enabledCategories].join(',');
        const url = `/earnings/api/data?categories=${catIds}&sort=${this.config.sortField}&order=${this.config.sortOrder}`;

        document.getElementById('loadingState')?.classList.remove('d-none');
        document.getElementById('dataContainer')?.classList.add('d-none');
        document.getElementById('emptyState')?.classList.add('d-none');

        try {
            const resp = await fetch(url);
            const data = await resp.json();
            this.data.stocks = data.stocks || [];
            this.data.categories = data.categories || this.data.categories;

            // 更新快照信息
            const info = document.getElementById('snapshotInfo');
            if (info) {
                if (data.snapshot_date) {
                    const status = data.is_today ? '' : ' (非今日数据)';
                    info.textContent = `快照日期: ${data.snapshot_date}${status}`;
                } else {
                    info.textContent = '暂无快照数据';
                }
            }

            document.getElementById('loadingState')?.classList.add('d-none');

            if (this.data.stocks.length === 0) {
                document.getElementById('emptyState')?.classList.remove('d-none');
            } else {
                document.getElementById('dataContainer')?.classList.remove('d-none');
                this.renderTable();
            }
        } catch (e) {
            console.error('获取数据失败:', e);
            document.getElementById('loadingState')?.classList.add('d-none');
            document.getElementById('emptyState')?.classList.remove('d-none');
        }
    },

    // --- 表格渲染 ---
    renderTable() {
        const isProfit = this.config.activeTab === 'profit';
        const stocks = this.sortStocks([...this.data.stocks]);

        // 表头
        const header = document.getElementById('tableHeader');
        const qLabels = stocks.length > 0 ? stocks[0].quarters : ['Q1', 'Q2', 'Q3', 'Q4'];
        const dataLabel = isProfit ? '利润' : '营收';
        const valuationLabel = isProfit ? 'PE动态' : 'PS动态';
        const valuationField = isProfit ? 'pe_dynamic' : 'ps_dynamic';

        header.innerHTML = `
            <th>代码</th>
            <th>名称</th>
            <th class="number" data-sort="market_cap">市值</th>
            ${qLabels.map((q, i) => `<th class="number">${q || 'Q' + (i + 1)}${dataLabel}</th>`).join('')}
            <th class="number sorted" data-sort="${valuationField}">${valuationLabel} <span class="sort-icon">${this.config.sortOrder === 'asc' ? '↑' : '↓'}</span></th>
        `;

        // 绑定列头排序
        header.querySelectorAll('th[data-sort]').forEach(th => {
            th.addEventListener('click', () => {
                const field = th.dataset.sort;
                if (this.config.sortField === field) {
                    this.config.sortOrder = this.config.sortOrder === 'asc' ? 'desc' : 'asc';
                } else {
                    this.config.sortField = field;
                    this.config.sortOrder = 'asc';
                }
                this.renderTable();
            });
        });

        // 表体
        const body = document.getElementById('tableBody');
        body.innerHTML = stocks.map(s => {
            const values = isProfit ? s.profit : s.revenue;
            const valuation = isProfit ? s.pe_dynamic : s.ps_dynamic;
            return `
                <tr>
                    <td class="stock-code">${s.stock_code}</td>
                    <td class="stock-name">${s.stock_name}</td>
                    <td class="number">${this.formatMarketCap(s.market_cap)}</td>
                    ${values.map(v => `<td class="number">${this.formatAmount(v)}</td>`).join('')}
                    <td class="${valuation != null ? 'valuation' : 'loss'}">${valuation != null ? valuation.toFixed(1) : '亏损'}</td>
                </tr>
            `;
        }).join('');
    },

    sortStocks(stocks) {
        const field = this.config.sortField;
        const asc = this.config.sortOrder === 'asc';
        return stocks.sort((a, b) => {
            const va = a[field], vb = b[field];
            // NULL 排最后
            if (va == null && vb == null) return 0;
            if (va == null) return 1;
            if (vb == null) return -1;
            return asc ? va - vb : vb - va;
        });
    },

    // --- 格式化 ---
    formatMarketCap(val) {
        if (val == null) return '-';
        if (val >= 1e12) return (val / 1e12).toFixed(2) + '万亿';
        if (val >= 1e8) return (val / 1e8).toFixed(0) + '亿';
        if (val >= 1e4) return (val / 1e4).toFixed(0) + '万';
        return val.toFixed(0);
    },

    formatAmount(val) {
        if (val == null) return '-';
        if (Math.abs(val) >= 1e8) return (val / 1e8).toFixed(1) + '亿';
        if (Math.abs(val) >= 1e4) return (val / 1e4).toFixed(0) + '万';
        return val.toFixed(0);
    },

    // --- 刷新 ---
    async refresh() {
        try {
            const resp = await fetch('/earnings/api/refresh', { method: 'POST' });
            const data = await resp.json();
            const toast = document.createElement('div');
            toast.className = 'refresh-toast';
            toast.textContent = data.message || '正在刷新...';
            document.body.appendChild(toast);
            setTimeout(() => toast.remove(), 3000);
        } catch (e) {
            console.error('刷新失败:', e);
        }
    },
};

document.addEventListener('DOMContentLoaded', () => EarningsPage.init());
```

- [ ] **Step 2: Commit**

```bash
git add app/static/js/earnings-page.js
git commit -m "feat: 添加财报估值页面前端逻辑"
```

---

### Task 8: 导航栏集成

**Files:**
- Modify: `app/templates/base.html` — 侧边栏新增"财报估值"入口

- [ ] **Step 1: 在 base.html 导航栏添加入口**

在 `app/templates/base.html` 的顶层导航（`走势看板` 和 `交易策略` 之间，或 `交易策略` 之后），添加：

```html
<a class="nav-link" href="{{ url_for('earnings_page.index') }}">财报估值</a>
```

- [ ] **Step 2: 验证页面可访问**

启动应用，访问 `http://127.0.0.1:5000/earnings/`，确认页面正常渲染，导航栏有"财报估值"入口。

- [ ] **Step 3: Commit**

```bash
git add app/templates/base.html
git commit -m "feat: 导航栏添加财报估值入口"
```

---

### Task 9: 端到端验证

- [ ] **Step 1: 手动触发快照生成**

访问页面点击"刷新数据"按钮，或通过命令行：

```bash
python -c "
from app import create_app
app = create_app()
with app.app_context():
    from app.strategies.earnings_snapshot import EarningsSnapshotStrategy
    s = EarningsSnapshotStrategy()
    signals = s.scan()
    print(signals)
"
```

- [ ] **Step 2: 验证页面数据展示**

1. 刷新 `/earnings/` 页面
2. 确认板块Toggle默认选中有持仓的板块
3. 确认表格显示股票数据，利润Tab有PE动态列
4. 切换到"按营收估值"Tab，确认列变为营收+PS动态
5. 点击列头验证排序功能
6. 切换板块Toggle验证过滤功能

- [ ] **Step 3: Commit（如有修复）**

```bash
git add -u
git commit -m "fix: 财报估值页面端到端修复"
```
