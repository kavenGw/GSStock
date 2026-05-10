# Portfolio Shortlist Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基于 `docs/analysis/` 文档证据 + 实时技术形态全局排序，把当前 23 行重点池压缩到 ≤ 10 只持仓，输出 HTML 报告 + patch JSON 由用户审完后落库。

**Architecture:** 模块化拆分到 `app/services/portfolio_shortlist/` 共 5 个职责单一文件（doc_cache / scoring / technical / theme_allocator / report_renderer），复用 `UnifiedStockDataService.get_trend_data` + `app/services/td_sequential.py` 已有实现；一次性入口脚本 `scripts/_portfolio_shortlist.py` 跑完即删，逻辑通过 spec + commit 留痕。

**Tech Stack:** Python 3.10 / pytest / SQLAlchemy / PyYAML / Jinja2-free 字符串拼装 HTML / pandas（OHLC 计算）

**Spec：** `docs/superpowers/specs/2026-05-10-portfolio-shortlist-design.md`

---

## File Structure

| 路径 | 角色 | 留库 |
|---|---|---|
| `app/services/portfolio_shortlist/__init__.py` | 模块入口，re-export | ✅ |
| `app/services/portfolio_shortlist/doc_cache.py` | MD5 缓存层 | ✅ |
| `app/services/portfolio_shortlist/scoring.py` | 6 维度打分 | ✅ |
| `app/services/portfolio_shortlist/technical.py` | 技术形态指标计算 | ✅ |
| `app/services/portfolio_shortlist/theme_allocator.py` | 入选后主题内权重分配 | ✅ |
| `app/services/portfolio_shortlist/report_renderer.py` | HTML + markdown 渲染 | ✅ |
| `tests/test_portfolio_shortlist_doc_cache.py` | 缓存层 unit test | ✅ |
| `tests/test_portfolio_shortlist_scoring.py` | 打分 unit test | ✅ |
| `tests/test_portfolio_shortlist_technical.py` | 技术形态 unit test | ✅ |
| `tests/test_portfolio_shortlist_allocator.py` | 权重分配 unit test | ✅ |
| `tests/test_portfolio_shortlist_renderer.py` | 渲染 smoke test | ✅ |
| `scripts/_portfolio_shortlist.py` | 一次性入口编排脚本 | ❌ 跑完删除 |
| `.claude/skills/portfolio-init/.cache/shortlist/<code>.json` | 缓存目录 | ❌ gitignore |
| `D:\Git\GSStockHold\portfolio-shortlist-2026-05-10.html` | 报告（用户审） | ❌ git 工程外 |
| `.omc/artifacts/portfolio-shortlist-patch-2026-05-10.json` | patch JSON | ❌ gitignore |

---

## Task 1: 模块骨架 + .gitignore + 缓存目录

**Files:**
- Create: `app/services/portfolio_shortlist/__init__.py`
- Modify: `.gitignore` (append cache dir)
- Create: `.claude/skills/portfolio-init/.cache/.gitkeep`

- [ ] **Step 1: 创建模块目录与 `__init__.py`**

```python
# app/services/portfolio_shortlist/__init__.py
"""Portfolio shortlist evaluation engine.

把候选股按 (rating + docs 证据 + 技术形态) 打分后取 Top N，
入选后按打分归一化分配主题内 StockWeight。

详见 docs/superpowers/specs/2026-05-10-portfolio-shortlist-design.md
"""

from app.services.portfolio_shortlist.doc_cache import DocCache
from app.services.portfolio_shortlist.scoring import score_stock, ScoreBreakdown
from app.services.portfolio_shortlist.technical import compute_technical
from app.services.portfolio_shortlist.theme_allocator import allocate_weights
from app.services.portfolio_shortlist.report_renderer import render_html, render_markdown

__all__ = [
    'DocCache',
    'score_stock',
    'ScoreBreakdown',
    'compute_technical',
    'allocate_weights',
    'render_html',
    'render_markdown',
]
```

- [ ] **Step 2: 在 `.gitignore` 末尾追加缓存目录**

打开 `.gitignore`，在末尾追加：

```
# portfolio-shortlist 缓存（按股票 md5 命中跳过 docs 重读）
.claude/skills/portfolio-init/.cache/
```

- [ ] **Step 3: 占位 `.gitkeep`**

```bash
mkdir -p .claude/skills/portfolio-init/.cache/shortlist
echo "# 缓存目录占位（实际内容已 gitignore）" > .claude/skills/portfolio-init/.cache/.gitkeep
```

注意：`.gitkeep` 在被 ignore 的目录里要 `git add -f` 才能进库，但本任务不强制——如果加入失败就跳过，目录会由脚本运行时自动创建。

- [ ] **Step 4: 验证模块可 import（不依赖未实现子模块）**

由于 `__init__.py` re-export 了未实现的子模块，先把 import 改为延迟懒加载：

```python
# app/services/portfolio_shortlist/__init__.py（重写）
"""Portfolio shortlist evaluation engine.

详见 docs/superpowers/specs/2026-05-10-portfolio-shortlist-design.md
"""
# 子模块由调用方按需 import：
#   from app.services.portfolio_shortlist.doc_cache import DocCache
#   from app.services.portfolio_shortlist.scoring import score_stock
#   ...
```

- [ ] **Step 5: 跑一次 import 验证**

```bash
PYTHONIOENCODING=utf-8 python -c "import app.services.portfolio_shortlist; print('OK')"
```

期望输出：`OK`

- [ ] **Step 6: Commit**

```bash
rtk git add app/services/portfolio_shortlist/__init__.py .gitignore
rtk git commit -m "feat(shortlist): 创建 portfolio_shortlist 模块骨架 + 缓存目录 gitignore"
```

---

## Task 2: DocCache（MD5 缓存层）

**Files:**
- Create: `app/services/portfolio_shortlist/doc_cache.py`
- Test: `tests/test_portfolio_shortlist_doc_cache.py`

接口契约：
- `DocCache(cache_dir: Path).get_or_compute(stock_code, stock_name, doc_paths, extractor)` → `dict`
  - 输入 doc_paths：`list[Path]`
  - 缓存命中条件：所有 doc 的 md5 与缓存一致 且 doc 数量一致
  - 命中 → 返回 cache['summary']
  - 未命中 → 调 `extractor(stock_code, doc_paths) -> dict`，写缓存后返回
- 缓存文件 `<cache_dir>/<stock_code>.json`，schema 见 spec §2

- [ ] **Step 1: 写失败测试**

