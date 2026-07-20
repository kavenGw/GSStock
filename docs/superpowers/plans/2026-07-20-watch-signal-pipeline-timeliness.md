# 盯盘信号管线中间层 + 时效层 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在盯盘"7 检测器 → Slack 推送"间插入 `WatchSignalPipeline` 纯函数中间层（同 tick 合并/分级/上下文），并把 A 股差异化提频到 1min + 新增分时异动检测器 + 前后端新鲜度对齐。

**Architecture:** `WatchAlertService` 产原始 `list[Signal]`（新增第 8 个 `intraday_momentum` 检测器）→ `WatchSignalPipeline.process()` 按股聚合、加权共振分级、上下文增强，产 `ConsolidatedAlert` → `NotificationService.push_watch_alerts()` 一股一条直推、跳过 LOW → `watch_alert.scan()` 返回 `[]`（复用 `watch_realtime` 直推先例，绕过逐条 `dispatch_signal`）。时效层：`watch_preload` 改 `interval:1` + 差异化市场 gating；`/watch/prices` 补 `age_seconds`；`watch.js` 按市场渲染真实新鲜度。

**Tech Stack:** Python 3.10 / Flask / SQLAlchemy / dataclass / APScheduler 策略插件框架 / pytest / 前端原生 JS + ECharts。

**Spec:** `docs/superpowers/specs/2026-07-20-watch-signal-pipeline-timeliness-design.md`

## Global Constraints

- 所有 git / pytest 命令前加 `rtk`，链式 `&&` 中也要。
- `git add` 与 `git commit` **放进同一条 Bash 命令链**（并行 session 会抢 index）；中文多行 message 走文件 `git commit -F`，用精确路径 add。
- 单测命令：`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest <path> -v`。
- 单测平铺 `tests/test_*.py`，不建子目录。
- 不写 backup 文件、不写多余注释（只保留关键流程注释）。
- 写含中文的文件必须 `encoding='utf-8'`。
- 响应中文。
- 本 spec 改 `app/` 代码 → 执行前应开**独立 git worktree** 隔离（`superpowers:using-git-worktrees`）。
- `WatchSignalPipeline` 必须是纯函数：不碰 DB、不发网络、不 import service 层取数入口。
- 跨 tick 去重仍归 `WatchAlertService._fired`；管线只做同 tick 内合并。

---

## File Structure

| 文件 | 职责 | 状态 |
|---|---|---|
| `app/services/watch_signal_pipeline.py` | 管线纯函数 + `ConsolidatedAlert` dataclass + 权重表 | 新增 |
| `app/services/watch_alert_service.py` | +`_check_intraday_momentum` +`_price_ring`/`_momentum_cooldown` 状态 | 改 |
| `app/services/notification.py` | +`push_watch_alerts(alerts)` 合并排版 | 改 |
| `app/strategies/watch_alert/__init__.py` | scan 编排：检测→管线→直推→返回 `[]` | 改 |
| `app/strategies/watch_preload/__init__.py` | `interval:1` + `_should_refresh_market` gating | 改 |
| `app/routes/watch.py` | `/prices` 每条补 `age_seconds` | 改 |
| `app/static/js/watch.js` | price 行按市场渲染真实新鲜度 | 改 |
| `tests/test_watch_signal_pipeline.py` | 管线单测 | 新增 |
| `tests/test_watch_alert_service.py` | 分时异动检测器单测（若已存在则扩） | 新增/扩 |
| `tests/test_watch_preload_cadence.py` | 差异化 gating 单测 | 新增 |
| `.claude/rules/watch.md` / `.claude/rules/notifications.md` | 同步管线/提频/新排版 | 文档 |

---

## 参考：现有接口签名（实现者须知）

- `Signal`（`app/strategies/base.py`）：`Signal(strategy, priority, title, detail, data: dict, timestamp)`。`data` 含 `stock_code / alert_type / direction / level` 等。
- `WatchAlertService._make_signal(name, code, title, detail, data)` → `Signal`，其中 `signal.title = f'{name}({code}) {title}'`（**带 name(code) 前缀**）。
- `WatchAlertService.check_alerts(prices, name_map, alert_params_map, td_results, trading_minutes) -> list[Signal]`。
- `prices[code]`：`current_price / change_percent / volume / name / high / low / _is_degraded / last_fetch_time(ISO 字符串)`。
- `alert_params_map[code]`：`target_prices / volume_baseline / volume_anomaly_ratio / support_levels / resistance_levels / ma_levels`。
- `trading_minutes[code]`：`{elapsed, total}`（分钟）。
- `NotificationService.send_slack(message, channel) -> bool`；`CHANNEL_WATCH` 已定义（`notification.py`）。
- 方向 → emoji：`{high,above,up,buy,resistance_break}`→🔴（A 股涨用红）；`{low,below,down,sell,support_break}`→🟢。

---

### Task 1: `WatchSignalPipeline` 核心 — 分组/加权/共振/分级

**Files:**
- Create: `app/services/watch_signal_pipeline.py`
- Test: `tests/test_watch_signal_pipeline.py`

