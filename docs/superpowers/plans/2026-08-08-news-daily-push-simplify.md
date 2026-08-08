# news_daily 每日 8 点推送精简 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从每日 8 点 `news_daily` 推送中移除「⚡关键信号」与「📉高点回退提醒」两块重复内容，同时保住仍被其他策略依赖的 signal_cache 刷新和 `/value_dip` 页面。

**Architecture:** 纯删除型改动，无新增模块。三处代码点：`app/strategies/daily_briefing/__init__.py`（高点回退推送）、`app/services/notification.py`（关键信号生成 + Block Kit 分支 + 调用点）、`app/llm/prompts/daily_briefing.py`（GLM prompt 的 `alert_signals` 输入）。测试策略采用「移除守卫测试」（assert `not hasattr(...)`），与本仓既有的 `tests/test_alert_removed.py` 模式一致：先写守卫测试看它失败（属性还在），再删代码让它通过。

**Tech Stack:** Python 3 / Flask / pytest。测试命令固定为 `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest ...`。

## Global Constraints

- 所有 `git` / `pytest` 命令前加 `rtk`（本仓约定）。
- pytest 必须带 `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0` 前缀，且 **env 赋值写在 `rtk` 之前**。
- `git add` 与 `git commit` 必须写在**同一条 Bash 命令链**里（并行 session 会抢 git index）。中文多行 commit message 走 `.git/MSG.txt` 文件，不用 heredoc。
- 不写 backup 文件，不留被注释掉的死代码——删就删干净。
- 不新增多余注释。
- 本任务在 **main 分支**直接进行还是开 worktree：本改动动 `app/` 代码，按仓规应开独立 git worktree 隔离。若执行者已在 worktree 中，注意 worktree 里 `.git` 是文件，`git commit -F .git/MSG.txt` 会失败，改用 `-F ../MSG.txt` 之类仓外路径。
- 不得修改 `ValueDipService`、`/value_dip` 路由、`price_alert` 策略、`watch_alert` 的任何行为。

---

## File Structure

| 文件 | 动作 | 职责变化 |
|------|------|---------|
| `app/strategies/daily_briefing/__init__.py` | 修改 | 删除 `_push_pullback_alert` / `_format_pullback_message` 及调用；保留 `_refresh_signal_cache` |
| `tests/test_value_dip_briefing.py` | 修改 | 从「格式化行为测试」改为「移除守卫测试」 |
| `tests/test_pullback_support_resistance.py` | 修改 | 删除 3 个 formatter 测试，保留 2 个 `ValueDipService` 测试 |
| `app/services/notification.py` | 修改 | 删除 `format_alert_signals`；`build_briefing_blocks` 去掉 `alerts_text` 形参与分支；`push_daily_report` 去掉相关调用 |
| `app/llm/prompts/daily_briefing.py` | 修改 | `label_map` 与 docstring 去掉 `alert_signals` |
| `tests/test_daily_briefing_alert_signals_removed.py` | 新建 | 关键信号移除守卫 + `build_briefing_blocks` 新签名回归 |
| `.claude/rules/notifications.md` | 修改 | 排版规范示例不再引用已删除的推送标题 |

---

## Task 1: 移除「📉高点回退提醒」推送

**Files:**
- Modify: `app/strategies/daily_briefing/__init__.py:42`（`_scan_weekday` 里的调用）、`:89-127`（两个方法）
- Test: `tests/test_value_dip_briefing.py`（改写）、`tests/test_pullback_support_resistance.py`（删 3 个测试）

**Interfaces:**
- Consumes: 无（本任务是链路终点的删除）
- Produces: `DailyBriefingStrategy` 上不再存在 `_push_pullback_alert` / `_format_pullback_message` 两个属性。后续任务不依赖本任务产物。

- [ ] **Step 1: 改写 `tests/test_value_dip_briefing.py` 为移除守卫测试**

把整个文件替换为：

```python
from app.strategies.daily_briefing import DailyBriefingStrategy


def test_value_dip_push_removed():
    assert not hasattr(DailyBriefingStrategy, '_push_value_dip_alert')
    assert not hasattr(DailyBriefingStrategy, '_format_value_dip_message')


def test_pullback_push_removed():
    """高点回退提醒已下线（信息与盯盘告警重复），value_dip 页面仍保留。"""
    assert not hasattr(DailyBriefingStrategy, '_push_pullback_alert')
    assert not hasattr(DailyBriefingStrategy, '_format_pullback_message')


def test_value_dip_service_kept():
    """ValueDipService 仍服务 /value_dip 页面，不随推送一起下线。"""
    from app.services.value_dip import ValueDipService
    assert hasattr(ValueDipService, 'get_pullback_ranking')
```

