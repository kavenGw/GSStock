# stock-deep-redo + 估值机制 token/维护优化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 stock-deep-redo 的估值数据从正文散文改为 frontmatter 结构化承载（doc→yaml 同步去 LLM 化），并把两段审查合并降级 sonnet，回写 skill 文档。

**Architecture:** 三个相互独立的改动。(1) `_docs_schema.py` 新增可选 `valuation` 块校验；(2) 新建 `scripts/sync_valuations.py` 确定性脚本，扫 buffett 档 frontmatter 的 `valuation` 块、flatten 后 upsert `valuations.yaml`；(3) 改 `SKILL.md` / `playbook.md` 反映新审查流程与脚本同步。前两项有单测（TDD），第三项是文档编辑，以 lint 全绿 + 内部一致性为验收。

**Tech Stack:** Python 3 / PyYAML / pytest。Windows 环境（git bash + PowerShell），git 命令前缀 `rtk`。

## Global Constraints

- 响应中文；不写多余注释；不写 backup 文件。
- 所有 git/pytest 命令前加 `rtk`，链式 `&&` 中也要；env 赋值在 `rtk` 之前。
- 单测放 `tests/test_*.py` 平铺，不用子目录。
- 跑测试：`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ -v`。
- 写含中文的文件显式 `encoding='utf-8'`（`PYTHONIOENCODING` 只管 stdout/stderr）。
- frontmatter `stock_code` 必须字符串引号（防 YAML int 化丢前导 0）。
- `valuations.yaml` 条目字段为**扁平**结构（`bear`/`base`/`bull`/`dividend_yield` 在顶层），不是嵌套——frontmatter 的嵌套 `valuation:` 块由 sync 脚本 flatten 写入。
- `valuations.yaml` 现有 157 条含非 buffett 来源条目；sync 脚本**只 upsert 不删除**未匹配条目。
- `git add` 与 `git commit` 放进同一条 Bash 命令链，用精确路径，不 `git add -A`。

---

## 文件结构

| 文件 | 职责 | 动作 |
|------|------|------|
| `scripts/_docs_schema.py` | 共享 frontmatter schema 校验 | 修改：加 `VALUATION_CURRENCIES` 常量 + `valuation` 块可选校验 |
| `tests/test_docs_schema.py` | schema 单测 | 修改：加 `valuation` 校验用例 |
| `scripts/sync_valuations.py` | 扫 buffett 档 → upsert valuations.yaml | 新建 |
| `tests/test_sync_valuations.py` | sync 脚本单测 | 新建 |
| `.claude/skills/stock-deep-redo/SKILL.md` | 总编排 | 修改：审查节 + Phase C 同步节 |
| `.claude/skills/stock-deep-redo/references/playbook.md` | 撰写/审查参考 | 修改：§1 frontmatter 模板 + §8 重写 + §9 派发骨架 |

---

## Task 1: `_docs_schema.py` 新增可选 `valuation` 块校验

**Files:**
- Modify: `scripts/_docs_schema.py`（加常量 + `validate_frontmatter` 内校验逻辑）
- Test: `tests/test_docs_schema.py`

**Interfaces:**
- Consumes: 现有 `validate_frontmatter(fm: dict, path: Path) -> list[str]`。
- Produces: `VALUATION_CURRENCIES: set[str] = {'CNY', 'USD', 'HKD'}`；`validate_frontmatter` 对含 `valuation` 的 frontmatter 追加校验——`valuation` 须为 mapping；`bear`/`base`/`bull`/`dividend_yield` 须为数字或 `None`；`currency`（若有）须 ∈ `VALUATION_CURRENCIES`。缺 `valuation` 不报错。

- [ ] **Step 1: 写失败测试**

在 `tests/test_docs_schema.py` 末尾追加：

