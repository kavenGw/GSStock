# 盯盘信号管线中间层 + 时效层 — 设计

- **日期**：2026-07-20
- **范围**：盯盘告警降噪（信号管线中间层）+ 时效强化（差异化提频 + 分时异动 + 前端新鲜度对齐）
- **状态**：设计已确认，待写实现计划

## 背景与动机

盯盘现有链路：

```
scheduler._run_strategy(name)
  → strategy.scan() 返回 list[Signal]
  → 逐条 event_bus.publish(signal) → NotificationService.dispatch_signal(signal)
     → 逐条去重 + emoji + 格式化 + send_slack
```

三个调度策略职责分离：`watch_preload`（3min force_refresh 写缓存）、`watch_alert`（1min 只读缓存跑 7 检测器）、`watch_realtime`（`*/15` LLM 实时分析直推）。

**已确认的核心痛点**：

1. **告警刷屏 / 噪音**：`watch_alert.scan()` 一轮返回 N 条 Signal（同一只股票可能多条），每条各自 `event_bus.publish` → `dispatch_signal` 逐条推 Slack。同股同一 tick 的破位、下穿均线、放量会变成 3 条独立消息。无跨检测器合并、无优先级分级、无上下文，弱信号与强信号同权刷屏。
2. **时效被 3min preload 卡住**：`watch_preload` 统一 3min force_refresh 写缓存，`watch_alert` 每 1min 只读缓存 → 告警新鲜度实际被 3min 卡住。前端 `/watch/prices` 每 60s 轮询的却是同一份 3min 缓存，**"60s 刷新"是假象**。
3. **分时异动无即时捕捉**：现有"盘中极值"检测器用 API high/low 在 1min tick 上跑，无急拉急跌/放量的速度检测。

**本 spec 目标**：在"7 检测器"与"Slack 推送"之间插入 `WatchSignalPipeline` 纯函数中间层，把逐条信号重构成"一股一条、带主次、带分级、带上下文"的合并推送；同时把 A 股数据刷新差异化提频到 1min，让告警不再看陈价，并新增 1min 级分时异动检测器。

## 非目标（明确不做，但留接缝）

- **命中率反馈闭环 / 告警落库表**（→ 后续 SP3）：仅在 `ConsolidatedAlert.fired_signals` 预留原始信号数据，SP3 落库只需在 push 处加一行。本 spec 不建表、不建评估器。
- **板块联动 / 事件驱动检测器**（→ 后续 SP4）：作为新 detector 未来插入同一管线。
- **告警状态持久化 / 重启恢复**（健壮性方向，本轮未选）：`_fired` / `_price_ring` / 极值仍在内存单例，盘中重启会重置——**已知限制，文档标注**。
- **真·秒级 tick 数据源**：A 股经腾讯 `m1` 最细 1min bar，无 tick 数据，超本 spec 范围。

## 架构总览

### 数据流 Before → After

```
【现状】
watch_alert.scan()
  → check_alerts() 返回 N 条 Signal（同股可能多条）
  → 逐条 event_bus.publish → dispatch_signal → N 条独立 Slack 消息   ❌ 刷屏

【改造后】
watch_alert.scan()
  → check_alerts() 返回 N 条原始 Signal（含新增分时异动检测器）
  → WatchSignalPipeline.process(raw, prices, params, names)
       ├ 分组：按 stock_code 聚合
       ├ 加权 + 共振：算主信号/次信号，映射 HIGH/MID/LOW
       ├ 上下文增强：涨幅 / 量比 / 区间位置
       └ emit：每股一个 ConsolidatedAlert
  → NotificationService.push_watch_alerts(consolidated)   ✅ 一股一条
  → scan() 返回 []（复用 watch_realtime 直推先例，绕过逐条 dispatch）
```

### 模块边界（单一职责、可独立测试）

| 单元 | 职责 | 依赖 | 状态 |
|---|---|---|---|
| `WatchAlertService` | 检测（7+1 检测器），产原始 Signal | 纯计算，无 DB/网络 | 改（+ 分时异动检测器） |
| `WatchSignalPipeline` | 合并 / 分级 / 上下文，产 ConsolidatedAlert | 纯函数，只吃 dict | **新增** |
| `NotificationService.push_watch_alerts` | 合并信号排版 + Slack | pipeline 输出 | 新增方法 |
| `watch_alert.scan` | 编排：取数 → 检测 → 管线 → 直推 | 上述三者 | 改 |
| `watch_preload` | 差异化提频写缓存 | 无 | 改 |

