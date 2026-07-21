# ADR 跨市场溢价每日推送 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 `daily_briefing` 每日推送里新增两条 ADR 跨市场溢价（TSMC 美台 + SK海力士 美韩），当前溢价% + 较昨日变化，展示 + 喂 GLM 双路。

**Architecture:** 严格照搬现有 ETF溢价 的双层结构：`BriefingService.get_adr_premium_data()` 出结构化数据、`NotificationService.format_adr_premium_summary()` 出文案；昨日值存 `data/adr_premium_prev.json` 标记文件。取数复用 `unified_stock_data_service.get_yfinance_batch_quotes`（底层 `yf.Ticker(sym).history`，对 ADR/本土股/FX pair 全通用）。

**Tech Stack:** Python / Flask / yfinance（经 UnifiedStockDataService）/ pytest。无新第三方依赖。

## Global Constraints

- 所有 git / pytest 命令前加 `rtk`（链式 `&&` 中也要）。
- 单测放 `tests/test_*.py` 平铺，不建子目录。
- 写含中文的文件必须显式 `encoding='utf-8'`（Windows cp950 坑）。
- 跑测试：`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest ...`（env 赋值在 `rtk` 之前）。
- 不写多余注释；不留 backup 文件。
- 溢价口径（verbatim）：`premium% = us_close / (home_close × ratio / fx_rate) − 1`，正=美股溢价、负=折价。FX（`TWD=X`/`KRW=X`）是「每 1 USD 多少本币」，故本币折 USD 要除以它。
- `get_yfinance_batch_quotes(symbols, cache_type)` 返回 `{symbol: {'close': float, 'change_percent': float, 'name': str}}`，无价的 symbol 不在返回 dict 里（或值为 None）。

---

### Task 1: 配置 + 数据层核心（取数 + 溢价计算 + 降级，暂无持久化）

**Files:**
- Create: `app/config/adr_premium.py`
- Modify: `app/services/briefing.py`（顶部 imports 区加 `import os` / `import json` + 常量；`BriefingService` 类内新增 `_compute_premium` 静态方法 + `get_adr_premium_data` 静态方法）
- Test: `tests/test_adr_premium.py`

**Interfaces:**
- Produces:
  - `app.config.adr_premium.ADR_PREMIUM_PAIRS: list[dict]`，每项 `{'key','name','us','home','ratio','fx'}`
  - `BriefingService._compute_premium(us_close, home_close, fx_rate, ratio) -> float | None`（溢价%，保留 2 位；任一入参 falsy 或 fair≤0 返回 None）
  - `BriefingService.get_adr_premium_data() -> {'pairs': [{'key','name','us_price','home_price','fx','ratio','premium_rate','prev_premium','delta','error'}]}`（本 Task 内 `prev_premium`/`delta` 恒为 None，Task 2 补）

- [ ] **Step 1: 写配置文件**

Create `app/config/adr_premium.py`：

```python
"""ADR 跨市场溢价标的配置

ratio = 每 1 ADR 对应几股本土股。TSM=5（公认）。
SK海力士 HXSCL 为 OTC 未挂牌 ADR，ratio 待实测确认（见 plan 末尾说明），
未确认前置 None → 该腿溢价不可算、推送显「—」。
"""

ADR_PREMIUM_PAIRS = [
    {'key': 'tsmc',    'name': 'TSM',      'us': 'TSM',   'home': '2330.TW',   'ratio': 5,    'fx': 'TWD=X'},
    {'key': 'skhynix', 'name': 'SK海力士', 'us': 'HXSCL', 'home': '000660.KS', 'ratio': None, 'fx': 'KRW=X'},
]
```

- [ ] **Step 2: 写失败测试（公式 + 降级）**

Create `tests/test_adr_premium.py`：