**Interfaces:**
- Produces:
  - `SIGNAL_WEIGHTS: dict[str, int]`
  - `@dataclass ConsolidatedAlert(code:str, name:str, priority:str, direction:str, primary_line:str, secondary_lines:list, context_line:str, fired_signals:list)`
  - `WatchSignalPipeline.process(raw_signals:list, prices:dict, params_map:dict, name_map:dict, trading_minutes:dict=None) -> list[ConsolidatedAlert]`
  - `WatchSignalPipeline._direction_sign(direction:str) -> int`
- Consumes: `Signal`（`app/strategies/base.py`）。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_watch_signal_pipeline.py
from app.strategies.base import Signal
from app.services.watch_signal_pipeline import (
    WatchSignalPipeline, ConsolidatedAlert, SIGNAL_WEIGHTS,
)


def _sig(code, alert_type, direction='', title='X'):
    return Signal(strategy='watch_alert', priority='HIGH',
                  title=f'测试({code}) {title}', detail='',
                  data={'stock_code': code, 'alert_type': alert_type, 'direction': direction})


def test_group_one_alert_per_stock():
    raw = [
        _sig('603626', 'resistance_break', 'resistance_break', '突破阻力 30.0 | 当前 30.05'),
        _sig('603626', 'ma_crossover', 'up', '上穿 MA5'),
        _sig('600519', 'td_sequential', 'buy', 'TD九转买入'),
    ]
    alerts = WatchSignalPipeline.process(raw, {}, {}, {'603626': '科森科技', '600519': '茅台'})
    assert len(alerts) == 2
    by_code = {a.code: a for a in alerts}
    assert by_code['603626'].primary_line == '突破阻力 30.0 | 当前 30.05'
    assert '上穿 MA5' in by_code['603626'].secondary_lines
    assert by_code['603626'].name == '科森科技'


def test_priority_high_on_confluence():
    # 破位(4) + 同向下穿MA(3×0.5=1.5) + 放量(+1) = 6.5 → HIGH
    raw = [
        _sig('603626', 'support_break', 'support_break', '跌破支撑'),
        _sig('603626', 'ma_crossover', 'down', '下穿 MA5'),
        _sig('603626', 'volume_anomaly', '', '放量'),
    ]
    alerts = WatchSignalPipeline.process(raw, {}, {}, {})
    assert alerts[0].priority == 'HIGH'


def test_priority_low_on_weak_single():
    # 单条 intraday_extreme(2) < 3 → LOW
    raw = [_sig('603626', 'intraday_extreme', 'high', '刷新前高')]
    alerts = WatchSignalPipeline.process(raw, {}, {}, {})
    assert alerts[0].priority == 'LOW'


def test_opposite_direction_not_stacked():
    # 破位(4) + 反向上穿MA(不叠加) → agg=4 → MID（非 HIGH）
    raw = [
        _sig('603626', 'support_break', 'support_break', '跌破支撑'),
        _sig('603626', 'ma_crossover', 'up', '上穿 MA5'),
    ]
    alerts = WatchSignalPipeline.process(raw, {}, {}, {})
    assert alerts[0].priority == 'MID'


def test_ignores_signal_without_stock_code():
    raw = [Signal(strategy='watch_alert', priority='HIGH', title='x', detail='', data={})]
    assert WatchSignalPipeline.process(raw, {}, {}, {}) == []
```

- [ ] **Step 2: 运行确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_signal_pipeline.py -v`
Expected: FAIL（`ModuleNotFoundError: watch_signal_pipeline`）

- [ ] **Step 3: 写实现**

```python
# app/services/watch_signal_pipeline.py
"""盯盘信号管线中间层 — 同 tick 合并/分级/上下文增强（纯函数，无 DB/网络）"""
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

SIGNAL_WEIGHTS = {
    'td_sequential': 5,
    'target_price': 5,
    'support_break': 4,
    'resistance_break': 4,
    'intraday_momentum': 3,
    'ma_crossover': 3,
    'support_hold': 2,
    'resistance_test': 2,
    'intraday_extreme': 2,
    'volume_anomaly': 1,
}

_BULLISH = {'high', 'above', 'up', 'buy', 'resistance_break'}
_BEARISH = {'low', 'below', 'down', 'sell', 'support_break'}


@dataclass
class ConsolidatedAlert:
    code: str
    name: str
    priority: str
    direction: str
    primary_line: str
    secondary_lines: list = field(default_factory=list)
    context_line: str = ''
    fired_signals: list = field(default_factory=list)


class WatchSignalPipeline:

    @staticmethod
    def _direction_sign(direction: str) -> int:
        if direction in _BULLISH:
            return 1
        if direction in _BEARISH:
            return -1
        return 0

    @staticmethod
    def _weight(sig) -> float:
        return SIGNAL_WEIGHTS.get((sig.data or {}).get('alert_type'), 1)

    @staticmethod
    def _strip_prefix(title: str, name: str, code: str) -> str:
        prefix = f'{name}({code}) '
        return title[len(prefix):] if title.startswith(prefix) else title

    @staticmethod
    def process(raw_signals, prices, params_map, name_map, trading_minutes=None):
        trading_minutes = trading_minutes or {}

        grouped = {}
        for sig in raw_signals:
            code = (sig.data or {}).get('stock_code')
            if not code:
                continue
            grouped.setdefault(code, []).append(sig)

        alerts = []
        for code, sigs in grouped.items():
            name = name_map.get(code, code)
            primary = max(sigs, key=WatchSignalPipeline._weight)
            primary_dir = (primary.data or {}).get('direction', '')
            primary_sign = WatchSignalPipeline._direction_sign(primary_dir)

            agg = WatchSignalPipeline._weight(primary)
            has_volume = False
            for s in sigs:
                if s is primary:
                    continue
                at = (s.data or {}).get('alert_type')
                if at == 'volume_anomaly':
                    has_volume = True
                    continue
                s_sign = WatchSignalPipeline._direction_sign((s.data or {}).get('direction', ''))
                if s_sign != 0 and s_sign == primary_sign:
                    agg += WatchSignalPipeline._weight(s) * 0.5
            if has_volume:
                agg += 1

            priority = 'HIGH' if agg >= 5 else ('MID' if agg >= 3 else 'LOW')

            primary_line = WatchSignalPipeline._strip_prefix(primary.title, name, code)
            secondary_lines = [
                WatchSignalPipeline._strip_prefix(s.title, name, code)
                for s in sigs if s is not primary
            ]
            context_line = WatchSignalPipeline._build_context(code, prices, params_map, trading_minutes)

            alerts.append(ConsolidatedAlert(
                code=code, name=name, priority=priority, direction=primary_dir,
                primary_line=primary_line, secondary_lines=secondary_lines,
                context_line=context_line,
                fired_signals=[s.data for s in sigs],
            ))
        return alerts

    @staticmethod
    def _build_context(code, prices, params_map, trading_minutes):
        return ''  # Task 2 实现
```

