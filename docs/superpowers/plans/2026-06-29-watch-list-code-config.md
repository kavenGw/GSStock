# 盯盘股票池迁为代码配置 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把盯盘助手的股票池从 DB 表 `WatchList` 迁为代码常量 `WATCH_CODES`（唯一权威源），移除一切手动增删入口。

**Architecture:** 在 `app/config/stock_codes.py` 新增 `WATCH_CODES` 列表常量；`WatchService` 的 getter 改读该常量（零 DB 访问）；删除增删路由、前端增删 UI、`WatchList` 模型；`watch_alert` 策略改用新 `get_market_map()`。`WatchAnalysis` 表与 AI 分析链路完全不动。

**Tech Stack:** Python 3 / Flask / SQLAlchemy / pytest；前端 Bootstrap + 原生 JS。

## Global Constraints

- 响应中文；不写多余注释；不写 backup 文件（git 留痕足够）。
- 所有 git/pytest 命令前加 `rtk`，链式 `&&` 中也要。
- 单测运行：`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ -v`（env 赋值必须在 `rtk` 之前）。
- 路由层测试用 `Flask() + register_blueprint(watch_bp)` 注入，避开 `create_app()` 副作用（启 17 任务 + crawl4ai + LLM）。
- 单测平铺在 `tests/test_*.py`，不建子目录。
- `WATCH_CODES` 每条 `market` 显式写死，不靠 `MarketIdentifier.identify` 推断（其不认 `.KS`）。
- 改 `app/` 代码——实现应在独立 git worktree 进行（执行 skill 负责）。
- commit 协议：`git add <精确路径> && git commit` 同一条 Bash 命令链；提交后 `git show --stat <sha>` 核对只含本任务文件。

## 迁移前盯盘池（7 只，全部已查证正确）

| code | name | market |
|------|------|--------|
| 300223 | 北京君正 | A |
| 603986 | 兆易创新 | A |
| 600183 | 生益科技 | A |
| 000660.KS | SK海力士 | KR |
| 2631.HK | 天岳先进 | HK |
| 2577.HK | 英诺赛科 | HK |
| 9981.HK | 沃尔核材 | HK |

## 文件结构

- **Modify** `app/config/stock_codes.py` — 新增 `WATCH_CODES` 常量
- **Modify** `app/services/watch_service.py` — getter 改读 WATCH_CODES；新增 `get_market_map()`；删 `add_stock`/`remove_stock`；import 改只引 `WatchAnalysis`
- **Modify** `app/routes/watch.py` — 删 `/add`、`/remove/<code>`、`/stocks/search`
- **Modify** `app/strategies/watch_alert/__init__.py` — 用 `get_market_map()` 替代 `WatchList.query`
- **Modify** `app/templates/watch.html` — 删添加按钮/Modal/搜索区
- **Modify** `app/static/js/watch.js` — 删 `addStock`/`removeStock`/`searchStocks` 及移除按钮渲染
- **Modify** `app/models/watch_list.py` — 删 `WatchList` 类（留 `WatchAnalysis`）
- **Modify** `app/models/__init__.py`、`app/__init__.py` — import 移除 `WatchList`
- **Create** `tests/test_watch_config.py` — service 层单测

---

### Task 1: WATCH_CODES 配置 + WatchService 改读配置

把数据源从 `WatchList.query` 切到 `WATCH_CODES` 常量，并新增 `get_market_map()`。这是整个迁移的核心，service 层全部 getter 一次性切换并加测试。

**Files:**
- Modify: `app/config/stock_codes.py`（文件尾追加 `WATCH_CODES`）
- Modify: `app/services/watch_service.py:1-57`（import + 四个 getter，删 add/remove）
- Test: `tests/test_watch_config.py`（新建）