- [ ] **Step 2: 运行测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_value_dip_briefing.py -v`

Expected: `test_pullback_push_removed` FAIL（`assert not True`，因为方法还在）；另两个 PASS。

- [ ] **Step 3: 删除 `_scan_weekday` 中的调用**

在 `app/strategies/daily_briefing/__init__.py` 的 `_scan_weekday` 里，删除末尾这两行（连同其上方的空行）：

```python
        self._push_pullback_alert()
```

删除后 `_scan_weekday` 应以 `except Exception as e: logger.error(f'[每日简报] 推送失败: {e}')` 结尾。

- [ ] **Step 4: 删除两个静态方法**

删除 `_push_pullback_alert` 与 `_format_pullback_message` 的完整定义（原 L89–127，从 `@staticmethod` 装饰器到 `return '\n'.join(lines)` 为止，含两者之间的空行）。删除后文件最后一个方法是 `_refresh_signal_cache`。

**注意：不要删 `_refresh_signal_cache`** —— `price_alert` 策略（盘中每 5 分钟）读同一份 signal_cache，且它覆盖持仓+关注全集，比 `watch_realtime._refresh_watch_signals`（仅 `WATCH_CODES`）宽。

- [ ] **Step 5: 删除 `tests/test_pullback_support_resistance.py` 中依赖 formatter 的 3 个测试**

删除 `test_format_renders_support_and_resistance`、`test_format_omits_missing_sr`、`test_format_renders_single_side` 三个函数，并删除文件顶部已无用的 import 行 `from app.strategies.daily_briefing import DailyBriefingStrategy`。

**保留** `_mk_ohlc`、`_CLOSES_25`、`test_calc_changes_attaches_support_resistance`、`test_calc_changes_sr_none_when_insufficient_data` —— 它们测的是 `ValueDipService`，属保留组件。

删除后文件应为：

```python
from app.services.value_dip import ValueDipService


def _mk_ohlc(closes):
    """把收盘价序列造成 OHLC dict 列表（high=close+2, low=close-2）"""
    return [
        {'date': f'2026-06-{i + 1:02d}', 'open': c,
         'high': c + 2, 'low': c - 2, 'close': c, 'volume': 1000}
        for i, c in enumerate(closes)
    ]


# 25 日：先涨到 120 再回落到 100，制造下方支撑与上方压力
_CLOSES_25 = [95, 96, 98, 100, 103, 106, 110, 113, 116, 118, 120, 119, 117,
              115, 113, 111, 109, 107, 105, 103, 102, 101, 100, 100, 100]


def test_calc_changes_attaches_support_resistance():
    info = ValueDipService._calc_stock_changes('300223', '北京君正', _mk_ohlc(_CLOSES_25))
    assert info['support'] is not None
    assert info['resistance'] is not None
    assert info['support'] < info['price'] < info['resistance']


def test_calc_changes_sr_none_when_insufficient_data():
    info = ValueDipService._calc_stock_changes('300223', '北京君正', _mk_ohlc(_CLOSES_25[:10]))
    assert info['support'] is None
    assert info['resistance'] is None
```

- [ ] **Step 6: 运行两个测试文件确认全绿**

Run:
```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_value_dip_briefing.py tests/test_pullback_support_resistance.py -v > .pytest_out.txt 2>&1; grep -E "passed|failed" .pytest_out.txt; rm .pytest_out.txt
```

（走文件再 grep：本仓 `create_app` 触发的 crawl4ai 进度条打到 stdout，会把 pytest 摘要顶出可见区。）

Expected: `5 passed`。

- [ ] **Step 7: 确认无残留引用**

Run: `rtk grep -rn "_push_pullback_alert\|_format_pullback_message" app/ tests/`

Expected: 只有 `tests/test_value_dip_briefing.py` 里那两行 `assert not hasattr(...)`，`app/` 下零命中。

- [ ] **Step 8: 提交**

```bash
printf 'refactor(briefing): 移除每日8点高点回退提醒推送\n\n信息与盯盘告警（支撑跌破/盘中急跌/TD九转）重复。\nValueDipService 与 /value_dip 页面保留。\n' > .git/MSG.txt && rtk git add app/strategies/daily_briefing/__init__.py tests/test_value_dip_briefing.py tests/test_pullback_support_resistance.py && rtk git commit -F .git/MSG.txt
```

---

## Task 2: 移除「⚡关键信号」全链路

**Files:**
- Modify: `app/services/notification.py:236-360`（删 `format_alert_signals`）、`:1014-1066`（`build_briefing_blocks`）、`:1265`/`:1329`/`:1363-1367`（`push_daily_report`）
- Modify: `app/llm/prompts/daily_briefing.py:15`、`:36`
- Test: `tests/test_daily_briefing_alert_signals_removed.py`（新建）

**Interfaces:**
- Consumes: 无（与 Task 1 无依赖，可独立执行）
- Produces:
  - `NotificationService.format_alert_signals` 不再存在；
  - `NotificationService.build_briefing_blocks(briefing_text: str, core_insights: str = '', action_suggestions: str = '') -> list`（三参数，`alerts_text` 已移除）；
  - `build_daily_briefing_prompt(all_data)` 不再读取 `all_data['alert_signals']`。

- [ ] **Step 1: 新建守卫测试文件**

创建 `tests/test_daily_briefing_alert_signals_removed.py`：

```python
import inspect

