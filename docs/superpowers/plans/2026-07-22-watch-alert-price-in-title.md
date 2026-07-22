# watch_alert 标题行前置股价 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** watch_alert 合并告警标题行改为 `emoji *名(代码)* 股价 涨幅 [优先级]`，股价从第二行提到标题并按类型去重。

**Architecture:** 两处改动 + 文档。`WatchSignalPipeline.process()` 给 `ConsolidatedAlert` 补 `current_price` 字段（与 `change_percent` 同源同对称），并新增 `_strip_current` helper 剥离 A 类告警尾部 ` | 当前 X`（B 类比较主语保留）。`NotificationService.push_watch_alerts` 重排标题行，价格千分位去尾零，价格/涨幅各自独立可选。

**Tech Stack:** Python 3, dataclass, `re`, pytest, unittest.mock。纯函数 + Slack mrkdwn 文本拼装，无新依赖。

## Global Constraints

- 响应/文档中文；不写多余注释；不写 backup 文件。
- 所有 git/pytest 命令加 `rtk` 前缀；env 赋值在 `rtk` 之前。
- 测试命令：`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_signal_pipeline.py -v`（该测试文件函数级 import NotificationService + patch send_slack，无需 create_app）。
- emoji 四态判定不变：`chg is None→⚠️` / `>0→🔴` / `<0→🟢` / `==0→⚪`。
- 价格格式铁律：`f'{p:,.2f}'.rstrip('0').rstrip('.')` —— 千分位 + 去无意义尾零，不丢有效精度。
- 标题优先级前保留两空格 `  [优先级]`（沿用现有视觉风格）。
- 去重正则铁律：`re.sub(r' \| 当前 [\d.]+$', '', line)` —— 仅删尾部 ` | 当前 X` 段，B 类（`当前` 在句首或句中作比较主语）不匹配、天然保留。
- 投研写档不涉及；本改动在 main 分支（app/ 代码但小改，无需 worktree —— 若并行 session 活跃再评估）。

---

### Task 1: Pipeline — current_price 字段 + A 类去重

**Files:**
- Modify: `app/services/watch_signal_pipeline.py`（`ConsolidatedAlert` dataclass L26-36；`process()` L98-111；`_strip_prefix` 之后 L61 新增 helper）
- Test: `tests/test_watch_signal_pipeline.py`

**Interfaces:**
- Consumes: `prices.get(code, {}).get('current_price')`（unified 实时价 dict 字段，见 stock-data-cache.md：键名是 `current_price` 不是 `price`）。
- Produces:
  - `ConsolidatedAlert.current_price: Optional[float] = None` —— Task 2 标题拼装消费。
  - `WatchSignalPipeline._strip_current(line: str) -> str` —— 内部 helper。
  - `process()` 产出的 `primary_line` / `secondary_lines` 中 A 类尾部 ` | 当前 X` 已剥离；B 类保留。

- [ ] **Step 1: 更新会被去重打断的现有断言 + 写新失败测试**

编辑 `tests/test_watch_signal_pipeline.py`：

把现有 `test_group_one_alert_per_stock`（L22）的断言从：
```python
    assert by_code['603626'].primary_line == '突破阻力 30.0 | 当前 30.05'
```
改为（去重后尾部 ` | 当前 30.05` 被剥离）：
```python
    assert by_code['603626'].primary_line == '突破阻力 30.0'
```

在文件末尾追加：
```python
def test_process_populates_current_price():
    raw = [_sig('603626', 'resistance_break', 'resistance_break', '突破阻力 30.0 | 当前 30.05')]
    prices = {'603626': {'current_price': 30.05, 'change_percent': 2.35, 'volume': 1200}}
    alerts = WatchSignalPipeline.process(raw, prices, {}, {'603626': '科森科技'})
    assert alerts[0].current_price == 30.05


def test_process_current_price_defaults_none_when_missing():
    raw = [_sig('600519', 'td_sequential', 'buy', 'TD九转买入 | 当前 100.00')]
    alerts = WatchSignalPipeline.process(raw, {}, {}, {'600519': '茅台'})
    assert alerts[0].current_price is None


def test_strips_trailing_current_from_primary_and_secondary():
    # A 类：支撑阻力 / TD九转 尾部 | 当前 X 被剥离
    raw = [
        _sig('603626', 'resistance_break', 'resistance_break', '突破阻力 30.0 | 当前 30.05'),
        _sig('603626', 'td_sequential', 'buy', 'TD九转买入信号 | 当前 30.05'),
    ]
    alerts = WatchSignalPipeline.process(raw, {}, {}, {'603626': '科森科技'})
    a = alerts[0]
    assert a.primary_line == '突破阻力 30.0'
    assert a.secondary_lines == ['TD九转买入信号']


def test_preserves_current_as_comparison_subject():
    # B 类：当前 X 是比较主语，保留（无尾部 | 当前 段）
    raw = [_sig('000660.KS', 'target_price', 'below', '当前 1805500.00 < 目标 1892000.0')]
    alerts = WatchSignalPipeline.process(raw, {}, {}, {'000660.KS': 'SK海力士'})
    assert alerts[0].primary_line == '当前 1805500.00 < 目标 1892000.0'
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_signal_pipeline.py -v`
Expected: `test_process_populates_current_price` FAIL（`AttributeError: ... has no attribute 'current_price'` 或 dataclass 无该字段）；`test_group_one_alert_per_stock` / `test_strips_trailing_current_from_primary_and_secondary` FAIL（primary_line 仍含 ` | 当前 X`）。