```python
def _buffett_fm(**extra):
    fm = {
        'doc_type': 'buffett', 'stock_code': '603986', 'stock_name': '兆易创新',
        'sector': 'semiconductor', 'subsector': 'storage', 'themes': ['memory'],
        'rating': 'core', 'conviction_date': '2026-05-31', 'thesis': 't',
    }
    fm.update(extra)
    return fm


def test_valuation_absent_ok():
    violations = validate_frontmatter(_buffett_fm(), Path('/dummy.md'))
    assert not any('valuation' in v for v in violations)


def test_valuation_valid_ok():
    fm = _buffett_fm(valuation={
        'bear': 100.0, 'base': 120.0, 'bull': 150.0,
        'currency': 'CNY', 'dividend_yield': 1.2,
    })
    violations = validate_frontmatter(fm, Path('/dummy.md'))
    assert not any('valuation' in v for v in violations)


def test_valuation_null_values_ok():
    fm = _buffett_fm(valuation={'bear': None, 'base': None, 'bull': None, 'currency': 'HKD'})
    violations = validate_frontmatter(fm, Path('/dummy.md'))
    assert not any('valuation' in v for v in violations)


def test_valuation_not_mapping():
    fm = _buffett_fm(valuation=[1, 2, 3])
    violations = validate_frontmatter(fm, Path('/dummy.md'))
    assert any('valuation must be a mapping' in v for v in violations)


def test_valuation_bad_number_type():
    fm = _buffett_fm(valuation={'bear': '便宜', 'base': 1.0, 'bull': 2.0, 'currency': 'CNY'})
    violations = validate_frontmatter(fm, Path('/dummy.md'))
    assert any('valuation.bear must be number or null' in v for v in violations)


def test_valuation_bad_currency():
    fm = _buffett_fm(valuation={'bear': 1.0, 'base': 2.0, 'bull': 3.0, 'currency': 'JPY'})
    violations = validate_frontmatter(fm, Path('/dummy.md'))
    assert any("valuation.currency 'JPY'" in v for v in violations)
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_docs_schema.py -v -k valuation`
Expected: FAIL — `test_valuation_not_mapping` / `test_valuation_bad_number_type` / `test_valuation_bad_currency` 断言失败（校验逻辑尚未存在，无 valuation 违例产出）。

- [ ] **Step 3: 加常量**

`scripts/_docs_schema.py` 中 `RATINGS` 定义下方追加：

```python
VALUATION_CURRENCIES: set[str] = {'CNY', 'USD', 'HKD'}
```

- [ ] **Step 4: 加校验逻辑**

`scripts/_docs_schema.py` 的 `validate_frontmatter` 函数内，`return violations` 之前插入：

```python
    if 'valuation' in fm:
        val = fm['valuation']
        if not isinstance(val, dict):
            violations.append(f"{p}: valuation must be a mapping (got {type(val).__name__})")
        else:
            for k in ('bear', 'base', 'bull', 'dividend_yield'):
                if k in val and val[k] is not None and not isinstance(val[k], (int, float)):
                    violations.append(
                        f"{p}: valuation.{k} must be number or null (got {type(val[k]).__name__})")
            cur = val.get('currency')
            if cur is not None and cur not in VALUATION_CURRENCIES:
                violations.append(
                    f"{p}: valuation.currency '{cur}' not in {sorted(VALUATION_CURRENCIES)}")
```