```python
from app.services.briefing import BriefingService


def test_compute_premium_positive():
    # us=190, home=1000 TWD, fx=32 (1 USD=32 TWD), ratio=5
    # fair = 1000 * 5 / 32 = 156.25 ; premium = 190/156.25 - 1 = +21.60%
    assert BriefingService._compute_premium(190.0, 1000.0, 32.0, 5) == 21.6


def test_compute_premium_discount():
    # fair = 156.25 ; us=150 → 150/156.25 - 1 = -4.00%
    assert BriefingService._compute_premium(150.0, 1000.0, 32.0, 5) == -4.0


def test_compute_premium_none_when_ratio_missing():
    assert BriefingService._compute_premium(190.0, 1000.0, 32.0, None) is None


def test_compute_premium_none_when_leg_missing():
    assert BriefingService._compute_premium(None, 1000.0, 32.0, 5) is None
    assert BriefingService._compute_premium(190.0, None, 32.0, 5) is None
    assert BriefingService._compute_premium(190.0, 1000.0, None, 5) is None


def test_get_adr_premium_data_degrades_per_leg(monkeypatch):
    # TSM 全腿有价 → 有 premium；SK 缺 US 价 → premium None + error
    fake_quotes = {
        'TSM': {'close': 190.0}, '2330.TW': {'close': 1000.0}, 'TWD=X': {'close': 32.0},
        '000660.KS': {'close': 200000.0}, 'KRW=X': {'close': 1380.0},
        # HXSCL 缺失
    }
    monkeypatch.setattr(
        'app.services.unified_stock_data.unified_stock_data_service.get_yfinance_batch_quotes',
        lambda symbols, cache_type: fake_quotes,
    )
    monkeypatch.setattr(BriefingService, '_load_adr_prev', staticmethod(lambda: {}))
    monkeypatch.setattr(BriefingService, '_save_adr_prev', staticmethod(lambda store: None))

    pairs = BriefingService.get_adr_premium_data()['pairs']
    by_key = {p['key']: p for p in pairs}
    assert by_key['tsmc']['premium_rate'] == 21.6
    assert by_key['skhynix']['premium_rate'] is None
    assert by_key['skhynix']['error']
```

- [ ] **Step 3: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_adr_premium.py -v`
Expected: FAIL —— `AttributeError: ... _compute_premium` / `get_adr_premium_data`。

- [ ] **Step 4: 加常量与 imports**

在 `app/services/briefing.py` 顶部 import 区（第 9-14 行附近）补：

```python
import os
import json
```

并在 imports 之后、类定义之前加模块常量：

```python
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
ADR_PREV_FILE = os.path.join(DATA_DIR, 'adr_premium_prev.json')
```

- [ ] **Step 5: 实现 `_compute_premium` 与 `get_adr_premium_data`**

在 `BriefingService` 类内新增（放在 `get_etf_premium_data` 之后即可）：

```python
    @staticmethod
    def _compute_premium(us_close, home_close, fx_rate, ratio):
        if not us_close or not home_close or not fx_rate or not ratio:
            return None
        fair = home_close * ratio / fx_rate
        if fair <= 0:
            return None
        return round((us_close / fair - 1) * 100, 2)

    @staticmethod
    def get_adr_premium_data() -> dict:
        """获取 ADR 跨市场溢价（当前溢价% + 较昨日变化）"""
        from app.services.unified_stock_data import unified_stock_data_service
        from app.config.adr_premium import ADR_PREMIUM_PAIRS

        symbols = []
        for p in ADR_PREMIUM_PAIRS:
            symbols += [p['us'], p['home'], p['fx']]
        symbols = list(dict.fromkeys(symbols))

        quotes = unified_stock_data_service.get_yfinance_batch_quotes(symbols, 'adr_premium_yf')
        prev = BriefingService._load_adr_prev()
        today_str = date.today().isoformat()

        pairs = []
        new_store = dict(prev)
        for p in ADR_PREMIUM_PAIRS:
            us_close = (quotes.get(p['us']) or {}).get('close')
            home_close = (quotes.get(p['home']) or {}).get('close')
            fx_rate = (quotes.get(p['fx']) or {}).get('close')
            premium = BriefingService._compute_premium(us_close, home_close, fx_rate, p.get('ratio'))

            prev_premium = (prev.get(p['key']) or {}).get('premium')
            delta = round(premium - prev_premium, 2) if (premium is not None and prev_premium is not None) else None

            error = None
            if premium is None:
                error = 'ratio待确认' if not p.get('ratio') else '行情缺失'
            else:
                new_store[p['key']] = {'date': today_str, 'premium': premium}

            pairs.append({
                'key': p['key'], 'name': p['name'],
                'us_price': us_close, 'home_price': home_close,
                'fx': fx_rate, 'ratio': p.get('ratio'),
                'premium_rate': premium, 'prev_premium': prev_premium,
                'delta': delta, 'error': error,
            })

        BriefingService._save_adr_prev(new_store)
        return {'pairs': pairs}
