# 赛事获取调度层重试队列设计

> 解决问题：07:00 LoL 赛程推送时，部分联赛（截图为 LCK / 先锋赛）虽已经过单次调用内部 3 次退避重试 `[1s, 3s, 8s]`，仍因 API 持续异常窗口而失败，直接推 "数据获取失败" 影响阅读体验。

## 目标

- 首轮（07:00）拉取后，**成功联赛立即推送**，失败联赛不出现在首条消息里
- 失败联赛进入挂起队列，**5min × 3 轮**调度层延后重试
- 重试期间任何一轮拿到 → 立即"补推"该联赛
- 全部 3 轮都失败才推"数据获取失败"
- NBA 同语义（视作单 unit），整体失败时延后重试

## 非目标

- 不持久化到 DB（状态只活 ~15min，进程内内存即可）
- 不改 `_fetch_lol_esports_schedule` 内部 3×退避重试（保留作为底层重试）
- 不引入跨进程协调（单 worker 部署假设）

## 架构

### 推送单元（unit）

把"一次推送"切成更细的粒度：每个 LoL 联赛、整个 NBA 各为一个独立 unit，状态机：

```
首轮拉取
  ├─ 成功 → 立即推送 → state = pushed（终态）
  └─ 失败 → enqueue → state = pending
                       ↓
              APScheduler 一次性 job (now+5min)
                       ↓
                   _retry_one
                       ├─ 成功 → 补推 → pushed
                       └─ 失败
                           ├─ attempts < 3 → 再挂 5min 后任务
                           └─ attempts == 3 → 推"获取失败" → failed
```

### 状态存储

进程内模块级字典 `_pending: dict[str, _PendingUnit]`：

```python
@dataclass
class _PendingUnit:
    date: date           # 目标推送日期（北京时间 today）
    kind: str            # 'lol' | 'nba'
    name: str            # 'LCK' / '先锋赛' / 'LPL' / 'NBA'
    attempts: int        # 1=首轮已失败，3=终态
    max_attempts: int = 3
```

key = `f"{date.isoformat()}:{kind}:{name}"`，保证同日同 unit 不重复入队。

**进程重启**：APScheduler 用内存 jobstore（项目现状），状态字典与挂起 job 一起丢失 — 一致语义，最多漏一次补推，可接受。

## 模块划分

### 新增 `app/services/esports_retry_queue.py`

```python
def enqueue(date_, kind: str, name: str) -> None:
    """首轮或某轮失败后调用。attempts 自增，挂下一次重试 job。
    幂等：同 key 已 pending 直接 return。"""

def _retry_one(key: str) -> None:
    """APScheduler 一次性 job 的回调。
    - 重新拉该 unit 数据
    - 成功 → 补推 + pop _pending
    - 失败 + attempts < 3 → 再挂 5min 后任务
    - 失败 + attempts == 3 → 推"获取失败" + pop _pending
    - 跨日（unit.date != today_cst）→ 静默 pop，不推
    """

def clear_for_date(date_) -> None:
    """测试/清理用，移除指定日期所有挂起 unit 及其 APScheduler job。"""
```

内部辅助：
- `_push_lol_unit(name, matches)` / `_push_nba_unit(games)` — 单 unit 推送（首推与补推共用，只在头部 emoji/标题区分"今日 / 补充"）
- `_push_failed(kind, name)` — 终告"数据获取失败（已重试 3 次）"

### 改造 `app/strategies/esports_daily_schedule/__init__.py`

`_push_nba_today` / `_push_lol_today` 拿到结果后：

| 现行 | 新行为 |
|------|--------|
| `lol is None` → 推 `🎮 今日 LoL 赛程\n数据获取失败` | `enqueue(today, 'lol', league)` 对每个 `LOL_ALWAYS_SHOW` 联赛 |
| 某联赛 `data is None` → 拼 `*LCK*\n数据获取失败` 段 | 跳过该段，`enqueue(today, 'lol', league)` |
| NBA `nba is None` → 推 `🏀 今日 NBA 赛程\n数据获取失败` | `enqueue(today, 'nba', 'NBA')` |
| 成功联赛/NBA | 不变，立即推送 |

首推消息只列成功联赛；如果首轮所有联赛都失败，首推消息整段不发（避免发 "LoL 赛程（0 场）" 空消息）。

## 推送格式

### 首推（保持现状）

```
🎮 *今日 LoL 赛程* (2场)

*LPL* (2场)
  · 17:00  WeiboGaming vs Xi'an Team WE
  · 19:00  Shenzhen NIN... vs Anyone's Legend
```

### 补推（新增）

```
🎮 *LoL 补充* — *LCK* (3场)
  · 17:00  T1 vs Gen.G
  · ...
```

```
🏀 *NBA 补充* (5场)
  · 09:00  湖人 vs 勇士
  · ...
```

### 终告（新增）

```
🎮 *LoL — LCK* 数据获取失败（已重试 3 次）
```

```
🏀 *今日 NBA 赛程* 数据获取失败（已重试 3 次）
```

频道与首推一致：LoL → `news_lol`，NBA → `news_nba`。