```python
# tests/test_portfolio_shortlist_doc_cache.py
import json
import pytest
from pathlib import Path

from app.services.portfolio_shortlist.doc_cache import DocCache


@pytest.fixture
def cache_dir(tmp_path):
    return tmp_path / 'shortlist'


@pytest.fixture
def doc_a(tmp_path):
    p = tmp_path / 'doc_a.md'
    p.write_text('content A v1', encoding='utf-8')
    return p


@pytest.fixture
def doc_b(tmp_path):
    p = tmp_path / 'doc_b.md'
    p.write_text('content B', encoding='utf-8')
    return p


def test_first_call_invokes_extractor_and_writes_cache(cache_dir, doc_a):
    cache = DocCache(cache_dir)
    calls = []

    def extractor(code, paths):
        calls.append(code)
        return {'logic': 'L', 'valuation': 'V', 'catalyst': 'C',
                'theme_fit': 'T', 'realized_or_invalidated': 'R'}

    summary = cache.get_or_compute('600000', '某股', [doc_a], extractor)

    assert calls == ['600000']
    assert summary['logic'] == 'L'
    cache_file = cache_dir / '600000.json'
    assert cache_file.exists()
    data = json.loads(cache_file.read_text(encoding='utf-8'))
    assert data['stock_code'] == '600000'
    assert len(data['docs']) == 1
    assert data['docs'][0]['md5']  # md5 字段非空


def test_unchanged_md5_skips_extractor(cache_dir, doc_a):
    cache = DocCache(cache_dir)
    calls = []

    def extractor(code, paths):
        calls.append(code)
        return {'logic': 'first', 'valuation': '', 'catalyst': '',
                'theme_fit': '', 'realized_or_invalidated': ''}

    cache.get_or_compute('600000', '某股', [doc_a], extractor)
    cache.get_or_compute('600000', '某股', [doc_a], extractor)  # 第二次

    assert calls == ['600000'], '第二次应命中缓存，不调 extractor'


def test_md5_change_triggers_recompute(cache_dir, doc_a):
    cache = DocCache(cache_dir)
    calls = []

    def extractor(code, paths):
        calls.append(code)
        return {'logic': 'x', 'valuation': '', 'catalyst': '',
                'theme_fit': '', 'realized_or_invalidated': ''}

    cache.get_or_compute('600000', '某股', [doc_a], extractor)
    doc_a.write_text('content A v2 CHANGED', encoding='utf-8')
    cache.get_or_compute('600000', '某股', [doc_a], extractor)

    assert calls == ['600000', '600000'], 'doc 内容变化应重算'


def test_new_doc_added_triggers_recompute(cache_dir, doc_a, doc_b):
    cache = DocCache(cache_dir)
    calls = []

    def extractor(code, paths):
        calls.append(code)
        return {'logic': 'x', 'valuation': '', 'catalyst': '',
                'theme_fit': '', 'realized_or_invalidated': ''}

    cache.get_or_compute('600000', '某股', [doc_a], extractor)
    cache.get_or_compute('600000', '某股', [doc_a, doc_b], extractor)

    assert calls == ['600000', '600000'], '新增 doc 应重算'


def test_version_mismatch_triggers_recompute(cache_dir, doc_a):
    cache = DocCache(cache_dir, schema_version=1)
    calls = []

    def extractor(code, paths):
        calls.append(code)
        return {'logic': 'x', 'valuation': '', 'catalyst': '',
                'theme_fit': '', 'realized_or_invalidated': ''}

    cache.get_or_compute('600000', '某股', [doc_a], extractor)
    cache_v2 = DocCache(cache_dir, schema_version=2)
    cache_v2.get_or_compute('600000', '某股', [doc_a], extractor)

    assert calls == ['600000', '600000'], 'schema_version 变化应重算'
```

- [ ] **Step 2: 跑测试看失败**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_portfolio_shortlist_doc_cache.py -v
```

期望：5 条 FAIL（`ImportError: doc_cache`）

- [ ] **Step 3: 实现 `doc_cache.py`**

```python
# app/services/portfolio_shortlist/doc_cache.py
"""MD5 缓存层 — 按股票聚合多个 doc 的 md5，命中则跳过 extractor。"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Callable

ExtractorFn = Callable[[str, list[Path]], dict]


def _md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


class DocCache:
    def __init__(self, cache_dir: Path, schema_version: int = 1):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.schema_version = schema_version

    def get_or_compute(
        self,
        stock_code: str,
        stock_name: str,
        doc_paths: list,
        extractor: ExtractorFn,
    ) -> dict:
        cache_file = self.cache_dir / f'{stock_code}.json'
        current_md5s = {str(p): _md5(Path(p)) for p in doc_paths}

        if cache_file.exists():
            try:
                cached = json.loads(cache_file.read_text(encoding='utf-8'))
                if (
                    cached.get('version') == self.schema_version
                    and len(cached.get('docs', [])) == len(doc_paths)
                    and all(
                        d['md5'] == current_md5s.get(d['path'])
                        for d in cached['docs']
                    )
                ):
                    return cached['summary']
            except (json.JSONDecodeError, KeyError):
                pass  # 损坏缓存视为 miss

        summary = extractor(stock_code, [Path(p) for p in doc_paths])
        cache_file.write_text(
            json.dumps(
                {
                    'stock_code': stock_code,
                    'stock_name': stock_name,
                    'docs': [
                        {
                            'path': str(p),
                            'md5': current_md5s[str(p)],
                            'extracted_at': datetime.now().isoformat(timespec='seconds'),
                        }
                        for p in doc_paths
                    ],
                    'summary': summary,
                    'version': self.schema_version,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding='utf-8',
        )
        return summary
```

- [ ] **Step 4: 跑测试看通过**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_portfolio_shortlist_doc_cache.py -v
```

期望：5 PASSED

- [ ] **Step 5: Commit**

```bash
rtk git add app/services/portfolio_shortlist/doc_cache.py tests/test_portfolio_shortlist_doc_cache.py
rtk git commit -m "feat(shortlist): DocCache MD5 缓存层 + 单测"
```

---

## Task 3: scoring 模块（6 维度打分公式）

**Files:**
- Create: `app/services/portfolio_shortlist/scoring.py`
- Test: `tests/test_portfolio_shortlist_scoring.py`

接口契约：
```python
score_stock(rating: str, summary: dict, technical: dict) -> ScoreBreakdown
# rating ∈ {core, config, watch, exclude}
# summary: docs 5 段提取结果（dict 字段：logic/valuation/catalyst/theme_fit/realized_or_invalidated）
#   每段附带 0-1 浮点子分（由调用方人工评估给出，summary 字段值是元组 (text, sub_score)）
# technical: dict {ma20_position, volume_ratio, support_ok, td_signal, trend_direction}
# 返回 ScoreBreakdown(total, base, logic, valuation, catalyst, theme_fit, realized, technical)
```

打分公式见 spec §3。简化为：每子分 ∈ [0, 1] × 维度满分。

- [ ] **Step 1: 写失败测试**

```python
# tests/test_portfolio_shortlist_scoring.py
import pytest

from app.services.portfolio_shortlist.scoring import score_stock, ScoreBreakdown


def make_summary(logic=0.8, valuation=0.7, catalyst=0.9, theme_fit=1.0, realized=0.0):
    return {
        'logic': ('强主线', logic),
        'valuation': ('PE 合理', valuation),
        'catalyst': ('Q2 财报锚', catalyst),
        'theme_fit': ('核心受益', theme_fit),
        'realized_or_invalidated': ('未失效', realized),
    }


def make_tech(ma20=1.0, vol=1.0, support=1.0, td=0.5, trend=1.0):
    return {
        'ma20_position': ma20,
        'volume_ratio': vol,
        'support_ok': support,
        'td_signal': td,
        'trend_direction': trend,
    }


def test_core_full_score():
    sb = score_stock('core', make_summary(1, 1, 1, 1, 0), make_tech(1, 1, 1, 1, 1))
    assert sb.base == 50
    assert sb.logic == 15
    assert sb.valuation == 10
    assert sb.catalyst == 10
    assert sb.technical == 10
    # realized 中性（0）→ 0 调整
    assert sb.realized == 0
    # theme_fit 不在 spec 单独维度（spec §3 表里 theme_fit 含在 logic / catalyst 评估中），
    # 这里独立 0-5 加成项；满分 5
    assert sb.theme_fit == 5
    assert sb.total == 50 + 15 + 10 + 10 + 10 + 5  # 100


def test_config_partial():
    sb = score_stock('config', make_summary(0.5, 0.6, 0.4, 0.5, 0.0), make_tech(0.5, 0.5, 0.5, 0.5, 0.5))
    assert sb.base == 25
    assert 0 < sb.total < 100


def test_realized_invalidated_penalty():
    # realized=-1.0 表示已失效（最大扣分）
    sb = score_stock('core', make_summary(1, 1, 1, 1, -1.0), make_tech(1, 1, 1, 1, 1))
    assert sb.realized == -20
    sb_pos = score_stock('core', make_summary(1, 1, 1, 1, 1.0), make_tech(1, 1, 1, 1, 1))
    assert sb_pos.realized == 5  # 新催化加成上限


def test_watch_excluded_from_competition():
    with pytest.raises(ValueError, match='rating must be core or config'):
        score_stock('watch', make_summary(), make_tech())


def test_breakdown_dict_shape():
    sb = score_stock('core', make_summary(), make_tech())
    d = sb.as_dict()
    assert set(d.keys()) >= {'total', 'base', 'logic', 'valuation', 'catalyst',
                             'theme_fit', 'realized', 'technical'}
```

- [ ] **Step 2: 跑测试看失败**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_portfolio_shortlist_scoring.py -v
```

期望：5 FAIL

- [ ] **Step 3: 实现 `scoring.py`**

```python
# app/services/portfolio_shortlist/scoring.py
"""6 维度打分公式 — spec §3。