**Interfaces:**
- Produces:
  - `app.config.stock_codes.WATCH_CODES: list[dict]` — 每条 `{'code': str, 'name': str, 'market': str}`
  - `WatchService.get_watch_codes() -> list[str]`
  - `WatchService.get_watch_list() -> list[dict]` — 每条 `{'id': int, 'stock_code': str, 'stock_name': str, 'market': str, 'added_at': None}`
  - `WatchService.get_watched_markets() -> list[str]` — 按 `['A','US','HK','KR','TW','JP']` 优先级排序
  - `WatchService.get_market_map() -> dict[str, str]` — `{code: market}`

- [ ] **Step 1: 在 `app/config/stock_codes.py` 文件末尾追加 WATCH_CODES**

```python
# 盯盘股票池（唯一权威源，替代 watch_list 表）
WATCH_CODES = [
    {'code': '300223',    'name': '北京君正',  'market': 'A'},
    {'code': '603986',    'name': '兆易创新',  'market': 'A'},
    {'code': '600183',    'name': '生益科技',  'market': 'A'},
    {'code': '000660.KS', 'name': 'SK海力士',  'market': 'KR'},
    {'code': '2631.HK',   'name': '天岳先进',  'market': 'HK'},
    {'code': '2577.HK',   'name': '英诺赛科',  'market': 'HK'},
    {'code': '9981.HK',   'name': '沃尔核材',  'market': 'HK'},
]
```

- [ ] **Step 2: 写失败测试 `tests/test_watch_config.py`**

```python
from app.config.stock_codes import WATCH_CODES
from app.services.watch_service import WatchService


def test_get_watch_codes_matches_config_order():
    codes = WatchService.get_watch_codes()
    assert codes == [e['code'] for e in WATCH_CODES]
    assert len(codes) == 7
    assert '2631.HK' in codes and '2577.HK' in codes


def test_get_watch_list_fields():
    items = WatchService.get_watch_list()
    assert len(items) == len(WATCH_CODES)
    first = items[0]
    assert set(first.keys()) >= {'id', 'stock_code', 'stock_name', 'market', 'added_at'}
    assert first['added_at'] is None
    by_code = {i['stock_code']: i for i in items}
    assert by_code['000660.KS']['stock_name'] == 'SK海力士'
    assert by_code['000660.KS']['market'] == 'KR'


def test_get_watched_markets_priority_order():
    markets = WatchService.get_watched_markets()
    assert markets == ['A', 'HK', 'KR']


def test_get_market_map():
    mm = WatchService.get_market_map()
    assert mm['000660.KS'] == 'KR'
    assert mm['2631.HK'] == 'HK'
    assert mm['300223'] == 'A'
    assert len(mm) == 7
```

- [ ] **Step 3: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_config.py -v`
Expected: FAIL —— `get_market_map` 不存在（AttributeError）/ 现有 getter 仍走 DB 返回旧数据。

- [ ] **Step 4: 改写 `app/services/watch_service.py` 顶部 import（line 1-9）**

把 `from app.models.watch_list import WatchList, WatchAnalysis` 改为只引 `WatchAnalysis`，并新增 WATCH_CODES import：

```python
import json
import logging
from datetime import date, datetime

from app import db
from app.config.stock_codes import WATCH_CODES
from app.models.watch_list import WatchAnalysis

logger = logging.getLogger(__name__)
```

（注意：删掉原 `from app.utils.market_identifier import MarketIdentifier` —— 仅 `add_stock` 用过它，本任务删 add_stock 后不再需要。若文件他处仍用则保留。）

- [ ] **Step 5: 替换四个 getter + 删除 add/remove（`app/services/watch_service.py` 的 `get_watch_list` / `add_stock` / `remove_stock` / `get_watch_codes` / `get_watched_markets` 整段，约 line 15-57）**

```python
    @staticmethod
    def get_watch_list() -> list[dict]:
        """获取盯盘列表（来自 WATCH_CODES 配置）"""
        return [{'id': i, 'stock_code': e['code'], 'stock_name': e['name'],
                 'market': e['market'], 'added_at': None}
                for i, e in enumerate(WATCH_CODES)]

    @staticmethod
    def get_watch_codes() -> list[str]:
        """获取盯盘列表的股票代码"""
        return [e['code'] for e in WATCH_CODES]

    @staticmethod
    def get_market_map() -> dict:
        """{股票代码: 市场}"""
        return {e['code']: e['market'] for e in WATCH_CODES}

    @staticmethod
    def get_watched_markets() -> list[str]:
        """获取盯盘列表涉及的市场（按优先级排序）"""
        priority = ['A', 'US', 'HK', 'KR', 'TW', 'JP']
        markets = {e['market'] for e in WATCH_CODES if e['market']}
        return [m for m in priority if m in markets] + [m for m in markets if m not in priority]