### 关键设计约束

- `WatchSignalPipeline` 是**纯函数**（`list[Signal] + 上下文 dict → list[ConsolidatedAlert]`），不碰 DB、不发网络 → 单测零副作用、易 TDD。
- 跨 tick 去重仍由 `WatchAlertService._fired` 负责（管线只做**同 tick 内**合并），职责不重叠。
- 上下文数据全部复用 scan 里已取的 `prices / alert_params_map / td_results` → **零新增取数**。

## 组件设计

### 1. `WatchSignalPipeline`（新增 `app/services/watch_signal_pipeline.py`）

**签名**：`process(raw_signals, prices, params_map, name_map) -> list[ConsolidatedAlert]`

- `prices[code]`：含 `current_price / change_percent / volume`
- `params_map[code]`：含 `support_levels / resistance_levels / ma_levels / volume_baseline`

**Stage 1 · 分组**：`{code: [signal, ...]}`，按 `signal.data['stock_code']` 聚合。

**Stage 2 · 加权**：`alert_type → weight`

| alert_type | 权重 | 理由 |
|---|---|---|
| `td_sequential` | 5 | 九转完成，强反转信号 |
| `target_price` | 5 | 用户手设目标，意图最强 |
| `support_break` / `resistance_break` | 4 | 关键位破位，趋势性 |
| `intraday_momentum`（新） | 3 | 急拉急跌 |
| `ma_crossover` | 3 | 均线穿越 |
| `support_hold` / `resistance_test` | 2 | 测试未破 |
| `intraday_extreme` | 2 | 刷新日内高低 |
| `volume_anomaly` | 1 | 修饰量，很少单独成信号，主要给同股其他信号加成 |

**Stage 3 · 共振 → 分级**

```
primary = 同股最高权重信号
agg = primary.weight
    + Σ(其余同向信号 × 0.5)         # 方向一致才叠加（如破位 + 下穿 MA 同向）
    + (含 volume_anomaly ? +1 : 0)  # 量价配合加成
分级：agg >= 5 → HIGH；3 <= agg < 5 → MID；agg < 3 → LOW
```

- 主信号 = 权重最高那条；次信号 = 其余（同向优先展示）
- **LOW 静默**（只 debug log 不推），MID/HIGH 推送 → 直接解决刷屏 + 弱信号噪音

**Stage 4 · 上下文增强**（全部从已有 dict 算，零取数）

- 涨幅：`prices[code].change_percent` → `+2.3%`
- 量比：`当前量 / volume_baseline`（用 `_check_volume_anomaly` 同款归一逻辑）→ `1.8x`
- 区间位置：`curr` 相对最近上方阻力 / 下方支撑 → `距上方阻力 30.0(+1.5%)`

**Stage 5 · emit**

```python
@dataclass
class ConsolidatedAlert:
    code: str
    name: str
    priority: str            # HIGH / MID / LOW
    direction: str           # 主信号方向，决定 emoji 🔴/🟢
    primary_line: str        # "突破阻力 30.0 | 当前 30.05"
    secondary_lines: list    # ["下穿 MA5 20.50", "放量 1.8x"]
    context_line: str        # "涨幅 +2.3% | 量比 1.8x | 距上方阻力 32.0(+6.5%)"
    fired_signals: list      # 原始 signal.data 列表 —— 为 SP3 命中率反馈预留落库 hook
```

**产出示例**（同股原本刷 3 条 → 合并 1 条）：

```
🔴 *科森科技(603626)* 突破阻力
突破阻力 30.00 | 当前 30.05
  · 下穿 MA5 20.50
  · 放量 1.8x
涨幅 +2.3% | 量比 1.8x | 距上方阻力 32.00(+6.5%)   [HIGH]
```

### 2. `WatchAlertService` 新增分时异动检测器