```

> 注：`_load_adr_prev`/`_save_adr_prev` 在 Task 2 实现；本 Task 的降级测试已 monkeypatch 掉这两个方法，故 Task 1 测试不依赖它们的真实实现。若单独跑 Task 1 需先加两个占位（`return {}` / `pass`），Task 2 再补全——为避免占位，建议 Task 1、2 连续实现、Task 1 Step 6 暂跳过持久化相关断言。

- [ ] **Step 6: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_adr_premium.py -v`
Expected: PASS（5 个 test 全绿；`get_adr_premium_data` 测试因 monkeypatch 了 load/save 不触真实文件）。

- [ ] **Step 7: Commit**

```bash
rtk git add app/config/adr_premium.py app/services/briefing.py tests/test_adr_premium.py && rtk git commit -m "feat(briefing): ADR 溢价数据层（取数+计算+降级）"
```

---

### Task 2: 昨日值持久化 + delta

**Files:**
- Modify: `app/services/briefing.py`（`BriefingService` 类内新增 `_load_adr_prev` / `_save_adr_prev`）
- Test: `tests/test_adr_premium.py`（追加）

**Interfaces:**
- Produces:
  - `BriefingService._load_adr_prev() -> dict`（读 `ADR_PREV_FILE`，缺失/损坏返回 `{}`）
  - `BriefingService._save_adr_prev(store: dict) -> None`（写 `ADR_PREV_FILE`，`ensure_ascii=False` + `encoding='utf-8'`）
- Consumes: `get_adr_premium_data`（Task 1）已调用这两个方法并实现「某腿 premium=None 不覆盖旧值」（`new_store = dict(prev)` 起手、仅有效腿写入）。

- [ ] **Step 1: 写失败测试（roundtrip + delta + 不覆盖）**

在 `tests/test_adr_premium.py` 追加：

```python
def test_prev_roundtrip(tmp_path, monkeypatch):
    f = tmp_path / 'prev.json'
    monkeypatch.setattr('app.services.briefing.ADR_PREV_FILE', str(f))
    assert BriefingService._load_adr_prev() == {}          # 文件不存在
    BriefingService._save_adr_prev({'tsmc': {'date': '2026-07-20', 'premium': 1.82}})
    assert BriefingService._load_adr_prev()['tsmc']['premium'] == 1.82


def test_prev_corrupt_returns_empty(tmp_path, monkeypatch):
    f = tmp_path / 'prev.json'
    f.write_text('{ not json', encoding='utf-8')
    monkeypatch.setattr('app.services.briefing.ADR_PREV_FILE', str(f))
    assert BriefingService._load_adr_prev() == {}


def test_delta_computed_from_prev(tmp_path, monkeypatch):
    f = tmp_path / 'prev.json'
    f.write_text('{"tsmc": {"date": "2026-07-20", "premium": 20.0}}', encoding='utf-8')
    monkeypatch.setattr('app.services.briefing.ADR_PREV_FILE', str(f))
    monkeypatch.setattr(
        'app.services.unified_stock_data.unified_stock_data_service.get_yfinance_batch_quotes',
        lambda symbols, cache_type: {
            'TSM': {'close': 190.0}, '2330.TW': {'close': 1000.0}, 'TWD=X': {'close': 32.0},
            'HXSCL': {'close': 10.0}, '000660.KS': {'close': 200000.0}, 'KRW=X': {'close': 1380.0},
        },
    )
    pairs = {p['key']: p for p in BriefingService.get_adr_premium_data()['pairs']}
    # 今日 tsmc=21.6, 昨日 20.0 → delta=1.6
    assert pairs['tsmc']['delta'] == 1.6
    # skhynix ratio=None → premium None → delta None，且不覆盖（此处本无旧值）
    assert pairs['skhynix']['delta'] is None


def test_none_premium_does_not_overwrite_prev(tmp_path, monkeypatch):
    f = tmp_path / 'prev.json'
    f.write_text('{"skhynix": {"date": "2026-07-19", "premium": -0.5}}', encoding='utf-8')
    monkeypatch.setattr('app.services.briefing.ADR_PREV_FILE', str(f))
    monkeypatch.setattr(
        'app.services.unified_stock_data.unified_stock_data_service.get_yfinance_batch_quotes',
        lambda symbols, cache_type: {'TSM': {'close': 190.0}, '2330.TW': {'close': 1000.0}, 'TWD=X': {'close': 32.0}},
    )
    BriefingService.get_adr_premium_data()
    # skhynix 今日无价（ratio 也 None）→ 旧值仍在
    assert BriefingService._load_adr_prev()['skhynix']['premium'] == -0.5
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_adr_premium.py -k "prev or delta or overwrite" -v`
Expected: FAIL —— `AttributeError: ... _load_adr_prev`（若 Task 1 用了占位则断言不符）。

