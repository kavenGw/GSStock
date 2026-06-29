# 盯盘公司自动并入「我的公司」新闻关键字 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让盯盘池（`WATCH_CODES`）里的公司自动并入「我的公司」新闻关键字，既被主动爬取新闻、也出现在「公司」标签页过滤里，免去两处重复维护。

**Architecture:** 方案 A —— 启动时幂等 seed `WATCH_CODES` 进 `company_keyword` 表，新增 `source` 列区分 `manual`/`watch`。`WATCH_CODES` 仍是唯一权威源，DB 行只是它的同步投影；爬虫轮转调度与「公司」标签页过滤零改动复用。UI 对 `source='watch'` 行只读展示、带「盯盘」徽标、无删除按钮，路由层加服务端守卫防绕过。

**Tech Stack:** Flask + Flask-SQLAlchemy + SQLite（`data/stock.db` 公共库）、pytest、原生 JS 模板（`app/static/js/news.js`）。

设计来源：`docs/superpowers/specs/2026-06-29-watch-companies-into-news-keywords-design.md`

## Global Constraints

- 响应中文；不写多余注释；不写 backup 文件（git 留痕足够）。
- 所有 `git` / `pytest` 命令前加 `rtk`，链式 `&&` 中也要；env 赋值（`PYTHONIOENCODING` / `SCHEDULER_ENABLED`）必须在 `rtk` 之前。
- 单测命令：`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ -v`。
- 单测平铺在 `tests/test_*.py`，不建子目录。
- `git add` 与 `git commit` 放进同一条 Bash 命令链（并行 session 会抢 index）；提交后 `rtk git show --stat <sha>` 核对只含本任务文件。
- `company_keyword` 表在默认库 `data/stock.db`（`CompanyKeyword` 无 `__bind_key__`），用 `db.engine`（默认 bind）操作，**不要**连 `private`。
- `source` 取值仅 `'manual'` | `'watch'`，列默认 `'manual'`。
- `WATCH_CODES` 是盯盘唯一权威源；DB 的 watch 行是同步投影，每次启动由 seed 重建，不得反向改写 `WATCH_CODES`。

---

### Task 1: `CompanyKeyword` 加 `source` 列（模型 + 迁移）

为 `company_keyword` 表加 `source` 列。模型声明默认 `'manual'`；对已存在的旧库用幂等 `ALTER TABLE` 迁移补列（仿照现有 `migrate_*` 的 inspector 守卫模式）。

**Files:**
- Modify: `app/models/news.py:37-44`（`CompanyKeyword` 类）
- Modify: `app/__init__.py`（新增 `migrate_company_keyword_table()`，紧跟 `migrate_wyckoff_table()` 定义之后；并在调用块 `app/__init__.py:294` 之后加调用）
- Test: `tests/test_watch_companies_seed.py`

**Interfaces:**
- Produces:
  - `CompanyKeyword.source`：`db.Column(db.String(10), default='manual')`
  - `migrate_company_keyword_table() -> None`（幂等：列已存在则 no-op，表不存在则静默 return）

- [ ] **Step 1: 写失败测试**

在 `tests/test_watch_companies_seed.py` 写入文件头 + 第一个测试。`app_ctx` fixture 建一个独立的文件型 sqlite Flask app（避免污染 `data/stock.db`，避免 `:memory:` 多连接陷阱）：

```python
import pytest
from flask import Flask


@pytest.fixture
def app_ctx(tmp_path):
    """独立 sqlite Flask app，含 company_keyword 表，隔离于 data/stock.db。"""
    from app import db
    import app.models.news  # noqa: F401  注册模型到 metadata
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{tmp_path}/t.db'
    app.config['SQLALCHEMY_BINDS'] = {'private': f'sqlite:///{tmp_path}/tp.db'}
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()


def test_company_keyword_source_defaults_manual(app_ctx):
    from app import db
    from app.models.news import CompanyKeyword
    c = CompanyKeyword(name='测试公司')
    db.session.add(c)
    db.session.commit()
    assert c.source == 'manual'
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_companies_seed.py -v`
Expected: FAIL —— `AttributeError: 'CompanyKeyword' object has no attribute 'source'` 或 `c.source` 为 `None`（列尚未声明）。

- [ ] **Step 3: 模型加列**

`app/models/news.py`，在 `CompanyKeyword` 类 `created_at` 行之后加：

```python
    source = db.Column(db.String(10), default='manual')
```

改后该类应为：