- [ ] **Step 3: 给 dataclass 加字段**

`app/services/watch_signal_pipeline.py` `ConsolidatedAlert`（L34-35 附近），在 `change_percent` 旁加：
```python
    change_percent: Optional[float] = None
    current_price: Optional[float] = None
```

- [ ] **Step 4: 新增 `_strip_current` helper**

在 `_strip_prefix`（L55-61）之后新增：
```python
    @staticmethod
    def _strip_current(line: str) -> str:
        return re.sub(r' \| 当前 [\d.]+$', '', line)
```

- [ ] **Step 5: process() 应用去重 + 填充 current_price**

把 `process()` 里 primary/secondary 构造（L98-102）改为：
```python
            primary_line = WatchSignalPipeline._strip_current(
                WatchSignalPipeline._strip_prefix(primary.title, name, code))
            secondary_lines = [
                WatchSignalPipeline._strip_current(
                    WatchSignalPipeline._strip_prefix(s.title, name, code))
                for s in sigs if s is not primary
            ]
```

在 `ConsolidatedAlert(...)` 构造（L105-111）里 `change_percent=...` 后加一行：
```python
                change_percent=prices.get(code, {}).get('change_percent'),
                current_price=prices.get(code, {}).get('current_price'),
```

- [ ] **Step 6: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_signal_pipeline.py -v`
Expected: 上述新增/修改的 4 个 pipeline 测试 PASS。（Task 2 前颜色/push 测试仍可能 FAIL —— 标题顺序未改，属预期，Task 2 修复。）

- [ ] **Step 7: Commit**

```bash
rtk git add app/services/watch_signal_pipeline.py tests/test_watch_signal_pipeline.py && rtk git commit -m "feat(watch): ConsolidatedAlert 补 current_price + A类去重 | 当前 X

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Notification — 标题行重排（名 价 涨幅）

**Files:**
- Modify: `app/services/notification.py:push_watch_alerts`（L103-113 标题拼装）
- Test: `tests/test_watch_signal_pipeline.py`

**Interfaces:**
- Consumes: `ConsolidatedAlert.current_price`（Task 1 产出）、`.change_percent`、`.name`、`.code`、`.priority`、`.primary_line`、`.secondary_lines`、`.context_line`。
- Produces: 标题行文本 `{emoji} *{name}({code})* [{price}] [{chg}]  [{priority}]` —— price 仅 `current_price is not None` 时拼、chg 仅 `change_percent is not None` 时拼。

- [ ] **Step 1: 更新会被标题重排打断的现有测试 + 写新失败测试**

编辑 `tests/test_watch_signal_pipeline.py`。

改 `test_push_skips_low_and_formats_high`：给 `high` fixture 加 `current_price=30.05`，并把标题断言从：
```python
    assert '🔴 +2.30% *科森科技(603626)*' in text
```
改为：
```python
    assert '🔴 *科森科技(603626)* 30.05 +2.30%' in text
```
（其余断言 `[HIGH]` / `突破阻力 30.00 | 当前 30.05`（此 fixture 直接构造、未过 process，不受去重影响）/ `  · 下穿 MA5 20.50` 保持不变。）

改 4 个颜色测试断言（现 L138/L145/L152/L167），新顺序为 emoji → 名(代码) → 涨幅（这些 fixture 无 current_price，故无价格段）：
```python
# test_color_up_is_red
    assert '🔴 *科森科技(603626)* +2.35%' in _push_one(a)
# test_color_down_is_green
    assert '🟢 *茅台(600519)* -1.20%' in _push_one(a)
# test_color_flat_is_white
    assert '⚪ *茅台(600519)* +0.00%' in _push_one(a)
# test_color_bug_regression_up_but_below_target_is_red
    assert '🔴 *SK海力士(000660.KS)* +2.35%' in _push_one(a)
```
（`test_color_missing_is_warning` 断言 `'⚠️ *茅台(600519)*'` 新旧格式一致，不改。）