- [ ] **Step 5: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_docs_schema.py -v`
Expected: PASS（含原有用例 + 6 个新 valuation 用例）。

- [ ] **Step 6: 跑存量 frontmatter lint 确认不回归**

Run: `PYTHONIOENCODING=utf-8 rtk python scripts/lint_docs_frontmatter.py`
Expected: exit 0（存量 160 档均无 `valuation` 块，新校验不影响）。

- [ ] **Step 7: 提交**

```bash
rtk git add scripts/_docs_schema.py tests/test_docs_schema.py && rtk git commit -m "feat(docs-schema): frontmatter 加可选 valuation 块校验"
```

---

## Task 2: 新建 `scripts/sync_valuations.py` 同步脚本

**Files:**
- Create: `scripts/sync_valuations.py`
- Test: `tests/test_sync_valuations.py`

**Interfaces:**
- Consumes: `scripts._docs_schema.parse_frontmatter(path) -> (dict, str)`、`_as_str_date(v) -> str`。
- Produces:
  - `infer_market(stock_code: str) -> str`（'A'/'HK'/'US'）
  - `default_currency(market: str) -> str`
  - `build_entry(fm: dict, source_doc: str) -> dict`（扁平条目，键序：stock_code, stock_name, market, currency, sector, rating, [watch_reason], bear, base, bull, [dividend_yield], conviction_date, source_doc）
  - `upsert(entries: list[dict], new_entry: dict) -> list[dict]`（按 stock_code 原地替换或追加）
  - `sync(docs_root: Path, yaml_path: Path, only_code: str | None = None) -> int`（扫 `*buffett*.md`、跳过无 `valuation` 块的、upsert 写回，返回 upsert 条数）
  - CLI：`python scripts/sync_valuations.py [--stock-code CODE]`

- [ ] **Step 1: 写失败测试**

新建 `tests/test_sync_valuations.py`：

```python
from pathlib import Path
import sys

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.sync_valuations import (
    infer_market, default_currency, build_entry, upsert, sync,
)


def test_infer_market():
    assert infer_market('603986') == 'A'
    assert infer_market('000021') == 'A'
    assert infer_market('00992.HK') == 'HK'
    assert infer_market('03888') == 'HK'
    assert infer_market('AAPL') == 'US'


def test_default_currency():
    assert default_currency('A') == 'CNY'
    assert default_currency('HK') == 'HKD'
    assert default_currency('US') == 'USD'


def test_build_entry_flattens_valuation():
    fm = {
        'stock_code': '603986', 'stock_name': '兆易创新',
        'sector': 'semiconductor', 'rating': 'watch', 'watch_reason': 'x',
        'conviction_date': '2026-05-31',
        'valuation': {'bear': 100.0, 'base': 120.0, 'bull': 150.0,
                      'currency': 'CNY', 'dividend_yield': 1.2},
    }
    e = build_entry(fm, 'sectors/semiconductor/storage/foo.md')
    assert e['stock_code'] == '603986'
    assert e['market'] == 'A'
    assert e['currency'] == 'CNY'
    assert (e['bear'], e['base'], e['bull']) == (100.0, 120.0, 150.0)
    assert e['dividend_yield'] == 1.2
    assert e['watch_reason'] == 'x'
    assert e['conviction_date'] == '2026-05-31'
    assert e['source_doc'] == 'sectors/semiconductor/storage/foo.md'
    keys = list(e.keys())
    assert keys.index('stock_code') == 0
    assert keys.index('bear') < keys.index('conviction_date')


def test_build_entry_null_and_no_dividend():
    fm = {
        'stock_code': '00992.HK', 'stock_name': '联想集团',
        'sector': 'electronics', 'rating': 'config',
        'conviction_date': '2026-06-08',
        'valuation': {'bear': None, 'base': None, 'bull': None, 'currency': 'HKD'},
    }
    e = build_entry(fm, 'foo.md')
    assert e['bear'] is None
    assert 'dividend_yield' not in e
    assert 'watch_reason' not in e
    assert e['currency'] == 'HKD'


def test_build_entry_infers_currency_when_absent():
    fm = {
        'stock_code': '603986', 'stock_name': 'X', 'sector': 'semiconductor',
        'rating': 'core', 'conviction_date': '2026-05-31',
        'valuation': {'bear': 1.0, 'base': 2.0, 'bull': 3.0},
    }
    e = build_entry(fm, 'foo.md')
    assert e['currency'] == 'CNY'