- [ ] **Step 4: 运行确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_signal_pipeline.py -v`
Expected: PASS（5 passed）

- [ ] **Step 5: Commit**

```bash
cat > .git/MSG.txt <<'EOF'
feat(watch): 新增 WatchSignalPipeline 核心 — 分组/加权/共振/分级

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
rtk git add app/services/watch_signal_pipeline.py tests/test_watch_signal_pipeline.py && rtk git commit -F .git/MSG.txt && rm -f .git/MSG.txt
```

---

### Task 2: `WatchSignalPipeline._build_context` — 上下文增强

**Files:**
- Modify: `app/services/watch_signal_pipeline.py`（`_build_context`）
- Test: `tests/test_watch_signal_pipeline.py`

**Interfaces:**
- Produces: `_build_context(code, prices, params_map, trading_minutes) -> str`，输出形如 `涨幅 +2.30% | 量比 1.8x | 距上方阻力 32.0(+6.5%)`。
- Consumes: `prices[code].change_percent/volume/current_price`、`params_map[code].volume_baseline/support_levels/resistance_levels`、`trading_minutes[code].elapsed/total`。

- [ ] **Step 1: 写失败测试**

```python
# 追加到 tests/test_watch_signal_pipeline.py
def test_context_change_volume_range():
    prices = {'603626': {'current_price': 30.05, 'change_percent': 2.30, 'volume': 1200}}
    params = {'603626': {'volume_baseline': 1000, 'resistance_levels': [32.0, 35.0], 'support_levels': [28.0]}}
    tm = {'603626': {'elapsed': 120, 'total': 240}}  # 半天 → 归一化 ×2 → 量比 2.4x
    ctx = WatchSignalPipeline._build_context('603626', prices, params, tm)
    assert '涨幅 +2.30%' in ctx
    assert '量比 2.4x' in ctx
    assert '距上方阻力 32.0(+6.5%)' in ctx


def test_context_uses_support_when_no_resistance_above():
    prices = {'600519': {'current_price': 100.0, 'change_percent': -1.0, 'volume': 0}}
    params = {'600519': {'resistance_levels': [90.0], 'support_levels': [95.0, 80.0]}}
    ctx = WatchSignalPipeline._build_context('600519', prices, params, {})
    assert '距下方支撑 95.0(-5.0%)' in ctx


def test_context_skips_volume_ratio_on_unit_glitch():
    prices = {'603626': {'current_price': 30.0, 'change_percent': 0, 'volume': 999999}}
    params = {'603626': {'volume_baseline': 100}}
    tm = {'603626': {'elapsed': 240, 'total': 240}}  # 比率>50 → 跳过量比
    ctx = WatchSignalPipeline._build_context('603626', prices, params, tm)
    assert '量比' not in ctx
```

- [ ] **Step 2: 运行确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_signal_pipeline.py -k context -v`
Expected: FAIL（`_build_context` 返回空串）

- [ ] **Step 3: 写实现**

```python
# 替换 watch_signal_pipeline.py 的 _build_context 桩

    VOLUME_RATIO_CAP = 50.0

    @staticmethod
    def _build_context(code, prices, params_map, trading_minutes):
        p = prices.get(code, {})
        params = params_map.get(code, {})
        parts = []

        chg = p.get('change_percent')
        if chg is not None:
            parts.append(f'涨幅 {chg:+.2f}%')

        baseline = params.get('volume_baseline', 0)
        volume = p.get('volume')
        if baseline and volume:
            tm = trading_minutes.get(code) or {}
            elapsed = tm.get('elapsed', 0)
            total = tm.get('total', 0)
            normalized = volume / (elapsed / total) if elapsed > 0 and total > 0 else volume
            ratio = normalized / baseline
            if ratio < WatchSignalPipeline.VOLUME_RATIO_CAP:
                parts.append(f'量比 {ratio:.1f}x')

        curr = p.get('current_price')
        if curr:
            resistances = sorted(l for l in params.get('resistance_levels', []) if l and l > curr)
            supports = sorted((l for l in params.get('support_levels', []) if l and l < curr), reverse=True)
            if resistances:
                r = resistances[0]
                parts.append(f'距上方阻力 {r}({(r - curr) / curr * 100:+.1f}%)')
            elif supports:
                s = supports[0]
                parts.append(f'距下方支撑 {s}({(s - curr) / curr * 100:+.1f}%)')

        return ' | '.join(parts)
```