## 调度集成

用 `app.scheduler.scheduler.add_job(...)`：

```python
scheduler.add_job(
    _retry_one,
    'date',
    run_date=datetime.now(_CST) + timedelta(minutes=5),
    args=[key],
    id=f"esports_retry:{key}",
    replace_existing=True,  # 防御性
)
```

`replace_existing=True` 配合 `enqueue()` 入口的幂等检查双重保险。

## 边角

| 场景 | 处理 |
|------|------|
| 进程重启，pending 丢失 | 接受，最多漏一次补推；对应 APScheduler job 也随内存型 jobstore 丢失，状态一致 |
| 单 unit 重复 enqueue（同 key） | 入口 `if key in _pending: return` 幂等 |
| 跨日（重试时 today 已变） | `_retry_one` 起手对比 `unit.date != today_cst` 直接 pop 不推，避免凌晨发昨日赛程 |
| 第 N 轮拉到了空 `{'today': [], 'yesterday': []}` | 视作"成功+今日无赛事"。LoL 部分：常驻联赛（`LOL_ALWAYS_SHOW`）补推"今日无赛事"消息；非常驻不推。NBA 部分：补推"今日无关注球队比赛"。终态 pushed |
| `_fetch_lol_esports_schedule` 抛非 retriable 4xx（401/403/404） | 当前返回 None，本设计仍按"失败"挂队列；3 轮后推"数据获取失败"。能接受 — 401/403 是配置/权限问题需要人工介入，重试本身确实救不回，但终告消息可以触达运营 |
| NBA 球队过滤后为空 | 与重试无关，沿用现有 "无关注球队比赛"，state = pushed |

## 时序示例

```
07:00:00  cron 触发 scan()
          ├─ get_nba_schedule() → games  ✅ 推 "🏀 今日 NBA 赛程 (3场)"
          ├─ get_lol_schedule() → {LPL: ok, LCK: None, 先锋赛: None, ...}
          ├─ 推 "🎮 今日 LoL 赛程 (2场) - LPL ..."（仅 LPL）
          ├─ enqueue(today, 'lol', 'LCK')      → attempts=1, job@07:05
          └─ enqueue(today, 'lol', '先锋赛')   → attempts=1, job@07:05

07:05:00  _retry_one("2026-05-07:lol:LCK") → 拉到 → 推 "🎮 LoL 补充 LCK (3场)"
          _retry_one("2026-05-07:lol:先锋赛") → 仍失败 → attempts=2, job@07:10

07:10:00  _retry_one("2026-05-07:lol:先锋赛") → 仍失败 → attempts=3, job@07:15

07:15:00  _retry_one("2026-05-07:lol:先锋赛") → 仍失败 → 推 "🎮 LoL — 先锋赛 数据获取失败（已重试 3 次）"
```

## 测试

`tests/test_esports_retry_queue.py`，mock `EsportsService._fetch_lol_esports_schedule` / `EsportsService.get_nba_schedule` 与 `app.scheduler.scheduler.add_job` / `NotificationService.send_slack`：

1. **首轮全成功** → `_pending` 空、`add_job` 未调用、Slack 仅首推消息
2. **LCK 首轮失败 + 第 2 轮成功** → 首推不含 LCK，补推 "LoL 补充 LCK"，`_pending` 清空
3. **LCK 全 3 轮失败** → 第 3 轮触发 "数据获取失败" 终告，`_pending` 清空
4. **NBA 首轮失败 + 第 2 轮成功** → 首推无 NBA 消息（NBA 整 unit 失败），补推完整 NBA 消息
5. **跨日丢弃** → 构造 `unit.date = yesterday`，`_retry_one` 直接 pop 不推
6. **重复 enqueue 幂等** → 同 key 调 2 次，`add_job` 仅调用 1 次
7. **第 N 轮拉到空数据** → 常驻联赛补推 "今日无赛事"，终态 pushed
8. **首轮所有联赛失败** → 不发首条消息，全部挂队列；模拟 3 轮全失败 → 每个 unit 各自终告

## 实施步骤

参考 writing-plans 阶段细化。粗粒度：

1. 新建 `app/services/esports_retry_queue.py`（含 `_PendingUnit`、`enqueue`、`_retry_one`、`clear_for_date` 与内部推送辅助）
2. 改造 `app/strategies/esports_daily_schedule/__init__.py`（首轮失败调 `enqueue` 而非直接推失败）
3. 单测 `tests/test_esports_retry_queue.py`（8 用例覆盖）
4. CLAUDE.md 在 "赛事推送配置" 节加一段说明重试队列语义
5. 跑全量测试 `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/ -v`

## 不引入的复杂度（YAGNI）

- 持久化（DB / 文件） — 进程重启丢失可接受
- 跨进程协调（Redis 等） — 单 worker 部署
- 可配置重试次数 / 间隔环境变量 — 5min × 3 轮够用，需要时再加
- 重试时区分 retriable / non-retriable 4xx — 底层 `_fetch_lol_esports_schedule` 已经做过区分，调度层简化为统一重试
