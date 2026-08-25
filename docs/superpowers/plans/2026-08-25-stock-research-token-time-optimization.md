# stock-research 优化实施计划 —— 消除重复支付与返工

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 stock-research 每轮重复支付的约 15KB 固定 prompt、约 4KB lens 内联、以及八成重复的 report 内容一次性消除，并把两条已沉淀的教训（L24 竞价假价、L25 缺回测）变成代码，在不降低产出质量的前提下降低单轮 token 与返工时间。

**Architecture:** 三层改造。(1) 新建 6 份 `.claude/agents/sr-*.md`，把角色定义、证据分级、取数规矩、汇报协议从每轮 prompt 搬进 frontmatter + body，各自绑定 `model`/`effort`/`skills`。(2) 把 261 行的 `sector-lenses.md` 拆成 7 份精确粒度文件，使「subagent 自读会挑错节」的前提消失。(3) 把 evidence 与 report 合并为单文件（明细层 + 结论层），闸门从「mtime 静默猜测」改为「`end:` 戳判定」，且**新旧格式并存**以消除切换风险。

**Tech Stack:** Python 3.10（`scripts/`，标准库 + pytest）；Markdown + YAML frontmatter；无新增第三方依赖。

**Spec:** `docs/superpowers/specs/2026-08-25-stock-research-token-time-optimization-design.md`

## Global Constraints

- 语言中文；不写多余注释；不留 backup 文件（git 留痕足够）。
- 所有 `git` / `pytest` 命令前加 `rtk`，链式 `&&` 中每条都要；**env 赋值必须在 `rtk` 之前**（`PYTHONIOENCODING=utf-8 rtk python -m pytest ...`，写成 `rtk PYTHONIOENCODING=...` 会报 Binary not found）。
- Windows 编码铁律：脚本内所有 `open()` / `read_text()` / `write_text()` **必须显式 `encoding='utf-8'`**（默认 cp950 会炸中文）。
- 算行数用 `python -c "print(sum(1 for _ in open(p, encoding='utf-8')))"`，**不要用 `wc -l`**（对含中文 UTF-8 文件偶发误报）。
- **不要用 heredoc 写含引号的长 Markdown**（Windows bash 易 EOF 失配，本计划撰写时已实测踩中）；改用 Write 工具或 `scripts/_xxx.py` 跑完即删。
- `git add <精确路径...> && git commit` **必须同一条命令链**（并行 session 会抢 index）；**绝不用 `git commit -- <pathspec>`**（提交工作区而非暂存区，会裹挟他人在写改动）。
- 测试平铺在 `tests/test_*.py`，不建子目录；测试文件用 `sys.path.insert(0, repo_root)` 后 `from scripts.X import ...`。
- 本计划所有脚本与测试**不 import `app`**，不需要 `SCHEDULER_ENABLED=0`。
- **分支策略**（沿用 `2026-08-22` 计划的精细版）：Task 1–4 带 pytest 测试 → 在**独立 worktree**；Task 5 合回 main；Task 6–7 纯文档契约 → 在 **main**。
- **lessons 编号永久**：`Ln` 一旦分配不复用、不重排。

## 与两份历史计划的关系（实施前必读）

本仓已有两份同方向的**已实施**计划，读懂它们才不会推翻已验证的成果：

| 计划 | 已实施的成果 | 与本计划的关系 |
|---|---|---|
| `2026-08-08-stock-deep-redo-提速.md` | ①汇报写固定路径文件；②Phase A 拆三路并行；③**控制者内联注入命中 lens，不让写手读整份 `sector-lenses.md`**；④耗时账机制（基线 40min→29min） | **Task 3 是对 ③ 的升级而非推翻**：③ 针对的是「261 行大杂烩文件」，本计划把它拆成 70 行精确粒度文件，于是「代读」可以退化为「自读」而不会挑错节。**Task 6 必须同步 ④ 的耗时账读取逻辑**，因为合并后 report 文件名变了 |
| `2026-08-22-stock-deep-redo-瘦身与闸门机制化.md` | ①`deep_redo_gate.py` + `deep_redo_anchor_audit.py`；②SKILL.md 378→247 行；③`lessons.md` 编号化 | **Task 4 修改的正是它产出的 `deep_redo_gate.py`**，必须同步改 `tests/test_deep_redo_gate.py` |

两份计划**均未涉及** agent 定义、`effort` 字段、evidence/report 合并（已 grep 确认 0 匹配）——本计划的 Task 2 / 4 / 6 是全新领域，不重复劳动。

## 对 spec 的三处修正（实施以本计划为准）

1. **spec §3.4「废除 `--quiet-min`」→ 改为「默认值 3.0 降到 0.5」。**
   `tests/test_deep_redo_gate.py` 的 docstring 记录了一条实测教训：光智轮 A1 在 report 落盘后 14 分钟又追加 325 行，所以「report 存在」对「是否收工」没有判别力。该教训成立的前提是**两份文件**（report 先落盘、evidence 后追加）。合并为单文件后前提消失，但保留 0.5 分钟 mtime 保险仍比完全废除稳妥，且已消除 83% 的空等。
2. **spec §4 批 3「原子」→ 改为「新旧格式并存，不必原子」。**
   闸门改成**新格式优先、找不到则回退旧双文件格式**，于是 Task 4（闸门）与 Task 6（文档契约）可分别合并，任一先落地都不会让流程断掉。
3. **spec 漏了耗时账的连带影响**。08-08 计划建立的耗时账要读六份 `-phase*-report.md` 的 `start`/`end` 戳，合并后文件名变为 `-A1.md` 等，**Task 6 必须同步这段指令**，否则耗时账读不到文件。

---

### Task 1: `quote_guard.py` —— 把 L24 竞价断言变成代码

**Files:**
- Create: `scripts/quote_guard.py`
- Test: `tests/test_quote_guard.py`

**Interfaces:**
- Consumes: 无（叶子任务）
- Produces:
  - `class QuoteRejected(Exception)` — 断言失败抛出，`str(exc)` 含中文原因
  - `infer_market(code: str) -> str` — 返回 `'HK'` / `'A'` / `'US'`
  - `in_session(market: str, ts: datetime) -> bool`
  - `guard(quote: dict, *, allow_preopen: bool = False) -> dict` — 通过则原样返回；`allow_preopen` 放行时给返回值加 `quote['preopen_warning']`
  - quote dict 必需键：`code`, `price`, `volume`, `timestamp`(datetime), `market_cap`, `shares`

- [ ] **Step 1: 写失败测试**

创建 `tests/test_quote_guard.py`：