def test_upsert_updates_existing_in_place():
    entries = [{'stock_code': '603986', 'base': 1}, {'stock_code': '000001', 'base': 2}]
    upsert(entries, {'stock_code': '603986', 'base': 99})
    assert entries[0]['base'] == 99
    assert len(entries) == 2


def test_upsert_appends_new():
    entries = [{'stock_code': '603986'}]
    upsert(entries, {'stock_code': '000001'})
    assert len(entries) == 2 and entries[1]['stock_code'] == '000001'


def _write_doc(d: Path, name: str, code: str, base: float):
    d.mkdir(parents=True, exist_ok=True)
    (d / name).write_text(
        '---\n'
        'doc_type: buffett\n'
        f"stock_code: '{code}'\n"
        'stock_name: 兆易创新\n'
        'sector: semiconductor\n'
        'subsector: storage\n'
        'themes: [memory]\n'
        'rating: watch\n'
        'watch_reason: x\n'
        'conviction_date: 2026-05-31\n'
        'thesis: t\n'
        'valuation:\n'
        '  bear: 100.0\n'
        f'  base: {base}\n'
        '  bull: 150.0\n'
        '  currency: CNY\n'
        '  dividend_yield: 1.2\n'
        '---\n# 正文\n', encoding='utf-8')


def test_sync_end_to_end_creates_yaml(tmp_path):
    docs_root = tmp_path / 'docs'
    _write_doc(docs_root / 'sectors/semiconductor/storage',
               '2026-05-31-兆易创新-buffett分析.md', '603986', 120.0)
    yaml_path = tmp_path / 'valuations.yaml'
    n = sync(docs_root, yaml_path)
    assert n == 1
    data = yaml.safe_load(yaml_path.read_text(encoding='utf-8'))
    assert data[0]['stock_code'] == '603986'
    assert data[0]['base'] == 120.0
    assert data[0]['source_doc'] == 'sectors/semiconductor/storage/2026-05-31-兆易创新-buffett分析.md'


def test_sync_skips_docs_without_valuation(tmp_path):
    docs_root = tmp_path / 'docs'
    d = docs_root / 'sectors/semiconductor/storage'
    d.mkdir(parents=True)
    (d / '2026-01-01-无估值-buffett分析.md').write_text(
        "---\ndoc_type: buffett\nstock_code: '000001'\nstock_name: X\n"
        "sector: semiconductor\nsubsector: s\nthemes: [t]\nrating: core\n"
        "conviction_date: 2026-01-01\nthesis: t\n---\n# 正文\n", encoding='utf-8')
    yaml_path = tmp_path / 'valuations.yaml'
    n = sync(docs_root, yaml_path)
    assert n == 0
    assert not yaml_path.exists() or yaml.safe_load(yaml_path.read_text(encoding='utf-8')) in (None, [])


def test_sync_upserts_into_existing_yaml(tmp_path):
    docs_root = tmp_path / 'docs'
    _write_doc(docs_root / 'sectors/semiconductor/storage',
               '2026-05-31-兆易创新-buffett分析.md', '603986', 120.0)
    yaml_path = tmp_path / 'valuations.yaml'
    yaml_path.write_text(
        yaml.dump([
            {'stock_code': '000878', 'stock_name': '云南铜业', 'base': 7.78},
            {'stock_code': '603986', 'stock_name': '旧', 'base': 1.0},
        ], allow_unicode=True, sort_keys=False), encoding='utf-8')
    n = sync(docs_root, yaml_path)
    assert n == 1
    data = yaml.safe_load(yaml_path.read_text(encoding='utf-8'))
    assert len(data) == 2  # 未新增，原 603986 被更新
    by_code = {r['stock_code']: r for r in data}
    assert by_code['603986']['base'] == 120.0   # 已更新
    assert by_code['000878']['base'] == 7.78     # 未匹配条目保留