输入子分 ∈ [0, 1]（realized 维度 ∈ [-1, 1]），按各维度满分线性映射。
"""

from dataclasses import dataclass, asdict


_RATING_BASE = {'core': 50, 'config': 25}
_LOGIC_MAX = 15
_VALUATION_MAX = 10
_CATALYST_MAX = 10
_THEME_FIT_MAX = 5  # 主题契合独立加成（spec §3 维度④）
_TECHNICAL_MAX = 10
_REALIZED_PENALTY = -20  # realized=-1
_REALIZED_BONUS = 5      # realized=+1


@dataclass
class ScoreBreakdown:
    total: float
    base: int
    logic: float
    valuation: float
    catalyst: float
    theme_fit: float
    realized: float
    technical: float

    def as_dict(self) -> dict:
        return asdict(self)


def _avg(d: dict, default: float = 0.5) -> float:
    if not d:
        return default
    vals = [v for v in d.values() if v is not None]
    return sum(vals) / len(vals) if vals else default


def score_stock(rating: str, summary: dict, technical: dict) -> ScoreBreakdown:
    if rating not in _RATING_BASE:
        raise ValueError(f'rating must be core or config, got {rating}')

    def sub(field: str) -> float:
        v = summary.get(field, ('', 0.5))
        return v[1] if isinstance(v, tuple) else 0.5

    base = _RATING_BASE[rating]
    logic = round(sub('logic') * _LOGIC_MAX, 2)
    valuation = round(sub('valuation') * _VALUATION_MAX, 2)
    catalyst = round(sub('catalyst') * _CATALYST_MAX, 2)
    theme_fit = round(sub('theme_fit') * _THEME_FIT_MAX, 2)

    realized_score = sub('realized_or_invalidated')  # ∈ [-1, 1]
    if realized_score >= 0:
        realized = round(realized_score * _REALIZED_BONUS, 2)
    else:
        realized = round(realized_score * abs(_REALIZED_PENALTY), 2)

    technical_score = round(_avg(technical) * _TECHNICAL_MAX, 2)

    total = base + logic + valuation + catalyst + theme_fit + realized + technical_score

    return ScoreBreakdown(
        total=round(total, 2),
        base=base,
        logic=logic,
        valuation=valuation,
        catalyst=catalyst,
        theme_fit=theme_fit,
        realized=realized,
        technical=technical_score,
    )
```

- [ ] **Step 4: 跑测试看通过**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_portfolio_shortlist_scoring.py -v
```

期望：5 PASSED

- [ ] **Step 5: Commit**

```bash
rtk git add app/services/portfolio_shortlist/scoring.py tests/test_portfolio_shortlist_scoring.py
rtk git commit -m "feat(shortlist): 6 维度打分公式 + 单测"
```

---

## Task 4: technical 模块（技术形态指标）

**Files:**
- Create: `app/services/portfolio_shortlist/technical.py`
- Test: `tests/test_portfolio_shortlist_technical.py`

接口契约：
```python
compute_technical(ohlc: list[dict]) -> dict
# 输入：30 日 OHLC（每行 {date, open, high, low, close, volume}），来自 UnifiedStockDataService.get_trend_data
# 返回：{
#   'ma20_position': float ∈ [0, 1],   # 当前价 vs MA20 站上为 1，破位为 0
#   'volume_ratio': float ∈ [0, 1],    # 5d/30d 量比，0.8-1.2 给 1，缩量 < 0.8 → 0.3
#   'support_ok': float ∈ [0, 1],      # 近 30d 高/低位置，距 30d 高 < 5% 给 1
#   'td_signal': float ∈ [0, 1],       # 调 td_sequential.calculate；buy setup→1，sell setup→0
#   'trend_direction': float ∈ [0, 1], # 30d 收盘斜率正 → 1
# }
```

- [ ] **Step 1: 写失败测试（用合成 OHLC 数据）**

```python
# tests/test_portfolio_shortlist_technical.py
import pytest
from datetime import date, timedelta

from app.services.portfolio_shortlist.technical import compute_technical


def make_ohlc(closes: list[float], volumes: list[int] = None) -> list[dict]:
    """构造 N 行 OHLC，date 从 30 天前递增；high=close+1, low=close-1, open=close。"""
    if volumes is None:
        volumes = [10000] * len(closes)
    start = date.today() - timedelta(days=len(closes) - 1)
    rows = []
    for i, (c, v) in enumerate(zip(closes, volumes)):
        d = start + timedelta(days=i)
        rows.append({
            'date': d.isoformat(), 'open': c, 'high': c + 1,
            'low': c - 1, 'close': c, 'volume': v,
        })
    return rows


def test_uptrend_full_score():
    closes = [10 + i * 0.2 for i in range(30)]   # 持续上涨
    ohlc = make_ohlc(closes)
    result = compute_technical(ohlc)
    assert result['ma20_position'] == 1.0  # 现价 > MA20
    assert result['trend_direction'] == 1.0
    assert 0.8 <= result['support_ok'] <= 1.0  # 接近 30d 高


def test_downtrend_breaks_ma():
    closes = [20 - i * 0.3 for i in range(30)]   # 持续下跌
    ohlc = make_ohlc(closes)
    result = compute_technical(ohlc)
    assert result['ma20_position'] == 0.0  # 破位
    assert result['trend_direction'] == 0.0


def test_volume_shrink():
    closes = [15.0] * 30
    volumes = [10000] * 25 + [3000] * 5  # 近 5 日量缩
    ohlc = make_ohlc(closes, volumes)
    result = compute_technical(ohlc)
    assert result['volume_ratio'] < 0.5  # 量比明显偏低


def test_volume_normal():
    closes = [15.0] * 30
    volumes = [10000] * 30
    ohlc = make_ohlc(closes, volumes)
    result = compute_technical(ohlc)
    assert result['volume_ratio'] >= 0.8


def test_empty_ohlc_returns_neutral():
    result = compute_technical([])
    assert all(0.4 <= v <= 0.6 for v in result.values())  # 全部 0.5 中性


def test_returns_required_keys():
    result = compute_technical(make_ohlc([15.0] * 30))
    assert set(result.keys()) == {
        'ma20_position', 'volume_ratio', 'support_ok',
        'td_signal', 'trend_direction',
    }
```

- [ ] **Step 2: 跑测试看失败**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_portfolio_shortlist_technical.py -v
```

期望：6 FAIL

- [ ] **Step 3: 实现 `technical.py`**

```python
# app/services/portfolio_shortlist/technical.py
"""技术形态指标计算 — spec §5。