- [ ] **Step 4: 运行确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_signal_pipeline.py -v`
Expected: PASS（8 passed）

- [ ] **Step 5: Commit**

```bash
cat > .git/MSG.txt <<'EOF'
feat(watch): WatchSignalPipeline 上下文增强（涨幅/量比/区间位置）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
rtk git add app/services/watch_signal_pipeline.py tests/test_watch_signal_pipeline.py && rtk git commit -F .git/MSG.txt && rm -f .git/MSG.txt
```

---

### Task 3: `NotificationService.push_watch_alerts` — 合并排版直推

**Files:**
- Modify: `app/services/notification.py`（新增 `push_watch_alerts` 静态方法）
- Modify: `.claude/rules/notifications.md`（合并推送新格式）
- Test: `tests/test_watch_signal_pipeline.py`（push 排版 + LOW skip）

**Interfaces:**
- Produces: `NotificationService.push_watch_alerts(alerts:list[ConsolidatedAlert]) -> bool`（推送 MID/HIGH，跳过 LOW；返回是否有推送）。
- Consumes: `ConsolidatedAlert`（Task 1）、`send_slack`、`CHANNEL_WATCH`。

- [ ] **Step 1: 写失败测试**

```python
# 追加到 tests/test_watch_signal_pipeline.py
from unittest.mock import patch
from app.services.notification import NotificationService


def test_push_skips_low_and_formats_high():
    high = ConsolidatedAlert(
        code='603626', name='科森科技', priority='HIGH', direction='resistance_break',
        primary_line='突破阻力 30.00 | 当前 30.05',
        secondary_lines=['下穿 MA5 20.50', '放量 1.8x'],
        context_line='涨幅 +2.30% | 量比 1.8x | 距上方阻力 32.00(+6.5%)',
    )
    low = ConsolidatedAlert(code='600519', name='茅台', priority='LOW', direction='high',
                            primary_line='刷新前高')
    sent = []
    with patch.object(NotificationService, 'send_slack', side_effect=lambda t, c: sent.append((t, c)) or True):
        ok = NotificationService.push_watch_alerts([high, low])
    assert ok is True
    assert len(sent) == 1  # LOW 被跳过
    text, _ = sent[0]
    assert '🔴 *科森科技(603626)*' in text
    assert '[HIGH]' in text
    assert '突破阻力 30.00 | 当前 30.05' in text
    assert '  · 下穿 MA5 20.50' in text
    assert '涨幅 +2.30%' in text
```

- [ ] **Step 2: 运行确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_signal_pipeline.py -k push -v`
Expected: FAIL（`AttributeError: push_watch_alerts`）

- [ ] **Step 3: 写实现**

在 `app/services/notification.py` 的 `NotificationService` 类内、`dispatch_signal` 之后新增：

```python
    @staticmethod
    def push_watch_alerts(alerts) -> bool:
        """合并盯盘告警推送：一股一条，跳过 LOW（LOW 只 debug log）"""
        pushed = 0
        for a in alerts:
            if a.priority == 'LOW':
                logger.debug(f'[盯盘告警] {a.name}({a.code}) LOW 静默: {a.primary_line}')
                continue
            if a.direction in ('high', 'above', 'up', 'buy', 'resistance_break'):
                emoji = '🔴'
            elif a.direction in ('low', 'below', 'down', 'sell', 'support_break'):
                emoji = '🟢'
            else:
                emoji = '⚠️'
            lines = [f'{emoji} *{a.name}({a.code})*  [{a.priority}]', a.primary_line]
            for s in a.secondary_lines:
                lines.append(f'  · {s}')
            if a.context_line:
                lines.append(a.context_line)
            if NotificationService.send_slack('\n'.join(lines), CHANNEL_WATCH):
                pushed += 1
        return pushed > 0
```