文件末尾追加新测试：
```python
def test_title_order_name_price_change():
    a = ConsolidatedAlert(code='603626', name='科森科技', priority='HIGH',
                          direction='resistance_break', primary_line='突破阻力 30.0',
                          current_price=30.05, change_percent=2.30)
    text = _push_one(a)
    assert '🔴 *科森科技(603626)* 30.05 +2.30%  [HIGH]' in text


def test_title_price_thousands_and_trim_zeros():
    a = ConsolidatedAlert(code='000660.KS', name='SK海力士', priority='MID',
                          direction='resistance_break', primary_line='突破阻力 1936000.0',
                          current_price=1938000.00, change_percent=5.56)
    assert '*SK海力士(000660.KS)* 1,938,000 +5.56%' in _push_one(a)


def test_title_price_trims_to_integer_when_whole():
    a = ConsolidatedAlert(code='600519', name='茅台', priority='MID',
                          direction='up', primary_line='测试',
                          current_price=26.00, change_percent=1.0)
    assert '*茅台(600519)* 26 +1.00%' in _push_one(a)


def test_title_price_keeps_cents():
    a = ConsolidatedAlert(code='600519', name='茅台', priority='MID',
                          direction='up', primary_line='测试',
                          current_price=150.25, change_percent=1.0)
    assert '*茅台(600519)* 150.25 +1.00%' in _push_one(a)


def test_title_no_price_when_current_price_none():
    a = ConsolidatedAlert(code='603626', name='科森科技', priority='HIGH',
                          direction='resistance_break', primary_line='突破阻力 30.0',
                          current_price=None, change_percent=2.30)
    text = _push_one(a)
    assert '🔴 *科森科技(603626)* +2.30%' in text
    assert 'None' not in text
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_signal_pipeline.py -v`
Expected: 新增 5 个 title 测试与改过断言的颜色/push 测试 FAIL（当前标题仍为旧顺序 `emoji 涨幅 名`）。

- [ ] **Step 3: 重写 push_watch_alerts 标题拼装**

`app/services/notification.py`，把 emoji 判定后的 `head` / `lines`（现 L112-113）：
```python
            head = f'{emoji} {chg:+.2f}% ' if chg is not None else f'{emoji} '
            lines = [f'{head}*{a.name}({a.code})*  [{a.priority}]', a.primary_line]
```
替换为：
```python
            parts = [emoji, f'*{a.name}({a.code})*']
            if a.current_price is not None:
                parts.append(f'{a.current_price:,.2f}'.rstrip('0').rstrip('.'))
            if chg is not None:
                parts.append(f'{chg:+.2f}%')
            lines = [f"{' '.join(parts)}  [{a.priority}]", a.primary_line]
```
（emoji 四态判定 L103-111 不动；`for s in a.secondary_lines` / `context_line` 追加逻辑 L114-117 不动。）

- [ ] **Step 4: 运行测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_signal_pipeline.py -v`
Expected: 全部 PASS（含 Task 1 的 pipeline 测试 + 本任务 title/颜色/push 测试）。

- [ ] **Step 5: Commit**

```bash
rtk git add app/services/notification.py tests/test_watch_signal_pipeline.py && rtk git commit -m "feat(watch): 告警标题行重排为 名(代码) 股价 涨幅

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: 文档 — 更新 notifications.md 合并推送格式

**Files:**
- Modify: `.claude/rules/notifications.md`（「合并推送（信号管线）」段，现 L53）

**Interfaces:**
- Consumes: Task 1/2 落定的标题格式与去重规则。
- Produces: 无代码接口，纯文档。

- [ ] **Step 1: 更新格式描述**

把 `.claude/rules/notifications.md` L53「合并推送（信号管线）」段里描述标题格式的句子：
```
格式：`emoji *名称(代码)* [优先级]` 首行 + 主信号行 + 次信号 `  · ` bullet + 上下文行（涨幅/量比/区间位置）。
```
改为：
```
格式：`emoji *名称(代码)* 股价 涨幅 [优先级]` 首行（股价千分位去尾零、change_percent 非空才拼涨幅）+ 主信号行 + 次信号 `  · ` bullet + 上下文行（量比/区间位置）。股价提到标题后，A 类告警（支撑阻力/TD九转/动量）主/次信号行尾部 ` | 当前 X` 由 `_strip_current` 去重剥离；B 类（盘中极值/目标价/均线穿越）`当前 X` 作比较主语保留。
```

- [ ] **Step 2: 校验无破坏（文档改动，跑一遍全测试兜底）**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_signal_pipeline.py -v`
Expected: 全部 PASS（文档改动不影响测试，仅确认工作树干净）。

- [ ] **Step 3: Commit**

```bash
rtk git add .claude/rules/notifications.md && rtk git commit -m "docs(notifications): 同步 watch_alert 标题前置股价 + A类去重规则

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## 验收（全部完成后）

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_signal_pipeline.py -v`
Expected: 全绿。核对 spec 验收标准 1-5：标题 `emoji *名(代码)* 千分位价 ±X.XX%  [优先级]`；价格 `1938000.00→1,938,000`/`26.00→26`/`150.25→150.25`；A 类去 ` | 当前 X`、B 类保留；缺失兜底正确。