```python
"""行情取数守卫：拒绝集合竞价参考价、零成交、字段错位的报价。

L24（2026-08-25 建滔积层板轮）：控制者 09:00:20 读到 hk01888 报 40.360/+14.99%、
成交仅 95 手，据此把「中报超预期导致跳涨」写进三路 A 的派发；而 09:20 开盘后
实为 35.320/+0.63%，因果完全反了。三路 subagent 全被污染、两轮校准。
"""
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.quote_guard import QuoteRejected, guard, in_session, infer_market

SHARES = 3_151_450_000


def _quote(price, volume, ts, *, code='hk01888', shares=SHARES, market_cap=None):
    return {
        'code': code,
        'price': price,
        'volume': volume,
        'timestamp': ts,
        'shares': shares,
        'market_cap': market_cap if market_cap is not None else price * shares,
    }


def test_infer_market():
    assert infer_market('hk01888') == 'HK'
    assert infer_market('sh600183') == 'A'
    assert infer_market('sz300757') == 'A'
    assert infer_market('NVDA') == 'US'


def test_in_session_hk():
    assert in_session('HK', datetime(2026, 8, 25, 10, 13)) is True
    assert in_session('HK', datetime(2026, 8, 25, 9, 0)) is False
    assert in_session('HK', datetime(2026, 8, 25, 9, 20)) is False
    assert in_session('HK', datetime(2026, 8, 25, 12, 30)) is False


def test_rejects_preopen_auction_price():
    """本条就是 L24 的原始现场：09:00:20、成交 95 手、报 40.360。"""
    q = _quote(40.360, 95, datetime(2026, 8, 25, 9, 0, 20))
    with pytest.raises(QuoteRejected) as exc:
        guard(q)
    assert '竞价' in str(exc.value)


def test_rejects_zero_volume():
    q = _quote(35.320, 0, datetime(2026, 8, 25, 10, 13))
    with pytest.raises(QuoteRejected) as exc:
        guard(q)
    assert '成交' in str(exc.value)


def test_rejects_market_cap_mismatch():
    """市值与 价×股本 不符 = 字段错位；旧档曾把振幅字段当 PB 用。"""
    q = _quote(35.320, 5_000_000, datetime(2026, 8, 25, 10, 13),
               market_cap=35.320 * SHARES * 1.5)
    with pytest.raises(QuoteRejected) as exc:
        guard(q)
    assert '自洽' in str(exc.value)


def test_accepts_valid_intraday_quote():
    q = _quote(35.320, 5_000_000, datetime(2026, 8, 25, 10, 13))
    assert guard(q) is q


def test_allow_preopen_passes_but_marks_warning():
    q = _quote(40.360, 95, datetime(2026, 8, 25, 9, 0, 20))
    out = guard(q, allow_preopen=True)
    assert '不可作行情锚' in out['preopen_warning']
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 rtk python -m pytest tests/test_quote_guard.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'scripts.quote_guard'`

- [ ] **Step 3: 写实现**

创建 `scripts/quote_guard.py`：

```python
"""行情取数守卫：拒绝集合竞价参考价、零成交、字段错位的报价。

用法：
    from scripts.quote_guard import guard, QuoteRejected
    try:
        q = guard(quote_dict)
    except QuoteRejected as exc:
        print(f'取数被拒：{exc}')

见 stock-research references/lessons.md L24。
"""
from __future__ import annotations

from datetime import datetime, time

MIN_VOLUME = 1_000
MARKET_CAP_TOLERANCE = 0.01

MARKET_SESSIONS = {
    'HK': ((time(9, 30), time(12, 0)), (time(13, 0), time(16, 0))),
    'A': ((time(9, 30), time(11, 30)), (time(13, 0), time(15, 0))),
    'US': ((time(9, 30), time(16, 0)),),
}


class QuoteRejected(Exception):
    """报价未通过守卫断言。"""


def infer_market(code: str) -> str:
    c = code.lower()
    if c.startswith('hk'):
        return 'HK'
    if c.startswith(('sh', 'sz')):
        return 'A'
    return 'US'


def in_session(market: str, ts: datetime) -> bool:
    sessions = MARKET_SESSIONS[market]
    t = ts.time()
    return any(start <= t <= end for start, end in sessions)


def guard(quote: dict, *, allow_preopen: bool = False) -> dict:
    market = infer_market(quote['code'])
    ts = quote['timestamp']
    if not in_session(market, ts):
        if not allow_preopen:
            raise QuoteRejected(
                f"{quote['code']} 时戳 {ts:%H:%M:%S} 不在 {market} 连续交易时段内 —— "
                '这是集合竞价参考价或非交易时段快照，不可作行情锚')
        quote['preopen_warning'] = '竞价参考价，不可作行情锚'
        return quote
    if quote['volume'] < MIN_VOLUME:
        raise QuoteRejected(
            f"{quote['code']} 成交量仅 {quote['volume']} —— 疑为竞价挂单或停牌，不可作行情锚")
    implied = quote['price'] * quote['shares']
    cap = quote['market_cap']
    if cap and abs(implied - cap) / cap > MARKET_CAP_TOLERANCE:
        raise QuoteRejected(
            f"{quote['code']} 市值不自洽：价×股本={implied:,.0f} vs 报市值={cap:,.0f} —— "
            '疑为字段索引错位')
    return quote
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 rtk python -m pytest tests/test_quote_guard.py -v`
Expected: PASS，7 passed

- [ ] **Step 5: 提交**

```bash
rtk git add scripts/quote_guard.py tests/test_quote_guard.py && rtk git commit -m "feat(stock-research): quote_guard 拒绝竞价参考价/零成交/字段错位

把 L24 变成代码：2026-08-25 建滔积层板轮控制者 09:00:20 读到竞价价 40.360
(+14.99%、成交 95 手)，据此把「中报超预期导致跳涨」写进三路 A 派发，而开盘
后实为 35.320(+0.63%)，因果完全反了，三路全被污染 + 两轮校准。"
```

---

### Task 2: 六份 `sr-*` agent 定义

**Files:**
- Create: `.claude/agents/sr-a1-anchor.md`, `sr-a2-thesis.md`, `sr-a3-lens.md`, `sr-writer.md`, `sr-reviewer.md`, `sr-finalize.md`
- Test: `tests/test_sr_agent_defs.py`

**Interfaces:**
- Consumes: `scripts/quote_guard.py`（Task 1）—— `sr-a1-anchor` body 引用它
- Produces: 六个 agent 名供 `Agent(subagent_type=...)` 调用；Task 6 的 `dispatch.md` 依赖这些名字

- [ ] **Step 1: 写失败测试**

创建 `tests/test_sr_agent_defs.py`：