- [ ] **Step 4: 运行确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_signal_pipeline.py -v`
Expected: PASS（9 passed）

- [ ] **Step 5: 更新 notifications.md**

在 `.claude/rules/notifications.md` 的「盯盘告警推送格式」节末尾追加：

```markdown
**合并推送（信号管线）**：`watch_alert` 不再逐条 dispatch，而是经 `WatchSignalPipeline` 按股合并 → `NotificationService.push_watch_alerts()` 一股一条。格式：`emoji *名称(代码)* [优先级]` 首行 + 主信号行 + 次信号 `  · ` bullet + 上下文行（涨幅/量比/区间位置）。优先级 HIGH/MID 推送，LOW 静默（只 debug log）。分级 = 主信号权重 + 同向次信号×0.5 + 量价配合+1。
```

- [ ] **Step 6: Commit**

```bash
cat > .git/MSG.txt <<'EOF'
feat(watch): 新增 push_watch_alerts 合并排版直推 + 文档同步

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
rtk git add app/services/notification.py tests/test_watch_signal_pipeline.py .claude/rules/notifications.md && rtk git commit -F .git/MSG.txt && rm -f .git/MSG.txt
```

---

### Task 4: `WatchAlertService._check_intraday_momentum` — 分时异动检测器

**Files:**
- Modify: `app/services/watch_alert_service.py`（+状态 +检测器 +接入 check_alerts）
- Test: `tests/test_watch_alert_service.py`

**Interfaces:**
- Produces: `WatchAlertService._check_intraday_momentum(code, name, data) -> list[Signal]`，产 `alert_type='intraday_momentum'`、`direction='up'|'down'`、`change_pct` 的 Signal。
- Consumes: `data.current_price`、`self._price_ring`、`self._momentum_cooldown`、`self._make_signal`。

**关键设计**：`_price_ring[code]=deque(maxlen=5)` 每 tick 存 `(datetime, price)`；取窗口内最旧价算速度；`|Δ%| ≥ 1.5%`（默认，≤3min 窗口）触发；同向 cooldown = `WATCH_ALERT_COOLDOWN_MINUTES`。**注意**：单例状态在 `__new__` 初始化、`_reset_if_new_day` 清空。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_watch_alert_service.py
from datetime import datetime, timedelta
from app.services.watch_alert_service import WatchAlertService


def _fresh_service():
    # 重置单例状态，避免测试间污染
    svc = WatchAlertService()
    svc._price_ring = {}
    svc._momentum_cooldown = {}
    svc._fired = {}
    svc._last_trading_date = datetime.now().strftime('%Y-%m-%d')
    return svc


def test_momentum_fires_on_fast_rise():
    svc = _fresh_service()
    now = datetime.now()
    # 手动灌入 3 分钟前的旧价
    from collections import deque
    svc._price_ring['603626'] = deque([(now - timedelta(minutes=3), 30.0)], maxlen=5)
    sigs = svc._check_intraday_momentum('603626', '科森科技', {'current_price': 30.6})  # +2%
    assert len(sigs) == 1
    assert sigs[0].data['alert_type'] == 'intraday_momentum'
    assert sigs[0].data['direction'] == 'up'


def test_momentum_silent_below_threshold():
    svc = _fresh_service()
    now = datetime.now()
    from collections import deque
    svc._price_ring['603626'] = deque([(now - timedelta(minutes=3), 30.0)], maxlen=5)
    sigs = svc._check_intraday_momentum('603626', '科森科技', {'current_price': 30.2})  # +0.67%
    assert sigs == []


def test_momentum_cooldown_dedup():
    svc = _fresh_service()
    now = datetime.now()
    from collections import deque
    svc._price_ring['603626'] = deque([(now - timedelta(minutes=3), 30.0)], maxlen=5)
    first = svc._check_intraday_momentum('603626', '科森科技', {'current_price': 30.6})
    second = svc._check_intraday_momentum('603626', '科森科技', {'current_price': 30.7})
    assert len(first) == 1 and second == []  # cooldown 内不重复


def test_momentum_ring_maxlen():
    svc = _fresh_service()
    for i in range(8):
        svc._check_intraday_momentum('603626', '科森科技', {'current_price': 30.0 + i * 0.01})
    assert len(svc._price_ring['603626']) == 5
```

- [ ] **Step 2: 运行确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_alert_service.py -v`
Expected: FAIL（`AttributeError: _check_intraday_momentum` / `_price_ring`）

- [ ] **Step 3: 写实现**

在 `app/services/watch_alert_service.py`：

1) `__new__` 内新增状态（`_instance._fired = {}` 附近）：
```python
            cls._instance._price_ring = {}
            cls._instance._momentum_cooldown = {}
```

2) `_reset_if_new_day` 内追加清空：
```python
            self._price_ring = {}
            self._momentum_cooldown = {}
```

3) 顶部常量区（`VOLUME_RATIO_CAP` 附近）新增：
```python
    INTRADAY_MOMENTUM_WINDOW_MIN = 3
    INTRADAY_MOMENTUM_PCT = 1.5
```

4) 新增检测器方法：
```python
    def _check_intraday_momentum(self, code: str, name: str, data: dict) -> list[Signal]:
        from collections import deque
        signals = []
        curr = data.get('current_price')
        if curr is None:
            return signals

        now = datetime.now()
        ring = self._price_ring.setdefault(code, deque(maxlen=5))

        ref_px = None
        window_sec = self.INTRADAY_MOMENTUM_WINDOW_MIN * 60 + 5
        for ts, px in ring:
            if (now - ts).total_seconds() <= window_sec:
                ref_px = px
                break
        ring.append((now, curr))

        if not ref_px or ref_px == curr:
            return signals

        change_pct = (curr - ref_px) / ref_px * 100
        if abs(change_pct) < self.INTRADAY_MOMENTUM_PCT:
            return signals

        direction = 'up' if change_pct > 0 else 'down'
        cooldown_key = f'momentum:{code}:{direction}'
        last = self._momentum_cooldown.get(cooldown_key)
        cooldown_min = int(os.environ.get('WATCH_ALERT_COOLDOWN_MINUTES', '5'))
        if last and now - last < timedelta(minutes=cooldown_min):
            return signals

        label = '急拉' if direction == 'up' else '急跌'
        signals.append(self._make_signal(name, code,
            f'{label} {change_pct:+.1f}% | 当前 {curr:.2f}',
            '',
            {'alert_type': 'intraday_momentum', 'direction': direction, 'change_pct': change_pct}))
        self._momentum_cooldown[cooldown_key] = now
        return signals