```

`add_stock` 与 `remove_stock` 整两个方法**删除**。`WatchAnalysis` 相关方法（`get_today_analysis` / `save_analysis` / `get_all_today_analyses`）保持不变。

- [ ] **Step 6: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_config.py -v`
Expected: PASS（4 passed）

- [ ] **Step 7: 提交**

```bash
rtk git add app/config/stock_codes.py app/services/watch_service.py tests/test_watch_config.py && rtk git commit -m "feat(watch): 盯盘池迁为 WATCH_CODES 配置，WatchService 改读配置" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>" && rtk git show --stat HEAD | head -15
```

---

### Task 2: watch_alert 策略改用 get_market_map

`watch_alert` 是 `WatchList` 的最后一个非清理引用，必须在删模型前切走。

**Files:**
- Modify: `app/strategies/watch_alert/__init__.py:24-37`
- Test: 复用既有 watch_alert 测试（若有）+ 导入冒烟

**Interfaces:**
- Consumes: `WatchService.get_market_map() -> dict[str, str]`（Task 1 产出）

- [ ] **Step 1: 改 `app/strategies/watch_alert/__init__.py` 的 scan 方法（line 25-37 区段）**

删除 `from app.models.watch_list import WatchList`，把 `market_map` 构造改为：

```python
    def scan(self) -> list[Signal]:
        from app.services.trading_calendar import TradingCalendarService
        from app.services.watch_service import WatchService

        codes = WatchService.get_watch_codes()
        if not codes:
            return []

        market_map = WatchService.get_market_map()
```

（原 `items = WatchList.query.filter(...)` 与基于它的 `market_map` 推导两行一并删除；下游对 `market_map` 的使用不变。`MarketIdentifier` 若 scan 内他处仍引用则保留其 import。）

- [ ] **Step 2: 冒烟——确认模块可导入且无 WatchList 残留引用**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -c "import app.strategies.watch_alert; print('ok')"`
Expected: 打印 `ok`，无 ImportError。

- [ ] **Step 3: 确认 watch_alert 内已无 WatchList**

Run: `rtk git grep -n "WatchList" app/strategies/watch_alert/__init__.py`
Expected: 无输出（exit 1）。

- [ ] **Step 4: 提交**

```bash
rtk git add app/strategies/watch_alert/__init__.py && rtk git commit -m "refactor(watch): watch_alert 改用 WatchService.get_market_map 替代 WatchList 查询" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>" && rtk git show --stat HEAD | head -10
```

---

### Task 3: 删除增删路由

移除服务于手动编辑的三个路由，使后端无任何写盯盘池入口。

**Files:**
- Modify: `app/routes/watch.py:21-35, 104-117`
- Test: 路由冒烟（`Flask() + register_blueprint`）

- [ ] **Step 1: 写失败测试，追加到 `tests/test_watch_config.py`**

```python
def _watch_client():
    from flask import Flask
    from app.routes import watch_bp
    app = Flask(__name__)
    app.register_blueprint(watch_bp)
    return app.test_client()


