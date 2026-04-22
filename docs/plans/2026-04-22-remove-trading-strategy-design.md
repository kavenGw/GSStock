# 移除交易策略模块 — 设计与实施计划

日期：2026-04-22
作者：Claude (planner)
决定：**彻底删除**交易策略（Trading Strategy）UI 模块代码、模板、静态资源与数据库表数据。

---

## 1. 背景与目标

项目中 `app/routes/strategy.py` + `app/services/trading_strategy.py` + `app/models/trading_strategy.py` + `app/templates/trading_strategy.html` 构成了一个独立的"交易策略" UI 模块（导航栏入口 `/strategies`），当前已无使用价值，决定下线。

**注意区分**：本次移除的是**交易策略 UI 模块**，**不动** `app/strategies/` 目录（那是调度器/简报用的策略插件框架，被 `scheduler/`、`watch_alert`、`daily_briefing`、`volume_alert` 等依赖）。

## 2. 需求摘要

- 删除所有交易策略相关的代码、模板、JS、CSS 文件。
- 清理 Blueprint 注册、模型注册、init 调用、导航入口。
- 在 `app` 启动时一次性 DROP 两张表（`trading_strategies`、`strategy_executions`），**数据不留档**。
- 移除后应用能正常启动、所有其他页面/后台任务不受影响。

## 3. 验收标准

- [ ] `grep -r "trading_strategy\|TradingStrategy\|strategy_bp\|url_for('strategy\."` 在 `app/`、`docs/TECHNICAL_DOCUMENTATION.md` 下**零命中**（`graphify-out/` 不算，重建知识图即可覆盖）。
- [ ] `python run.py` 启动无报错，终端无 `ImportError / NoReferencedTableError / UndefinedError`。
- [ ] 访问 `http://127.0.0.1:5000/` 主页，导航栏不再出现"交易策略"链接；强制访问 `/strategies/` 返回 404。
- [ ] 其他页面（预警、盯盘、走势看板、价值洼地、财报估值、产业链、持仓看板、每日收益、仓位配平）全部可正常打开。
- [ ] 后台调度器启动正常：`watch_alert`、`daily_briefing`、`volume_alert`、`news_*`、`github_release` 等策略插件不受影响。
- [ ] 数据库 `data/stock.db` 中不再存在 `trading_strategies` 与 `strategy_executions` 两张表（`sqlite3 data/stock.db ".tables"`）。
- [ ] 知识图重建：`python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"` 成功。

## 4. 清单（文件 / 代码级别）

### 4.1 直接删除的文件（6 个）

| 路径 | 说明 |
|------|------|
| `app/routes/strategy.py` | 11 个 REST 端点（CRUD + 执行记录 + 统计） |
| `app/services/trading_strategy.py` | `TradingStrategyService`（9 个静态方法） + 默认策略初始化 |
| `app/models/trading_strategy.py` | `TradingStrategy` + `StrategyExecution` 模型 |
| `app/templates/trading_strategy.html` | 策略列表 / 新增编辑 / 执行记录模态框 |
| `app/static/js/trading_strategy.js` | 页面控制器 |
| `app/static/css/trading_strategy.css` | 页面样式（81 行） |

### 4.2 需要编辑的文件（4 个）

**① `app/routes/__init__.py`**
- 第 15 行：删除 `strategy_bp = Blueprint('strategy', __name__, url_prefix='/strategies')`
- 第 23 行导入列表中移除 `strategy`

**② `app/__init__.py`**
- 第 240 行导入列表中移除 `strategy_bp`
- 第 253 行删除 `app.register_blueprint(strategy_bp)`
- 第 262 行模型导入列表中移除 `TradingStrategy, StrategyExecution`
- 第 295-297 行整块删除：
  ```python
  # 初始化默认交易策略
  from app.services.trading_strategy import TradingStrategyService
  TradingStrategyService.init_default_strategies()
  ```
- 在 `db.create_all()`（第 264 行）**之前**新增一次性 DROP 迁移（见 §5）

**③ `app/models/__init__.py`**
- 第 19 行删除 `from app.models.trading_strategy import TradingStrategy, StrategyExecution`
- 第 25 行 `__all__` 中移除 `'TradingStrategy', 'StrategyExecution'`

**④ `app/templates/base.html`**
- 第 33 行删除 `<a class="nav-link" href="{{ url_for('strategy.index') }}">交易策略</a>`

### 4.3 文档同步

- `docs/TECHNICAL_DOCUMENTATION.md` 若有提及交易策略模块的章节，一并删除（grep 定位后处理）。
- `CLAUDE.md` 未提及该模块，无需改动。
- `graphify-out/` 不手工改，按 CLAUDE.md 要求收尾执行 `_rebuild_code` 重建。