```

5) 接入 `check_alerts` 循环（`self._check_intraday_extreme(...)` 之后一行）：
```python
            signals.extend(self._check_intraday_momentum(code, name, data))
```

- [ ] **Step 4: 运行确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_alert_service.py -v`
Expected: PASS（4 passed）

- [ ] **Step 5: Commit**

```bash
cat > .git/MSG.txt <<'EOF'
feat(watch): 新增分时异动检测器（急拉急跌 1min 级速度）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
rtk git add app/services/watch_alert_service.py tests/test_watch_alert_service.py && rtk git commit -F .git/MSG.txt && rm -f .git/MSG.txt
```

---

### Task 5: `watch_alert.scan` 编排 — 检测→管线→直推→返回 `[]`

**Files:**
- Modify: `app/strategies/watch_alert/__init__.py`（scan 尾部）
- Modify: `.claude/rules/watch.md`（管线接入说明）

**Interfaces:**
- Consumes: `WatchAlertService.check_alerts`（Task 4 已含 momentum）、`WatchSignalPipeline.process`（Task 1/2）、`NotificationService.push_watch_alerts`（Task 3）。
- Produces: `scan()` 返回 `[]`（不再向 event_bus 抛信号）。

- [ ] **Step 1: 改实现**

将 `app/strategies/watch_alert/__init__.py` `scan` 末尾：
```python
        service = WatchAlertService()
        signals = service.check_alerts(
            watch_prices, name_map,
            alert_params_map=alert_params_map,
            td_results=td_results,
            trading_minutes=trading_minutes,
        )

        if signals:
            logger.info(f'[盯盘告警] 产出 {len(signals)} 个信号')
        return signals
```
替换为：
```python
        service = WatchAlertService()
        signals = service.check_alerts(
            watch_prices, name_map,
            alert_params_map=alert_params_map,
            td_results=td_results,
            trading_minutes=trading_minutes,
        )
        if not signals:
            return []

        from app.services.watch_signal_pipeline import WatchSignalPipeline
        from app.services.notification import NotificationService
        alerts = WatchSignalPipeline.process(
            signals, watch_prices, alert_params_map, name_map, trading_minutes)
        pushable = [a for a in alerts if a.priority != 'LOW']
        if pushable:
            NotificationService.push_watch_alerts(alerts)
            logger.info(f'[盯盘告警] 合并推送 {len(pushable)} 股（原始 {len(signals)} 信号）')
        return []
```

- [ ] **Step 2: 冒烟验证（策略可加载、scan 返回 list）**

Run:
```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -c "from app.strategies.watch_alert import WatchAlertStrategy; s=WatchAlertStrategy(); print('OK', type(s.scan).__name__)"
```
Expected: 打印 `OK function`（无 import 错误）。

- [ ] **Step 3: 更新 watch.md**

在 `.claude/rules/watch.md` 「AI分析调度」节后新增一段：
```markdown
## 盯盘告警信号管线（合并/分级/上下文）

`watch_alert.scan` 不再逐条 `event_bus.publish`，而是 `check_alerts` 产原始信号 → `WatchSignalPipeline.process`（`app/services/watch_signal_pipeline.py`，纯函数）按股合并、加权共振分级（HIGH/MID/LOW）、上下文增强（涨幅/量比/区间位置）→ `NotificationService.push_watch_alerts` 一股一条直推、`scan` 返回 `[]`（复用 watch_realtime 直推先例）。跨 tick 去重仍归 `WatchAlertService._fired`；管线只做同 tick 合并。新增第 8 检测器 `_check_intraday_momentum`（≤3min ±1.5% 急拉急跌，`_price_ring` 环形缓冲，内存态盘中重启会重置——已知限制）。
```

- [ ] **Step 4: Commit**

```bash
cat > .git/MSG.txt <<'EOF'
feat(watch): watch_alert 接入信号管线合并直推 + 文档同步

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
rtk git add app/strategies/watch_alert/__init__.py .claude/rules/watch.md && rtk git commit -F .git/MSG.txt && rm -f .git/MSG.txt
```

---

### Task 6: `watch_preload` 差异化提频

**Files:**
- Modify: `app/strategies/watch_preload/__init__.py`
- Test: `tests/test_watch_preload_cadence.py`

**Interfaces:**
- Produces: `WatchPreloadStrategy._should_refresh_market(market:str, tick:int, non_a_every:int=3) -> bool`（纯函数：A 股每 tick，非 A 每 `non_a_every` tick）。
- 副作用变更：`schedule` 改 `interval_minutes:1`；A 股价格/分时每 tick，美股/港股每 3 tick；趋势 A 股每 15 tick、非 A 每 45 tick。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_watch_preload_cadence.py
from app.strategies.watch_preload import WatchPreloadStrategy


def test_a_share_refreshes_every_tick():
    assert all(WatchPreloadStrategy._should_refresh_market('A', t) for t in range(6))


def test_non_a_refreshes_every_third_tick():
    assert WatchPreloadStrategy._should_refresh_market('US', 0) is True
    assert WatchPreloadStrategy._should_refresh_market('US', 1) is False
    assert WatchPreloadStrategy._should_refresh_market('US', 2) is False
    assert WatchPreloadStrategy._should_refresh_market('HK', 3) is True