def test_add_remove_search_routes_removed():
    c = _watch_client()
    assert c.post('/watch/add', json={'stock_code': 'X'}).status_code == 404
    assert c.delete('/watch/remove/300223').status_code == 404
    assert c.get('/watch/stocks/search?q=x').status_code == 404
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_config.py::test_add_remove_search_routes_removed -v`
Expected: FAIL（路由仍存在，返回 200 而非 404）

- [ ] **Step 3: 删 `app/routes/watch.py` 的三个路由函数**

删除整段 `add_stock`（line 21-29，`@watch_bp.route('/add', ...)`）、`remove_stock`（line 32-35，`@watch_bp.route('/remove/<stock_code>', ...)`）、`search_stocks`（line 104-117，`@watch_bp.route('/stocks/search')`，含其内部 `from app.models.stock import Stock`）。其余路由（`index`/`watch_list`/`prices`/`analyze`/`get_analysis`/`market_status`/`chart_data`/`earnings`）保持不变。

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_config.py -v`
Expected: PASS（5 passed）

- [ ] **Step 5: 提交**

```bash
rtk git add app/routes/watch.py tests/test_watch_config.py && rtk git commit -m "feat(watch): 删除盯盘增删/搜索路由(/add /remove /stocks/search)" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>" && rtk git show --stat HEAD | head -10
```

---

### Task 4: 删除前端增删 UI

移除 watch.html 的添加按钮/Modal/搜索区，与 watch.js 的增删方法及移除按钮渲染，使前端纯只读。

**Files:**
- Modify: `app/templates/watch.html:61-62, 86-88, 95-108`
- Modify: `app/static/js/watch.js:392, 987-1056`

- [ ] **Step 1: 删 `app/templates/watch.html` 添加入口**

- 删 header「添加」按钮（line 61-62，`<button ... data-bs-target="#addStockModal"> ... 添加 </button>`）
- empty state（line 86-88）：删「添加股票」按钮，文案保留/改为 `<p class="mt-3 text-muted">暂无盯盘股票，请在 app/config/stock_codes.py 的 WATCH_CODES 配置</p>`
- 删整个添加股票 Modal（line 95-108 起的 `<div class="modal fade" id="addStockModal" ...>` 完整块，含 `stockSearchInput` 输入框与 `searchResults` 容器，直到该 modal `</div>` 闭合）

- [ ] **Step 2: 删 `app/static/js/watch.js` 增删方法与按钮**

- 删 line 392 单元格 `<td class="text-end"><button ... onclick="Watch.removeStock('${code}')" ...></td>`（连同其所在表格行的该列；若表头有对应空列也一并删）
- 删 `// --- 增删 ---` 注释块下的 `addStock`（~988-1008）、`removeStock`（~1010-1033）、`searchStocks`（~1035-1056）三个方法整段

- [ ] **Step 3: 冒烟——确认无残留引用**

Run: `rtk git grep -nE "addStockModal|searchStocks|Watch\.addStock|Watch\.removeStock|stockSearchInput|stocks/search" app/templates/watch.html app/static/js/watch.js`
Expected: 无输出（exit 1）——所有增删引用已清除。

- [ ] **Step 4: 提交**

```bash
rtk git add app/templates/watch.html app/static/js/watch.js && rtk git commit -m "feat(watch): 移除盯盘前端增删UI(添加按钮/Modal/搜索/移除按钮)，改为只读" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>" && rtk git show --stat HEAD | head -10
```

---

### Task 5: 删除 WatchList 模型

清理 dead model。此时已无任何运行时引用（Task 1 service、Task 2 strategy、Task 3 route 均已切走）。

**Files:**
- Modify: `app/models/watch_list.py:5-14`
- Modify: `app/models/__init__.py`（移除 `WatchList` 导出）
- Modify: `app/__init__.py:276`（批量 import 移除 `WatchList`）

- [ ] **Step 1: 删 `app/models/watch_list.py` 的 WatchList 类**

删除 `class WatchList(db.Model): ...`（line 5-14）整段，**保留** `from datetime import datetime` / `from app import db` 与 `class WatchAnalysis(db.Model): ...`。

- [ ] **Step 2: 改 `app/models/__init__.py` 移除 WatchList**