```python
"""六份 sr-* agent 定义的 frontmatter 契约。

它们承载了原本每轮重写进 prompt 的约 15KB 固定内容；字段写错会静默退化成
默认 model/effort（没有报错），因此必须有断言守着。
"""
import re
from pathlib import Path

import pytest

AGENTS_DIR = Path(__file__).resolve().parent.parent / '.claude' / 'agents'

EXPECTED = {
    'sr-a1-anchor': {'model': 'opus', 'effort': 'high'},
    'sr-a2-thesis': {'model': 'opus', 'effort': 'medium'},
    'sr-a3-lens': {'model': 'opus', 'effort': 'medium'},
    'sr-writer': {'model': 'opus', 'effort': 'high'},
    'sr-reviewer': {'model': 'sonnet', 'effort': 'high'},
    'sr-finalize': {'model': 'sonnet', 'effort': 'low'},
}

VALID_MODELS = {'opus', 'sonnet', 'haiku', 'fable'}
VALID_EFFORTS = {'low', 'medium', 'high', 'xhigh', 'max'}


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding='utf-8')
    m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    assert m, f'{path.name} 缺 frontmatter'
    out = {}
    for line in m.group(1).split('\n'):
        if ':' in line and not line.startswith((' ', '-')):
            k, _, v = line.partition(':')
            out[k.strip()] = v.strip()
    return out


@pytest.mark.parametrize('name', sorted(EXPECTED))
def test_agent_def_exists_and_fields_valid(name):
    path = AGENTS_DIR / f'{name}.md'
    assert path.exists(), f'缺 {path}'
    fm = _frontmatter(path)
    assert fm['name'] == name
    assert fm['model'] == EXPECTED[name]['model']
    assert fm['effort'] == EXPECTED[name]['effort']
    assert fm['model'] in VALID_MODELS
    assert fm['effort'] in VALID_EFFORTS


@pytest.mark.parametrize('name', sorted(EXPECTED))
def test_description_declares_dispatch_only(name):
    """agent 定义会进全局列表，必须声明只由 stock-research 派发，防误触发。"""
    fm = _frontmatter(AGENTS_DIR / f'{name}.md')
    assert 'stock-research' in fm['description']
    assert '勿直接调用' in fm['description']


def test_writer_and_reviewer_prebind_doc_spec():
    """写手/审查员预绑 buffett-doc-spec，省掉每轮 prompt 里叮嘱 Skill 加载。"""
    for name in ('sr-writer', 'sr-reviewer'):
        fm = _frontmatter(AGENTS_DIR / f'{name}.md')
        assert 'buffett-doc-spec' in fm.get('skills', '')


def test_a1_body_requires_quote_guard_and_backtest():
    """A1 的两条防返工要求必须写死在定义里，不依赖控制者每轮记得叮嘱。"""
    body = (AGENTS_DIR / 'sr-a1-anchor.md').read_text(encoding='utf-8')
    assert 'quote_guard' in body
    assert '上年同期' in body
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 rtk python -m pytest tests/test_sr_agent_defs.py -v`
Expected: FAIL —— `缺 .../.claude/agents/sr-a1-anchor.md`

- [ ] **Step 3: 建 `sr-a1-anchor.md`**

用 Write 工具创建 `.claude/agents/sr-a1-anchor.md`：

```markdown
---
name: sr-a1-anchor
description: stock-research 模式 1/2 的 A1 数据锚采证路。仅由 stock-research 控制者派发，勿直接调用。
model: opus
effort: high
---

你是投研采证 A1（数据锚）。你是本轮**所有硬数字的唯一权威源**，A2/A3 以定性为主，冲突以你为准。

## 取数铁律

- **行情必须经 `scripts/quote_guard.py` 断言**，不得直接解析腾讯字段后就用。竞价参考价、零成交、市值不自洽三种情况一律拒绝（lessons L24）。
- 港股 `q=hk01888` 字段索引异于 A 股，必须 dump 全串自辨。已知身份：`[1]`名称 `[3]`现价 `[4]`昨收 `[30]`时戳 `[32]`涨跌% `[33]/[34]`当日高/低 `[36]`成交量 `[39]`**静态 PE（不是 TTM）** `[43]`当日振幅%（**不是 PB**）`[44]/[45]`市值(亿) `[47]`股息率% `[48]/[49]`52周高/低 `[57]`**PE-TTM** `[58]`**PB** `[69]/[70]`总股本 `[72]`DPS。
- 行情锚必须明写「盘中 + 精确时刻」还是「收盘」，不许把盘中价写成收盘价。
- 市值自洽校验必做：现价 × 总股本 = 市值。
- 港/美股市值/PE/PB/52 周优先 WebFetch `stockanalysis.com` 或 Yahoo，**双源交叉**。亏损标的 PE=N/A 改看 PS/PB/Forward PE。

## 裁决纪律

- **凡你用来裁决的比率型指标，先跑一遍上年同期，确认该指标在本公司不存在季节性偏置**（lessons L25）。半年 vs 全年、单季 vs 年度尤其危险：季节性与营运资金周期会让指标天然落在阈值一侧，此时它测的是日历不是经营。
- 逐条对账旧档关键假设与 §11 触发器，每条标【证实 / 证伪 / 无信息】，证伪的给财报原文数字 + 页码/URL。
- 一次性项剥离：非经常损益、减值、汇兑、政府补助 → 写出扣除后的可比口径。

## 证据分级

【硬】= 公司公告/财报/交易所披露/官方声明；【软】= 券商研报/产业媒体/第三方分析；【缺】= 找不到，**明写「未找到公开证据」，不许编**。每个关键数字挂 URL + 日期。中英文交叉检索。区分官方披露 / 媒体转述 / 分析师预测，不得混用。

## 脚本纪律

一次性取数脚本写到 `scripts/_a1_*.py`，用 `PYTHONIOENCODING=utf-8 python scripts/_a1_xxx.py` 跑，写文件显式 `encoding='utf-8'`，**别用 heredoc**（Windows bash 易 EOF 失配），管道可能吞 stdout（验证改写文件再读）。**跑完必须 `rm`，不入库。**

## 交付

产出文件路径与格式见控制者派发。汇报**必须**写进文件，消息回传是可选冗余通道，不是交付方式。
```

- [ ] **Step 4: 建其余五份**

用 Write 工具逐份创建。**frontmatter 严格按 `EXPECTED` 表**；body 是把 `references/dispatch.md` 现有原文**整体迁移**（不是重写），源行号如下（`dispatch.md` 共 116 行）：

| 目标文件 | frontmatter | body 源 | 迁移内容 |
|---|---|---|---|
| `sr-a2-thesis.md` | `model: opus`<br>`effort: medium` | `dispatch.md:39-79` 中的 **A2 段**（"**A2 论点验证**"起至 "**A3 lens 专项**"前） | 逐条核实多空论点、**每条必给反驳点**、供给侧论点逐家拆「退出/扩产/政策」的范围+时间表+动机、报价/需求数据注明机构间分歧、标的最新动向 |
| `sr-a3-lens.md` | `model: opus`<br>`effort: medium` | `dispatch.md:39-79` 中的 **A3 段** | 逐条回应不许跳过、查不到明写「未找到公开证据」、概念维度标【实证/概念】 |
| `sr-writer.md` | `model: opus`<br>`effort: high`<br>`skills: buffett, buffett-doc-spec` | `dispatch.md:80-102`（`## 2. Phase B`整节） | 七文件产出、`index.md` frontmatter 不写 `related_docs`、`events.md` 已存在则不碰、抗中断落盘顺序、`【待锚】`占位再填、数字镜像纪律、变化清单格式、只跑 `lint_docs_frontmatter.py` 不跑 refs 不 git add/commit、派发坑（`Stream idle timeout` 时用 SendMessage 续跑勿重派） |
| `sr-reviewer.md` | `model: sonnet`<br>`effort: high`<br>`skills: buffett-doc-spec` | `dispatch.md:103-111`（`## 3. 合并审查`整节） | 两段正文必须完整写进文件、所有含数字的 frontmatter 字段与正文逐个比对、8 条红线、Critical/Major/Minor/Nit 分级、每条给文件名 + 行号 + 两处冲突原文 |
| `sr-finalize.md` | `model: sonnet`<br>`effort: low` | `references/finalize.md` **全文**（56 行） | 动作清单 1-11 + 提交铁律（`git rm`+`git add`+`git commit` 同一命令链、禁止 `git commit -- <pathspec>`、提交后 `git show --stat HEAD` 与 `git show HEAD:` 亲验、不主动 push） |