## 5. 数据库处理（用户已确认：彻底删除）

在 `app/__init__.py` 中 `db.create_all()` 之前插入一次性 DROP：

```python
from sqlalchemy import inspect as sa_inspect, text
_insp = sa_inspect(db.engine)
_existing = set(_insp.get_table_names())
for _t in ('strategy_executions', 'trading_strategies'):  # 先子表后父表
    if _t in _existing:
        with db.engine.connect() as _conn:
            _conn.execute(text(f'DROP TABLE IF EXISTS {_t}'))
            _conn.commit()
        logging.info(f'[移除] 已删除表 {_t}')
```

**顺序要点**：必须先 DROP `strategy_executions`（子表，持有 FK），再 DROP `trading_strategies`，否则 SQLite 在启用 FK 时会失败。

**落地策略**：该迁移代码在首次启动时执行一次、后续启动因表已不存在自动跳过。此迁移块可以在下一次 release 时移除（留个 TODO 备注）。

## 6. 风险与缓解

| 风险 | 可能性 | 缓解 |
|------|-------|------|
| 其他模块 import `TradingStrategy`/`TradingStrategyService` | 已 grep 验证零引用（排除 strategy.py 自身与 __init__.py） | — |
| `app/strategies/` 插件误删 | 中 | 执行时按清单白名单操作，`app/strategies/` 整目录**不动** |
| 数据库 DROP 失败（表不存在、FK） | 低 | 用 `DROP TABLE IF EXISTS` + 先子后父顺序 |
| 用户数据永久丢失 | 已由用户确认 | 事前已用 AskUserQuestion 确认；如反悔，`data/stock.db` 可从 OS 级备份 / 最近一次自动备份恢复 |
| `graphify-out/` 缓存陈旧 | 低 | 收尾执行 `_rebuild_code` |
| Windows 下 SQLite 文件被其他进程占用导致 DROP 失败 | 低 | 按现有应用单进程运行假设即可；若真占用，停 `run.py` 后重启 |

## 7. 实施步骤（建议顺序）

1. **清理导航入口**（防止前端再点进去）：编辑 `app/templates/base.html` 第 33 行。
2. **卸载 Blueprint 注册**：编辑 `app/routes/__init__.py`、`app/__init__.py`（保留模型导入，最后步骤一起改）。
3. **卸载模型注册**：编辑 `app/models/__init__.py`、`app/__init__.py` 第 262 行、删除 295-297 行的默认初始化。
4. **添加 DROP 迁移代码**：在 `app/__init__.py` `db.create_all()` 之前插入 §5 代码块。
5. **删除文件**（6 个）：routes/services/models/templates/static。
6. **清理文档**：grep `docs/TECHNICAL_DOCUMENTATION.md` 中可能的提及并删除段落。
7. **启动验证**：`python run.py`，观察日志含 `[移除] 已删除表 strategy_executions` / `trading_strategies`（首次）；再次重启应无这两行（表已不存在）。
8. **手动点检**：打开浏览器访问主页 + 导航栏每个链接。
9. **数据库核验**：`sqlite3 data/stock.db ".tables"` 确认两表已消失。
10. **重建知识图**：`python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"`。
11. **Git 提交**：一个原子 commit，遵循项目 commit 风格（`chore: 移除交易策略模块` 或 `refactor: remove trading strategy module`）。

## 8. 验证步骤（照着跑一遍）

```bash
# 1. 静态引用检查（应全部为空 / 只有 graphify-out）
rtk grep "TradingStrategy" app/
rtk grep "trading_strategy" app/
rtk grep "strategy_bp" app/
rtk grep "url_for('strategy\." app/

# 2. 启动
SCHEDULER_ENABLED=0 python run.py
# 观察：无 ImportError；首次含 "[移除] 已删除表 ..." 日志

# 3. 数据库验证
sqlite3 data/stock.db ".tables" | grep -E "trading_strategies|strategy_executions"
# 应无输出

# 4. HTTP 验证
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5000/strategies/
# 应为 404

# 5. 其他页面冒烟（任选几个）
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5000/
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5000/watch/
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5000/briefing/
```

## 9. 回滚

仅代码 `git revert <commit>` 即可恢复 6 个文件与 4 处编辑。**数据表与数据无法通过 revert 恢复**（用户已确认接受）；若真需恢复表结构，可从 git 历史取回 `app/models/trading_strategy.py` 让 `db.create_all()` 重建空表。

## 10. 后续（Follow-ups）

- 下个版本（或执行后 >1 周确认稳定）再提一个小 PR，把 §5 的一次性 DROP 迁移代码块删除，避免堆积历史迁移。

---

**就绪状态**：清单、引用检查、DB 处理方案、验证步骤均已闭环，可直接进入实施。