def test_sync_only_stock_code_filter(tmp_path):
    docs_root = tmp_path / 'docs'
    base_dir = docs_root / 'sectors/semiconductor/storage'
    _write_doc(base_dir, '2026-05-31-兆易创新-buffett分析.md', '603986', 120.0)
    _write_doc(base_dir, '2026-05-31-其它-buffett分析.md', '000001', 50.0)
    yaml_path = tmp_path / 'valuations.yaml'
    n = sync(docs_root, yaml_path, only_code='603986')
    assert n == 1
    data = yaml.safe_load(yaml_path.read_text(encoding='utf-8'))
    assert [r['stock_code'] for r in data] == ['603986']
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_sync_valuations.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.sync_valuations'`。

- [ ] **Step 3: 写实现**

新建 `scripts/sync_valuations.py`：

```python
"""扫 docs/stock-analytics/**/*buffett*.md 的 frontmatter valuation 块，
flatten 后 upsert 到 docs/stock-analytics/valuations.yaml。

用法：
    python scripts/sync_valuations.py                 # 全量扫描 upsert
    python scripts/sync_valuations.py --stock-code 603986   # 只同步单只
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from typing import Optional

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts._docs_schema import parse_frontmatter, _as_str_date

DOCS_ROOT = Path(__file__).resolve().parent.parent / 'docs' / 'stock-analytics'
YAML_PATH = DOCS_ROOT / 'valuations.yaml'

_CURRENCY_BY_MARKET = {'A': 'CNY', 'HK': 'HKD', 'US': 'USD'}


def infer_market(stock_code: str) -> str:
    """6 位纯数字→A；含 .HK 或 4-5 位纯数字→HK；字母开头→US。"""
    code = stock_code.upper()
    if '.HK' in code:
        return 'HK'
    if code.isdigit():
        return 'A' if len(code) == 6 else 'HK'
    return 'US'


def default_currency(market: str) -> str:
    return _CURRENCY_BY_MARKET.get(market, 'CNY')


def build_entry(fm: dict, source_doc: str) -> dict:
    """从 buffett frontmatter + valuation 块组装扁平 valuations.yaml 条目。"""
    val = fm.get('valuation') or {}
    market = infer_market(str(fm['stock_code']))
    currency = val.get('currency') or default_currency(market)
    entry: dict = {
        'stock_code': str(fm['stock_code']),
        'stock_name': fm.get('stock_name'),
        'market': market,
        'currency': currency,
        'sector': fm.get('sector'),
        'rating': fm.get('rating'),
    }
    if fm.get('watch_reason'):
        entry['watch_reason'] = fm['watch_reason']
    entry['bear'] = val.get('bear')
    entry['base'] = val.get('base')
    entry['bull'] = val.get('bull')
    if val.get('dividend_yield') is not None:
        entry['dividend_yield'] = val['dividend_yield']
    entry['conviction_date'] = _as_str_date(fm.get('conviction_date'))
    entry['source_doc'] = source_doc
    return entry


def upsert(entries: list[dict], new_entry: dict) -> list[dict]:
    """按 stock_code 原地替换已有条目，不存在则追加。"""
    for i, e in enumerate(entries):
        if e.get('stock_code') == new_entry['stock_code']:
            entries[i] = new_entry
            return entries
    entries.append(new_entry)
    return entries


def _load_entries(yaml_path: Path) -> list[dict]:
    if not yaml_path.exists():
        return []
    data = yaml.safe_load(yaml_path.read_text(encoding='utf-8'))
    return data if isinstance(data, list) else []


def sync(docs_root: Path, yaml_path: Path, only_code: Optional[str] = None) -> int:
    """扫 buffett 档，把含 valuation 块的（可选按 only_code 过滤）upsert 进 yaml，返回 upsert 条数。"""
    entries = _load_entries(yaml_path)
    count = 0
    for md in sorted(docs_root.rglob('*buffett*.md')):
        fm, _ = parse_frontmatter(md)
        if not fm or fm.get('doc_type') != 'buffett' or 'valuation' not in fm:
            continue
        if only_code is not None and str(fm.get('stock_code')) != str(only_code):
            continue
        source_doc = md.relative_to(docs_root).as_posix()
        upsert(entries, build_entry(fm, source_doc))
        count += 1
    if count:
        yaml_path.write_text(
            yaml.dump(entries, allow_unicode=True, sort_keys=False, width=4096),
            encoding='utf-8')
    return count


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--stock-code', default=None, help='只同步该代码（默认全量扫描）')
    ap.add_argument('--docs-root', default=str(DOCS_ROOT))
    ap.add_argument('--yaml-path', default=str(YAML_PATH))
    args = ap.parse_args()
    n = sync(Path(args.docs_root), Path(args.yaml_path), only_code=args.stock_code)
    print(f"synced {n} entr{'y' if n == 1 else 'ies'} into {args.yaml_path}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_sync_valuations.py -v`