**三处迁移时必须加的内容**（原 dispatch.md 里没有，属本次新增）：

1. `sr-a2-thesis.md` / `sr-a3-lens.md` 末尾各加与 `sr-a1-anchor.md` **逐字相同**的「## 证据分级」与「## 脚本纪律」两节，并各加一句：
   `> 硬数字以 A1 为准。你以定性为主，与 A1 冲突时一律让位。`
2. `sr-a3-lens.md` 加「## lens 选取规则」节，含 Task 3 的完整映射表，规则为：
   `加载全部 x-*.md（横切，默认跑识别）+ 按 subsector 匹配的 1–2 份板块专属。无板块专属命中时只跑横切，并在产出里明写「无板块专属 lens 命中」。`
3. `sr-writer.md` 加一句：
   `按 references/lenses/ 映射表自读命中 lens 的【撰写落点】【双面必答】【监控指标模板】三节，命中 lens 的每个必查项正文都要有回应。`

- [ ] **Step 5: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 rtk python -m pytest tests/test_sr_agent_defs.py -v`
Expected: PASS，14 passed（6 参数化 × 2 + 2 独立）

- [ ] **Step 6: 人工确认 agent 可被识别**

在 Claude Code 中执行 `ListAgents`，确认列出 6 个 `sr-*`。若未列出，检查 `.claude/agents/` 是否在仓库根的 `.claude/` 下。

- [ ] **Step 7: 提交**

```bash
rtk git add .claude/agents/ tests/test_sr_agent_defs.py && rtk git commit -m "feat(stock-research): 六份 sr-* agent 定义固化每轮重写的固定内容

把角色定义/证据分级/取数规矩/汇报协议从每轮 prompt 搬进 agent frontmatter+body,
各带 model+effort, 写手与审查员预绑 buffett-doc-spec。实测单轮四份 prompt 约 24KB
中约 15KB 是固定内容, 此前每轮重付一次。

A1 定义写死两条防返工要求: 取行情必须经 quote_guard(L24)、比率型指标先回测
上年同期(L25)。"
```

---

### Task 3: `sector-lenses.md` 拆成 7 份精确粒度文件

**Files:**
- Create: `.claude/skills/stock-research/references/lenses/x-ai.md`, `x-growth.md`, `x-dividend-value.md`, `pcb-ccl.md`, `storage-dram-nand.md`, `storage-nor-flash.md`, `metals-copper.md`
- Delete: `.claude/skills/stock-research/references/sector-lenses.md`
- Test: `tests/test_lenses_split.py`

**Interfaces:**
- Consumes: 无
- Produces: 7 个 lens 文件路径 + 映射表，供 `sr-a3-lens`（Task 2）与 `sr-writer` body 引用、Task 6 的 `dispatch.md` / `mode-deep.md` / `SKILL.md` 引用

**拆分映射**（源文件 `sector-lenses.md` 的 `## ` 节 → 目标文件）：

| 源节 | 目标文件 | 类型 |
|---|---|---|
| AI（横切 · 默认对每只股跑识别） | `lenses/x-ai.md` | 横切（默认） |
| 成长 / 扩产 / 客户增长（横切） | `lenses/x-growth.md` | 横切（默认） |
| 分红/价值股（横切 · consumer/materials/energy/industrial/financial 默认） | `lenses/x-dividend-value.md` | 横切（条件默认） |
| PCB / CCL | `lenses/pcb-ccl.md` | 板块专属 |
| 存储 — DRAM / NAND | `lenses/storage-dram-nand.md` | 板块专属 |
| 存储 — NOR Flash | `lenses/storage-nor-flash.md` | 板块专属 |
| 铜 / 铜矿 / 有色金属 | `lenses/metals-copper.md` | 板块专属 |

- [ ] **Step 1: 写失败测试**

创建 `tests/test_lenses_split.py`：

```python
"""lens 拆分的内容守恒与结构完整性。

拆分的目的不是省 token，而是让「subagent 自读会挑错节」的前提消失：
原 sector-lenses.md 261 行是大杂烩（实测单轮只命中约 70 行），拆成精确粒度
后自读不可能挑错节，于是控制者不必再摘原文内联（内联铁律降级为混合口径）。
"""
from pathlib import Path

import pytest

LENSES = Path(__file__).resolve().parent.parent / '.claude' / 'skills' / \
    'stock-research' / 'references' / 'lenses'

CROSS_CUTTING = ('x-ai.md', 'x-growth.md', 'x-dividend-value.md')
SECTOR_SPECIFIC = ('pcb-ccl.md', 'storage-dram-nand.md',
                   'storage-nor-flash.md', 'metals-copper.md')
ALL_LENSES = CROSS_CUTTING + SECTOR_SPECIFIC

REQUIRED_SECTIONS = ('【识别信号】', '【必查清单（采证 face）】',
                     '【撰写落点（撰写 face）】', '【双面必答】', '【监控指标模板】')


@pytest.mark.parametrize('name', ALL_LENSES)
def test_lens_file_exists(name):
    assert (LENSES / name).exists(), f'缺 {name}'


@pytest.mark.parametrize('name', ALL_LENSES)
def test_lens_has_all_required_sections(name):
    """每份 lens 必须自包含四节，否则自读的 agent 会拿到残缺清单。"""
    text = (LENSES / name).read_text(encoding='utf-8')
    for sec in REQUIRED_SECTIONS:
        assert sec in text, f'{name} 缺 {sec}'


def test_old_monolith_removed():
    """旧大杂烩必须删除，否则控制者会去读一个已废弃的文件。"""
    old = LENSES.parent / 'sector-lenses.md'
    assert not old.exists(), '拆分后 sector-lenses.md 必须删除'


def test_cross_cutting_prefix_convention():
    """x- 前缀是 sr-a3-lens 判断「是否默认加载」的依据，不能乱改。"""
    for name in CROSS_CUTTING:
        assert name.startswith('x-')
    for name in SECTOR_SPECIFIC:
        assert not name.startswith('x-')
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 rtk python -m pytest tests/test_lenses_split.py -v`
Expected: FAIL —— `缺 x-ai.md`（且 `test_old_monolith_removed` 也失败）

- [ ] **Step 3: 用脚本机械拆分（保证内容无损）**

创建临时脚本 `scripts/_split_lenses.py`（跑完即删）：