- [ ] **Step 3: 实现持久化**

在 `BriefingService` 类内（`get_adr_premium_data` 附近）加：

```python
    @staticmethod
    def _load_adr_prev() -> dict:
        try:
            with open(ADR_PREV_FILE, encoding='utf-8') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

    @staticmethod
    def _save_adr_prev(store: dict) -> None:
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(ADR_PREV_FILE, 'w', encoding='utf-8') as f:
                json.dump(store, f, ensure_ascii=False)
        except OSError as e:
            logger.warning(f'[简报.ADR溢价] 昨日值写入失败: {e}')
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_adr_premium.py -v`
Expected: PASS（全部 9 个 test）。

- [ ] **Step 5: Commit**

```bash
rtk git add app/services/briefing.py tests/test_adr_premium.py && rtk git commit -m "feat(briefing): ADR 溢价昨日值持久化 + delta"
```

---

### Task 3: 文案层 `format_adr_premium_summary`

**Files:**
- Modify: `app/services/notification.py`（`NotificationService` 类内新增，放在 `format_etf_premium_summary` 之后，第 655 行附近）
- Test: `tests/test_adr_premium.py`（追加）

**Interfaces:**
- Produces: `NotificationService.format_adr_premium_summary() -> str`（紧凑单行，两腿全废或无 pairs 返回 `''`）
- Consumes: `BriefingService.get_adr_premium_data()`（Task 1/2）

- [ ] **Step 1: 写失败测试**

在 `tests/test_adr_premium.py` 追加：

```python
from app.services.notification import NotificationService


def _patch_pairs(monkeypatch, pairs):
    monkeypatch.setattr(BriefingService, 'get_adr_premium_data',
                        staticmethod(lambda: {'pairs': pairs}))


def test_format_premium_and_discount_with_arrows(monkeypatch):
    _patch_pairs(monkeypatch, [
        {'name': 'TSM', 'premium_rate': 1.82, 'delta': 0.5, 'error': None},
        {'name': 'SK海力士', 'premium_rate': -0.31, 'delta': -0.2, 'error': None},
    ])
    out = NotificationService.format_adr_premium_summary()
    assert out == '🌏 ADR溢价: TSM +1.82%(溢价)↑0.5pct | SK海力士 -0.31%(折价)↓0.2pct'


def test_format_no_arrow_when_delta_none(monkeypatch):
    _patch_pairs(monkeypatch, [{'name': 'TSM', 'premium_rate': 1.82, 'delta': None, 'error': None}])
    assert NotificationService.format_adr_premium_summary() == '🌏 ADR溢价: TSM +1.82%(溢价)'


def test_format_dash_for_missing_leg(monkeypatch):
    _patch_pairs(monkeypatch, [
        {'name': 'TSM', 'premium_rate': 1.82, 'delta': None, 'error': None},
        {'name': 'SK海力士', 'premium_rate': None, 'delta': None, 'error': '行情缺失'},
    ])
    assert NotificationService.format_adr_premium_summary() == '🌏 ADR溢价: TSM +1.82%(溢价) | SK海力士 —'


def test_format_empty_when_all_missing(monkeypatch):
    _patch_pairs(monkeypatch, [
        {'name': 'TSM', 'premium_rate': None, 'delta': None, 'error': 'x'},
        {'name': 'SK海力士', 'premium_rate': None, 'delta': None, 'error': 'x'},
    ])
    assert NotificationService.format_adr_premium_summary() == ''
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_adr_premium.py -k format -v`
Expected: FAIL —— `AttributeError: ... format_adr_premium_summary`。

- [ ] **Step 3: 实现文案方法**