Expected: PASS（全部用例）。

- [ ] **Step 5: 对真实 docs 干跑验证无副作用**

Run: `PYTHONIOENCODING=utf-8 rtk python scripts/sync_valuations.py`
Expected: 打印 `synced 0 entries ...`（存量 buffett 档尚无 `valuation` 块，不改动 valuations.yaml）。
随后 `rtk git status` 确认 `valuations.yaml` 无改动。

- [ ] **Step 6: 提交**

```bash
rtk git add scripts/sync_valuations.py tests/test_sync_valuations.py && rtk git commit -m "feat(valuations): 新增 sync_valuations.py 从 frontmatter 确定性同步"
```

---

## Task 3: 回写 SKILL.md / playbook.md

**Files:**
- Modify: `.claude/skills/stock-deep-redo/SKILL.md`
- Modify: `.claude/skills/stock-deep-redo/references/playbook.md`

**Interfaces:**
- Consumes: Task 1 的 `valuation` frontmatter 块、Task 2 的 `scripts/sync_valuations.py --stock-code <code>`。
- Produces: 文档描述与新流程一致（审查合并降级 sonnet + opus 异常升级；Phase C 用脚本同步；frontmatter 模板含 valuation 块）。无新代码接口。

- [ ] **Step 1: SKILL.md — 改两段式审查节**

把 `SKILL.md` 中 `### 两段式审查（每段派 1 个 read-only subagent，opus）` 整节（含其下两点编号列表与"有 Critical/Important 问题…"段）替换为：

```markdown
### 合并审查（派 1 个 read-only subagent，sonnet；异常升 opus）
一个 sonnet 只读 subagent，单 prompt 内**先规格、后质量**两段顺序输出（顺序不可反）：
1. **规格符合性**：13 节齐全？frontmatter 合规（含 `valuation` 块与正文 §0/§9/§3 数字一致）？三情景概率 Σ=100%
   且期望值算术对？AI 维度都打了标？供给侧双面写了吗？数字可追溯无造数？无范围外夹带？命中 lens 的必查项是否
   在正文均有回应（查无证据也写明）？**命中成长 lens 时**：扩产达产 / 客户增长预期（分层兑证）/ 跑道长度是否
   均有回应？bull 是否被增长证据包门控？→ 输出 SPEC-COMPLIANT 或问题清单。
2. **分析质量**：内在一致性、概率可辩护性、供给侧双面是否走过场、"贵"是否被诚实消化、AI 是否蹭概念拔高、
   增长是否被诚实证据化、bull 赋权是否与增长证据强度匹配、slop 检查、buffett 框架贴合度、监控指标是否带阈值可执行。
   → APPROVED / APPROVED-WITH-NITS / CHANGES-REQUESTED。

**纪律保持**：审查员是独立 subagent（非撰写者自审），撰写≠审查上下文铁律不变。
**异常升级**：sonnet 给出 `CHANGES-REQUESTED`，或规格段发现 Critical 问题 → 控制者**追派 1 个 opus 只读审查员
复核该结论**，再据复核让撰写 subagent 修；同一审查上下文复审直到过。Minor nits 可修后控制者直接核验。
```