```python
"""把 sector-lenses.md 按 ## 节机械拆成 lenses/*.md，保证正文逐字无损。"""
import re
from pathlib import Path

REF = Path('.claude/skills/stock-research/references')
SRC = REF / 'sector-lenses.md'
OUT = REF / 'lenses'

MAPPING = [
    ('AI（横切', 'x-ai.md'),
    ('成长 / 扩产 / 客户增长', 'x-growth.md'),
    ('分红/价值股', 'x-dividend-value.md'),
    ('PCB / CCL', 'pcb-ccl.md'),
    ('存储 — DRAM / NAND', 'storage-dram-nand.md'),
    ('存储 — NOR Flash', 'storage-nor-flash.md'),
    ('铜 / 铜矿 / 有色金属', 'metals-copper.md'),
]

text = SRC.read_text(encoding='utf-8')
heads = [(m.start(), m.group().strip()) for m in re.finditer(r'^## .*$', text, re.M)]
OUT.mkdir(exist_ok=True)

total = 0
for i, (pos, head) in enumerate(heads):
    end = heads[i + 1][0] if i + 1 < len(heads) else len(text)
    body = text[pos:end].rstrip() + '\n'
    target = next((f for key, f in MAPPING if key in head), None)
    if target is None:
        print(f'!! 未映射的节：{head}')
        continue
    (OUT / target).write_text(body, encoding='utf-8')
    total += len(body)
    print(f'{target:26s} <- {head[:40]}  ({len(body)} chars)')

print(f'\n拆出正文合计 {total} chars；源文件 {len(text)} chars（差额=文件头与节间空行）')
```

Run: `PYTHONIOENCODING=utf-8 python scripts/_split_lenses.py`
Expected: 7 行映射输出，无 `!! 未映射的节`

- [ ] **Step 4: 人工校验内容无损，然后删源文件与临时脚本**

```bash
PYTHONIOENCODING=utf-8 python -c "print(sum(1 for _ in open('.claude/skills/stock-research/references/sector-lenses.md',encoding='utf-8')))"
```
记下行数（应为 261）。再算 7 份之和：
```bash
PYTHONIOENCODING=utf-8 python -c "
from pathlib import Path
d=Path('.claude/skills/stock-research/references/lenses')
print(sum(sum(1 for _ in open(p,encoding='utf-8')) for p in d.glob('*.md')))"
```
两数差额应仅为源文件头部说明行与节间空行（个位数）。差额过大说明有节漏拆，**停下检查**。

确认后：
```bash
rm .claude/skills/stock-research/references/sector-lenses.md scripts/_split_lenses.py
```

- [ ] **Step 5: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 rtk python -m pytest tests/test_lenses_split.py -v`
Expected: PASS，16 passed

- [ ] **Step 6: 提交**

```bash
rtk git add .claude/skills/stock-research/references/lenses/ tests/test_lenses_split.py && rtk git rm -q .claude/skills/stock-research/references/sector-lenses.md && rtk git commit -m "refactor(stock-research): sector-lenses 拆 7 份精确粒度文件

3 份横切(x- 前缀, 默认跑识别) + 4 份板块专属。拆分推翻内联铁律的前提:
原铁律理由是「自读会挑错节 —— 261 行只命中约 70 行」, 拆分后文件本身即
精确粒度, 挑错节不再可能, 故 lens 可由 sr-a3-lens/sr-writer 自读。

这是对 2026-08-08 提速计划第三根杠杆的升级而非推翻: 那轮针对的是大杂烩
文件, 本轮把文件本身做精确。"
```

---

### Task 4: 闸门支持 evidence/report 合并格式（新旧并存）

**Files:**
- Modify: `scripts/deep_redo_gate.py`
- Modify: `tests/test_deep_redo_gate.py`

**Interfaces:**
- Consumes: 无
- Produces:
  - `_lane_docs(artifacts, prefix, lane) -> tuple[Path | None, Path | None, Path | None]` — 返回 `(merged, evidence, report)`，`merged` 非 None 表示走新格式
  - 新格式文件名约定：`{stock}-{date}-{lane}.md`（lane ∈ `A1`/`A2`/`A3`/`B`/`review`）
  - 新格式必需结构：含 `## 结论层` 且含 `^end:` 戳
  - `--quiet-min` 默认值由 `3.0` 改为 `0.5`

**关键设计**：新格式优先、找不到回退旧双文件格式。因此本任务合并后，**旧流程仍完全可用**，Task 6 的文档切换可以独立进行。

- [ ] **Step 1: 写失败测试**

在 `tests/test_deep_redo_gate.py` 末尾追加（保留全部现有用例，它们是旧格式的回归测试）：

```python
# ---------- 合并格式（evidence + report 单文件）----------

def _merged_body(lines: int = 30, *, with_end: bool = True,
                 with_conclusion: bool = True) -> str:
    parts = ['start: 2026-08-22 08:30:00', '', '## 明细层', '']
    parts += [f'- 证据行 {i}：https://example.com/{i} （2026-08-22）' for i in range(lines)]
    if with_conclusion:
        parts += ['', '## 结论层', '', '对账：证实 3 / 证伪 1 / 无信息 2。']
    if with_end:
        parts += ['', 'end: 2026-08-22 08:52:00']
    return '\n'.join(parts) + '\n'


def _make_merged_a(tmp_path: Path, *, lanes=('A1', 'A2', 'A3'), age_min=5.0, **kw):
    art = tmp_path / 'artifacts'
    art.mkdir(exist_ok=True)
    for lane in lanes:
        _write(art / f'{STOCK}-{DATE}-{lane}.md', _merged_body(**kw), age_min)
    return art


def test_merged_phase_a_all_green(tmp_path, capsys):
    art = _make_merged_a(tmp_path)
    rc = main([STOCK, DATE, '--phase', 'A', '--artifacts', str(art)])
    assert rc == 0, capsys.readouterr().out
    assert 'A READY' in capsys.readouterr().out


def test_merged_missing_end_stamp(tmp_path, capsys):
    """end: 戳写在文件最末，它的存在即「全文写完」——这是合并格式的核心判据。"""
    art = _make_merged_a(tmp_path, with_end=False)
    rc = main([STOCK, DATE, '--phase', 'A', '--artifacts', str(art)])
    out = capsys.readouterr().out
    assert rc == 1
    assert 'end:' in out


def test_merged_missing_conclusion_section(tmp_path, capsys):
    """只有明细层没有结论层 = 采证完了但没做对账，不许放行。"""
    art = _make_merged_a(tmp_path, with_conclusion=False, with_end=False)
    rc = main([STOCK, DATE, '--phase', 'A', '--artifacts', str(art)])
    out = capsys.readouterr().out
    assert rc == 1
    assert '结论层' in out


def test_merged_no_end_and_stale_reports_died_before_delivery(tmp_path, capsys):
    """明细层有内容、无 end 戳、且很久没动 = 大概率死在交付前（L22）。"""
    art = _make_merged_a(tmp_path, with_end=False, age_min=30.0)
    rc = main([STOCK, DATE, '--phase', 'A', '--stale-min', '20',
               '--artifacts', str(art)])
    out = capsys.readouterr().out
    assert rc == 1
    assert '死在交付前' in out


def test_merged_format_takes_precedence_over_legacy(tmp_path, capsys):
    """两种格式同时存在时以合并格式为准，避免读到上一轮的残留旧文件。"""
    art = _make_phase_a(tmp_path)                      # 旧格式，全绿
    _write(art / f'{STOCK}-{DATE}-A1.md',
           _merged_body(with_end=False), 5.0)          # 新格式 A1 未完成
    rc = main([STOCK, DATE, '--phase', 'A', '--artifacts', str(art)])
    out = capsys.readouterr().out
    assert rc == 1
    assert 'A1' in out and 'end:' in out


def test_default_quiet_min_is_half_minute(tmp_path, capsys):
    """合并后 end 戳是主判据，mtime 只作保险 —— 默认从 3.0 降到 0.5。"""
    from scripts.deep_redo_gate import build_parser
    assert build_parser().parse_args([STOCK, DATE, '--phase', 'A']).quiet_min == 0.5


def test_merged_phase_b_and_review(tmp_path, capsys):
    art = tmp_path / 'artifacts'
    art.mkdir()
    _write(art / f'{STOCK}-{DATE}-B.md', _merged_body(), 5.0)
    d = _make_folder(tmp_path)
    rc = main([STOCK, DATE, '--phase', 'B', '--doc', str(d), '--artifacts', str(art)])
    assert rc == 0, capsys.readouterr().out

    body = _merged_body().replace(
        '对账：证实 3 / 证伪 1 / 无信息 2。',
        'SPEC-COMPLIANT\n\nAPPROVED-WITH-NITS')
    _write(art / f'{STOCK}-{DATE}-review.md', body, 1.0)
    rc = main([STOCK, DATE, '--phase', 'review', '--artifacts', str(art)])
    assert rc == 0, capsys.readouterr().out
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 rtk python -m pytest tests/test_deep_redo_gate.py -v`
Expected: 现有用例 PASS；7 个新用例 FAIL（合并格式未被识别，报 `MISSING: evidence`）

