# news_watch 告警按当日涨跌上色 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 `news_watch` 频道的盯盘合并告警 emoji 只按当日涨跌幅（`change_percent` 符号）上色，不再按信号方向。

**Architecture:** 在 `ConsolidatedAlert` 上新增 `change_percent` 字段并在 `WatchSignalPipeline.process()` 从 `prices` 灌入；`NotificationService.push_watch_alerts` 改读该字段决定 emoji（涨🔴/跌🟢/平盘⚪/缺失⚠️）。`direction` 字段保留但不再用于上色。

**Tech Stack:** Python / Flask / pytest。测试 runner：`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest`。

## Global Constraints

- 所有 git / pytest 命令前加 `rtk`；env 赋值（`PYTHONIOENCODING=utf-8` / `SCHEDULER_ENABLED=0`）必须在 `rtk` 之前。
- 不写多余注释、不留 backup 文件。
- 颜色规则四态（唯一权威）：`change_percent > 0`→🔴；`< 0`→🟢；`== 0`→⚪；`is None`→⚠️。
- 不改动 `push_realtime_analysis`（AI 买卖建议 emoji）与 `dispatch_signal`（对 news_watch 已是死代码）。
- `direction` 字段保留，仅停止用于上色。
- 推送格式（标题行 `emoji *名称(代码)*  [优先级]` + 主信号行 + `  · ` 次信号 + 上下文行）与 LOW 静默行为不变。

---

### Task 1: `ConsolidatedAlert` 携带 change_percent

**Files:**
- Modify: `app/services/watch_signal_pipeline.py`（`ConsolidatedAlert` dataclass + `process()` 构造处 line ~103-108）
- Test: `tests/test_watch_signal_pipeline.py`

**Interfaces:**
- Produces: `ConsolidatedAlert.change_percent: float | None`（默认 `None`）；`WatchSignalPipeline.process(raw_signals, prices, params_map, name_map, trading_minutes=None)` 返回的每条 alert 的 `change_percent` == `prices.get(code, {}).get('change_percent')`。

- [ ] **Step 1: 写失败测试**

在 `tests/test_watch_signal_pipeline.py` 末尾追加：

```python
def test_process_populates_change_percent():
    raw = [_sig('603626', 'resistance_break', 'resistance_break', '突破阻力 30.0 | 当前 30.05')]
    prices = {'603626': {'current_price': 30.05, 'change_percent': 2.35, 'volume': 1200}}
    alerts = WatchSignalPipeline.process(raw, prices, {}, {'603626': '科森科技'})
    assert len(alerts) == 1
    assert alerts[0].change_percent == 2.35


def test_process_change_percent_defaults_none_when_missing():
    raw = [_sig('600519', 'td_sequential', 'buy', 'TD九转买入')]
    alerts = WatchSignalPipeline.process(raw, {}, {}, {'600519': '茅台'})
    assert alerts[0].change_percent is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_signal_pipeline.py::test_process_populates_change_percent -v`
Expected: FAIL —— `TypeError: __init__() got an unexpected keyword argument 'change_percent'` 或 `AttributeError: 'ConsolidatedAlert' object has no attribute 'change_percent'`。

- [ ] **Step 3: 加字段 + 灌值**

在 `app/services/watch_signal_pipeline.py` 的 `ConsolidatedAlert` dataclass 中，`context_line: str = ''` 之后、`fired_signals` 之前（或任意字段位置，保持有默认值）加：

```python
    change_percent: float = None
```

在 `process()` 里构造 `ConsolidatedAlert(...)` 处（当前 line ~103-108），把 `change_percent` 传入。改成：

```python
            alerts.append(ConsolidatedAlert(
                code=code, name=name, priority=priority, direction=primary_dir,
                primary_line=primary_line, secondary_lines=secondary_lines,
                context_line=context_line,
                change_percent=prices.get(code, {}).get('change_percent'),
                fired_signals=[s.data for s in sigs],
            ))
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_signal_pipeline.py -v`
Expected: PASS（含两条新测试 + 原有全部）。

- [ ] **Step 5: 提交**

```bash
rtk git add app/services/watch_signal_pipeline.py tests/test_watch_signal_pipeline.py && rtk git commit -m "feat(watch): ConsolidatedAlert 携带 change_percent"
```

---

### Task 2: push_watch_alerts 按 change_percent 上色