在 `app/services/notification.py` 的 `NotificationService` 类内，`format_etf_premium_summary` 之后加：

```python
    @staticmethod
    def format_adr_premium_summary() -> str:
        """格式化 ADR 跨市场溢价用于推送"""
        try:
            from app.services.briefing import BriefingService
            data = BriefingService.get_adr_premium_data()
            pairs = data.get('pairs', [])
            if not pairs:
                return ''

            parts = []
            any_valid = False
            for p in pairs:
                pr = p.get('premium_rate')
                if pr is None:
                    parts.append(f"{p['name']} —")
                    continue
                any_valid = True
                tag = '溢价' if pr >= 0 else '折价'
                seg = f"{p['name']} {pr:+.2f}%({tag})"
                delta = p.get('delta')
                if delta is not None and delta != 0:
                    arrow = '↑' if delta > 0 else '↓'
                    seg += f"{arrow}{abs(delta):.1f}pct"
                parts.append(seg)

            return f"🌏 ADR溢价: {' | '.join(parts)}" if any_valid else ''
        except Exception as e:
            logger.warning(f'[通知.ADR溢价] 格式化失败: {e}')
            return ''
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_adr_premium.py -v`
Expected: PASS（全部 13 个 test）。

- [ ] **Step 5: Commit**

```bash
rtk git add app/services/notification.py tests/test_adr_premium.py && rtk git commit -m "feat(notification): ADR 溢价推送文案"
```

---

### Task 4: 接线（push_daily_report 文本 + Block Kit + GLM prompt）

**Files:**
- Modify: `app/services/notification.py`（`push_daily_report` 取值/market_lines/all_data；`build_market_blocks` 签名 + ADR block）
- Modify: `app/llm/prompts/daily_briefing.py`（`label_map` 加 `adr_premium`）
- Test: `tests/test_adr_premium.py`（追加 prompt + block 断言）

**Interfaces:**
- Consumes: `NotificationService.format_adr_premium_summary()`（Task 3）、`BriefingService.get_adr_premium_data()`（Task 1/2）
- Produces: `build_market_blocks(..., adr_text: str = '')` 新增末位可选参数

- [ ] **Step 1: 写失败测试（prompt + block）**

在 `tests/test_adr_premium.py` 追加：

```python
from app.llm.prompts.daily_briefing import build_daily_briefing_prompt


def test_prompt_renders_adr_premium():
    prompt = build_daily_briefing_prompt({'adr_premium': '🌏 ADR溢价: TSM +1.82%(溢价)'})
    assert 'ADR溢价' in prompt
    assert 'TSM +1.82%(溢价)' in prompt


def test_market_blocks_include_adr(monkeypatch):
    _patch_pairs(monkeypatch, [
        {'name': 'TSM', 'premium_rate': 1.82, 'delta': 0.5, 'error': None},
    ])
    # 其余 BriefingService 取数在 build_market_blocks 里被 try/except 兜底，无价时走 except 分支
    blocks = NotificationService.build_market_blocks(
        indices_text='', futures_text='', etf_text='',
        sectors_text='', technical_text='', adr_text='🌏 ADR溢价: TSM +1.82%(溢价)↑0.5pct',
    )
    dumped = str(blocks)
    assert 'ADR溢价' in dumped and 'TSM' in dumped
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_adr_premium.py -k "prompt or blocks" -v`
Expected: FAIL —— prompt 不含 ADR溢价 / `build_market_blocks` 无 `adr_text` 参数报 TypeError。

- [ ] **Step 3: prompt label_map 加 adr_premium**

在 `app/llm/prompts/daily_briefing.py` 的 `label_map`，`'etf_premium': 'ETF溢价',` 之后加一行：

```python
        'adr_premium': 'ADR溢价',
```

并在 docstring 的 key 列表里 `- etf_premium: ETF溢价` 之后补 `- adr_premium: ADR跨市场溢价`。

- [ ] **Step 4: build_market_blocks 加 adr block**

改签名（第 1138-1141 行），在末尾加 `adr_text: str = ''`：

```python
    def build_market_blocks(indices_text: str, futures_text: str, etf_text: str,
                            sectors_text: str, technical_text: str,
                            dram_text: str = '', earnings_text: str = '',
                            pe_text: str = '', ai_text: str = '',
                            adr_text: str = '') -> list:
```