- [ ] **Step 3: 改闸门**

在 `scripts/deep_redo_gate.py` 中，于 `_check_report` 之后插入：

```python
CONCLUSION_RE = re.compile(r'^##\s*结论层', re.M)


def _lane_docs(artifacts: Path, prefix: str, lane: str
               ) -> tuple[Path | None, Path | None, Path | None]:
    """新格式优先：合并单文件存在则用它，否则回退旧的 evidence + report 双文件。"""
    merged = artifacts / f'{prefix}-{lane}.md'
    if merged.exists():
        return merged, None, None
    evidence = _find_one(artifacts, f'{prefix}-evidence-{lane}-*.md')
    legacy = 'review' if lane == 'review' else f'phase{lane}'
    return None, evidence, artifacts / f'{prefix}-{legacy}-report.md'


def _check_merged(path: Path, tag: str, now: float,
                  quiet_min: float, stale_min: float) -> tuple[list[str], list[str]]:
    """合并格式的三条判据：篇幅、结论层、end 戳。"""
    problems: list[str] = []
    notes: list[str] = []
    text = _read(path)
    lines = _count_lines(path)
    if lines < MIN_EVIDENCE_LINES:
        problems.append(f'{tag} NOT-READY: only {lines} lines (<{MIN_EVIDENCE_LINES})')
    if not CONCLUSION_RE.search(text):
        problems.append(f'{tag} NOT-READY: 缺 ## 结论层')
    age = _age_min(path, now)
    if not END_STAMP_RE.search(text):
        if age > stale_min:
            problems.append(
                f'{tag} NOT-READY: 缺 end: 时间戳且 {age:.1f}min 未动 —— '
                '大概率死在交付前，控制者接管')
        else:
            problems.append(f'{tag} NOT-READY: 缺 end: 时间戳')
    elif age < quiet_min:
        problems.append(f'{tag} NOT-READY: mtime {age:.1f}min ago (<{quiet_min})')
    return problems, notes
```

把 `check_phase_a` 的循环体改为：

```python
    for lane in lanes:
        merged, evidence, report = _lane_docs(artifacts, prefix, lane)
        if merged is not None:
            p, n = _check_merged(merged, lane, now, quiet_min, stale_min)
            problems += p
            notes += n
            continue
        if evidence is None:
            problems.append(f'{lane} MISSING: evidence')
        else:
            lines = _count_lines(evidence)
            if lines < MIN_EVIDENCE_LINES:
                problems.append(
                    f'{lane} NOT-READY: evidence only {lines} lines (<{MIN_EVIDENCE_LINES})')
            age = _age_min(evidence, now)
            if age < quiet_min:
                problems.append(
                    f'{lane} NOT-READY: evidence mtime {age:.1f}min ago (<{quiet_min})')
            elif age > stale_min:
                notes.append(
                    f'{lane} NOTE: evidence mtime {age:.1f}min ago — 若该路仍在跑，'
                    '确认它是收工而非卡住')
        problems += _check_report(report, lane)
```

`check_phase_b` 开头改为：

```python
def check_phase_b(artifacts: Path, stock: str, date: str, doc: str,
                  now: float = 0.0, quiet_min: float = 0.5,
                  stale_min: float = 20.0) -> list[str]:
    prefix = f'{stock}-{date}'
    merged, _, report = _lane_docs(artifacts, prefix, 'B')
    if merged is not None:
        problems, _ = _check_merged(merged, 'B', now or time.time(), quiet_min, stale_min)
    else:
        problems = _check_report(report, 'B')
```

`check_review` 开头改为：

```python
def check_review(artifacts: Path, stock: str, date: str,
                 now: float = 0.0, quiet_min: float = 0.5,
                 stale_min: float = 20.0) -> list[str]:
    prefix = f'{stock}-{date}'
    merged, _, legacy = _lane_docs(artifacts, prefix, 'review')
    report = merged if merged is not None else legacy
    if merged is not None:
        problems, _ = _check_merged(merged, 'review', now or time.time(),
                                    quiet_min, stale_min)
    else:
        problems = _check_report(report, 'review')
    if not report.exists():
        return problems
```

`build_parser` 中把 `--quiet-min` 默认值与帮助文本改为：

```python
    ap.add_argument('--quiet-min', type=float, default=0.5,
                    help='mtime 至少多少分钟不变才算收工（默认 0.5；合并格式下 end: 戳是主判据，'
                         'mtime 仅作保险）')
```

`main()` 中把 B / review 两支的调用改为传入 `now` 与两个阈值：

```python
        problems = check_phase_b(artifacts, args.stock, args.date, args.doc,
                                 now, args.quiet_min, args.stale_min)
    else:
        problems = check_review(artifacts, args.stock, args.date,
                                now, args.quiet_min, args.stale_min)
```

同时把模块 docstring 的用法段补一行：

```
新旧两种产物格式并存：优先找 <股票名>-<日期>-<lane>.md（evidence+report 合并，
明细层 + 结论层 + end: 戳），找不到才回退旧的 -evidence-<lane>-*.md 与 -phase<lane>-report.md。
```

- [ ] **Step 4: 跑测试确认全绿**

Run: `PYTHONIOENCODING=utf-8 rtk python -m pytest tests/test_deep_redo_gate.py -v`
Expected: PASS，全部用例（旧 17 个 + 新 7 个）通过。**若任一旧用例失败，说明破坏了向后兼容，必须修到全绿再往下走。**

- [ ] **Step 5: 提交**

```bash
rtk git add scripts/deep_redo_gate.py tests/test_deep_redo_gate.py && rtk git commit -m "feat(stock-research): 闸门支持 evidence/report 合并格式, 新旧并存

新格式 <股票名>-<日期>-<lane>.md 含明细层+结论层+end: 戳; 找不到则回退旧双文件,
故文档契约可独立切换、不必与本改动原子。

--quiet-min 默认 3.0 -> 0.5: 合并后 end: 戳写在文件最末, 其存在即全文写完,
mtime 只作保险。旧设计靠 mtime 静默 3min 猜收工, 实测单轮空等三次。
(光智轮教训「report 存在无判别力」的前提是两份文件, 合并后前提消失。)

无 end 戳且超 --stale-min 时明确报「大概率死在交付前」(L22)。"
```