def test_schedule_is_one_minute():
    assert WatchPreloadStrategy.schedule == 'interval_minutes:1'
```

- [ ] **Step 2: 运行确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_preload_cadence.py -v`
Expected: FAIL（`_should_refresh_market` 不存在 / schedule 仍为 `:3`）

- [ ] **Step 3: 改实现**

`app/strategies/watch_preload/__init__.py`：

1) 常量与 schedule：
```python
BACKOFF_CAP = 8
NON_A_REFRESH_EVERY = 3   # 美股/港股每 3 tick(≈3min)刷新
```
```python
    schedule = "interval_minutes:1"
```

2) 新增纯函数：
```python
    @staticmethod
    def _should_refresh_market(market: str, tick: int, non_a_every: int = NON_A_REFRESH_EVERY) -> bool:
        if market == 'A':
            return True
        return tick % non_a_every == 0
```

3) 价格预取循环加入 cadence gating（`for market, m_codes in market_codes.items():` 内，`_should_skip` 之前）：
```python
        for market, m_codes in market_codes.items():
            if not self._should_refresh_market(market, self._tick_count):
                continue
            if self._should_skip(market):
                continue
            ...（原取价逻辑不变）
```

4) 趋势预取按市场分档（替换原 `trend_interval` 块）：
```python
        trend_interval = self._config.get('trend_interval', 15)
        a_codes_trend = market_codes.get('A', [])
        non_a_trend = [c for m, l in market_codes.items() if m != 'A' for c in l]
        if a_codes_trend and self._tick_count % trend_interval == 0:
            try:
                unified_stock_data_service.get_trend_data(a_codes_trend, days=7)
                unified_stock_data_service.get_trend_data(a_codes_trend, days=30)
                logger.info(f'[盯盘预取] A股走势预取完成: {len(a_codes_trend)}只 (tick={self._tick_count})')
            except Exception as e:
                logger.error(f'[盯盘预取] A股走势预取失败: {e}')
        if non_a_trend and self._tick_count % (trend_interval * 3) == 0:
            try:
                unified_stock_data_service.get_trend_data(non_a_trend, days=7)
                unified_stock_data_service.get_trend_data(non_a_trend, days=30)
                logger.info(f'[盯盘预取] 非A走势预取完成: {len(non_a_trend)}只 (tick={self._tick_count})')
            except Exception as e:
                logger.error(f'[盯盘预取] 非A走势预取失败: {e}')
```

> 注：A 股分时预取块（`a_codes = market_codes.get('A', [])` 那段）保持每 tick 不变。

- [ ] **Step 4: 运行确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_preload_cadence.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: 更新 watch.md 环境变量表**

在 `.claude/rules/watch.md` 「盯盘助手配置」的数据流一行改为反映差异化提频：
```markdown
- 数据流：init→缓存恢复→API刷新→定时轮询（价格60s/分析15min/市场状态5min）；后端 A股每分钟 force_refresh，美股/港股每3分钟（差异化提频，见 watch_preload）
```

- [ ] **Step 6: Commit**

```bash
cat > .git/MSG.txt <<'EOF'
feat(watch): watch_preload 差异化提频（A股1min/美港股3min）

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
rtk git add app/strategies/watch_preload/__init__.py tests/test_watch_preload_cadence.py .claude/rules/watch.md && rtk git commit -F .git/MSG.txt && rm -f .git/MSG.txt
```

---

### Task 7: `/watch/prices` 补 `age_seconds`

**Files:**
- Modify: `app/routes/watch.py`（`prices()` 每条 price 补 `age_seconds`）
- Test: `tests/test_watch_prices_age.py`

**Interfaces:**
- Produces: `/watch/prices` 返回的每条 `price_list` 项新增 `age_seconds:int|None`（从 `data['last_fetch_time']` ISO 时间戳算，解析失败为 None）。
- Consumes: 缓存 price dict 的 `last_fetch_time`（`datetime.now().isoformat()` 格式）。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_watch_prices_age.py
from datetime import datetime, timedelta
from app.routes.watch import _price_age_seconds


def test_age_from_isoformat():
    ts = (datetime.now() - timedelta(seconds=90)).isoformat()
    age = _price_age_seconds({'last_fetch_time': ts})
    assert 85 <= age <= 95


def test_age_none_on_missing():
    assert _price_age_seconds({}) is None


def test_age_none_on_garbage():
    assert _price_age_seconds({'last_fetch_time': 'not-a-date'}) is None
```

- [ ] **Step 2: 运行确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_prices_age.py -v`
Expected: FAIL（`ImportError: _price_age_seconds`）

- [ ] **Step 3: 改实现**

`app/routes/watch.py`：模块级新增 helper（`index()` 之前）：
```python
from datetime import datetime


def _price_age_seconds(data: dict):
    ts = data.get('last_fetch_time')
    if not ts:
        return None
    try:
        return int((datetime.now() - datetime.fromisoformat(ts)).total_seconds())
    except (ValueError, TypeError):
        return None
```
在 `prices()` 组装 `price_list.append({...})` 的字典里新增一行：
```python
                'age_seconds': _price_age_seconds(data),
```