**Files:**
- Modify: `app/services/notification.py`（`push_watch_alerts`，line ~96-116；替换 line ~103-108 的 emoji 块）
- Test: `tests/test_watch_signal_pipeline.py`

**Interfaces:**
- Consumes: `ConsolidatedAlert.change_percent`（Task 1 产出）。

- [ ] **Step 1: 写失败测试**

先更新现有 `test_push_skips_low_and_formats_high`：给 `high` 的构造补 `change_percent=2.30`（保持断言 🔴）。定位这段并改：

```python
    high = ConsolidatedAlert(
        code='603626', name='科森科技', priority='HIGH', direction='resistance_break',
        primary_line='突破阻力 30.00 | 当前 30.05',
        secondary_lines=['下穿 MA5 20.50', '放量 1.8x'],
        context_line='涨幅 +2.30% | 量比 1.8x | 距上方阻力 32.00(+6.5%)',
        change_percent=2.30,
    )
```

在 `tests/test_watch_signal_pipeline.py` 末尾追加四态 + bug 回归测试：

```python
def _push_one(alert):
    from unittest.mock import patch
    from app.services.notification import NotificationService
    sent = []
    with patch.object(NotificationService, 'send_slack',
                      side_effect=lambda t, c: sent.append((t, c)) or True):
        NotificationService.push_watch_alerts([alert])
    return sent[0][0] if sent else ''


def test_color_up_is_red():
    a = ConsolidatedAlert(code='603626', name='科森科技', priority='HIGH',
                          direction='resistance_break', primary_line='突破阻力 30.00 | 当前 30.05',
                          change_percent=2.35)
    assert '🔴 *科森科技(603626)*' in _push_one(a)


def test_color_down_is_green():
    a = ConsolidatedAlert(code='600519', name='茅台', priority='HIGH',
                          direction='resistance_break', primary_line='突破阻力 100 | 当前 100.5',
                          change_percent=-1.20)
    assert '🟢 *茅台(600519)*' in _push_one(a)


def test_color_flat_is_white():
    a = ConsolidatedAlert(code='600519', name='茅台', priority='HIGH',
                          direction='up', primary_line='测试',
                          change_percent=0)
    assert '⚪ *茅台(600519)*' in _push_one(a)


def test_color_missing_is_warning():
    a = ConsolidatedAlert(code='600519', name='茅台', priority='HIGH',
                          direction='up', primary_line='测试',
                          change_percent=None)
    assert '⚠️ *茅台(600519)*' in _push_one(a)


def test_color_bug_regression_up_but_below_target_is_red():
    # 核心 bug：信号方向落在 below/support_break 一侧，但当日在涨 → 必须 🔴
    a = ConsolidatedAlert(code='000660.KS', name='SK海力士', priority='HIGH',
                          direction='below', primary_line='当前 1805500.00 < 目标 1892000.0',
                          change_percent=2.35)
    assert '🔴 *SK海力士(000660.KS)*' in _push_one(a)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_signal_pipeline.py::test_color_bug_regression_up_but_below_target_is_red -v`
Expected: FAIL —— 当前 `push_watch_alerts` 按 `direction='below'` 判成 🟢，断言 🔴 失败。

- [ ] **Step 3: 改 emoji 逻辑**

在 `app/services/notification.py:push_watch_alerts` 中，把现有的 direction 判断块（当前 line ~103-108）：

```python
            if a.direction in ('high', 'above', 'up', 'buy', 'resistance_break'):
                emoji = '🔴'
            elif a.direction in ('low', 'below', 'down', 'sell', 'support_break'):
                emoji = '🟢'
            else:
                emoji = '⚠️'
```

替换为：

```python
            chg = a.change_percent
            if chg is None:
                emoji = '⚠️'
            elif chg > 0:
                emoji = '🔴'
            elif chg < 0:
                emoji = '🟢'
            else:
                emoji = '⚪'
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_signal_pipeline.py -v`
Expected: PASS（全部，含四态 + bug 回归 + 更新后的 `test_push_skips_low_and_formats_high`）。

- [ ] **Step 5: 提交**

```bash
rtk git add app/services/notification.py tests/test_watch_signal_pipeline.py && rtk git commit -m "fix(watch): news_watch 告警按当日涨跌上色，不再按信号方向"
```

---

## 收尾

- [ ] 跑一次盯盘管线相关全量测试确认无回归：

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_signal_pipeline.py -v`
Expected: 全绿。