```python
class CompanyKeyword(db.Model):
    __tablename__ = 'company_keyword'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    last_fetched_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    source = db.Column(db.String(10), default='manual')
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_companies_seed.py -v`
Expected: PASS。

- [ ] **Step 5: 加迁移函数 + 幂等测试**

`app/__init__.py`，在 `migrate_wyckoff_table()` 定义之后新增（默认 bind，inspector 守卫）：

```python
def migrate_company_keyword_table():
    """迁移 company_keyword 表：添加 source 列"""
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    try:
        columns = [col['name'] for col in inspector.get_columns('company_keyword')]
    except Exception:
        return

    if 'source' in columns:
        return

    logging.info("迁移 company_keyword 表: 添加 source 列")
    with db.engine.connect() as conn:
        conn.execute(text("ALTER TABLE company_keyword ADD COLUMN source VARCHAR(10) DEFAULT 'manual'"))
        conn.commit()
    logging.info("company_keyword 表迁移完成")
```

在 `tests/test_watch_companies_seed.py` 追加幂等测试（列已存在时 no-op、不抛错）：

```python
def test_migrate_company_keyword_idempotent(app_ctx):
    from app import migrate_company_keyword_table
    migrate_company_keyword_table()
    migrate_company_keyword_table()  # 连跑两次不抛错
```

- [ ] **Step 6: 接线迁移调用**

`app/__init__.py:294`，在 `migrate_wyckoff_table()` 调用之后加一行：

```python
        migrate_wyckoff_table()
        migrate_company_keyword_table()
```

- [ ] **Step 7: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_companies_seed.py -v`
Expected: 2 passed。

- [ ] **Step 8: Commit**

```bash
rtk git add app/models/news.py app/__init__.py tests/test_watch_companies_seed.py && rtk git commit -m "feat(news): company_keyword 加 source 列 + 幂等迁移"
```

---

### Task 2: `seed_watch_companies()` 同步盯盘公司进表

新建幂等 seed：把 `WATCH_CODES` 名称 upsert 为 `source='watch'`，并清理已移出盯盘池的旧 watch 行。接线到 `app/seeds/__init__.py` 与 `create_app()`。

**Files:**
- Create: `app/seeds/watch_companies.py`
- Modify: `app/seeds/__init__.py`（导出 `seed_watch_companies`）
- Modify: `app/__init__.py:296-313`（导入 + 调用块加 `seed_watch_companies`）
- Test: `tests/test_watch_companies_seed.py`（追加）

**Interfaces:**
- Consumes: `CompanyKeyword.source`（Task 1）、`WATCH_CODES`（`app/config/stock_codes.py`，每条含 `name`）
- Produces: `seed_watch_companies() -> None`（幂等；upsert watch 名 + 删除 stale watch 行；失败只 warning 不抛）

- [ ] **Step 1: 写失败测试（幂等 + 升级 + 清理）**

在 `tests/test_watch_companies_seed.py` 追加：

```python
def test_seed_watch_companies_idempotent(app_ctx):
    from app import db
    from app.models.news import CompanyKeyword
    from app.seeds.watch_companies import seed_watch_companies
    from app.config.stock_codes import WATCH_CODES

    watch_names = {e['name'] for e in WATCH_CODES}
    seed_watch_companies()
    seed_watch_companies()  # 第二次不应重复建行

    rows = CompanyKeyword.query.filter_by(source='watch').all()
    assert {r.name for r in rows} == watch_names
    assert len(rows) == len(watch_names)  # 无重复


def test_seed_upgrades_manual_to_watch(app_ctx):
    from app import db
    from app.models.news import CompanyKeyword
    from app.seeds.watch_companies import seed_watch_companies
    from app.config.stock_codes import WATCH_CODES

    name = WATCH_CODES[0]['name']
    db.session.add(CompanyKeyword(name=name, source='manual'))
    db.session.commit()

    seed_watch_companies()

    rows = CompanyKeyword.query.filter_by(name=name).all()
    assert len(rows) == 1
    assert rows[0].source == 'watch'


def test_seed_cleans_stale_watch_rows(app_ctx):
    from app import db
    from app.models.news import CompanyKeyword
    from app.seeds.watch_companies import seed_watch_companies

    db.session.add(CompanyKeyword(name='已退出盯盘的公司', source='watch'))
    db.session.commit()

    seed_watch_companies()

    assert CompanyKeyword.query.filter_by(name='已退出盯盘的公司').first() is None