- [ ] **Step 2: SKILL.md — 改 Phase C 的 valuations 同步点**

把 `### Phase C — 收尾（派 1 个 subagent，sonnet 足够）` 节内 `- **同步 valuations.yaml**：从新档 §0/§9 提取 bear/base/bull 每股内在价值 + §3/§11 提取 dividend_yield 分红率，upsert 到 `docs/stock-analytics/valuations.yaml`（按 `stock_code` 去重，更新已有条目或追加新条目）。\n  详见 `references/playbook.md` §8「valuations.yaml 同步」。` 这一条替换为：

```markdown
- **同步 valuations.yaml**：估值数字已由 Phase B 写进 buffett 档 frontmatter 的 `valuation` 块，
  此处只需运行 `PYTHONIOENCODING=utf-8 rtk python scripts/sync_valuations.py --stock-code <code>`
  确定性 upsert（无需 LLM 再从正文提取）。详见 `references/playbook.md` §8。
```

- [ ] **Step 3: SKILL.md — 改总编排标题行**

把 `## 总编排：3 阶段 subagent + 两段式审查` 改为 `## 总编排：3 阶段 subagent + 合并审查`。

- [ ] **Step 4: playbook.md — §1 frontmatter 模板加 valuation 块**

`playbook.md` §1 的 frontmatter 代码块中，`thesis: 一句话投资论点` 行下方、`related_docs:` 行上方插入：

```yaml
valuation:                   # 可选；Phase B 写入，Phase C 用 sync_valuations.py 同步到 valuations.yaml
  bear: 6.50                 # 每股内在价值（原币），无法估算填 null
  base: 7.78
  bull: 8.87
  currency: CNY              # CNY / USD / HKD，与每股估值币种一致
  dividend_yield: 2.8        # 分红率（%），无分红填 null
```

- [ ] **Step 5: playbook.md — 重写 §8**

把 `## 8. valuations.yaml 同步` 整节（从 `## 8.` 到 `## 9.` 之前的全部内容）替换为：

```markdown
## 8. valuations.yaml 同步

估值数字由 **Phase B 撰写时写进 buffett 档 frontmatter 的 `valuation` 块**（见 §1 模板），
Phase C 用确定性脚本 upsert 到 `docs/stock-analytics/valuations.yaml`，**不再用 LLM 从正文提取**。

### frontmatter valuation 块字段

| 字段 | 含义 | 缺省 |
|------|------|------|
| `bear`/`base`/`bull` | 三情景每股内在价值（原币） | 无法估值填 `null` |
| `currency` | `CNY`/`USD`/`HKD`，与每股估值币种一致 | 缺省时脚本按市场推断 |
| `dividend_yield` | 分红率（%） | 无分红填 `null` |

撰写纪律：
- 三档每股内在价值与正文 §0/§9 一致；分红率与 §3/§11 一致（规格审查核对镜像同步）。
- **消费/材料/能源/工业/金融**标的分红率是重要收益来源，Phase A 须联网查最新年度分红，Phase B 在 §3/§11 写出并填入 `valuation.dividend_yield`。
- **港股/美股**每股估值用对应币种（HKD/USD）；A+H 选定口径由 frontmatter `stock_code` 本身体现，`currency` 随之。

### 同步操作（Phase C）

```bash
PYTHONIOENCODING=utf-8 rtk python scripts/sync_valuations.py --stock-code <code>
```

脚本扫 `*buffett*.md` 的 frontmatter，flatten `valuation` 块为扁平条目（`market` 按 `stock_code` 推断），
按 `stock_code` upsert valuations.yaml（已存在→更新、不存在→追加），**不删除未匹配的存量条目**。
无参数则全量扫描 upsert。详见 `scripts/sync_valuations.py`。
```