---

### Task 5: 脚本改动合回 main，清理 worktree

**Files:**
- 无新增；把 Task 1–4 的 commit 合回 `main`

**Interfaces:**
- Consumes: Task 1–4 的全部 commit
- Produces: `main` 上可用的 `quote_guard.py`、6 份 agent 定义、7 份 lens 文件、支持双格式的闸门

- [ ] **Step 1: 在 worktree 跑全量测试**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ -q > /tmp/pytest_out.txt 2>&1; grep -E "passed|failed" /tmp/pytest_out.txt`

Expected: 无 failed。**注意**：crawl4ai 进度条走 stdout，`2>/dev/null` 挡不住，所以必须重定向到文件再 grep（见 `.claude/rules/dev-environment.md`）。

- [ ] **Step 2: 合回 main**

```bash
rtk git -C D:/Git/stock checkout main && rtk git -C D:/Git/stock merge --no-ff <worktree-branch> -m "merge: stock-research 优化 Task 1-4（quote_guard / agent 定义 / lens 拆分 / 闸门双格式）"
```

- [ ] **Step 3: 在 main 复跑测试并确认 commit 在链上**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_quote_guard.py tests/test_sr_agent_defs.py tests/test_lenses_split.py tests/test_deep_redo_gate.py -q
rtk git merge-base --is-ancestor <Task4 的 SHA> HEAD && echo "✓ 在链上"
```

**注意**：并行 session 的 commit 会在拓扑上交错插入，`git log -3` 短列表可能看不到刚落的 commit，那不代表脱链——用 `merge-base --is-ancestor` 判断（`.claude/rules/dev-environment.md`）。

- [ ] **Step 4: 清理 worktree**

```bash
rtk git -C D:/Git/stock worktree remove <worktree-path>
```

---

### Task 6: 文档契约切换（在 main 进行）

**Files:**
- Modify: `.claude/skills/stock-research/references/dispatch.md`（§0.1 汇报协议、§0.2 内联铁律、§1–§4 各节精简）
- Modify: `.claude/skills/stock-research/SKILL.md`（references 索引表）
- Modify: `.claude/skills/stock-research/references/mode-deep.md`（配套文件说明、先做步骤 5、Phase A/B/review 闸门句、收尾耗时账）
- Modify: `.claude/skills/stock-research/references/mode-earnings.md`（A1′ 产出路径）
- Modify: `.claude/skills/stock-research/references/mode-news.md`、`mode-meeting.md`（如含 evidence/report 双文件表述）

**Interfaces:**
- Consumes: Task 2 的六个 agent 名、Task 3 的 lens 文件路径与映射表、Task 4 的新格式文件名约定
- Produces: 控制者派发时使用的新契约（agent 名 + 变量清单 + 合并产出路径）

- [ ] **Step 1: 改 `dispatch.md` §0.1 汇报协议**

把「evidence 落 `...-evidence-A{1,2,3}-<后缀>.md`，汇报写到 `...-phase{lane}-report.md`」整体替换为：

```markdown
### 0.1 产出文件协议（所有 subagent，硬约定）

每路只写**一份**文件：`.omc/artifacts/<股票名>-<日期>-<lane>.md`
（lane ∈ `A1` / `A2` / `A3` / `B` / `review` / `C`；追派复核写 `review-2`、Phase B 返修写 `B-2`）。

文件结构固定四段，**结论层必须最后写**——它的存在即「全文写完」的信号，闸门据此放行：

```
start: YYYY-MM-DD HH:MM:SS      ← 开工时跑 date "+%Y-%m-%d %H:%M:%S"

## 明细层                        ← 采证/撰写过程中边做边追加
...

## 结论层                        ← 全部完成后最后写
...

end: YYYY-MM-DD HH:MM:SS        ← 收工时再跑一次 date
```

控制者 `tail -80` 取结论层，需要下钻时再 `grep`/`sed` 读明细层。
消息回传是可选冗余通道，不是交付方式。

> **为什么合并**：实测 report 与 evidence 的行级重叠率 72.7%–83.0%、数字覆盖率
> 89.2%–97.7%——report 基本是 evidence 的摘要重述，单轮三份 report 约 30K 字里
> 八成是重复生成的内容。
```

- [ ] **Step 2: 改 `dispatch.md` §0.2 内联铁律为混合口径**

把「下列内容**必须摘原文内联**，不许写"去读 sector-lenses.md / 参考兄弟档 xxx.md"」那张表改为：

```markdown
| 内容 | 谁负责 | 方式 |
|---|---|---|
| 命中 lens 的四节全文 | **subagent 自读** | `references/lenses/` 已按精确粒度拆分（每份约 70 行），自读不会挑错节。映射表写在 `sr-a3-lens` / `sr-writer` 定义里 |
| 兄弟档口径要点（3-5 行） | **控制者摘原文内联** | 每轮不同的股票、不同的兄弟档，无法预先拆分 |
| 控制者裁定 | **控制者摘原文内联** | 同上 |
| 控制者前置观察 | **控制者内联**，写成「我的推断是 X，请核实 X 是否成立」[L5] | 可自验的事实（行情等）**须在派发前自验**，不靠格式兜底 [L24] |
```

并把原理由段改写为：

```markdown
静态、可预先拆分的参考内容改为 subagent 自读（`lenses/`）；动态、每轮不同的内容仍由控制者摘写内联。
2026-08-08 提速计划的原始理由是「自读整份参考文件会挑错节——sector-lenses 261 行只命中约 70 行」，
该理由建立在**文件是大杂烩**的前提上；拆分后文件本身即精确粒度，前提消失。兄弟档（791 行只有 3-5 条有用）
无法预拆，故仍内联。
```

- [ ] **Step 3: 改 `dispatch.md` §1–§4 为「变量清单」**

每节删掉已迁入 agent 定义的固定内容（角色定义、证据分级、取数脚本、汇报协议），只保留控制者每轮必须填的变量与派发坑。例如 §1 A1 节改为：

```markdown
**A1 数据锚** → `subagent_type: sr-a1-anchor`

每轮必给的变量：标的 + 代码 + 市场 + 今天日期 + 旧档关键假设清单 + §11 触发器 + 本轮特有必查项
（财报/事件材料、控制者前置观察）。**固定协议已在 agent 定义里，不要重复写进 prompt。**

派发坑：控制者的前置观察若含行情数字，**派发前必须自己跑一遍 `quote_guard`**——
L24 的三路污染就是因为把竞价参考价当成了实际涨幅写进三份 prompt。
```

同法改写另外三节，各自保留的变量与派发坑如下：