from app.services.notification import NotificationService
from app.llm.prompts.daily_briefing import build_daily_briefing_prompt


def test_format_alert_signals_removed():
    """关键信号已下线：盘中 price_alert 策略已推同一份 signal_cache。"""
    assert not hasattr(NotificationService, 'format_alert_signals')


def test_build_briefing_blocks_signature():
    params = list(inspect.signature(NotificationService.build_briefing_blocks).parameters)
    assert params == ['briefing_text', 'core_insights', 'action_suggestions']


def test_build_briefing_blocks_renders_without_alerts():
    blocks = NotificationService.build_briefing_blocks(
        '📊 持仓 (2026-08-08) | ¥100,000 | +1.2%\n🔴甲 +3.0% | 🟢乙 -1.0%',
        core_insights='市场情绪回暖',
        action_suggestions='关注半导体',
    )
    dumped = str(blocks)
    assert '今日核心观点' in dumped
    assert '持仓' in dumped
    assert '关键信号' not in dumped


def test_prompt_drops_alert_signals():
    prompt = build_daily_briefing_prompt({
        'position_summary': '持仓文本',
        'alert_signals': '不该出现的预警信号文本',
    })
    assert '持仓文本' in prompt
    assert '不该出现的预警信号文本' not in prompt
    assert '预警信号' not in prompt


def test_price_alert_strategy_kept():
    """signal_cache 的盘中消费者仍在，_refresh_signal_cache 因此必须保留。"""
    from app.strategies.price_alert import PriceAlertStrategy
    from app.strategies.daily_briefing import DailyBriefingStrategy
    assert PriceAlertStrategy.name == 'price_alert'
    assert hasattr(DailyBriefingStrategy, '_refresh_signal_cache')
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_daily_briefing_alert_signals_removed.py -v > .pytest_out.txt 2>&1; grep -E "passed|failed" .pytest_out.txt; rm .pytest_out.txt
```

Expected: `4 failed, 1 passed` —— 前四个测试因 `format_alert_signals` 仍在、签名仍含 `alerts_text`、prompt 仍含 `alert_signals` 而失败；`test_price_alert_strategy_kept` PASS。

- [ ] **Step 3: 删除 `format_alert_signals` 方法**

在 `app/services/notification.py` 删除从 `@staticmethod` + `def format_alert_signals(...)` 到其 `return {'text': text.rstrip('\n')}`（原 L236–360）的完整方法体。删除后 `format_briefing_summary` 的 `return` 之后紧接 `format_earnings_alerts`。

- [ ] **Step 4: 改 `build_briefing_blocks` 签名与实现**

签名改为：

```python
    @staticmethod
    def build_briefing_blocks(briefing_text: str, core_insights: str = '',
                              action_suggestions: str = '') -> list:
        """构建 Message 1 的 Block Kit blocks（核心观点 + 持仓）"""
```

并删除函数体末尾整个 `if alerts_text:` 分支（原 L1044–1064），使 `for line in briefing_text.split('\n'):` 循环结束后直接 `return blocks`。

- [ ] **Step 5: 改 `push_daily_report` 三处调用点**

① 删除这一行（原 L1265）：

```python
        alerts = NotificationService.format_alert_signals(codes, name_map, position_codes)
```

② 删除 `all_data` 字典里的这一行（原 L1329）：

```python
                    'alert_signals': alerts.get('text', ''),
```

③ 删除 msg1 拼装里的这两行（原 L1363–1364）：

```python
        if alerts.get('text'):
            msg1_parts.append(alerts['text'])
```

④ 更新 blocks 调用（原 L1366–1367）为：

```python
        msg1_blocks = NotificationService.build_briefing_blocks(
            briefing['text'], core_insights, action_suggestions)