在 ETF溢价 block 之后（第 1200 行 `blocks.append(B._block_section(etf_text))` 所在 except 块的紧后面）加 ADR block：

```python
        try:
            from app.services.briefing import BriefingService
            adr_data = BriefingService.get_adr_premium_data()
            items = []
            for p in adr_data.get('pairs', []):
                pr = p.get('premium_rate')
                if pr is None:
                    items.append(f"{p['name']}  `—`")
                    continue
                tag = '溢价' if pr >= 0 else '折价'
                seg = f"{p['name']}  `{pr:+.2f}%`  {tag}"
                delta = p.get('delta')
                if delta is not None and delta != 0:
                    seg += f" {'↑' if delta > 0 else '↓'}{abs(delta):.1f}pct"
                items.append(seg)
            if items:
                blocks.append(B._block_section('*ADR溢价*'))
                blocks.append(B._block_fields(items))
        except Exception:
            if adr_text:
                blocks.append(B._block_section(adr_text))
```

- [ ] **Step 5: push_daily_report 接线**

在 `app/services/notification.py` `push_daily_report` 内：

(a) 第 1302 行 `etf_text = NotificationService.format_etf_premium_summary()` 之后加：

```python
        adr_text = NotificationService.format_adr_premium_summary()
```

(b) `all_data` 字典（约第 1359 行）`'etf_premium': etf_text,` 之后加：

```python
                    'adr_premium': adr_text,
```

(c) `market_lines` 组装（约第 1414-1415 行）`market_lines.append(etf_text)` 之后加：

```python
        if adr_text:
            market_lines.append(adr_text)
```

(d) `build_market_blocks(...)` 调用（约第 1434-1437 行）末尾加实参：

```python
        msg3_blocks = NotificationService.build_market_blocks(
            indices_text, futures_text, etf_text, sectors_text, technical_text,
            dram_text, earnings.get('text', ''), pe.get('text', ''),
            ai_text, adr_text)
```

- [ ] **Step 6: 跑全量测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_adr_premium.py -v`
Expected: PASS（全部 15 个 test）。

- [ ] **Step 7: 回归 —— 确认没打断既有推送链路**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ -k "notification or briefing or daily" -v > _adr_regr.txt 2>&1; grep -E "passed|failed|error" _adr_regr.txt`
Expected: 无新增 failed/error；跑完 `rm _adr_regr.txt`。

- [ ] **Step 8: Commit**

```bash
rtk git add app/services/notification.py app/llm/prompts/daily_briefing.py tests/test_adr_premium.py && rtk git commit -m "feat(daily): ADR 溢价接入每日推送（文本+Block+GLM）"
```

---

## 收尾说明：HXSCL ratio 待确认（实施后手动）

`skhynix` 的 `ratio` 出厂置 `None` → SK 腿推送恒显「SK海力士 —」。要点亮它需确认 HXSCL（SK海力士未挂牌 OTC ADR）的存托比例：

1. 先确认 HXSCL 在 yfinance 有活跃 `close`（`yf.Ticker('HXSCL').history(period='5d')` 非空）。若长期空，SK 腿保持「—」即符合设计（已知限制，不算 bug）。
2. 若有价：查存托行公告的 ADR:普通股 比例（结构性事实，**不能**用价格反推——TSM 因外资溢价，价格反推会得错值）。锁定后把 `ratio` 写进 `app/config/adr_premium.py` 并补一条 `_compute_premium` 该比例的断言测试。
3. 公司调整 ADR 比例时需手更此配置。

## Self-Review

- **Spec 覆盖**：配置(§1)→Task1；数据层 get_adr_premium_data(§2)→Task1；持久化 prev.json(§3)→Task2；文案 format(§4)→Task3；接线双路+prompt(§5)→Task4；测试(§spec)→各 Task 内 TDD；已知限制→收尾说明。无遗漏。
- **占位扫描**：无 TBD/TODO；HXSCL ratio 是显式设计决策（None + 收尾说明），非占位。
- **类型一致**：`_compute_premium(us_close, home_close, fx_rate, ratio)`、`get_adr_premium_data()->{'pairs':[...]}`、`format_adr_premium_summary()->str`、`build_market_blocks(..., adr_text='')` 在各 Task 间签名一致；`premium_rate`/`prev_premium`/`delta`/`error` 字段名跨 Task 统一。