在该文件中找到 `WatchList` 的 import 与（若有）`__all__` 条目，删除 `WatchList`，保留 `WatchAnalysis`。

- [ ] **Step 3: 改 `app/__init__.py:276` 批量 import**

从该行 `from app.models import (... WatchList, WatchAnalysis ...)` 删除 `WatchList,`，保留 `WatchAnalysis`。

- [ ] **Step 4: 全仓确认无 WatchList 残留引用**

Run: `rtk git grep -n "WatchList" -- app/`
Expected: 无输出（exit 1）。

- [ ] **Step 5: 应用启动冒烟（验证 import 链无断裂）**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -c "from app import create_app; create_app(); print('app ok')"`
Expected: 末尾打印 `app ok`（前面调度器/crawl4ai 日志噪音可忽略），无 ImportError / NameError。

- [ ] **Step 6: 提交**

```bash
rtk git add app/models/watch_list.py app/models/__init__.py app/__init__.py && rtk git commit -m "refactor(watch): 删除 WatchList 模型(已迁为 WATCH_CODES 配置)，保留 WatchAnalysis" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>" && rtk git show --stat HEAD | head -10
```

---

### Task 6: 全量回归 + CLAUDE.md 同步

确认全测试通过，并把「盯盘池=代码配置」这一约定写进 watch rule，避免后人再去 DB 找。

**Files:**
- Modify: `.claude/rules/watch.md`（追加盯盘池配置说明）

- [ ] **Step 1: 跑全量单测**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ -v > .omc/artifacts/watch_test.log 2>&1; rtk grep -E "passed|failed|error" .omc/artifacts/watch_test.log | tail -5`
Expected: 全 passed，无 failed/error（管道吞 stdout 坑：写文件再 grep）。

- [ ] **Step 2: 在 `.claude/rules/watch.md` 追加一节**

在「盯盘助手配置」节后插入：

```markdown
## 盯盘股票池（代码配置，非 DB）

盯盘要盯哪些股票由 `app/config/stock_codes.py` 的 `WATCH_CODES` 常量决定（唯一权威源），不再有 `watch_list` 表/增删 UI/`/watch/add`/`/watch/remove`。改盯盘池=改 WATCH_CODES（每条 `{'code','name','market'}`，`market` 显式写死——`MarketIdentifier` 不认 `.KS` 等后缀会误判）。`WatchService` 的 `get_watch_codes/get_watch_list/get_watched_markets/get_market_map` 全部读该常量。`WatchAnalysis` 表（AI 分析结果）与盯盘池无关，仍在 DB。DB 里遗留的 `watch_list` 孤立表无害，未做 drop 迁移。
```

- [ ] **Step 3: 提交**

```bash
rtk git add .claude/rules/watch.md && rtk git commit -m "docs(watch): rule 记录盯盘池=WATCH_CODES 代码配置约定" -m "Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>" && rtk git show --stat HEAD | head -10
```

---

## Self-Review

**Spec coverage:**
- §1 WATCH_CODES → Task 1 ✓
- §2 WatchService 四 getter + get_market_map + 删 add/remove → Task 1 ✓
- §3 删三路由 → Task 3 ✓
- §4 watch_alert get_market_map → Task 2 ✓
- §5 前端增删 UI → Task 4 ✓
- §6 WatchList 模型清理（model/__init__/app.__init__）→ Task 5 ✓
- §测试 test_watch_config.py（4 getter + 路由 404）→ Task 1 + Task 3 ✓
- 非破坏性（不 drop 表）→ Task 5 Step 明确不加 drop 迁移 ✓

**Placeholder scan:** 无 TBD/TODO；每个改代码步骤含完整代码或精确删除指令。

**Type consistency:** `get_market_map()` 在 Task 1 定义、Task 2 消费，签名一致 `-> dict[str,str]`；`get_watch_codes` 返回 `list[str]` 全程一致；WATCH_CODES 条目键 `code/name/market` 在 config、service、rule 三处一致。