- [ ] **Step 6: playbook.md — 改 §9 派发骨架的审查与 Phase C 两条**

`playbook.md` §9 中，把 `**规格审查**（read-only）` 与 `**质量审查**（read-only）` 两段合并替换为：

```markdown
**合并审查**（read-only，sonnet）：给交付物+spec/playbook+evidence 路径；要求单 prompt 内先规格后质量两段输出——
规格段给逐项核对清单（13 节/frontmatter 含 valuation 块与正文一致/Σ概率=100% 且期望值算术/AI 标签/供给侧双面/
数字可追溯/无范围外夹带）输出 SPEC-COMPLIANT 或问题清单；质量段给质量维度（内在一致/概率可辩护/双面性/"贵"诚实度/
AI 不拔高/增长证据化/slop/buffett 贴合/监控可执行）输出 APPROVED / APPROVED-WITH-NITS / CHANGES-REQUESTED + 2-3 条做得好的点。
控制者收到 CHANGES-REQUESTED 或 Critical 规格问题时追派 1 个 opus 只读审查员复核该结论再放行修复。
```

并把 `**Phase C 收尾**` 段内 `**同步 valuations.yaml**（见 §8）：从新档提取 bear/base/bull 每股内在价值 + dividend_yield 分红率，upsert 到 `docs/stock-analytics/valuations.yaml`；` 替换为：

```markdown
**同步 valuations.yaml**（见 §8）：运行 `sync_valuations.py --stock-code <code>` 确定性 upsert（估值数字已在 frontmatter `valuation` 块）；
```

- [ ] **Step 7: 跑双 lint 确认不回归**

Run: `PYTHONIOENCODING=utf-8 rtk python scripts/lint_docs_frontmatter.py && PYTHONIOENCODING=utf-8 rtk python scripts/lint_docs_refs.py`
Expected: 两支均 exit 0（本任务只改 skill 文档，不动 docs/stock-analytics）。

- [ ] **Step 8: 内部一致性核读**

Read `.claude/skills/stock-deep-redo/SKILL.md` 与 `references/playbook.md`，确认：
- "合并审查"在 SKILL（总编排 + 审查节）与 playbook §9 三处措辞一致；无残留"两段式审查/派 2 个 opus"旧描述。
- Phase C 的 valuations 同步在 SKILL 与 playbook §8/§9 三处均指向 `sync_valuations.py`，无残留"LLM 提取"旧描述。
- playbook §1 frontmatter 模板含 `valuation` 块。
Expected: 无矛盾、无残留旧描述。

- [ ] **Step 9: 提交**

```bash
rtk git add .claude/skills/stock-deep-redo/SKILL.md .claude/skills/stock-deep-redo/references/playbook.md && rtk git commit -m "docs(stock-deep-redo): 审查合并降级 sonnet + Phase C 脚本同步 valuations"
```

---

## Self-Review 记录

- **Spec 覆盖**：改动 1（结构化承载）→ Task 1（schema）+ Task 2（脚本）+ Task 3 Step 4（frontmatter 模板）；改动 2（审查合并降级）→ Task 3 Step 1/3/6；改动 3（文档同步）→ Task 3 全部。验收标准 1→Task 1 Step 5/6；2→Task 2 Step 4；3→Task 3 Step 8；4→Task 3 Step 7。无遗漏。
- **占位符**：无 TBD/TODO；所有代码步骤含完整代码。
- **类型一致**：`build_entry`/`upsert`/`sync`/`infer_market`/`default_currency` 在 Task 2 Interfaces、测试、实现三处签名一致；`valuation` 块字段（bear/base/bull/currency/dividend_yield）在 Task 1、Task 2、Task 3 frontmatter 模板三处一致。
```