- **状态**：`_price_ring[code] = deque(maxlen=5)`，每 tick 存 `(datetime, price)`（单例内存，随 `_reset_if_new_day` 清）。
- **触发**：最近 k 分钟价格速度 `|Δ%| >= 阈值`（急拉 / 急跌），默认 **≤3min 内 ±1.5%**；`direction = up / down`。
- **量价配合**：若同时 `volume_anomaly` 命中 → 由管线 Stage 3 自动加成（放量急拉/急跌），检测器内**不耦合**量能逻辑。
- 产原始 Signal `alert_type='intraday_momentum'` → 走管线合并/分级，天然复用降噪。
- **阈值策略**：单一全局阈值先落地（≤3min ±1.5%），后续用 SP3 命中率数据再调；暂不按市场/波动率分档。
- **诚实边界**："即时"实际下限 = 1min 级速度检测，非字面秒级。

### 3. 时效层 · 差异化提频（`watch_preload` 改造）

`schedule` 从 `interval_minutes:3` 改为 `interval_minutes:1`，内部按市场分档：

| 市场 | 数据源 | 刷新档 | 依据 |
|---|---|---|---|
| A 股 | 腾讯 `qt.gtimg.cn` | **每 tick（1min）** | 并发安全、无限速、零成本 |
| 美股/港股 | yfinance | 每 3 tick（≈3min）+ 现有指数退避 | 限流风险，维持现状不加压 |

- A 股分时：本就每 tick，现在 = 1min（节奏更快，逻辑不变）。
- 趋势 7d/30d：A 股每 15 tick = 15min；美股/港股走慢档（每 45 tick），不给 yfinance 加压。
- `watch_alert` 保持 1min → **A 股告警新鲜度 3min → 1min**；美股/港股维持 3min。
- 复用现有 `_tick_count` + `_backoff` 机制，只加一层"市场 → 是否本 tick 刷新"的 gating。

### 4. 时效层 · 前后端新鲜度对齐

- 后端 A 股现 1min 新鲜 → 前端 `/watch/prices` 60s 轮询对 A 股**变真实**。
- 美股/港股仍 3min → `/watch/prices` 每条 price **新增 `age_seconds`**（从缓存时间戳算），前端按市场行**显示真实新鲜度**（如 "3min前"），不再让用户误以为都是 60s 新。
- 前端 `watch.js`：保持 60s 轮询，price 行渲染 per-market 新鲜度标记（复用已有 `stale` 字段，补 `age_seconds`）。

## 文件改动全景

| 文件 | 改动 | 新增/改 |
|---|---|---|
| `app/services/watch_signal_pipeline.py` | 管线纯函数 + `ConsolidatedAlert` | **新增** |
| `app/services/watch_alert_service.py` | `_check_intraday_momentum` + `_price_ring` 环形缓冲 | 改 |
| `app/strategies/watch_alert/__init__.py` | scan 编排：检测 → 管线 → `push_watch_alerts` → 返回 `[]` | 改 |
| `app/services/notification.py` | `push_watch_alerts(consolidated)` 合并排版 | 新增方法 |
| `app/strategies/watch_preload/__init__.py` | `interval:1` + 差异化市场 gating | 改 |
| `app/routes/watch.py` | `/prices` 补 `age_seconds` | 改 |
| `app/static/js/watch.js` | per-market 新鲜度渲染 | 改 |
| `.claude/rules/watch.md` + `.claude/rules/notifications.md` | 同步管线 / 提频 / 新排版 | 文档 |

## 测试策略（TDD 优先）

- **`tests/test_watch_signal_pipeline.py`**（新）：分组 / 权重共振 → 分级（HIGH/MID/LOW 边界）/ 上下文行拼装 / LOW 静默 / 同向叠加 vs 反向不叠加。管线是纯函数，最适合 TDD。
- **`tests/test_watch_alert_service.py`**（扩）：`_check_intraday_momentum` 速度阈值、方向、跨 tick 去重、环形缓冲 maxlen。
- **preload gating**：A 股每 tick、美股/港股每 3 tick 的 tick 计数逻辑。
- **`push_watch_alerts` 排版**：符合 `notifications.md` 规范（emoji + 主信号 + 次信号 bullet + context）的快照断言。
- 全量回归：`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ -v`。

## 分支策略

按 `.claude/rules/dev-environment.md`：本 spec 改 `app/` 代码（非投研写档）→ 实现阶段应开**独立 git worktree** 隔离，不污染 main、避免并行 session 抢 git index。

## 后续 spec 依赖链

```
本 spec（信号管线 + 时效） → SP3（命中率反馈闭环，依赖管线的分级 + fired_signals 落库）
                          → SP4（板块联动 / 事件驱动，作为新 detector 插入管线）
```