def test_seed_preserves_manual_rows(app_ctx):
    from app import db
    from app.models.news import CompanyKeyword
    from app.seeds.watch_companies import seed_watch_companies

    db.session.add(CompanyKeyword(name='我手动加的公司', source='manual'))
    db.session.commit()

    seed_watch_companies()

    row = CompanyKeyword.query.filter_by(name='我手动加的公司').first()
    assert row is not None
    assert row.source == 'manual'  # 手动行不受影响
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_companies_seed.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'app.seeds.watch_companies'`。

- [ ] **Step 3: 写 seed 实现**

新建 `app/seeds/watch_companies.py`：

```python
"""同步盯盘池 WATCH_CODES 进 company_keyword（source='watch'）。
WATCH_CODES 是唯一权威源，本 seed 只做 DB 投影同步。"""
import logging

from app import db
from app.models.news import CompanyKeyword
from app.config.stock_codes import WATCH_CODES

logger = logging.getLogger(__name__)


def seed_watch_companies():
    try:
        watch_names = {e['name'] for e in WATCH_CODES}
        existing = {c.name: c for c in CompanyKeyword.query.all()}

        for name in watch_names:
            row = existing.get(name)
            if row is None:
                db.session.add(CompanyKeyword(name=name, source='watch', is_active=True))
            else:
                row.source = 'watch'
                row.is_active = True

        for c in CompanyKeyword.query.filter_by(source='watch').all():
            if c.name not in watch_names:
                db.session.delete(c)

        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.warning(f'[seed] watch companies 同步失败: {e}')
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_companies_seed.py -v`
Expected: 全部 passed。

- [ ] **Step 5: 接线 seeds 导出**

`app/seeds/__init__.py`：导入加一行、`__all__` 加一项：

```python
from app.seeds.ccl_upstream_category import seed_ccl_upstream_category
from app.seeds.watch_companies import seed_watch_companies
```

```python
    'seed_ccl_upstream_category',
    'seed_watch_companies',
]
```

- [ ] **Step 6: 接线 create_app 调用**

`app/__init__.py:296-313`，导入元组加 `seed_watch_companies`，调用块末尾加调用（须在 `migrate_company_keyword_table()` 之后，依赖 `source` 列）：

```python
        from app.seeds import (
            seed_cpu_category,
            seed_worldcup_category,
            seed_ascend_category,
            seed_copper_category,
            seed_aerospace_materials_category,
            seed_apple_category,
            seed_photoresist_category,
            seed_ccl_upstream_category,
            seed_watch_companies,
        )
        seed_cpu_category()
        seed_worldcup_category()
        seed_ascend_category()
        seed_copper_category()
        seed_aerospace_materials_category()
        seed_apple_category()
        seed_photoresist_category()
        seed_ccl_upstream_category()
        seed_watch_companies()
```

- [ ] **Step 7: 全量回归**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_companies_seed.py tests/test_watch_config.py -v`
Expected: 全部 passed（确认未破坏盯盘配置测试）。

- [ ] **Step 8: Commit**

```bash
rtk git add app/seeds/watch_companies.py app/seeds/__init__.py app/__init__.py tests/test_watch_companies_seed.py && rtk git commit -m "feat(news): seed WATCH_CODES 进 company_keyword 并接线 create_app"
```

---

### Task 3: 路由层 —— GET 返 source / DELETE 守卫 / POST 不降级

`GET /news/companies` 返回 `source`；`DELETE` 拒删 `source='watch'`（防绕过前端）；`POST` 添加同名盯盘公司时不降级 source。

**Files:**
- Modify: `app/routes/news.py:94-127`（`get_companies` / `add_company` / `delete_company`）
- Test: `tests/test_watch_companies_seed.py`（追加路由测试，新增 `client_ctx` fixture）

**Interfaces:**
- Consumes: `CompanyKeyword.source`（Task 1）；`news_bp`（`app.routes`，url_prefix `/news`）
- Produces:
  - `GET /news/companies` → 每个 company dict 含 `{'id', 'name', 'source'}`
  - `DELETE /news/companies/<id>`：`source='watch'` → `{'success': False, 'error': 'watch company, not deletable'}`，行保留
  - `POST /news/companies`：命中 existing 分支时不改 `source`

- [ ] **Step 1: 写失败测试**

在 `tests/test_watch_companies_seed.py` 追加 `client_ctx` fixture 与路由测试：