```markdown
**Phase B 撰写** → `subagent_type: sr-writer`

每轮必给的变量：三份 A 路产出文件路径 + 旧档路径 + 新档目标文件夹
`sectors/<sector>/<subsector>/<股票名>/` + 兄弟档口径要点 3-5 行 + 控制者裁定
+ A+H 口径选定结果。**七文件结构与撰写纪律已在 agent 定义里。**

派发坑：写 300+ 行可能报 `Stream idle timeout`、文件 0 落盘。先 `ls <文件夹>` 确认
哪些未生成，再用 `SendMessage` 按原 agentId 续跑（"只 Write 缺的文件、勿再读文件/
联网、勿分段"），**别重派**。
```

```markdown
**合并审查** → `subagent_type: sr-reviewer`

每轮必给的变量：新档文件夹路径 + 三份 A 路产出文件路径 + 控制者裁定文件路径
+ **本轮命中的 lens 文件名**（审查员据此自读同一批 `lenses/*.md`——自读而非内联
才能保证它拿到与写手**逐字相同**的清单，这正是审"是否逐条回应"的前提）。

派发坑：审查是"只回 idle 不给正文"的重灾区，两段正文必须完整写进产出文件。
`CHANGES-REQUESTED` 或规格段 Critical → 追派复核（写 `review-2`）。
```

```markdown
**Phase C 收尾** → `subagent_type: sr-finalize`

每轮必给的变量：新档文件夹路径 + 待删旧档清单（控制者已 Read 确认 stock_code 一致）
+ `stock_code` + 需补反向条目的被链档路径与控制者备好的反向 YAML 条目
+ commit message 文件名 `.git/MSG-<股票名>-<日期>.txt`。
**动作清单已在 agent 定义里（原 finalize.md 全文）。**
```

- [ ] **Step 4: 改 `mode-deep.md` 四处**

1. 配套文件说明（第 10 行附近）：`sector-lenses.md` 一行改为
   `` - `references/lenses/` — 板块视角，已按精确粒度拆分；**由 sr-a3-lens / sr-writer 自读，控制者不再摘原文内联**。``
2. 先做步骤 5「选 lens」改为：
   `` 5. **确认 lens 命中**：按 subsector 对照 `references/lenses/` 映射表，把命中的板块专属 lens 文件名写进派发（横切 `x-*.md` 由 agent 默认全加载）。**不再摘原文内联。** ``
3. Phase A/B/review 三处闸门句：把 evidence/report 双文件表述改为「每路一份 `<股票名>-<日期>-<lane>.md`」。
4. **收尾耗时账**（2026-08-08 计划建立的可证伪依据）：把「读六份 report 文件的 `start`/`end` 头（`phaseA1`/`phaseA2`/...）」改为
   `` 读六份产出文件的 `start`/`end` 头（`A1`/`A2`/`A3`/`B`/`review`/`C`）``。
   **这一处最容易漏**——漏了耗时账就读不到文件，而它是「提速是否真的发生」的唯一可证伪依据。

- [ ] **Step 5: 改 `SKILL.md` references 索引表**

把 `| \`sector-lenses.md\` | 板块视角注册表，控制者摘原文内联 | 控制者 |` 改为
`| \`lenses/\` | 板块视角（7 份精确粒度） | sr-a3-lens / sr-writer **自读** |`

并把 `dispatch.md` 一行的描述改为 `每个 subagent 的**变量清单**（固定协议已在 .claude/agents/sr-*.md）`。

- [ ] **Step 6: 扫残留引用**

```bash
grep -rn "sector-lenses\|phaseA1-report\|phaseB-report\|review-report\|-evidence-A" .claude/skills/stock-research/ | grep -v lessons.md
```
Expected: 无输出。`lessons.md` 里的历史案例叙述保留（那是史料，不是活契约）。

- [ ] **Step 7: 提交**

```bash
rtk git add .claude/skills/stock-research/ && rtk git commit -m "refactor(stock-research): 契约切到 agent 定义 + 合并产出 + lens 自读

dispatch.md 从派发手册瘦成变量清单(固定协议已进 .claude/agents/sr-*.md);
内联铁律降级为混合口径(静态 lens 自读、动态兄弟档仍内联);
产出协议改为每路一份 <股票名>-<日期>-<lane>.md(明细层+结论层+end 戳)。

同步 2026-08-08 计划建立的耗时账读取逻辑到新文件名 —— 漏改会让耗时账读不到
文件, 而它是「提速是否真的发生」的唯一可证伪依据。"
```

---

### Task 7: 验收

**Files:** 无改动，只验证

- [ ] **Step 1: 全量测试**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ -q > /tmp/pytest_all.txt 2>&1; grep -E "passed|failed|error" /tmp/pytest_all.txt
```
Expected: 无 failed / error。

- [ ] **Step 2: 双 lint 未被波及**

```bash
PYTHONIOENCODING=utf-8 python scripts/lint_docs_frontmatter.py | tail -1
PYTHONIOENCODING=utf-8 python scripts/lint_docs_refs.py | tail -1
```
Expected: 两条均 OK。（本计划不碰 `docs/stock-analytics/`，若这里报错说明误伤，须回查。）

- [ ] **Step 3: 契约自洽检查清单**

逐项确认，任一不过就回到对应 Task：

- [ ] `ListAgents` 列出 6 个 `sr-*`
- [ ] `.claude/skills/stock-research/references/lenses/` 下 7 份，`sector-lenses.md` 已删
- [ ] `grep -rn "sector-lenses" .claude/skills/stock-research/ | grep -v lessons.md` 无输出
- [ ] `dispatch.md` 行数 < 60（原 116）
- [ ] `mode-deep.md` 收尾段的耗时账已指向新文件名 `A1`/`A2`/`A3`/`B`/`review`/`C`
- [ ] 闸门对旧格式仍放行（`pytest tests/test_deep_redo_gate.py -k "not merged"` 全绿）

- [ ] **Step 4: 验证 `effort` 档位真的生效（spec §7 待验假设 A2）**

`effort` 字段全局仅 7 处使用（对比 `model` 的 111 处），各档位的实际行为差异无实测数据。
最激进的一档是 `sr-finalize`（`sonnet` + `low`），下一轮投研的 Phase C 用它跑一次收尾，确认：

- [ ] 双 lint 仍双绿、valuations 仍正确同步、commit 只含本任务文件（即 `finalize.md` 的动作清单在 low effort 下仍被完整执行）
- [ ] 若 low 出现漏步（如漏跑 `--rewrite-blocks`、漏改反向链），**把 `sr-finalize.md` 的 effort 提到 `medium` 并在本计划追加一行记录**——这是本次唯一一处"猜"的参数，出问题就调，不要硬扛

- [ ] **Step 5: 端到端基线对比（下一轮真实投研时做，不阻塞本计划合并）**

下一次跑模式 1 时记录并与本轮基线对比：

| 指标 | 2026-08-25 建滔积层板基线 | 下一轮 |
|---|---|---|
| artifacts 总量 | 292KB | |
| 四份派发 prompt 合计 | 约 24KB | |
| 总墙钟 | 约 2h05（含约 40min 返工） | |
| 闸门空等次数 | 3 次 | |

**单样本噪声很大**（本轮就被写手配额中断干扰过），只用于校准预期，不作为回退依据。

- [ ] **Step 6: 追加教训（若实施中有新发现）**

按 `mode-deep.md` 维护规则：只在 `references/lessons.md` 追加 `L27+`（编号不复用、不重排），并在对应闸门处加 `[Ln]` 引用。