- [ ] **Step 4: 运行确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_prices_age.py -v`
Expected: PASS（3 passed）

- [ ] **Step 5: Commit**

```bash
cat > .git/MSG.txt <<'EOF'
feat(watch): /prices 每条补 age_seconds 供前端按市场显示真实新鲜度

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
rtk git add app/routes/watch.py tests/test_watch_prices_age.py && rtk git commit -F .git/MSG.txt && rm -f .git/MSG.txt
```

---

### Task 8: `watch.js` 前端按市场渲染真实新鲜度

**Files:**
- Modify: `app/static/js/watch.js`（price 行渲染读取 `age_seconds`）

**Interfaces:**
- Consumes: `/watch/prices` 返回的 `age_seconds`（Task 7）。
- Produces: price 行/表格显示新鲜度标记（如 `>2min` 时灰字 "Nmin前"），无新增网络请求。

> 前端无单测框架，本任务用手工冒烟验证。改动须**最小侵入**：只在已有 price 渲染函数里，用 `age_seconds` 决定是否附加新鲜度小标签，不动轮询周期（保持 60s）。

- [ ] **Step 1: 定位渲染点**

Run: `PYTHONIOENCODING=utf-8 rtk python -c "import re; s=open('app/static/js/watch.js',encoding='utf-8').read(); [print(i+1, l) for i,l in enumerate(s.splitlines()) if 'change_pct' in l or 'renderPrice' in l or 'stale' in l]"`
Expected: 打印含 price 渲染/`stale` 的行号，据此定位 price 行 DOM 组装处。

- [ ] **Step 2: 加新鲜度渲染**

在 price 行渲染处（读取 `p.change_pct`/`p.stale` 的同一函数），追加：
```javascript
// 新鲜度：age_seconds 超过 120s 时显示"Nmin前"灰字（美股/港股 3min 刷新会命中）
function freshnessTag(p) {
    if (p.age_seconds == null) return '';
    if (p.age_seconds <= 120) return '';
    const mins = Math.round(p.age_seconds / 60);
    return `<span class="price-age" title="缓存新鲜度">${mins}min前</span>`;
}
```
并在该股 price 单元格 HTML 末尾插入 `${freshnessTag(p)}`（`p` 为当前 price 项）。

- [ ] **Step 3: 加最小样式**

在 watch.html 的 `<style>` 或对应 css 追加：
```css
.price-age { margin-left: 4px; font-size: 11px; color: #999; }
```

- [ ] **Step 4: 手工冒烟**

Run: `python run.py`（另开终端），浏览器访问 http://127.0.0.1:5000/watch/ ，确认：A 股行无 "min前" 标记（1min 内新鲜），美股/港股行在盘中显示 "3min前" 类标记，页面无 JS 报错（F12 Console）。停掉 run.py。
Expected: 渲染正常、无 Console 报错。

- [ ] **Step 5: Commit**

```bash
cat > .git/MSG.txt <<'EOF'
feat(watch): 前端 price 行按市场显示真实缓存新鲜度

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
rtk git add app/static/js/watch.js app/templates/watch.html && rtk git commit -F .git/MSG.txt && rm -f .git/MSG.txt
```

---

### Task 9: 全量回归 + 已知限制文档收尾

**Files:**
- Modify: `.claude/rules/watch.md`（已知限制：内存态盘中重启重置）

- [ ] **Step 1: 全量 pytest**

Run:
```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ -v > .omc/artifacts/watch_pipeline_regress.txt 2>&1; grep -E "passed|failed|error" .omc/artifacts/watch_pipeline_regress.txt | tail -5
```
Expected: 全绿，无新增 `ModuleNotFoundError` / `failed` / `error`。若 `.omc/artifacts/` 不存在改写到 scratchpad 目录。

- [ ] **Step 2: 补已知限制说明**

确认 `.claude/rules/watch.md` 已含（Task 5 已加，若无则补）：内存态（`_fired`/`_price_ring`/极值/`_momentum_cooldown`）盘中重启会重置，可能导致极值重报/漏报，为已知限制（健壮性/持久化留后续 spec）。

- [ ] **Step 3: 确认无脱链 + 内容核对**

Run: `rtk git log --oneline -9`
Expected: 见到 Task 1–8 共 8 个 feat commit + 本任务收尾。逐一 `rtk git show --stat <sha>` 抽查只含本任务文件。

- [ ] **Step 4: Commit（如 Step 2 有改动）**

```bash
cat > .git/MSG.txt <<'EOF'
docs(watch): 标注盯盘内存态盘中重启重置为已知限制

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
rtk git add .claude/rules/watch.md && rtk git commit -F .git/MSG.txt && rm -f .git/MSG.txt
```

---

## Self-Review 记录

- **Spec 覆盖**：管线合并（T1）/分级共振（T1）/上下文增强（T2）/LOW 静默（T3）/直推（T3、T5）/分时异动检测器（T4）/差异化提频（T6）/前后端新鲜度对齐（T7、T8）/文档（T3、T5、T6、T9）/非目标接缝 `fired_signals`（T1）——全部有对应任务。
- **类型一致**：`ConsolidatedAlert` 字段（T1 定义）在 T3 push、T5 编排中一致引用；`process()` 签名 T1/T2/T5 一致；`_should_refresh_market` T6 定义即测试。
- **无占位符**：各代码步均含完整可运行代码与预期输出。