输入 30 日 OHLC（list of dict），输出 5 个 [0, 1] 子分给打分模块。
"""

from typing import Optional


def _ma(closes: list[float], window: int) -> Optional[float]:
    if len(closes) < window:
        return None
    return sum(closes[-window:]) / window


def _slope_sign(closes: list[float]) -> float:
    """简化斜率：尾值 vs 首值。"""
    if len(closes) < 2:
        return 0.5
    return 1.0 if closes[-1] > closes[0] else 0.0


def _td_signal_from_closes(closes: list[float]) -> float:
    """简化 TD 九转代理：连续 9 根收盘 < 4 根前 → buy setup（=1）；连续 9 根 > → sell setup（=0）。

    生产路径调 app/services/td_sequential.py，本模块为避免循环依赖延迟 import。
    """
    if len(closes) < 13:
        return 0.5
    try:
        from app.services.td_sequential import calculate_td
        signals = calculate_td(closes)
        last = signals[-1] if signals else None
        if last == 'buy_setup_9':
            return 1.0
        if last == 'sell_setup_9':
            return 0.0
        return 0.5
    except (ImportError, AttributeError):
        # td_sequential 接口与实际不一致时降级到本地启发式
        buy = sum(1 for i in range(-9, 0) if closes[i] < closes[i - 4]) >= 9
        sell = sum(1 for i in range(-9, 0) if closes[i] > closes[i - 4]) >= 9
        if buy:
            return 1.0
        if sell:
            return 0.0
        return 0.5


def compute_technical(ohlc: list[dict]) -> dict:
    if not ohlc:
        return {
            'ma20_position': 0.5, 'volume_ratio': 0.5, 'support_ok': 0.5,
            'td_signal': 0.5, 'trend_direction': 0.5,
        }

    closes = [r['close'] for r in ohlc]
    volumes = [r['volume'] for r in ohlc]
    cur = closes[-1]

    ma20 = _ma(closes, 20)
    ma20_position = 1.0 if (ma20 and cur >= ma20) else 0.0

    if len(volumes) >= 30:
        vol5 = sum(volumes[-5:]) / 5
        vol30 = sum(volumes[-30:]) / 30
        ratio = vol5 / vol30 if vol30 > 0 else 1.0
        if 0.8 <= ratio <= 1.5:
            volume_ratio = 1.0
        elif ratio > 1.5:
            volume_ratio = 0.8  # 过度放量也降分（拉高出货）
        else:
            volume_ratio = max(0.0, ratio / 0.8 * 0.5)
    else:
        volume_ratio = 0.5

    high30 = max(r['high'] for r in ohlc)
    low30 = min(r['low'] for r in ohlc)
    pos = (cur - low30) / (high30 - low30) if high30 > low30 else 0.5
    support_ok = pos  # 越接近高点越强（0-1 自然映射）

    td_signal = _td_signal_from_closes(closes)
    trend_direction = _slope_sign(closes)

    return {
        'ma20_position': ma20_position,
        'volume_ratio': round(volume_ratio, 3),
        'support_ok': round(support_ok, 3),
        'td_signal': td_signal,
        'trend_direction': trend_direction,
    }
```

- [ ] **Step 4: 跑测试看通过**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_portfolio_shortlist_technical.py -v
```

期望：6 PASSED（如 td_sequential 接口名不一致，会走 fallback 启发式仍 PASS）

- [ ] **Step 5: 验证 td_sequential 实际接口**

```bash
PYTHONIOENCODING=utf-8 python -c "import inspect; from app.services import td_sequential; print([n for n in dir(td_sequential) if not n.startswith('_')])"
```

如果输出里没有 `calculate_td`，记下实际函数名（如 `calculate` / `TDSequentialService.calculate`），更新 `_td_signal_from_closes` 的 import 与调用：

```python
# 如实际接口是 TDSequentialService().calculate(ohlc_dataframe)：
from app.services.td_sequential import TDSequentialService
df = ...  # 转 dataframe
signals = TDSequentialService().calculate(df)
```

- [ ] **Step 6: Commit**

```bash
rtk git add app/services/portfolio_shortlist/technical.py tests/test_portfolio_shortlist_technical.py
rtk git commit -m "feat(shortlist): 技术形态指标计算（MA20/量比/位置/TD/趋势）+ 单测"
```

---

## Task 5: theme_allocator 模块（入选后主题内权重分配）

**Files:**
- Create: `app/services/portfolio_shortlist/theme_allocator.py`
- Test: `tests/test_portfolio_shortlist_allocator.py`

接口契约：
```python
allocate_weights(
    selected: list[dict],   # [{stock_code, theme, score, current_price}, ...]
    themes_config: dict,    # config.yaml themes 段 {ai_compute: {weight: 0.30, ...}, ...}
    target_value: float,
    rules: dict,            # {single_stock_max_pct_of_theme: 0.50, share_unit: 100, ...}
) -> dict
# 返回：{
#   'allocations': [{stock_code, theme, weight, target_value, target_shares, capped: bool}, ...],
#   'theme_summary': [{theme, target_value, allocated_value, cash_buffer, n_selected}, ...],
#   'warnings': [str],   # 主题 0 入选 / 触顶溢出回流不下 等告警
# }
```

- [ ] **Step 1: 写失败测试**

```python
# tests/test_portfolio_shortlist_allocator.py
import pytest

from app.services.portfolio_shortlist.theme_allocator import allocate_weights


THEMES = {
    'ai': {'weight': 0.30, 'name': 'AI'},
    'memory': {'weight': 0.20, 'name': '存储'},
    'gold': {'weight': 0.10, 'name': '黄金'},
}
RULES = {'single_stock_max_pct_of_theme': 0.50, 'share_unit': 100}
TARGET = 100_000


def _by_code(allocations):
    return {a['stock_code']: a for a in allocations}


def test_two_stocks_same_theme_split_by_score():
    selected = [
        {'stock_code': 'A', 'theme': 'ai', 'score': 80, 'current_price': 50},
        {'stock_code': 'B', 'theme': 'ai', 'score': 40, 'current_price': 50},
    ]
    out = allocate_weights(selected, THEMES, TARGET, RULES)
    by = _by_code(out['allocations'])
    # AI 主题预算 30000，A 占 80/120, B 占 40/120
    assert pytest.approx(by['A']['target_value'], rel=0.05) == 30000 * 80 / 120
    assert pytest.approx(by['B']['target_value'], rel=0.05) == 30000 * 40 / 120


def test_share_rounding_floors_to_unit():
    selected = [{'stock_code': 'A', 'theme': 'ai', 'score': 100, 'current_price': 33.33}]
    out = allocate_weights(selected, THEMES, TARGET, RULES)
    by = _by_code(out['allocations'])
    assert by['A']['target_shares'] % 100 == 0


def test_single_stock_cap_50pct():
    # AI 30000 主题，单股上限 15000；如果只有 1 只入选满分，会被截顶
    selected = [{'stock_code': 'A', 'theme': 'ai', 'score': 100, 'current_price': 10}]
    out = allocate_weights(selected, THEMES, TARGET, RULES)
    by = _by_code(out['allocations'])
    assert by['A']['target_value'] <= 15000 + 1  # 1 元浮点容忍
    assert by['A']['capped'] is True
    summary = {s['theme']: s for s in out['theme_summary']}
    assert summary['ai']['cash_buffer'] >= 14000  # 剩余 ≥ 15k buffer


def test_theme_with_zero_selected_emits_warning():
    selected = [{'stock_code': 'A', 'theme': 'ai', 'score': 80, 'current_price': 50}]
    out = allocate_weights(selected, THEMES, TARGET, RULES)
    warnings_text = ' | '.join(out['warnings'])
    assert 'memory' in warnings_text or '存储' in warnings_text
    assert 'gold' in warnings_text or '黄金' in warnings_text


def test_overflow_redistributes_within_theme():
    # AI 30000 上限单股 15000；A 过分而 B 没满
    selected = [
        {'stock_code': 'A', 'theme': 'ai', 'score': 90, 'current_price': 10},
        {'stock_code': 'B', 'theme': 'ai', 'score': 30, 'current_price': 10},
    ]
    out = allocate_weights(selected, THEMES, TARGET, RULES)
    by = _by_code(out['allocations'])
    # 没截顶时 A 本应 30000 × 75% = 22500（超 15000 上限）→ A=15000，溢出 7500 给 B
    # B 原 7500 + 溢出 7500 = 15000（也触顶）→ 多余 0 进 buffer
    assert by['A']['target_value'] <= 15001
    assert by['B']['target_value'] <= 15001
    assert by['A']['capped'] is True
```

- [ ] **Step 2: 跑测试看失败**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_portfolio_shortlist_allocator.py -v
```

期望：5 FAIL

- [ ] **Step 3: 实现 `theme_allocator.py`**

```python
# app/services/portfolio_shortlist/theme_allocator.py
"""入选股按打分归一化分配主题内 StockWeight，触顶截顶 + 溢出回流。