```

⑤ 更新 `push_daily_report` 的 docstring：`"""一键推送每日报告（持仓+简报数据+GLM总结+预警+盯盘分析）"""` → `"""一键推送每日报告（持仓+简报数据+GLM总结+盯盘分析）"""`

⑥ 删除已变成死代码的 `position_codes` 计算块（原 L1256–1261）：

```python
        from app.services.position import PositionService
        position_codes = set()
        latest_date = PositionService.get_latest_date()
        if latest_date:
            pos_list = PositionService.get_snapshot(latest_date)
            position_codes = {p.stock_code for p in pos_list}
```

已核实：`position_codes` 在 `push_daily_report` 内的唯一消费者就是 ① 删掉的那行；该块算出的 `latest_date` 也不被复用——下方 `include_ai` 分支内部自己重新 `import PositionService` 并重新赋值 `latest_date`，与此块无关。

- [ ] **Step 6: 改 GLM prompt**

在 `app/llm/prompts/daily_briefing.py`：

① 删除 docstring 里的这一行：

```
            - alert_signals: 预警信号
```

② 删除 `label_map` 里的这一行：

```python
        'alert_signals': '预警信号',
```

- [ ] **Step 7: 运行测试确认全绿**

Run:
```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_daily_briefing_alert_signals_removed.py -v > .pytest_out.txt 2>&1; grep -E "passed|failed" .pytest_out.txt; rm .pytest_out.txt
```

Expected: `5 passed`。

- [ ] **Step 8: 确认无残留引用**

Run: `rtk grep -rn "format_alert_signals\|alerts_text\|alert_signals" app/ tests/`

Expected: 只有新建测试文件里作为字符串出现的 `'alert_signals'`（`test_prompt_drops_alert_signals` 的输入）和 `format_alert_signals`（hasattr 断言），`app/` 下零命中。

- [ ] **Step 9: 提交**

```bash
printf 'refactor(notification): 移除每日简报「关键信号」全链路\n\n展示与 GLM 输入一并下线；盘中 price_alert 已推同一份 signal_cache。\nbuild_briefing_blocks 去掉 alerts_text 形参。\n_refresh_signal_cache 保留（price_alert 覆盖面依赖它）。\n' > .git/MSG.txt && rtk git add app/services/notification.py app/llm/prompts/daily_briefing.py tests/test_daily_briefing_alert_signals_removed.py && rtk git commit -F .git/MSG.txt
```

---

## Task 3: 文档同步与全量回归

**Files:**
- Modify: `.claude/rules/notifications.md`（排版规范示例）

**Interfaces:**
- Consumes: Task 1 与 Task 2 的删除结果（全量 pytest 需要两者都已落地）
- Produces: 无代码产物

- [ ] **Step 1: 改 `.claude/rules/notifications.md` 的排版示例**

在「Slack 推送排版规范」章节，把

```
**标题**：`emoji + *粗体标题*`，如 `📉 *高点回退提醒*`
```

改为

```
**标题**：`emoji + *粗体标题*`，如 `🎯 *今日核心观点*`
```

（`📉 *高点回退提醒*` 指向已删除的代码，`🎯 今日核心观点` 是每日推送中仍存在的 header。）

- [ ] **Step 2: 全量单测**

Run:
```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ -v > .pytest_out.txt 2>&1; grep -E "passed|failed|error" .pytest_out.txt
```

Expected: 无 failed / error。若有失败，先看 `.pytest_out.txt` 全文定位是否与本次改动相关（本仓部分测试依赖网络/外部数据，若失败项与 notification / daily_briefing / value_dip 无关，记录下来但不算本任务回归）。

- [ ] **Step 3: 冒烟验证 blocks 与 prompt 可正常生成**

Run:
```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -c "import json; from app.services.notification import NotificationService as N; from app.llm.prompts.daily_briefing import build_daily_briefing_prompt as B; b=N.build_briefing_blocks('X 持仓 test', '观点', '建议'); print(json.dumps(b, ensure_ascii=False)[:300]); print('---'); print(B({'position_summary':'p','indices':'i'})[:200])"
```

Expected: 输出合法 JSON blocks 数组 + prompt 文本，无异常栈。

- [ ] **Step 4: 清理临时文件并提交**

```bash
rm -f .pytest_out.txt && printf 'docs(rules): notifications 排版示例改用仍存在的推送标题\n\n高点回退提醒已下线，规范文档不再引用已删除代码。\n' > .git/MSG.txt && rtk git add .claude/rules/notifications.md && rtk git commit -F .git/MSG.txt
```

- [ ] **Step 5: 确认三条 commit 都在链上**

Run: `rtk git log --oneline -4`

Expected: 看到 Task 1 / Task 2 / Task 3 三条 commit。若因并行 session 交错未在短列表中出现，用 `rtk git merge-base --is-ancestor <SHA> HEAD`（exit 0 = 仍在链上）确认，再 `rtk git show --stat <SHA>` 核对每条 commit 只含本任务文件。
