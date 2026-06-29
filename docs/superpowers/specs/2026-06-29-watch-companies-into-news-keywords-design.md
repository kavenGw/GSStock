# 盯盘公司自动并入「我的公司」新闻关键字 — 设计

- 日期：2026-06-29
- 状态：已确认，待实现
- 目标库：`data/stock.db`（`company_keyword` 表，公共库）

## 背景与问题

当前「我的公司」新闻关键字与盯盘池是两套独立维护的机制：

- **「我的公司」**：存 DB `company_keyword` 表（`CompanyKeyword`：`name` / `is_active` / `last_fetched_at` / `created_at`），news.html 有增删 UI（`/news/companies`）。两个消费点：
  1. `CompanyNewsService.fetch_company_news` —— 主动爬这些公司新闻（东财/Yahoo/Google），每 30min 按 `last_fetched_at` 轮转抓 `COMPANY_NEWS_MAX_COMPANIES`（默认 3）家。
  2. `NewsService.get_news_items(tab='company')` —— 「公司」标签页按公司名过滤快讯。
- **盯盘池**：`app/config/stock_codes.py` 的 `WATCH_CODES` 常量（写死，是盯盘唯一权威源，不走 DB）。

需求：盯盘池里的公司应**自动并入**「我的公司」，免去两处重复维护。并入后盯盘公司既被主动爬取新闻，也出现在「公司」标签页过滤里。

## 设计决策（已确认）

1. **包含范围**：两者都要 —— 主动爬取 + 标签页过滤。
2. **UI 呈现**：盯盘公司在管理列表里只读展示、带「盯盘」徽标、无删除按钮。
3. **实现路线**：方案 A —— 启动时幂等 seed `WATCH_CODES` 进 `company_keyword` 表，新增 `source` 列区分 `manual` / `watch`。`WATCH_CODES` 仍是唯一权威源，DB 行只是它的同步投影；爬虫轮转调度零改动复用。

（备选方案 B「读时 union 不入库」被否：爬虫 `last_fetched_at` 轮转需为盯盘公司另维护一套跟踪，复杂度更高且 UI 需前端合并两源。）

## 实现设计

### 1. 数据层

**迁移（schema 变更，走 `migrate_*`）** —— `app/__init__.py`

仿照现有内联 `migrate_position_table()` 等模式，新增：

```python
def migrate_company_keyword_table():
    with db.engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE company_keyword ADD COLUMN source VARCHAR(10) DEFAULT 'manual'"))
            conn.commit()
        except Exception:
            pass  # duplicate column —— 已迁移过
```

挂到 `create_app()` 内现有 `migrate_*()` 调用块（紧跟 `migrate_wyckoff_table()` 之后）。

**模型** —— `app/models/news.py`

`CompanyKeyword` 加列：

```python
source = db.Column(db.String(10), default='manual')  # 'manual' | 'watch'
```

**Seed（数据注入，幂等，走 `app/seeds/`）** —— 新建 `app/seeds/watch_companies.py`

```python
def seed_watch_companies():
    """同步 WATCH_CODES 名称进 company_keyword（source='watch'）。
    WATCH_CODES 是唯一权威源，本 seed 只做 DB 投影同步。"""
```

逻辑：

- 取 `WATCH_CODES` 全部 `name` 集合 `watch_names`。
- **Upsert**：对每个 watch name —— 若已有同名行 → 升级 `source='watch'`、`is_active=True`；否则新建 `CompanyKeyword(name=, source='watch')`。
- **清理 stale**：`source='watch'` 但 `name not in watch_names` 的行 → 删除（该公司已移出盯盘池）。
- 失败只记 warning 不抛出（遵循 seed 铁律）。

挂到 `create_app()` 内 seeds 导入 + 调用块（与 `seed_cpu_category()` 等并列）。**调用顺序须在 `migrate_company_keyword_table()` 之后**（依赖 `source` 列已存在）。

### 2. 消费层（零改动复用）

- `CompanyNewsService.fetch_company_news`：盯盘公司成为 DB 一等公民后，`last_fetched_at` 轮转 / `limit` / 排序逻辑**完全不动**，自动纳入爬取轮转。
- `NewsService.get_news_items(tab='company')`：查询 `CompanyKeyword.query.filter_by(is_active=True)` 已自动含 watch 行，「公司」标签页过滤自动覆盖盯盘公司。

### 3. 路由层 —— `app/routes/news.py`

- `GET /news/companies`：返回的每个 company dict 增加 `source` 字段。
- `DELETE /news/companies/<id>`：服务端守卫 —— 若 `c.source == 'watch'` 返回 `{'success': False, 'error': 'watch company, not deletable'}`，拒绝删除（防绕过前端直接调接口）。
- `POST /news/companies`（`add_company`）：手动添加同名盯盘公司时，命中 existing 分支只重置 `is_active=True`，**不降级** `source`（保持 `'watch'`）。

### 4. 前端 —— `app/templates/news.html`

「我的公司」管理列表渲染：

- 读取 company 的 `source` 字段。
- `source === 'watch'`：行尾加「盯盘」徽标（如 `<span class="badge">盯盘</span>`），**不渲染删除按钮**。
- `source === 'manual'`：保持现状（含删除按钮）。

## 边界情况

- **手动项与盯盘同名**：seed upsert 升级为 `source='watch'` → 归盯盘、不可删。可接受（用户想跟踪的本就是同一家）。
- **盯盘公司无 `last_fetched_at`（null）**：首轮按 `nullsfirst` 优先抓取，符合现有语义。
- **盯盘公司移出 `WATCH_CODES`**：下次启动 seed 清理阶段删除其 watch 行（连带 `last_fetched_at`）。若该名曾是手动项被升级过，也一并删除；用户如仍想跟踪可在 UI 重新手动添加。

## 测试

放 `tests/test_*.py` 平铺：

- **seed 幂等**：连续跑两次 `seed_watch_companies()`，watch 行数 = `len(WATCH_CODES)` 去重，不重复建行。
- **stale 清理**：DB 有一条 `source='watch'` 但不在 `WATCH_CODES` 的行，跑 seed 后被删除。
- **同名升级**：预置一条 `source='manual'` 且名在 `WATCH_CODES` 的行，跑 seed 后 `source` 变 `'watch'`。
- **DELETE 守卫**：对 `source='watch'` 行调 `DELETE /news/companies/<id>` 返回失败且行仍在。
- **tab='company' 覆盖**：`get_news_items(tab='company')` 的过滤集合含 watch 公司名。

（路由测试用 `Flask() + register_blueprint(news_bp)` 直接注入避免 `create_app()` 副作用；涉及 seed/DB 的用最小 sqlite + db.create_all。）

## 涉及文件清单

| 文件 | 改动 |
|------|------|
| `app/__init__.py` | 加 `migrate_company_keyword_table()` + seed 导入/调用 |
| `app/models/news.py` | `CompanyKeyword` 加 `source` 列 |
| `app/seeds/watch_companies.py` | 新建 `seed_watch_companies()` |
| `app/routes/news.py` | GET 返回 source / DELETE 守卫 / POST 不降级 |
| `app/templates/news.html` | 列表渲染 source 徽标 + 隐藏 watch 删除按钮 |
| `tests/test_watch_companies_seed.py` | 新增测试 |