spec §3.1, §4
"""

from collections import defaultdict
from math import floor


def _round_shares(value: float, price: float, unit: int) -> int:
    if price <= 0:
        return 0
    raw = value / price
    return int(floor(raw / unit + 1e-6) * unit)


def _allocate_in_theme(
    stocks: list[dict],
    theme_budget: float,
    cap_pct: float,
    share_unit: int,
) -> tuple[list[dict], float]:
    """主题内按 score 归一化分配 + 触顶截顶 + 溢出回流。"""
    if not stocks:
        return [], theme_budget

    cap_value = theme_budget * cap_pct
    total_score = sum(s['score'] for s in stocks)
    if total_score <= 0:
        return [], theme_budget

    targets = {s['stock_code']: theme_budget * s['score'] / total_score for s in stocks}
    capped = set()
    overflow = 0.0

    for code in list(targets):
        if targets[code] > cap_value:
            overflow += targets[code] - cap_value
            targets[code] = cap_value
            capped.add(code)

    # 溢出回流到未触顶股，按剩余 score 比例
    while overflow > 1e-3:
        remaining = [s for s in stocks if s['stock_code'] not in capped]
        if not remaining:
            break
        rem_total = sum(s['score'] for s in remaining)
        new_cap_hits = []
        for s in remaining:
            share = overflow * s['score'] / rem_total
            new_target = targets[s['stock_code']] + share
            if new_target > cap_value:
                new_cap_hits.append((s['stock_code'], new_target - cap_value))
                targets[s['stock_code']] = cap_value
                capped.add(s['stock_code'])
            else:
                targets[s['stock_code']] = new_target
        if not new_cap_hits:
            overflow = 0
        else:
            overflow = sum(o for _, o in new_cap_hits)

    allocations = []
    allocated_value = 0.0
    for s in stocks:
        code = s['stock_code']
        tv = targets[code]
        shares = _round_shares(tv, s['current_price'], share_unit)
        actual_value = shares * s['current_price']
        allocations.append({
            'stock_code': code,
            'theme': s['theme'],
            'weight': round(tv / theme_budget, 6) if theme_budget > 0 else 0,
            'target_value': round(tv, 2),
            'target_shares': shares,
            'actual_value': round(actual_value, 2),
            'current_price': s['current_price'],
            'score': s['score'],
            'capped': code in capped,
        })
        allocated_value += actual_value

    cash_buffer = round(theme_budget - allocated_value + overflow, 2)
    return allocations, cash_buffer


def allocate_weights(
    selected: list[dict],
    themes_config: dict,
    target_value: float,
    rules: dict,
) -> dict:
    cap_pct = rules.get('single_stock_max_pct_of_theme', 0.50)
    share_unit = rules.get('share_unit', 100)

    by_theme = defaultdict(list)
    for s in selected:
        by_theme[s['theme']].append(s)

    all_allocations = []
    theme_summary = []
    warnings = []

    for theme_key, cfg in themes_config.items():
        budget = target_value * cfg['weight']
        stocks = by_theme.get(theme_key, [])
        if not stocks:
            warnings.append(
                f'主题 {theme_key} ({cfg.get("name", theme_key)}) 当前 0 只入选 — '
                f'¥{budget:,.0f} 预算需用户决策（合并到其他主题 / 保留 cash buffer）'
            )
            theme_summary.append({
                'theme': theme_key, 'name': cfg.get('name', theme_key),
                'target_value': budget, 'allocated_value': 0,
                'cash_buffer': budget, 'n_selected': 0,
            })
            continue

        allocs, buffer = _allocate_in_theme(stocks, budget, cap_pct, share_unit)
        all_allocations.extend(allocs)
        theme_summary.append({
            'theme': theme_key, 'name': cfg.get('name', theme_key),
            'target_value': budget,
            'allocated_value': round(budget - buffer, 2),
            'cash_buffer': buffer, 'n_selected': len(stocks),
        })

    return {
        'allocations': all_allocations,
        'theme_summary': theme_summary,
        'warnings': warnings,
    }
```

- [ ] **Step 4: 跑测试看通过**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_portfolio_shortlist_allocator.py -v
```

期望：5 PASSED

- [ ] **Step 5: Commit**

```bash
rtk git add app/services/portfolio_shortlist/theme_allocator.py tests/test_portfolio_shortlist_allocator.py
rtk git commit -m "feat(shortlist): 入选后主题内权重分配（归一化+截顶+溢出回流）+ 单测"
```

---

## Task 6: report_renderer 模块（HTML + markdown 渲染）

**Files:**
- Create: `app/services/portfolio_shortlist/report_renderer.py`
- Test: `tests/test_portfolio_shortlist_renderer.py`

接口契约：
```python
render_html(payload: dict) -> str
render_markdown(payload: dict) -> str
# payload: {
#   'date': '2026-05-10',
#   'target_value': 433765,
#   'shortlist': [{stock_code, stock_name, theme, rating, breakdown: ScoreBreakdown.as_dict(),
#                  decision: 'keep'|'demote'|'capped_out', evidence: str, doc_paths: [...]}],
#   'demoted': [{stock_code, stock_name, reason, score}],   # 未入 Top 10
#   'capped_out': [...],                                    # 触顶硬出局
#   'allocations': allocator['allocations'],
#   'theme_summary': allocator['theme_summary'],
#   'warnings': allocator['warnings'],
# }
```

样式参考 `.claude/skills/portfolio-init/report-template.html` 的 CSS（保持视觉一致）。

- [ ] **Step 1: 写 smoke test**

```python
# tests/test_portfolio_shortlist_renderer.py
import re

from app.services.portfolio_shortlist.report_renderer import render_html, render_markdown


SAMPLE = {
    'date': '2026-05-10',
    'target_value': 433765,
    'shortlist': [
        {
            'stock_code': '601138', 'stock_name': '工业富联', 'theme': 'ai_compute',
            'rating': 'core',
            'breakdown': {'total': 92.5, 'base': 50, 'logic': 13, 'valuation': 8,
                          'catalyst': 9, 'theme_fit': 5, 'realized': 2.5, 'technical': 5},
            'decision': 'keep',
            'evidence': '工业富联 × ORCL 走势相关性 465 配对交易日',
            'doc_paths': ['docs/analysis/2026-05-09-工业富联-甲骨文-走势相关性专题.md'],
        },
    ],
    'demoted': [
        {'stock_code': '600600', 'stock_name': '青岛啤酒', 'reason': '主题外溢，估值偏中性',
         'score': 55.0},
    ],
    'capped_out': [
        {'stock_code': '300476', 'stock_name': '胜宏科技',
         'reason': '100 股市值 ¥35,866 < 主题上限 ¥65,065 但优先级低于其他 core'},
    ],
    'allocations': [
        {'stock_code': '601138', 'theme': 'ai_compute', 'weight': 0.34,
         'target_value': 44296, 'target_shares': 700, 'actual_value': 44296,
         'current_price': 63.28, 'score': 92.5, 'capped': False},
    ],
    'theme_summary': [
        {'theme': 'ai_compute', 'name': 'AI 算力', 'target_value': 130130,
         'allocated_value': 44296, 'cash_buffer': 85834, 'n_selected': 1},
    ],
    'warnings': ['主题 gold_defense (黄金防御) 当前 0 只入选 — ¥43,376 预算需用户决策'],
}


def test_render_html_returns_valid_doc():
    html = render_html(SAMPLE)
    assert html.startswith('<!DOCTYPE html>')
    assert '工业富联' in html
    assert '92.5' in html
    assert '主题 gold_defense' in html  # warning 渲染
    assert 'docs/analysis/2026-05-09-工业富联' in html  # doc 链接


def test_render_html_demoted_section():
    html = render_html(SAMPLE)
    assert '青岛啤酒' in html
    assert '主题外溢' in html


def test_render_markdown_has_tables():
    md = render_markdown(SAMPLE)
    assert '|' in md  # 至少一个 markdown 表
    assert '工业富联' in md
    assert '## ' in md  # 带二级标题


def test_warning_block_visible():
    html = render_html(SAMPLE)
    # warning 段应有特殊 CSS class（如 warn-box）便于视觉识别
    assert re.search(r'class="[^"]*warn', html)
```

- [ ] **Step 2: 跑测试看失败**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_portfolio_shortlist_renderer.py -v
```

期望：4 FAIL

- [ ] **Step 3: 实现 `report_renderer.py`**

```python
# app/services/portfolio_shortlist/report_renderer.py
"""HTML / markdown 渲染。CSS 风格对齐 .claude/skills/portfolio-init/report-template.html。"""

from html import escape


_CSS = """
* { box-sizing: border-box; }
body { font-family: -apple-system, "PingFang SC", sans-serif; max-width: 1180px;
  margin: 0 auto; padding: 0 20px 20px; color: #1f2937; line-height: 1.6; background: #fafafa; }
h1 { font-size: 24px; border-bottom: 2px solid #1f2937; padding-bottom: 8px; margin: 24px 0 4px; }
h2 { font-size: 18px; margin-top: 32px; color: #111827; border-left: 4px solid #2563eb; padding-left: 10px; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 13px; background: #fff; }
th, td { border: 1px solid #e5e7eb; padding: 7px 11px; text-align: left; vertical-align: top; }
th { background: #f3f4f6; font-weight: 600; }
.summary { background: #f0f9ff; border: 1px solid #bae6fd; padding: 14px 18px; border-radius: 6px; margin: 14px 0; }
.warn-box { background: #fef3c7; border: 1px solid #fde68a; padding: 12px 16px; border-radius: 6px; margin: 12px 0; }
.tag { display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 11px; }
.tag-core { background: #dcfce7; color: #166534; }
.tag-config { background: #dbeafe; color: #1e40af; }
.decision-keep { color: #16a34a; font-weight: 600; }
.decision-demote { color: #d97706; }
.decision-capped { color: #dc2626; }
.score-cell { font-weight: 600; color: #1f2937; }
"""


def _e(s) -> str:
    return escape(str(s if s is not None else ''))


def _decision_class(d: str) -> str:
    return {'keep': 'decision-keep', 'demote': 'decision-demote',
            'capped_out': 'decision-capped'}.get(d, '')


def _shortlist_rows(items):
    rows = []
    for s in items:
        b = s['breakdown']
        rating_tag = f'<span class="tag tag-{_e(s["rating"])}">{_e(s["rating"])}</span>'
        doc_links = ' '.join(
            f'<a href="file:///{_e(p)}">📄</a>' for p in s.get('doc_paths', [])
        )
        rows.append(
            f'<tr><td>{_e(s["stock_code"])}</td>'
            f'<td>{_e(s["stock_name"])} {doc_links}</td>'
            f'<td>{_e(s["theme"])}</td>'
            f'<td>{rating_tag}</td>'
            f'<td class="score-cell">{b["total"]}</td>'
            f'<td>{b["base"]}/{b["logic"]}/{b["valuation"]}/{b["catalyst"]}/'
            f'{b["theme_fit"]}/{b["realized"]}/{b["technical"]}</td>'
            f'<td class="{_decision_class(s["decision"])}">{_e(s["decision"])}</td>'
            f'<td>{_e(s["evidence"])}</td></tr>'
        )
    return '\n'.join(rows)


def _allocations_rows(allocs):
    return '\n'.join(
        f'<tr><td>{_e(a["stock_code"])}</td>'
        f'<td>{a["weight"]:.1%}</td>'
        f'<td>¥{a["target_value"]:,.0f}</td>'
        f'<td>{a["target_shares"]:,}</td>'
        f'<td>¥{a["current_price"]:.2f}</td>'
        f'<td>¥{a["actual_value"]:,.0f}</td>'
        f'<td>{"⚠️ 触顶" if a["capped"] else ""}</td></tr>'
        for a in allocs
    )


def _theme_rows(summary):
    return '\n'.join(
        f'<tr><td>{_e(t["name"])}</td>'
        f'<td>¥{t["target_value"]:,.0f}</td>'
        f'<td>¥{t["allocated_value"]:,.0f}</td>'
        f'<td>¥{t["cash_buffer"]:,.0f}</td>'
        f'<td>{t["n_selected"]}</td></tr>'
        for t in summary
    )


def _demoted_rows(items):
    return '\n'.join(
        f'<tr><td>{_e(s["stock_code"])}</td>'
        f'<td>{_e(s["stock_name"])}</td>'
        f'<td>{_e(s.get("score", ""))}</td>'
        f'<td>{_e(s["reason"])}</td></tr>'
        for s in items
    )


def render_html(payload: dict) -> str:
    warnings_html = ''
    if payload.get('warnings'):
        warnings_html = (
            '<div class="warn-box"><strong>⚠️ 告警</strong><ul>'
            + ''.join(f'<li>{_e(w)}</li>' for w in payload['warnings'])
            + '</ul></div>'
        )

    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<title>持仓精选 — {_e(payload['date'])}</title>
<style>{_CSS}</style></head><body>
<h1>持仓精选 — {_e(payload['date'])}</h1>
<div class="summary">目标总市值 <strong>¥{payload['target_value']:,.0f}</strong> |
入选 <strong>{len(payload['shortlist'])}</strong> 只 |
降级观察池 {len(payload['demoted'])} 只 | 硬约束出局 {len(payload['capped_out'])} 只</div>
{warnings_html}

<h2>入选 Top {len(payload['shortlist'])}</h2>
<table><thead><tr><th>代码</th><th>名称</th><th>主题</th><th>评级</th>
<th>总分</th><th>基/逻辑/估/催/题/兑/技</th><th>决定</th><th>证据</th></tr></thead>
<tbody>{_shortlist_rows(payload['shortlist'])}</tbody></table>

<h2>主题分配</h2>
<table><thead><tr><th>主题</th><th>预算</th><th>已分配</th><th>cash buffer</th><th>入选数</th></tr></thead>
<tbody>{_theme_rows(payload['theme_summary'])}</tbody></table>

<h2>个股分配</h2>
<table><thead><tr><th>代码</th><th>权重</th><th>目标市值</th><th>目标股数</th>
<th>现价</th><th>实际市值</th><th>触顶</th></tr></thead>
<tbody>{_allocations_rows(payload['allocations'])}</tbody></table>

<h2>降级观察池（未入 Top）</h2>
<table><thead><tr><th>代码</th><th>名称</th><th>得分</th><th>原因</th></tr></thead>
<tbody>{_demoted_rows(payload['demoted'])}</tbody></table>

<h2>硬约束出局（100 股触顶）</h2>
<table><thead><tr><th>代码</th><th>名称</th><th>得分</th><th>原因</th></tr></thead>
<tbody>{_demoted_rows(payload['capped_out'])}</tbody></table>

<footer style="margin-top:48px;color:#9ca3af;font-size:12px;text-align:center">
生成时间 {_e(payload['date'])} | 数据源 data/private.db | 由 portfolio_shortlist 模块生成
</footer>
</body></html>"""


def render_markdown(payload: dict) -> str:
    lines = [
        f"# 持仓精选 — {payload['date']}",
        '',
        f"目标总市值 **¥{payload['target_value']:,.0f}** | "
        f"入选 **{len(payload['shortlist'])}** 只 | "
        f"降级 {len(payload['demoted'])} 只 | 出局 {len(payload['capped_out'])} 只",
        '',
    ]
    if payload.get('warnings'):
        lines.append('## ⚠️ 告警')
        for w in payload['warnings']:
            lines.append(f'- {w}')
        lines.append('')

    lines.extend([
        f"## 入选 Top {len(payload['shortlist'])}", '',
        '| 代码 | 名称 | 主题 | 评级 | 总分 | 决定 | 证据 |',
        '|---|---|---|---|---|---|---|',
    ])
    for s in payload['shortlist']:
        lines.append(
            f"| {s['stock_code']} | {s['stock_name']} | {s['theme']} | "
            f"{s['rating']} | {s['breakdown']['total']} | "
            f"{s['decision']} | {s['evidence']} |"
        )
    lines.append('')

    lines.extend([
        '## 主题分配', '',
        '| 主题 | 预算 | 已分配 | cash buffer | 入选数 |',
        '|---|---|---|---|---|',
    ])
    for t in payload['theme_summary']:
        lines.append(
            f"| {t['name']} | ¥{t['target_value']:,.0f} | "
            f"¥{t['allocated_value']:,.0f} | ¥{t['cash_buffer']:,.0f} | {t['n_selected']} |"
        )
    return '\n'.join(lines)
```

- [ ] **Step 4: 跑测试看通过**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -m pytest tests/test_portfolio_shortlist_renderer.py -v
```

期望：4 PASSED

- [ ] **Step 5: Commit**

```bash
rtk git add app/services/portfolio_shortlist/report_renderer.py tests/test_portfolio_shortlist_renderer.py
rtk git commit -m "feat(shortlist): HTML + markdown 报告渲染 + smoke test"
```

---

## Task 7: 一次性入口脚本（编排所有模块）

**Files:**
- Create: `scripts/_portfolio_shortlist.py`（跑完后 rm，不入库）

骨架：

1. 读 `config.yaml` themes / rules
2. 读 `local-config.yaml` 拿 output_dir
3. `scan_universe(docs_root, config)` 复用 portfolio-init 风格扫 docs，得 `[{stock_code, stock_name, themes, rating, doc_path, ...}]`
4. 按 stock_code 聚合多 doc，过滤 rating ∈ {core, config}
5. 对每只候选：
   - `DocCache.get_or_compute(...)` 拿 5 段 summary（extractor 函数读 doc → **由 Claude 在脚本运行环境内人工填写子分**，见下）
   - 调 `UnifiedStockDataService.get_trend_data([code], days=30, force_refresh=True)`，转 list of dict 后调 `compute_technical`
   - 调 `score_stock(rating, summary, technical)` 算 ScoreBreakdown
6. 应用硬约束：100 股 × current_price > theme_budget × 0.50 → 入 capped_out
7. 全局排序 by total desc → 取 Top 10 入 shortlist；其他入 demoted
8. `allocate_weights(shortlist, themes, target_value, rules)` 分主题预算
9. `render_html` / `render_markdown` 写到 output_dir
10. 写 patch JSON 到 `.omc/artifacts/portfolio-shortlist-patch-2026-05-10.json`

- [ ] **Step 1: 创建脚本骨架**

```python
# scripts/_portfolio_shortlist.py
"""一次性脚本：把重点池压缩到 ≤ 10 只。

跑完后执行 `rm scripts/_portfolio_shortlist.py`，逻辑通过 spec + commit 留痕。
spec: docs/superpowers/specs/2026-05-10-portfolio-shortlist-design.md
"""

import json
import os
import sys
from datetime import date
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
os.environ.setdefault('SCHEDULER_ENABLED', '0')

from app import create_app  # noqa: E402
from app.services.portfolio_shortlist import (  # noqa: E402
    DocCache, score_stock, compute_technical,
    allocate_weights, render_html, render_markdown,
)


SKILL_DIR = ROOT / '.claude' / 'skills' / 'portfolio-init'
CACHE_DIR = SKILL_DIR / '.cache' / 'shortlist'
ARTIFACTS_DIR = ROOT / '.omc' / 'artifacts'
TODAY = date.today().isoformat()


def load_configs():
    config = yaml.safe_load((SKILL_DIR / 'config.yaml').read_text(encoding='utf-8'))
    local = yaml.safe_load((SKILL_DIR / 'local-config.yaml').read_text(encoding='utf-8'))
    return config, local


def scan_candidates(config: dict) -> list[dict]:
    """扫 docs/analysis/**/*.md → 按 stock_code 聚合 → 过滤 rating ∈ {core, config}。"""
    by_code = {}
    for md in (ROOT / 'docs' / 'analysis').rglob('*.md'):
        text = md.read_text(encoding='utf-8')
        if not text.startswith('---'):
            continue
        try:
            _, fm_text, _ = text.split('---', 2)
            fm = yaml.safe_load(fm_text)
        except (ValueError, yaml.YAMLError):
            continue
        if not fm or 'stock_code' not in fm:
            continue
        code = str(fm['stock_code']).zfill(6) if str(fm['stock_code']).isdigit() else str(fm['stock_code'])
        if fm.get('rating') not in ('core', 'config'):
            continue
        entry = by_code.setdefault(code, {
            'stock_code': code,
            'stock_name': fm['stock_name'],
            'themes': fm.get('themes') or [],
            'rating': fm['rating'],
            'doc_paths': [],
            'thesis': fm.get('thesis', ''),
        })
        entry['doc_paths'].append(str(md.relative_to(ROOT)))
        # 同股多 doc 时取最新 conviction_date 的 rating
        if fm.get('conviction_date', '') > entry.get('_cd', ''):
            entry['_cd'] = fm.get('conviction_date', '')
            entry['rating'] = fm['rating']
            entry['themes'] = fm.get('themes') or entry['themes']
    return list(by_code.values())


def extractor_stub(code: str, doc_paths: list) -> dict:
    """5 段摘要 + 子分 — 占位，由 Step 2 之后的人工评估替换。

    生产路径：脚本运行时由 Claude 在 REPL 中读每个 doc 后填实际子分。
    占位返回中性 0.5 给所有维度。
    """
    return {
        'logic': ('待人工评估', 0.5),
        'valuation': ('待人工评估', 0.5),
        'catalyst': ('待人工评估', 0.5),
        'theme_fit': ('待人工评估', 0.5),
        'realized_or_invalidated': ('待人工评估', 0.0),
    }


def fetch_technical_for(code: str, app) -> dict:
    from app.services.unified_stock_data import UnifiedStockDataService
    svc = UnifiedStockDataService()
    with app.app_context():
        result = svc.get_trend_data([code], days=30, force_refresh=True)
    stocks = result.get('stocks', []) if result else []
    if not stocks:
        return compute_technical([])
    return compute_technical(stocks[0].get('data', []))


def main():
    config, local = load_configs()
    output_dir = Path(local['portfolio']['output_dir'])
    output_dir.mkdir(parents=True, exist_ok=True)
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    target_value = local.get('portfolio', {}).get('target_value') or 433_765
    cache = DocCache(CACHE_DIR)
    candidates = scan_candidates(config)
    print(f'候选股 {len(candidates)} 只（rating ∈ core/config）', flush=True)

    app = create_app()
    scored = []
    for c in candidates:
        summary = cache.get_or_compute(
            c['stock_code'], c['stock_name'],
            [ROOT / p for p in c['doc_paths']],
            extractor_stub,
        )
        technical = fetch_technical_for(c['stock_code'], app)
        breakdown = score_stock(c['rating'], summary, technical)
        primary_theme = (c['themes'] or ['unknown'])[0]
        cur_price = _current_price(c['stock_code'], app)
        scored.append({
            **c, 'theme': primary_theme,
            'breakdown': breakdown.as_dict(),
            'score': breakdown.total,
            'current_price': cur_price,
            'summary': summary,
            'technical': technical,
        })

    scored.sort(key=lambda x: (-x['score'], x.get('rating', '')))

    rules = config['rules']
    capped_out = []
    eligible = []
    theme_budgets = {k: target_value * v['weight'] for k, v in config['themes'].items()}
    cap_pct = rules.get('single_stock_max_pct_of_theme', 0.50)
    share_unit = rules.get('share_unit', 100)
    for s in scored:
        budget = theme_budgets.get(s['theme'], 0)
        cap = budget * cap_pct
        if s['current_price'] * share_unit > cap:
            capped_out.append({
                'stock_code': s['stock_code'], 'stock_name': s['stock_name'],
                'reason': f'100 股 ¥{s["current_price"] * share_unit:,.0f} > 主题上限 ¥{cap:,.0f}',
                'score': s['score'],
            })
        else:
            eligible.append(s)

    shortlist = eligible[:10]
    demoted_raw = eligible[10:]
    demoted = [{
        'stock_code': s['stock_code'], 'stock_name': s['stock_name'],
        'reason': f'排名 {i + 11} / 总分 {s["score"]:.1f} 未进 Top 10',
        'score': s['score'],
    } for i, s in enumerate(demoted_raw)]

    selected_for_alloc = [{
        'stock_code': s['stock_code'], 'theme': s['theme'],
        'score': s['score'], 'current_price': s['current_price'],
    } for s in shortlist]
    allocator = allocate_weights(selected_for_alloc, config['themes'], target_value, rules)

    payload = {
        'date': TODAY,
        'target_value': target_value,
        'shortlist': [{
            'stock_code': s['stock_code'], 'stock_name': s['stock_name'],
            'theme': s['theme'], 'rating': s['rating'],
            'breakdown': s['breakdown'],
            'decision': 'keep',
            'evidence': s.get('thesis', ''),
            'doc_paths': s['doc_paths'],
        } for s in shortlist],
        'demoted': demoted,
        'capped_out': capped_out,
        'allocations': allocator['allocations'],
        'theme_summary': allocator['theme_summary'],
        'warnings': allocator['warnings'],
    }

    html_path = output_dir / f'portfolio-shortlist-{TODAY}.html'
    md_path = output_dir / f'portfolio-shortlist-{TODAY}.md'
    patch_path = ARTIFACTS_DIR / f'portfolio-shortlist-patch-{TODAY}.json'

    html_path.write_text(render_html(payload), encoding='utf-8')
    md_path.write_text(render_markdown(payload), encoding='utf-8')
    patch_path.write_text(json.dumps({
        'date': TODAY,
        'rating_changes': [
            {'stock_code': s['stock_code'], 'current_rating': s['rating'],
             'suggested_rating': 'core', 'reason': 'Top 10 入选'}
            for s in shortlist
        ] + [
            {'stock_code': d['stock_code'], 'current_rating': '?',
             'suggested_rating': 'watch', 'reason': d['reason']}
            for d in demoted
        ],
        'allocations': allocator['allocations'],
        'theme_summary': allocator['theme_summary'],
    }, ensure_ascii=False, indent=2), encoding='utf-8')

    print(f'HTML: {html_path}\nMD:   {md_path}\nPatch: {patch_path}')


def _current_price(code: str, app) -> float:
    from app.services.unified_stock_data import UnifiedStockDataService
    svc = UnifiedStockDataService()
    with app.app_context():
        prices = svc.get_realtime_prices([code], force_refresh=False)
    p = (prices or {}).get(code, {}) if isinstance(prices, dict) else {}
    return float(p.get('current_price') or 0)


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: 跑脚本一次（用 stub extractor）确认骨架走通**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python scripts/_portfolio_shortlist.py
```

期望：
- 打印 `候选股 N 只`
- 输出 3 个文件路径
- 不报错（如报错先修，常见：`get_realtime_prices` 返回结构、`themes` 为空字符串）

如果 `current_price` 全 0，检查 `_current_price` 实现匹配 `UnifiedStockDataService.get_realtime_prices` 实际返回结构（参考 `app/services/briefing.py` 调用范例）。

- [ ] **Step 3: 替换 stub extractor 为人工评估**

跑骨架确认无误后，替换 `extractor_stub` 为「Claude 在 REPL 模式下逐 doc 评估」逻辑：

把 stub 改为读 doc 全文，返回打印 prompt 让人工填写或读结构化片段。简化方案：

```python
def extractor_human(code: str, doc_paths: list) -> dict:
    """读全部 doc，输出 5 段摘要文本和子分。

    实际生产：脚本跑前手工调用本函数；为保持可重复，子分写入 _portfolio_shortlist_eval.json
    （由 Claude 主对话过程逐只评估后填入）。
    """
    eval_file = ROOT / '.omc' / 'artifacts' / '_shortlist_eval.json'
    if not eval_file.exists():
        # 第一次跑：把待评估清单 + doc 全文 dump 出来
        dump = {}
        for p in doc_paths:
            dump[code] = dump.get(code, [])
            dump[code].append({
                'path': str(p),
                'content': Path(p).read_text(encoding='utf-8'),
            })
        existing = {}
        if eval_file.exists():
            existing = json.loads(eval_file.read_text(encoding='utf-8'))
        existing[code] = {
            'docs': dump[code],
            'logic': ['待填', 0.5],
            'valuation': ['待填', 0.5],
            'catalyst': ['待填', 0.5],
            'theme_fit': ['待填', 0.5],
            'realized_or_invalidated': ['待填', 0.0],
        }
        eval_file.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding='utf-8')
        return {k: tuple(v) for k, v in existing[code].items() if k != 'docs'}

    data = json.loads(eval_file.read_text(encoding='utf-8'))
    if code not in data:
        return extractor_stub(code, doc_paths)
    return {k: tuple(v) for k, v in data[code].items() if k != 'docs'}
```

把 `main()` 里 `extractor_stub` 替换为 `extractor_human`。

- [ ] **Step 4: 跑一次产出 `_shortlist_eval.json`，由对话主线手工填子分**

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python scripts/_portfolio_shortlist.py
```

第一次跑只生成 `.omc/artifacts/_shortlist_eval.json`（每只股 docs 全文 + 待填子分），HTML/MD 用占位子分。

由对话主线（Claude）逐 doc 阅读后写入子分（每只股 5 维度 × 浮点数），然后再跑一次。

- [ ] **Step 5: 第二次跑产出最终报告**

子分填好后再跑：

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python scripts/_portfolio_shortlist.py
```

期望产出：
- HTML 报告含真实打分
- patch JSON 含 rating_changes 列表

- [ ] **Step 6: 验收**

打开 HTML 报告（用户在浏览器看）：
- 入选 ≤ 10 只 ✓
- 主题 0 入选时报告顶部红框 ✓
- 每只股显示 6 维度打分 + 决定 + 证据 ✓
- patch JSON 含 `(stock_code, suggested_rating, reason)` 列表 ✓

- [ ] **Step 7: 删除一次性脚本**

```bash
rm scripts/_portfolio_shortlist.py
```

`.omc/artifacts/` 目录的产物保留（已 gitignore）。

- [ ] **Step 8: Commit cleanup**

```bash
rtk git status
# 确认 scripts/_portfolio_shortlist.py 不在工作区，模块代码 + 测试已 commit
rtk git log --oneline -8
```

确认前几次的 commit 已落地（Task 1-6）。如本 Task 内有需要永久保留的小修复（如 `_current_price` 适配），单独 commit：

```bash
rtk git add app/services/portfolio_shortlist/  # 或具体文件
rtk git commit -m "fix(shortlist): 适配 UnifiedStockDataService.get_realtime_prices 返回结构"
```

---

## Task 8: 用户审报告 + 决定 patch 写库

不写代码，触发用户决策。

- [ ] **Step 1: 把 HTML 报告 URL 给用户**

```
报告已生成：D:\Git\GSStockHold\portfolio-shortlist-2026-05-10.html
patch JSON：.omc/artifacts/portfolio-shortlist-patch-2026-05-10.json
```

- [ ] **Step 2: 用户审完后回 3 个决定**

1. **入选 10 只是否同意**？需要替换的逐只指出
2. **主题 0 入选场景**（如黄金防御）：
   - (a) 把权重按比例分摊到其他入选主题
   - (b) 保留权重为 0，¥X 转 cash buffer
3. **rating 变更落库**：是否同意把 patch JSON 里的 `rating_changes` 应用到对应 docs 的 frontmatter（不直接改 config.yaml，只改 docs 里的 `rating` 字段）

- [ ] **Step 3: 落库（可选，由 portfolio-init 或 portfolio-rebalance 已有路径）**

如用户同意：
- 改 docs/analysis/**/*.md frontmatter rating 字段（一次性脚本或手工）
- 跑 `/portfolio-init` 走标准路径写 `RebalanceConfig` / `StockWeight` / `PositionPlan`
- 不需要本计划新增写库代码

---

## Self-Review Notes

- **Spec 覆盖**：spec §1-§7 各节都有对应 Task：§1 评估维度 → Task 3 / 4；§2 缓存 → Task 2；§3 打分 → Task 3；§3.1 分配 → Task 5；§4 主题 0 入选告警 → Task 5（test_theme_with_zero_selected_emits_warning）；§5 技术形态 → Task 4；§6 输出 → Task 6, 7；§7 风险 → Task 7 Step 5/6 由用户审兜底；§8 验收 → Task 7 Step 6
- **Placeholder**：Task 7 Step 3 的 extractor_human 会在 .omc/artifacts/_shortlist_eval.json 里产生「待填」占位，但这是设计上需要的人工干预点，由对话主线（Claude）阅读 docs 后真实填写，非 plan 失败
- **类型一致性**：score_stock 返回 ScoreBreakdown，调用方都通过 `.as_dict()` 或 `.total` 访问；allocate_weights 输入 dict 列表 + themes_config + target_value + rules，输出三段（allocations / theme_summary / warnings）一致
- **Task 4 td_sequential 接口名**：plan 里 import `calculate_td`，Step 5 引导验证实际函数名并修补；fallback 到本地启发式保证测试可通过

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-10-portfolio-shortlist.md`. Two execution options:

**1. Subagent-Driven (recommended)** — 派发 fresh subagent 跑每个 Task，task 间 review，迭代快

**2. Inline Execution** — 在当前 session 跑 executing-plans，按 checkpoint 批次执行

Which approach?