```python
@pytest.fixture
def client_ctx(tmp_path):
    """带 news_bp + DB 的测试 client，隔离于 data/stock.db。"""
    from app import db
    from app.routes import news_bp
    import app.models.news  # noqa: F401
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{tmp_path}/t.db'
    app.config['SQLALCHEMY_BINDS'] = {'private': f'sqlite:///{tmp_path}/tp.db'}
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    app.register_blueprint(news_bp)
    with app.app_context():
        db.create_all()
        with app.test_client() as client:
            yield app, client
        db.session.remove()


def test_get_companies_returns_source(client_ctx):
    from app import db
    from app.models.news import CompanyKeyword
    app, client = client_ctx
    db.session.add(CompanyKeyword(name='手动公司', source='manual'))
    db.session.add(CompanyKeyword(name='盯盘公司', source='watch'))
    db.session.commit()

    data = client.get('/news/companies').get_json()
    assert data['success']
    by_name = {c['name']: c for c in data['companies']}
    assert by_name['手动公司']['source'] == 'manual'
    assert by_name['盯盘公司']['source'] == 'watch'


def test_delete_watch_company_rejected(client_ctx):
    from app import db
    from app.models.news import CompanyKeyword
    app, client = client_ctx
    c = CompanyKeyword(name='盯盘公司', source='watch')
    db.session.add(c)
    db.session.commit()
    cid = c.id

    resp = client.delete(f'/news/companies/{cid}').get_json()
    assert resp['success'] is False
    assert db.session.get(CompanyKeyword, cid) is not None  # 行仍在


def test_delete_manual_company_ok(client_ctx):
    from app import db
    from app.models.news import CompanyKeyword
    app, client = client_ctx
    c = CompanyKeyword(name='手动公司', source='manual')
    db.session.add(c)
    db.session.commit()
    cid = c.id

    resp = client.delete(f'/news/companies/{cid}').get_json()
    assert resp['success'] is True
    assert db.session.get(CompanyKeyword, cid) is None


def test_add_existing_watch_keeps_source(client_ctx):
    from app import db
    from app.models.news import CompanyKeyword
    app, client = client_ctx
    c = CompanyKeyword(name='盯盘公司', source='watch')
    db.session.add(c)
    db.session.commit()

    client.post('/news/companies', json={'name': '盯盘公司'})

    row = CompanyKeyword.query.filter_by(name='盯盘公司').first()
    assert row.source == 'watch'  # 不被降级为 manual
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_companies_seed.py -k "companies or watch_company or source" -v`
Expected: FAIL —— `test_get_companies_returns_source`（返回缺 `source` 键）、`test_delete_watch_company_rejected`（watch 行被删，返回 success）。

- [ ] **Step 3: 改 `get_companies` 返回 source**

`app/routes/news.py:96-100`，把返回里的 dict 加 `source`：

```python
@news_bp.route('/companies')
def get_companies():
    companies = CompanyKeyword.query.filter_by(is_active=True).order_by(CompanyKeyword.created_at.desc()).all()
    return jsonify({
        'success': True,
        'companies': [{'id': str(c.id), 'name': c.name, 'source': c.source or 'manual'} for c in companies]
    })
```

- [ ] **Step 4: 改 `delete_company` 加 watch 守卫**

`app/routes/news.py:120-127`，在删除前判断 source：

```python
@news_bp.route('/companies/<int:company_id>', methods=['DELETE'])
def delete_company(company_id):
    c = db.session.get(CompanyKeyword, company_id)
    if not c:
        return jsonify({'success': False, 'error': 'not found'})
    if c.source == 'watch':
        return jsonify({'success': False, 'error': 'watch company, not deletable'})
    db.session.delete(c)
    db.session.commit()
    return jsonify({'success': True})
```

- [ ] **Step 5: 改 `add_company` 不降级 source**

`app/routes/news.py:103-117`，existing 分支只重置 `is_active`，不动 source（现状本就不改 source，此处显式保持，仅确保新建分支不误设）。确认实现为：

```python
@news_bp.route('/companies', methods=['POST'])
def add_company():
    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'error': 'name required'})
    existing = CompanyKeyword.query.filter_by(name=name).first()
    if existing:
        existing.is_active = True
        db.session.commit()
        return jsonify({'success': True, 'id': str(existing.id)})
    c = CompanyKeyword(name=name)
    db.session.add(c)
    db.session.commit()
    return jsonify({'success': True, 'id': str(c.id)})
```

（新建 `CompanyKeyword(name=name)` 不传 source → 走模型默认 `'manual'`，符合预期；existing 分支不触碰 source。）

- [ ] **Step 6: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_companies_seed.py -v`
Expected: 全部 passed。

- [ ] **Step 7: Commit**

```bash
rtk git add app/routes/news.py tests/test_watch_companies_seed.py && rtk git commit -m "feat(news): /companies 返回 source + DELETE 守卫 watch 行"
```

---

### Task 4: 前端 —— 盯盘行只读带「盯盘」徽标

`app/static/js/news.js` 渲染「我的公司」列表时，`source==='watch'` 行带徽标、不渲染删除按钮；`manual` 行不变。

**Files:**
- Modify: `app/static/js/news.js:307-314`（`companyKeywords` 渲染块）
- Modify: `app/templates/news.html`（可选：加 `.kw-watch` 徽标样式，紧邻 `.kw-company` 样式 `app/templates/news.html:55`）

**Interfaces:**
- Consumes: `GET /news/companies` 返回的 `c.source`（Task 3）

- [ ] **Step 1: 改渲染逻辑**

`app/static/js/news.js:307-314`，按 source 分支渲染（watch 行无删除按钮、带徽标）：

```javascript
            if (compData.success) {
                document.getElementById('companyKeywords').innerHTML = compData.companies.length
                    ? compData.companies.map(c => c.source === 'watch'
                        ? `
                        <span class="kw-manage-tag kw-company">
                            ${c.name}
                            <span class="kw-watch-badge">盯盘</span>
                        </span>
                    `
                        : `
                        <span class="kw-manage-tag kw-company">
                            ${c.name}
                            <button class="kw-delete" onclick="News.deleteCompany('${c.id}')">-</button>
                        </span>
                    `).join('')
                    : '<span class="text-muted">暂无公司</span>';
            }
```

- [ ] **Step 2: 加徽标样式**

`app/templates/news.html`，在 `.kw-company` 样式行（`app/templates/news.html:55`）之后加：

```css
.kw-watch-badge { margin-left: 4px; padding: 0 5px; font-size: 0.7em; border-radius: 6px; background: rgba(13,110,253,0.2); color: #6ea8fe; }
```

- [ ] **Step 3: 手动验证（无 JS 测试框架）**

启动应用并在浏览器核对：

Run: `SCHEDULER_ENABLED=0 rtk python run.py`（或 `start.bat`）
打开 `http://127.0.0.1:5000/news/` → 展开关键词管理 → 「我的公司」列表：
- 盯盘公司（如「兆易创新」「小米集团」）显示「盯盘」徽标、**无** `-` 删除按钮。
- 手动添加的公司仍带 `-` 删除按钮，点击可删。
- 盯盘公司无法删除（前端无按钮；即便直接调 `DELETE /news/companies/<id>` 也被 Task 3 守卫拒绝）。

- [ ] **Step 4: Commit**

```bash
rtk git add app/static/js/news.js app/templates/news.html && rtk git commit -m "feat(news): 盯盘公司只读展示带徽标、隐藏删除按钮"
```

---

## 收尾验证

- [ ] 全量单测：`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ -v`，确认无回归。
- [ ] 确认本次提交链只含本任务文件：对每个 commit `rtk git show --stat <sha>`。

## Self-Review（已对照 spec）

- **Spec coverage**：① source 列（迁移+模型）→ Task 1；② seed 同步 watch（upsert/清理/失败 warning）→ Task 2 + create_app 接线；③ 消费层零改动（爬虫轮转 / tab='company' 过滤）→ 无需改动，由 seed 写入的 watch 行自动覆盖，spec §2 已说明；④ 路由 GET/DELETE/POST → Task 3；⑤ UI 徽标+隐藏删除 → Task 4；⑥ 边界（同名升级 / null last_fetched / stale 清理）→ Task 2 测试覆盖前两项，第三项 last_fetched 由现有 nullsfirst 语义自然处理。
- **修正**：spec §4 写「`app/templates/news.html` 列表渲染」，实际渲染逻辑在 `app/static/js/news.js`（模板仅留 `#companyKeywords` 容器 + 样式）；Task 4 已改到正确文件。
- **Placeholder scan**：无 TBD/TODO，所有 step 含完整代码与命令。
- **Type consistency**：`source` 列名、`'manual'`/`'watch'` 取值、`seed_watch_companies()`、`migrate_company_keyword_table()`、路由返回键 `source` 跨任务一致。
