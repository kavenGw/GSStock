# 美股四态会话模型与夜盘（暗盘）行情接入 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把美股盯盘时段体系从「盘前/盘后」两态重构为「盘前/盘中/盘后/暗盘」四态，接入 Webull 夜盘行情，并修掉 `marketState=CLOSED` 被误判为盘后的陈价缺陷。

**Architecture:** 时段判定收敛到 `TradingCalendarService.get_us_session()`（本地时钟 + exchange-calendars 交易日历）作为唯一权威；新增 `app/services/webull_quote.py` 作为扩展时段报价源，yfinance 降为盘前/盘后兜底；`unified_stock_data.get_us_extended_quotes()` 保持为唯一出口，内部换源，调用方无感。

**Tech Stack:** Python 3 / Flask / requests / exchange-calendars / pytz / pytest + monkeypatch；前端原生 JS（`app/static/js/watch.js`）。

**Spec:** `docs/superpowers/specs/2026-09-16-us-overnight-session-design.md`

## Global Constraints

- 所有 git / pytest 命令前加 `rtk`，链式 `&&` 中也要。
- 单测命令固定为 `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest ...`，env 赋值必须在 `rtk` 之前。
- `git add` 与 `git commit` 必须在同一条命令链里（并行 session 会清空暂存区），中文 message 走 `.git/MSG.txt` 文件。
- commit message 结尾附 `Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>`。
- 不写多余注释，不留 backup 文件。
- 测试全部 mock HTTP，禁止打真实网络。
- 标识符保持英文不变：`extended`、`get_us_extended_quotes`、`cache_type='extended'`、`watch_extended_alert`、`US_EXT`、`ext`。
- session 枚举值固定为 `'pre' | 'regular' | 'post' | 'overnight' | None`，全仓一致。
- 时段边界一律左闭右开：`[04:00, open)` pre、`[open, close)` regular、`[close, 20:00)` post、`[20:00, 04:00)` overnight。

---

### Task 1: 四态会话模型 `get_us_session`

**Files:**
- Modify: `app/services/trading_calendar.py:55`（常量注释）、`app/services/trading_calendar.py:274-295`（`get_us_extended_session` 整体替换）
- Test: `tests/test_watch_us_extended.py`（替换 `TestUsExtendedSession` 类）

**Interfaces:**
- Consumes: 同文件已有的 `get_market_now`、`_get_timezone`、`is_trading_day(market, date)`、`get_market_hours(market, date) -> (open_time, close_time)`；`timedelta` / `Optional` 已在文件头导入，无需新增 import。
- Produces: `TradingCalendarService.get_us_session(dt: datetime = None) -> Optional[str]`，返回 `'pre' | 'regular' | 'post' | 'overnight' | None`。Task 3/4/6 依赖此签名。`get_us_extended_session` 就此删除，不留兼容壳。

**注意边界约定变更**：旧实现里 ET 16:00 算 regular、20:00 算 post；新实现按左闭右开，16:00 算 post、20:00 算 overnight。旧测试 `test_regular_hours_is_none` 与 `test_2000_is_post_2001_is_none` 会因此改写，这是预期内的。

- [ ] **Step 1: 写失败测试**

替换 `tests/test_watch_us_extended.py` 里整个 `TestUsExtendedSession` 类为：

```python
# 2026-07-06 周一、2026-07-10 周五、2026-07-11 周六、2026-07-12 周日 均为纽约日历
class TestUsSession:
    def test_0359_is_overnight(self):
        assert TradingCalendarService.get_us_session(_et(2026, 7, 6, 3, 59)) == 'overnight'

    def test_0400_is_pre(self):
        assert TradingCalendarService.get_us_session(_et(2026, 7, 6, 4, 0)) == 'pre'

    def test_0929_is_pre(self):
        assert TradingCalendarService.get_us_session(_et(2026, 7, 6, 9, 29)) == 'pre'

    def test_0930_to_1559_is_regular(self):
        assert TradingCalendarService.get_us_session(_et(2026, 7, 6, 9, 30)) == 'regular'
        assert TradingCalendarService.get_us_session(_et(2026, 7, 6, 15, 59)) == 'regular'

    def test_1600_is_post(self):
        assert TradingCalendarService.get_us_session(_et(2026, 7, 6, 16, 0)) == 'post'

    def test_1959_is_post(self):
        assert TradingCalendarService.get_us_session(_et(2026, 7, 6, 19, 59)) == 'post'

    def test_2000_is_overnight(self):
        assert TradingCalendarService.get_us_session(_et(2026, 7, 6, 20, 0)) == 'overnight'

    def test_friday_night_is_not_overnight(self):
        # 周五 20:00 后次日为周六，非交易日 → 无夜盘
        assert TradingCalendarService.get_us_session(_et(2026, 7, 10, 20, 0)) is None
        assert TradingCalendarService.get_us_session(_et(2026, 7, 10, 23, 0)) is None

    def test_sunday_night_is_overnight(self):
        # 周日 20:00 后次日为周一，归属周一的夜盘
        assert TradingCalendarService.get_us_session(_et(2026, 7, 12, 20, 0)) == 'overnight'

    def test_saturday_is_none(self):
        assert TradingCalendarService.get_us_session(_et(2026, 7, 11, 2, 0)) is None
        assert TradingCalendarService.get_us_session(_et(2026, 7, 11, 8, 0)) is None

    def test_half_day_post_starts_at_close(self, monkeypatch):
        # 半日市 13:00 收盘：13:00 起即为 post，而非 regular
        from datetime import time as _time
        monkeypatch.setattr(TradingCalendarService, 'get_market_hours',
                            classmethod(lambda cls, market, dt=None: (_time(9, 30), _time(13, 0))))
        assert TradingCalendarService.get_us_session(_et(2026, 7, 6, 12, 59)) == 'regular'
        assert TradingCalendarService.get_us_session(_et(2026, 7, 6, 13, 0)) == 'post'
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_us_extended.py::TestUsSession -v`
Expected: FAIL，`AttributeError: type object 'TradingCalendarService' has no attribute 'get_us_session'`

- [ ] **Step 3: 实现**

`app/services/trading_calendar.py:55` 的注释改为：

```python
    # 美股盘前/盘后时段边界（ET）；此区间之外为暗盘（夜盘）
    US_EXTENDED_HOURS = (time(4, 0), time(20, 0))
```

把 `get_us_extended_session`（274-295 行）整体替换为：

```python
    @classmethod
    def get_us_session(cls, dt: datetime = None) -> Optional[str]:
        """美股四态时段：'pre' | 'regular' | 'post' | 'overnight' | None

        边界左闭右开：[04:00, open) pre、[open, close) regular、
        [close, 20:00) post、[20:00, 04:00) overnight。

        夜盘（暗盘）归属其结束那天的交易日：周五 20:00 后次日非交易日故无夜盘，
        周日 20:00 起次日为周一故有夜盘。
        """
        market = 'US'
        if dt is None:
            dt = cls.get_market_now(market)
        elif dt.tzinfo is None:
            dt = cls._get_timezone(market).localize(dt)

        current = dt.time()
        ext_open, ext_close = cls.US_EXTENDED_HOURS

        if current >= ext_close:
            return 'overnight' if cls.is_trading_day(market, dt.date() + timedelta(days=1)) else None
        if current < ext_open:
            return 'overnight' if cls.is_trading_day(market, dt.date()) else None

        if not cls.is_trading_day(market, dt.date()):
            return None
        open_time, close_time = cls.get_market_hours(market, dt.date())
        if open_time is None or close_time is None:
            return None
        if current < open_time:
            return 'pre'
        if current < close_time:
            return 'regular'
        return 'post'
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_us_extended.py::TestUsSession -v`
Expected: 11 passed

- [ ] **Step 5: 提交**

```bash
cd /d/Git/stock && cat > .git/MSG.txt <<'MSG'
feat(watch): 美股时段判定扩为四态 get_us_session

- pre/regular/post/overnight 四态，边界统一左闭右开
- 夜盘归属结束日的交易日：周五晚无夜盘、周日晚有夜盘
- post 起算取 get_market_hours 的 close，半日市 13:00 收盘即转 post
- 删除 get_us_extended_session，不留兼容壳

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
rtk git add app/services/trading_calendar.py tests/test_watch_us_extended.py && rtk git commit -F .git/MSG.txt
```

（此时 `tests/test_watch_us_extended.py` 其余用例仍引用旧方法名会失败，Task 3/4/6 依次修复；本步只跑 `::TestUsSession`。）

---

### Task 2: Webull 扩展时段报价模块

**Files:**
- Create: `app/services/webull_quote.py`
- Test: `tests/test_webull_quote.py`（新建）

**Interfaces:**
- Consumes: 无（纯 HTTP 客户端，不依赖本仓其他模块）
- Produces:
  - `resolve_ticker_id(symbol: str) -> int | None`
  - `parse_quote(raw: dict, session: str) -> dict | None`，返回 `{'session', 'price', 'change_pct', 'time', 'source'}`，`source` 恒为 `'webull'`
  - `get_extended_quotes(symbols: list, session: str) -> dict`，形如 `{symbol: quote}`，取不到的 symbol 直接缺席
  - 模块级 `_ticker_ids: dict` 供测试清空
  - Task 3 依赖 `get_extended_quotes`。

- [ ] **Step 1: 写失败测试**

新建 `tests/test_webull_quote.py`：

```python
"""Webull 扩展时段报价：tickerId 解析与缓存、字段映射、session 由调用方给定、失败跳过"""
import pytest

from app.services import webull_quote


@pytest.fixture(autouse=True)
def _clear_ids():
    webull_quote._ticker_ids.clear()
    yield
    webull_quote._ticker_ids.clear()


class _Resp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


SEARCH_PAYLOAD = {'data': [
    {'symbol': 'NVDA', 'regionId': 1, 'tickerId': 111},
    {'symbol': 'NVDAX', 'regionId': 6, 'tickerId': 222},
    {'symbol': 'NVDA', 'regionId': 6, 'tickerId': 913257561},
]}


class TestResolveTickerId:
    def test_picks_us_region_exact_symbol(self, monkeypatch):
        monkeypatch.setattr(webull_quote.requests, 'get',
                            lambda url, **kw: _Resp(SEARCH_PAYLOAD))
        assert webull_quote.resolve_ticker_id('NVDA') == 913257561

    def test_caches_result(self, monkeypatch):
        calls = []

        def fake_get(url, **kw):
            calls.append(url)
            return _Resp(SEARCH_PAYLOAD)

        monkeypatch.setattr(webull_quote.requests, 'get', fake_get)
        webull_quote.resolve_ticker_id('NVDA')
        webull_quote.resolve_ticker_id('NVDA')
        assert len(calls) == 1

    def test_no_match_returns_none(self, monkeypatch):
        monkeypatch.setattr(webull_quote.requests, 'get',
                            lambda url, **kw: _Resp({'data': []}))
        assert webull_quote.resolve_ticker_id('NOPE') is None

    def test_http_failure_returns_none(self, monkeypatch):
        def boom(url, **kw):
            raise RuntimeError('network down')

        monkeypatch.setattr(webull_quote.requests, 'get', boom)
        assert webull_quote.resolve_ticker_id('NVDA') is None


class TestParseQuote:
    def test_ratio_converted_to_percent(self):
        raw = {'pPrice': '213.4712', 'pChRatio': '0.0061',
               'tradeTime': '2026-09-16T11:46:40.516+0000', 'overnight': 0}
        q = webull_quote.parse_quote(raw, 'pre')
        assert q == {'session': 'pre', 'price': 213.47, 'change_pct': 0.61,
                     'time': '2026-09-16T11:46:40.516+0000', 'source': 'webull'}

    def test_negative_ratio(self):
        q = webull_quote.parse_quote({'pPrice': '10', 'pChRatio': '-0.0234'}, 'post')
        assert q['change_pct'] == -2.34 and q['session'] == 'post'

    def test_session_comes_from_caller_not_overnight_flag(self):
        # Webull 说 overnight=0，调用方按时钟给 overnight，以调用方为准
        q = webull_quote.parse_quote({'pPrice': '10', 'pChRatio': '0', 'overnight': 0}, 'overnight')
        assert q['session'] == 'overnight'

    def test_missing_price_returns_none(self):
        assert webull_quote.parse_quote({'pPrice': None, 'pChRatio': '0.01'}, 'pre') is None
        assert webull_quote.parse_quote({'pPrice': '', 'pChRatio': '0.01'}, 'pre') is None
        assert webull_quote.parse_quote({}, 'pre') is None

    def test_missing_ratio_defaults_zero(self):
        assert webull_quote.parse_quote({'pPrice': '10'}, 'pre')['change_pct'] == 0.0


class TestGetExtendedQuotes:
    def _patch(self, monkeypatch, quotes):
        monkeypatch.setattr(webull_quote, 'resolve_ticker_id',
                            lambda symbol: {'NVDA': 1, 'AMD': 2, 'WOLF': 3}.get(symbol))
        monkeypatch.setattr(webull_quote, '_fetch_quote',
                            lambda ticker_id: quotes[ticker_id])

    def test_batch(self, monkeypatch):
        self._patch(monkeypatch, {1: {'pPrice': '10', 'pChRatio': '0.01'},
                                  2: {'pPrice': '20', 'pChRatio': '-0.02'}})
        out = webull_quote.get_extended_quotes(['NVDA', 'AMD'], 'pre')
        assert out['NVDA']['price'] == 10.0 and out['AMD']['change_pct'] == -2.0
        assert all(q['session'] == 'pre' for q in out.values())

    def test_unresolvable_symbol_skipped(self, monkeypatch):
        self._patch(monkeypatch, {1: {'pPrice': '10', 'pChRatio': '0.01'}})
        out = webull_quote.get_extended_quotes(['NVDA', 'UNKNOWN'], 'pre')
        assert set(out) == {'NVDA'}

    def test_fetch_failure_skipped(self, monkeypatch):
        def fetch(ticker_id):
            if ticker_id == 3:
                raise RuntimeError('boom')
            return {'pPrice': '10', 'pChRatio': '0.01'}

        monkeypatch.setattr(webull_quote, 'resolve_ticker_id',
                            lambda symbol: {'NVDA': 1, 'WOLF': 3}.get(symbol))
        monkeypatch.setattr(webull_quote, '_fetch_quote', fetch)
        assert set(webull_quote.get_extended_quotes(['NVDA', 'WOLF'], 'post')) == {'NVDA'}

    def test_empty_inputs(self, monkeypatch):
        assert webull_quote.get_extended_quotes([], 'pre') == {}
        assert webull_quote.get_extended_quotes(['NVDA'], None) == {}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_webull_quote.py -v`
Expected: FAIL，`ModuleNotFoundError: No module named 'app.services.webull_quote'`

- [ ] **Step 3: 实现**

新建 `app/services/webull_quote.py`：

```python
"""Webull 公开行情 — 美股盘前/盘后/夜盘报价（无需 API key）

session 一律由调用方按 TradingCalendarService.get_us_session() 给定；
Webull 返回的 overnight 字段仅用于校验与日志，不参与判定。
"""
import logging
from concurrent.futures import ThreadPoolExecutor

import requests

logger = logging.getLogger(__name__)

SEARCH_URL = 'https://quotes-gw.webullfintech.com/api/search/pc/tickers'
QUOTE_URL = 'https://quotes-gw.webullfintech.com/api/stock/tickerRealTime/getQuote'
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
           'Accept': 'application/json'}
US_REGION_ID = 6
TIMEOUT = 10

_ticker_ids = {}


def resolve_ticker_id(symbol: str) -> int | None:
    """symbol → Webull tickerId，进程内永久缓存（tickerId 稳定不变）"""
    if symbol in _ticker_ids:
        return _ticker_ids[symbol]
    try:
        resp = requests.get(SEARCH_URL,
                            params={'keyword': symbol, 'pageIndex': 1, 'pageSize': 10},
                            headers=HEADERS, timeout=TIMEOUT)
        resp.raise_for_status()
        for item in (resp.json().get('data') or []):
            if item.get('symbol') == symbol and item.get('regionId') == US_REGION_ID:
                _ticker_ids[symbol] = item['tickerId']
                return item['tickerId']
    except Exception as e:
        logger.debug(f'[Webull] {symbol} tickerId 解析失败: {e}')
    return None


def _fetch_quote(ticker_id: int) -> dict:
    resp = requests.get(QUOTE_URL,
                        params={'tickerId': ticker_id, 'includeSecu': 1, 'includeQuote': 1},
                        headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json() or {}


def parse_quote(raw: dict, session: str) -> dict | None:
    """pPrice/pChRatio → 扩展时段报价；pChRatio 是小数比率，×100 转百分比"""
    price = raw.get('pPrice')
    if price in (None, ''):
        return None
    ratio = raw.get('pChRatio')
    return {
        'session': session,
        'price': round(float(price), 2),
        'change_pct': round(float(ratio) * 100, 2) if ratio not in (None, '') else 0.0,
        'time': raw.get('tradeTime'),
        'source': 'webull',
    }


def get_extended_quotes(symbols: list, session: str) -> dict:
    """批量取扩展时段报价 {symbol: quote}；取不到的 symbol 直接缺席"""
    if not symbols or not session:
        return {}

    def fetch_one(symbol: str) -> tuple:
        try:
            ticker_id = resolve_ticker_id(symbol)
            if ticker_id is None:
                return symbol, None
            raw = _fetch_quote(ticker_id)
            quote = parse_quote(raw, session)
            if quote and session == 'overnight' and not raw.get('overnight'):
                logger.debug(f'[Webull] {symbol} 时钟判夜盘但 overnight=0')
            return symbol, quote
        except Exception as e:
            logger.debug(f'[Webull] {symbol} 取价失败: {e}')
            return symbol, None

    result = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        for symbol, quote in executor.map(fetch_one, symbols):
            if quote:
                result[symbol] = quote
    return result
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_webull_quote.py -v`
Expected: 13 passed

- [ ] **Step 5: 提交**

```bash
cd /d/Git/stock && cat > .git/MSG.txt <<'MSG'
feat(data): 新增 Webull 扩展时段报价模块

- resolve_ticker_id 走 /api/search/pc/tickers，regionId==6 精确匹配，进程内永久缓存
- getQuote 单票并发 3 路，pPrice/pChRatio x100 映射为 price/change_pct
- session 由调用方按时钟给定，Webull overnight 字段仅作校验日志

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
rtk git add app/services/webull_quote.py tests/test_webull_quote.py && rtk git commit -F .git/MSG.txt
```

---

### Task 3: `unified_stock_data` 换源 + session 缓存隔离 + 修 CLOSED 误判

**Files:**
- Modify: `app/services/unified_stock_data.py:3351-3425`（`_parse_extended_quote`、`get_us_extended_quotes`、`get_us_extended_cached`）
- Test: `tests/test_watch_us_extended.py`（替换 `TestParseExtendedQuote`、`TestGetUsExtendedQuotes`）

**Interfaces:**
- Consumes: Task 1 的 `TradingCalendarService.get_us_session()`；Task 2 的 `webull_quote.get_extended_quotes(symbols, session)`
- Produces:
  - `UnifiedStockDataService._parse_extended_quote(info: dict, session: str) -> dict | None`（签名新增 `session` 参数，不再从 `marketState` 推断）
  - `get_us_extended_quotes(stock_codes, force_refresh=False) -> dict`（对外签名不变）
  - `get_us_extended_cached(stock_codes) -> dict`（对外签名不变，新增按当前 session 过滤）
  - Task 4/6 依赖 `get_us_extended_cached`。

- [ ] **Step 1: 写失败测试**

替换 `tests/test_watch_us_extended.py` 里的 `TestParseExtendedQuote` 和 `TestGetUsExtendedQuotes` 两个类为：

```python
class TestParseExtendedQuote:
    def test_pre_market(self):
        info = {'preMarketPrice': 212.5175, 'preMarketChangePercent': -2.6444142,
                'preMarketTime': 1789389705}
        q = UnifiedStockDataService._parse_extended_quote(info, 'pre')
        assert q['session'] == 'pre'
        assert q['price'] == 212.52
        assert q['change_pct'] == -2.64
        assert q['time'] == '2026-09-14T08:41:45-04:00'
        assert q['source'] == 'yfinance'

    def test_post_market(self):
        info = {'postMarketPrice': 100.123, 'postMarketChangePercent': 1.234,
                'postMarketTime': 1789430400}
        q = UnifiedStockDataService._parse_extended_quote(info, 'post')
        assert q['price'] == 100.12 and q['change_pct'] == 1.23

    def test_overnight_has_no_yfinance_fallback(self):
        # 修掉旧的 CLOSED→post 误判：夜盘不得再拿停更的 postMarketPrice 冒充
        info = {'marketState': 'CLOSED', 'postMarketPrice': 50.0,
                'postMarketChangePercent': -0.5, 'postMarketTime': 1789430400}
        assert UnifiedStockDataService._parse_extended_quote(info, 'overnight') is None

    def test_regular_and_missing_return_none(self):
        assert UnifiedStockDataService._parse_extended_quote({'preMarketPrice': 1.0}, 'regular') is None
        assert UnifiedStockDataService._parse_extended_quote({}, 'pre') is None
        assert UnifiedStockDataService._parse_extended_quote({'preMarketPrice': None}, 'pre') is None


class TestGetUsExtendedQuotes:
    def _patch_session(self, monkeypatch, session):
        monkeypatch.setattr(TradingCalendarService, 'get_us_session',
                            classmethod(lambda cls, dt=None: session))

    def test_webull_is_primary(self, monkeypatch):
        from app.services import memory_cache as mc
        from app.services import webull_quote
        svc = unified_stock_data_service
        self._patch_session(monkeypatch, 'pre')
        mc.memory_cache.invalidate(cache_type='extended')
        monkeypatch.setattr(webull_quote, 'get_extended_quotes',
                            lambda symbols, session: {
                                c: {'session': session, 'price': 10.0, 'change_pct': 2.0,
                                    'time': 't', 'source': 'webull'} for c in symbols})
        monkeypatch.setattr(svc, '_fetch_yf_info',
                            lambda yf_code: (_ for _ in ()).throw(AssertionError('不应回落 yfinance')))

        out = svc.get_us_extended_quotes(['NVDA', 'AMD'], force_refresh=True)
        assert set(out) == {'NVDA', 'AMD'}
        assert out['NVDA']['source'] == 'webull' and out['NVDA']['session'] == 'pre'

    def test_falls_back_to_yfinance_for_missing(self, monkeypatch):
        from app.services import memory_cache as mc
        from app.services import webull_quote
        svc = unified_stock_data_service
        self._patch_session(monkeypatch, 'post')
        mc.memory_cache.invalidate(cache_type='extended')
        monkeypatch.setattr(webull_quote, 'get_extended_quotes',
                            lambda symbols, session: {'NVDA': {
                                'session': session, 'price': 10.0, 'change_pct': 1.0,
                                'time': 't', 'source': 'webull'}})
        monkeypatch.setattr(svc, '_fetch_yf_info',
                            lambda yf_code: {'postMarketPrice': 5.0,
                                             'postMarketChangePercent': -1.0,
                                             'postMarketTime': 1789430400})

        out = svc.get_us_extended_quotes(['NVDA', 'AMD'], force_refresh=True)
        assert out['NVDA']['source'] == 'webull'
        assert out['AMD']['source'] == 'yfinance' and out['AMD']['price'] == 5.0

    def test_overnight_does_not_fall_back(self, monkeypatch):
        from app.services import memory_cache as mc
        from app.services import webull_quote
        svc = unified_stock_data_service
        self._patch_session(monkeypatch, 'overnight')
        mc.memory_cache.invalidate(cache_type='extended')
        monkeypatch.setattr(webull_quote, 'get_extended_quotes', lambda symbols, session: {})
        monkeypatch.setattr(svc, '_fetch_yf_info',
                            lambda yf_code: (_ for _ in ()).throw(AssertionError('夜盘无兜底')))
        assert svc.get_us_extended_quotes(['NVDA'], force_refresh=True) == {}

    def test_regular_session_returns_empty(self, monkeypatch):
        from app.services import webull_quote
        svc = unified_stock_data_service
        self._patch_session(monkeypatch, 'regular')
        monkeypatch.setattr(webull_quote, 'get_extended_quotes',
                            lambda symbols, session: (_ for _ in ()).throw(AssertionError('盘中不取')))
        assert svc.get_us_extended_quotes(['NVDA'], force_refresh=True) == {}

    def test_cache_isolated_by_session(self, monkeypatch):
        from app.services import memory_cache as mc
        from app.services import webull_quote
        svc = unified_stock_data_service
        mc.memory_cache.invalidate(cache_type='extended')
        self._patch_session(monkeypatch, 'pre')
        monkeypatch.setattr(webull_quote, 'get_extended_quotes',
                            lambda symbols, session: {'NVDA': {
                                'session': session, 'price': 10.0, 'change_pct': 1.0,
                                'time': 't', 'source': 'webull'}})
        svc.get_us_extended_quotes(['NVDA'], force_refresh=True)
        assert svc.get_us_extended_cached(['NVDA'])['NVDA']['price'] == 10.0

        # 切到盘中：盘前价不得串场
        self._patch_session(monkeypatch, 'regular')
        assert svc.get_us_extended_cached(['NVDA']) == {}

        # 切到盘后：缓存里那条是 pre，同样失效
        self._patch_session(monkeypatch, 'post')
        assert svc.get_us_extended_cached(['NVDA']) == {}
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_us_extended.py::TestParseExtendedQuote tests/test_watch_us_extended.py::TestGetUsExtendedQuotes -v`
Expected: FAIL，`_parse_extended_quote() missing 1 required positional argument: 'session'`

- [ ] **Step 3: 实现**

把 `app/services/unified_stock_data.py:3351` 起的整节（到 `get_us_extended_cached` 结束）替换为：

```python
    # ============ 美股扩展时段（盘前/盘后/暗盘） ============
    EXTENDED_CACHE_TYPE = 'extended'
    EXTENDED_TTL_SECONDS = 600

    @staticmethod
    def _fetch_yf_info(yf_code: str) -> dict:
        import yfinance as yf
        return yf.Ticker(yf_code).info or {}

    @staticmethod
    def _parse_extended_quote(info: dict, session: str) -> dict | None:
        """yfinance 兜底解析：按调用方给定的 session 取对应字段

        夜盘无兜底 —— Yahoo 在 ET 20:00 后 marketState 转 CLOSED 但 postMarketPrice
        停在 20:00，拿来冒充夜盘价就是陈价。
        """
        key = {'pre': 'preMarket', 'post': 'postMarket'}.get(session)
        if not key:
            return None
        price = info.get(f'{key}Price')
        if price is None:
            return None
        ts = info.get(f'{key}Time')
        time_str = None
        if ts:
            tz = TradingCalendarService._get_timezone('US')
            time_str = datetime.fromtimestamp(int(ts), tz).isoformat()
        return {
            'session': session,
            'price': round(float(price), 2),
            'change_pct': round(float(info.get(f'{key}ChangePercent') or 0), 2),
            'time': time_str,
            'source': 'yfinance',
        }

    def get_us_extended_quotes(self, stock_codes: list, force_refresh: bool = False) -> dict:
        """美股扩展时段报价 {code: {session, price, change_pct, time, source}}，仅内存缓存

        主源 Webull，缺口由 yfinance 兜底（夜盘无兜底）。
        """
        if not stock_codes:
            return {}
        session = TradingCalendarService.get_us_session()
        if session in (None, 'regular'):
            return {}

        result = {} if force_refresh else self.get_us_extended_cached(stock_codes)
        todo = [c for c in stock_codes if c not in result]
        if not todo:
            return result

        from app.services import webull_quote
        fetched = webull_quote.get_extended_quotes(todo, session)

        missing = [c for c in todo if c not in fetched]
        if missing and session != 'overnight':
            def fallback_one(code: str) -> tuple:
                try:
                    info = self._fetch_yf_info(self._get_yfinance_symbol(code))
                    return code, self._parse_extended_quote(info, session)
                except Exception as e:
                    logger.debug(f"[数据服务.盘前盘后] {code} yfinance 兜底失败: {e}")
                    return code, None

            with ThreadPoolExecutor(max_workers=3) as executor:
                for code, quote in executor.map(fallback_one, missing):
                    if quote:
                        fetched[code] = quote

        now_str = datetime.now().isoformat()
        for code, quote in fetched.items():
            quote['last_fetch_time'] = now_str
            result[code] = quote
            memory_cache.set(code, self.EXTENDED_CACHE_TYPE, quote, ttl=self.EXTENDED_TTL_SECONDS)

        if fetched:
            by_source = {}
            for q in fetched.values():
                by_source[q['source']] = by_source.get(q['source'], 0) + 1
            logger.info(f"[数据服务.盘前盘后] {session} → {len(fetched)}只 {by_source}")
        return result

    def get_us_extended_cached(self, stock_codes: list) -> dict:
        """只读缓存；session 与当前时段不符的条目视为失效，避免跨时段串价"""
        if not stock_codes:
            return {}
        session = TradingCalendarService.get_us_session()
        if session in (None, 'regular'):
            return {}
        cached = memory_cache.get_batch(stock_codes, self.EXTENDED_CACHE_TYPE)
        return {c: q for c, q in cached.items() if q.get('session') == session}
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_us_extended.py::TestParseExtendedQuote tests/test_watch_us_extended.py::TestGetUsExtendedQuotes tests/test_webull_quote.py -v`
Expected: 22 passed

- [ ] **Step 5: 提交**

```bash
cd /d/Git/stock && cat > .git/MSG.txt <<'MSG'
feat(data): 扩展时段报价主源换 Webull，缓存按 session 隔离

- get_us_extended_quotes 先走 Webull，缺口由 yfinance 兜底；夜盘无兜底
- _parse_extended_quote 改为按调用方 session 取字段，不再从 marketState 推断
- 修 CLOSED 误判为盘后：ET 20:00 后 postMarketPrice 已停更，不得冒充夜盘价
- get_us_extended_cached 过滤 session 不符的条目，消除跨时段串价

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
rtk git add app/services/unified_stock_data.py tests/test_watch_us_extended.py && rtk git commit -F .git/MSG.txt
```

---

### Task 4: `/watch/market-status` 四态状态与美股「盘中」文案

**Files:**
- Modify: `app/routes/watch.py:162-178`
- Test: `tests/test_watch_us_extended.py`（替换 `TestMarketStatusExtended`）

**Interfaces:**
- Consumes: Task 1 的 `get_us_session(now)`
- Produces: `/watch/market-status` 的 `status` 新增 `'overnight'`；美股 `trading` 态 `status_text` 为 `'盘中'`，其余市场保持 `'交易中'`。Task 5 依赖 `'overnight'` 这个 status 值。

**关键顺序**：夜盘判定必须排在 `is_trading_day` 的休市分支之前——周日 ET 20:00 不是交易日但属于周一的夜盘。

- [ ] **Step 1: 写失败测试**

替换 `TestMarketStatusExtended` 类为：

```python
class TestMarketStatusExtended:
    def _patch(self, monkeypatch, et_time, is_trading_day=True, is_open=False):
        monkeypatch.setattr(WatchService, 'get_watched_markets', staticmethod(lambda: ['US']))
        tz = pytz.timezone('America/New_York')
        monkeypatch.setattr(TradingCalendarService, 'get_market_now',
                            classmethod(lambda cls, market: tz.localize(et_time)))
        monkeypatch.setattr(TradingCalendarService, 'is_trading_day',
                            classmethod(lambda cls, market, dt=None: is_trading_day))
        monkeypatch.setattr(TradingCalendarService, 'is_market_open',
                            classmethod(lambda cls, market, dt=None: is_open))

    def _us(self):
        return _make_client().get('/watch/market-status').get_json()['data']['US']

    def test_pre_market(self, monkeypatch):
        self._patch(monkeypatch, _et(2026, 7, 6, 8, 0))
        us = self._us()
        assert us['status'] == 'pre_market' and us['status_text'] == '盘前'

    def test_regular_says_pan_zhong(self, monkeypatch):
        self._patch(monkeypatch, _et(2026, 7, 6, 11, 0), is_open=True)
        us = self._us()
        assert us['status'] == 'trading' and us['status_text'] == '盘中'

    def test_post_market(self, monkeypatch):
        self._patch(monkeypatch, _et(2026, 7, 6, 17, 0))
        us = self._us()
        assert us['status'] == 'post_market' and us['status_text'] == '盘后'

    def test_late_night_is_overnight(self, monkeypatch):
        self._patch(monkeypatch, _et(2026, 7, 6, 21, 0))
        us = self._us()
        assert us['status'] == 'overnight' and us['status_text'] == '暗盘'

    def test_early_morning_is_overnight(self, monkeypatch):
        self._patch(monkeypatch, _et(2026, 7, 6, 3, 0))
        us = self._us()
        assert us['status'] == 'overnight' and us['status_text'] == '暗盘'

    def test_sunday_night_overnight_beats_holiday(self, monkeypatch):
        # 周日非交易日，但 20:00 后属周一夜盘，不得显示休市
        self._patch(monkeypatch, _et(2026, 7, 12, 21, 0), is_trading_day=False)
        monkeypatch.setattr(TradingCalendarService, 'get_us_session',
                            classmethod(lambda cls, dt=None: 'overnight'))
        us = self._us()
        assert us['status'] == 'overnight' and us['status_text'] == '暗盘'

    def test_saturday_is_holiday(self, monkeypatch):
        self._patch(monkeypatch, _et(2026, 7, 11, 8, 0), is_trading_day=False)
        monkeypatch.setattr(TradingCalendarService, 'get_us_session',
                            classmethod(lambda cls, dt=None: None))
        assert self._us()['status'] == 'holiday'


def test_non_us_market_keeps_jiao_yi_zhong(monkeypatch):
    monkeypatch.setattr(WatchService, 'get_watched_markets', staticmethod(lambda: ['A']))
    monkeypatch.setattr(TradingCalendarService, 'is_trading_day',
                        classmethod(lambda cls, market, dt=None: True))
    monkeypatch.setattr(TradingCalendarService, 'is_market_open',
                        classmethod(lambda cls, market, dt=None: True))
    a = _make_client().get('/watch/market-status').get_json()['data']['A']
    assert a['status'] == 'trading' and a['status_text'] == '交易中'
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_us_extended.py::TestMarketStatusExtended -v`
Expected: FAIL，`test_regular_says_pan_zhong` 得到 `'交易中'`、`test_late_night_is_overnight` 得到 `'closed'`

- [ ] **Step 3: 实现**

`app/routes/watch.py` 里，把 162-178 行（`ext_session = ...` 到 `status, status_text = 'pre_open', '未开盘'`）替换为：

```python
        us_session = TradingCalendarService.get_us_session(now) if key == 'US' else None

        if us_session == 'overnight':
            status, status_text = 'overnight', '暗盘'
        elif not is_trading_day:
            status, status_text = 'holiday', '休市'
        elif is_open:
            status, status_text = 'trading', ('盘中' if key == 'US' else '交易中')
        elif is_lunch:
            status, status_text = 'lunch', '午休'
        elif us_session == 'pre':
            status, status_text = 'pre_market', '盘前'
        elif us_session == 'post':
            status, status_text = 'post_market', '盘后'
        elif TradingCalendarService.is_after_close(key, now):
            status, status_text = 'closed', '已收盘'
        else:
            status, status_text = 'pre_open', '未开盘'
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_us_extended.py -v`
Expected: 除 `TestPreloadExtended`（Task 6 修）外全部 passed

- [ ] **Step 5: 提交**

```bash
cd /d/Git/stock && cat > .git/MSG.txt <<'MSG'
feat(watch): market-status 支持暗盘态，美股盘中文案改盘中

- status 新增 overnight/暗盘，判定排在休市分支之前（周日晚属周一夜盘）
- 美股 trading 文案改为盘中，A股/港股保持交易中

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
rtk git add app/routes/watch.py tests/test_watch_us_extended.py && rtk git commit -F .git/MSG.txt
```

---

### Task 5: 前端四态渲染

**Files:**
- Modify: `app/static/js/watch.js:595-604`（`_renderExtQuote`）、`app/static/js/watch.js:1260-1269`（`isActiveStatus` / `getStatusIcon`）

**Interfaces:**
- Consumes: Task 3 的 `ext.session` 可取 `'overnight'`；Task 4 的 `status === 'overnight'`
- Produces: 无下游依赖（前端叶子节点）

无自动化测试（原生 JS 无测试基建，与仓内现状一致）；验收走 Task 8 的人工核对。

- [ ] **Step 1: 改 `_renderExtQuote` 的 label**

把 595-604 行替换为：

```javascript
    // 美股盘前/盘后/暗盘报价：涨跌% 单元格下方一行小字，颜色沿用 price-up/down
    _renderExtQuote(ext, market) {
        if (!ext || ext.price == null) return '';
        const label = { pre: '盘前', post: '盘后', overnight: '暗盘' }[ext.session] || '';
        const cls = ext.change_pct > 0 ? 'price-up' : ext.change_pct < 0 ? 'price-down' : 'price-flat';
        const sign = ext.change_pct > 0 ? '+' : '';
        const pct = ext.change_pct != null ? `${sign}${ext.change_pct.toFixed(2)}%` : '--';
        return `<div class="small ${cls}">${label} ${this.formatPrice(ext.price, market)} ${pct}</div>`;
    },
```

- [ ] **Step 2: 改 `isActiveStatus` 与 `getStatusIcon`**

把 1260-1269 行替换为：

```javascript
    // 交易中与美股盘前/盘后/暗盘都视为活跃：价格轮询继续
    isActiveStatus(status) {
        return status === 'trading' || status === 'pre_market'
            || status === 'post_market' || status === 'overnight';
    },

    getStatusIcon(status) {
        const map = { trading: '🟢', lunch: '🟡', closed: '⚫', pre_open: '⚪', holiday: '⚫',
                      pre_market: '🔵', post_market: '🔵', overnight: '🌑' };
        return map[status] || '⚫';
    },
```

- [ ] **Step 3: 语法自检**

Run: `cd /d/Git/stock && node --check app/static/js/watch.js`
Expected: 无输出（语法通过）。若本机无 node，改用 `cd /d/Git/stock && PYTHONIOENCODING=utf-8 python -c "import io; s=io.open('app/static/js/watch.js',encoding='utf-8').read(); print('overnight 出现', s.count('overnight'), '次')"`，预期 3 次。

- [ ] **Step 4: 提交**

```bash
cd /d/Git/stock && cat > .git/MSG.txt <<'MSG'
feat(watch): 前端渲染暗盘时段

- _renderExtQuote label 改 map，新增 overnight 暗盘
- isActiveStatus 纳入 overnight，北京白天页面继续 60s 轮询
- getStatusIcon 加 overnight 图标

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
rtk git add app/static/js/watch.js && rtk git commit -F .git/MSG.txt
```

---

### Task 6: 推送标题与两个策略的时段判定

**Files:**
- Modify: `app/services/notification.py:133-144`（`push_extended_alerts`）
- Modify: `app/strategies/watch_preload/__init__.py:59-77`（`_preload_us_extended`）
- Modify: `app/strategies/watch_extended_alert/__init__.py:25-36`（`scan` 开头的时段判定）
- Test: `tests/test_watch_extended_alert.py`（补 overnight 用例）、`tests/test_watch_us_extended.py`（`TestPreloadExtended` 改打桩目标）

**Interfaces:**
- Consumes: Task 1 的 `get_us_session()`；Task 3 的 `get_us_extended_cached`
- Produces: `NotificationService.push_extended_alerts(session, rows) -> bool`，`session` 取 `'pre' | 'post' | 'overnight'`，其他值返回 `False`

- [ ] **Step 1: 写失败测试**

在 `tests/test_watch_extended_alert.py` 末尾追加（该文件若尚未 import `NotificationService`，在文件头补 `from app.services.notification import NotificationService`）：

```python
class TestOvernightSession:
    def test_overnight_title(self, monkeypatch):
        sent = []
        monkeypatch.setattr(NotificationService, 'send_slack',
                            staticmethod(lambda text, channel=None: sent.append(text) or True))
        rows = [{'code': 'NVDA', 'name': '英伟达', 'price': 213.47, 'change_pct': 5.2}]
        assert NotificationService.push_extended_alerts('overnight', rows) is True
        assert sent[0].startswith('🌑 *美股暗盘异动*')

    def test_pre_post_titles_unchanged(self, monkeypatch):
        sent = []
        monkeypatch.setattr(NotificationService, 'send_slack',
                            staticmethod(lambda text, channel=None: sent.append(text) or True))
        rows = [{'code': 'NVDA', 'name': '英伟达', 'price': 1.0, 'change_pct': 3.5}]
        NotificationService.push_extended_alerts('pre', rows)
        NotificationService.push_extended_alerts('post', rows)
        assert sent[0].startswith('🌙 *美股盘前异动*')
        assert sent[1].startswith('🌙 *美股盘后异动*')

    def test_unknown_session_not_pushed(self, monkeypatch):
        monkeypatch.setattr(NotificationService, 'send_slack',
                            staticmethod(lambda text, channel=None: (_ for _ in ()).throw(
                                AssertionError('盘中不应推送'))))
        rows = [{'code': 'NVDA', 'name': '英伟达', 'price': 1.0, 'change_pct': 9.9}]
        assert NotificationService.push_extended_alerts('regular', rows) is False
```

同时把 `tests/test_watch_us_extended.py` 的 `TestPreloadExtended._setup` 中这一行：

```python
        monkeypatch.setattr(TradingCalendarService, 'get_us_extended_session',
                            classmethod(lambda cls, dt=None: session))
```

改为：

```python
        monkeypatch.setattr(TradingCalendarService, 'get_us_session',
                            classmethod(lambda cls, dt=None: session))
```

并在该类追加：

```python
    def test_overnight_session_fetches(self, monkeypatch):
        strat, called = self._setup(monkeypatch, 'overnight')
        strat.scan()
        assert called == [(['AMD', 'NVDA'], True)]

    def test_regular_session_skips(self, monkeypatch):
        strat, called = self._setup(monkeypatch, 'regular')
        strat.scan()
        assert called == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_extended_alert.py::TestOvernightSession tests/test_watch_us_extended.py::TestPreloadExtended -v`
Expected: FAIL，overnight 标题拿到 `🌙 *美股盘后异动*`（旧的三元 fallback），`test_regular_session_skips` 因旧判定为真而触发取价

- [ ] **Step 3: 实现**

`app/services/notification.py` 的 `push_extended_alerts` 整体替换为：

```python
    @staticmethod
    def push_extended_alerts(session: str, rows: list) -> bool:
        """美股扩展时段异动合并一条：rows 已按 |涨跌幅| 降序，每条 {code,name,price,change_pct}"""
        if not rows:
            return False
        title = {'pre': '🌙 *美股盘前异动*', 'post': '🌙 *美股盘后异动*',
                 'overnight': '🌑 *美股暗盘异动*'}.get(session)
        if not title:
            return False
        lines = [title]
        for r in rows:
            price = f"${r['price']:,.2f}" if r.get('price') is not None else '—'
            lines.append(f"  · *{r['name']}({r['code']})* {price} "
                         f"{NotificationService.fmt_pct(r['change_pct'])}")
        return NotificationService.send_slack('\n'.join(lines), CHANNEL_WATCH)
```

`app/strategies/watch_preload/__init__.py` 的 `_preload_us_extended` 整体替换为：

```python
    def _preload_us_extended(self, us_codes: list[str], tick: int):
        """美股盘前/盘后/暗盘每 3 tick 取一次报价，退避键独立于盘中取价"""
        if not us_codes or not self._should_refresh_market('US', tick):
            return
        from app.services.trading_calendar import TradingCalendarService
        from app.services.unified_stock_data import unified_stock_data_service

        if TradingCalendarService.get_us_session() not in ('pre', 'post', 'overnight'):
            return
        if self._should_skip('US_EXT'):
            return
        try:
            quotes = unified_stock_data_service.get_us_extended_quotes(us_codes, force_refresh=True)
            ok = len(quotes) >= len(us_codes) * 0.5
            if ok:
                logger.debug(f'[盯盘预取] 美股扩展时段预取完成: {len(quotes)}只')
        except Exception as e:
            logger.error(f'[盯盘预取] 美股扩展时段预取失败: {e}')
            ok = False
        self._record_result('US_EXT', ok)
```

`app/strategies/watch_extended_alert/__init__.py` 的 `scan` 里，把：

```python
        session = TradingCalendarService.get_us_extended_session()
```

改为：

```python
        session = TradingCalendarService.get_us_session()
        if session == 'regular':
            session = None
```

其余（`if session != self._session: self._pushed = {}` 等）不动。

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_watch_extended_alert.py tests/test_watch_us_extended.py tests/test_webull_quote.py -v`
Expected: 全部 passed

- [ ] **Step 5: 提交**

```bash
cd /d/Git/stock && cat > .git/MSG.txt <<'MSG'
feat(watch): 暗盘异动推送与预取调度接入四态

- push_extended_alerts 标题改 map，新增美股暗盘异动；未知 session 不推
- watch_preload / watch_extended_alert 时段判定改 get_us_session，盘中不取不推
- 阈值暂不分段，夜盘沿用 threshold_pct 3，待实测噪音后再定

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
rtk git add app/services/notification.py app/strategies/watch_preload/__init__.py app/strategies/watch_extended_alert/__init__.py tests/test_watch_extended_alert.py tests/test_watch_us_extended.py && rtk git commit -F .git/MSG.txt
```

---

### Task 7: 术语清理与文档同步

**Files:**
- Modify: 上述各文件中残留的「暗盘」误用（主要是模块 docstring 与测试首行）
- Modify: `.claude/rules/watch.md:23`、`.claude/rules/notifications.md:39`、`CLAUDE.md`（项目概述数据源清单）

**Interfaces:**
- Consumes: Task 1-6 的全部产物
- Produces: 无代码接口变更；仅措辞与文档

经 Task 1-6 后多数「暗盘」误用已随代码替换消失，本任务收尾剩余处，确保「暗盘」仅在指夜盘时出现。

- [ ] **Step 1: 盘点残留**

Run:
```bash
cd /d/Git/stock && grep -rn "暗盘" --include=*.py --include=*.js --include=*.md app/ tests/ .claude/ CLAUDE.md
```

逐条判断：指夜盘的保留，指盘前/盘后的改掉。已知需改的行：
- `tests/test_watch_us_extended.py:1` → `"""美股扩展时段（盘前/盘中/盘后/暗盘）：时段判断、Webull/yfinance 取价、/prices ext 字段、市场状态文案、预取调度"""`
- `tests/test_watch_extended_alert.py:1` → `"""美股扩展时段异动推送：阈值、首推/复推、时段外重置、合并一条消息、缓存为空不推"""`
- `app/strategies/watch_extended_alert/__init__.py:1` → `"""美股扩展时段异动推送 — 盘前/盘后/暗盘涨跌超阈值合并一条推 Slack（只读缓存，不触发 API）"""`
- `app/strategies/watch_extended_alert/__init__.py:11` → `    description = "美股盘前/盘后/暗盘异动推送"`

- [ ] **Step 2: 更新 `.claude/rules/watch.md:23`**

把该行整段替换为：

```markdown
- **美股扩展时段（盘前/盘中/盘后/暗盘）**：`TradingCalendarService.get_us_session()` 判 ET 四态，边界左闭右开：`[04:00, open)` pre、`[open, close)` regular、`[close, 20:00)` post、`[20:00, 04:00)` overnight（暗盘/夜盘）。夜盘归属其结束日的交易日——周五 20:00 后无夜盘，周日 20:00 起有。post 起算取 `get_market_hours` 的 close，半日市 13:00 收盘即转 post。取价主源 **Webull**（`app/services/webull_quote.py`，无需 key，`pPrice`/`pChRatio×100`，tickerId 进程内永久缓存），缺口由 yfinance `Ticker.info` 的 `preMarket*`/`postMarket*` 兜底，**夜盘无兜底**（Yahoo 在 ET 20:00 后 `marketState=CLOSED` 但 `postMarketPrice` 已停更，拿来冒充即陈价）。仅内存缓存 `cache_type='extended'` TTL 10min，**缓存值带 session，读取时与当前时段不符即失效**；退避键 `US_EXT`。`watch_preload` 在非盘中扩展时段每 3 tick 调 `get_us_extended_quotes(force_refresh=True)`。`/watch/prices` 每条带 `ext`（非美股为 null），`/watch/market-status` 美股返回 `pre_market`「盘前」/`trading`「盘中」/`post_market`「盘后」/`overnight`「暗盘」（A股港股 `trading` 仍为「交易中」），前端 `isActiveStatus` 把四者视为活跃继续 60s 轮询，summary 表涨跌% 下一行小字显示。扩展时段价不进 `watch_alert` 告警/信号/AI；唯一推送口是 `watch_extended_alert` 策略（每分钟只读 `extended` 缓存，`|change_pct| ≥ threshold_pct`(3) 首推、再走 `restep_pct`(2) 才复推，一 tick 合并一条到 `news_watch`，进程内 `_pushed` 状态随时段切换清空、重启可能重推一次）。SK 海力士无美股行情（OTC HXSCL 在 Yahoo 404），只用 000660.KS。
```

- [ ] **Step 3: 更新 `.claude/rules/notifications.md:39`**

把该行替换为：

```markdown
- **美股扩展时段异动** `push_extended_alerts(session, rows)`：标题 `🌙 *美股盘前异动*`/`🌙 *美股盘后异动*`/`🌑 *美股暗盘异动*`，条目 `  · *名称(代码)* $价格 fmt_pct`，一 tick 一条；未知 session 不推。触发与去重逻辑在 `watch_extended_alert` 策略（见 watch.md）。
```

- [ ] **Step 4: 更新 `CLAUDE.md` 数据源清单**

把项目概述里的 `行情补充数据源 同花顺 / Twelve Data / Polygon` 改为：

```markdown
行情补充数据源 同花顺 / Twelve Data / Polygon / Webull（美股盘前盘后暗盘，无需 key）
```

- [ ] **Step 5: 确认无残留误用**

Run:
```bash
cd /d/Git/stock && grep -rn "暗盘" --include=*.py --include=*.js app/ tests/
```
Expected: 每一条都在指夜盘（overnight 语义），无一条指盘前/盘后。

- [ ] **Step 6: 跑全量测试**

Run:
```bash
cd /d/Git/stock && PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ -q > /tmp/pytest_all.txt 2>&1; grep -E "passed|failed|error" /tmp/pytest_all.txt | tail -3
```
Expected: 全绿，无 failed / error

- [ ] **Step 7: 提交**

```bash
cd /d/Git/stock && cat > .git/MSG.txt <<'MSG'
docs(watch): 术语清理，暗盘一词专指夜盘

- 原指盘前/盘后的暗盘全部改为扩展时段或盘前/盘后
- watch.md / notifications.md 更新为四态模型与 Webull 主源
- CLAUDE.md 数据源清单补入 Webull

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
rtk git add app/ tests/ .claude/rules/watch.md .claude/rules/notifications.md CLAUDE.md && rtk git commit -F .git/MSG.txt
```

---

### Task 8: 夜盘语义实测验证（须在北京时间 08:00–16:00 执行）

**Files:**
- Create（临时，跑完删）: `scripts/_verify_overnight.py`
- Modify（仅在验证不通过时）: `app/services/webull_quote.py`、`tests/test_webull_quote.py`

**Interfaces:**
- Consumes: Task 2 的 `webull_quote.get_extended_quotes` / `_fetch_quote` / `resolve_ticker_id`；Task 1 的 `get_us_session`
- Produces: 验证结论；若不达标则触发降级改动（Step 4）

这是整个计划里唯一必须在真实时间窗口完成的步骤。**若当前不在北京 08:00–16:00，跳过本任务并向用户报告「待窗口验证」，不要伪造结论。**

- [ ] **Step 1: 写验证脚本**

创建 `scripts/_verify_overnight.py`：

```python
"""夜盘语义实测：确认 overnight=1 时 pPrice 为夜盘实时价而非 ET 20:00 陈价

判据：两次采样间隔 60s，至少一只票的 pPrice 发生变化。
"""
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import webull_quote
from app.services.trading_calendar import TradingCalendarService

ET = ZoneInfo('America/New_York')
SYMS = ['NVDA', 'AMD', 'XPEV', 'LITE', 'WOLF', 'SOXX']

session = TradingCalendarService.get_us_session()
print(f'ET {datetime.now(ET):%Y-%m-%d %H:%M}  get_us_session() = {session}')
if session != 'overnight':
    print('不在夜盘窗口，验证中止')
    raise SystemExit(1)

first = {}
for sym in SYMS:
    tid = webull_quote.resolve_ticker_id(sym)
    raw = webull_quote._fetch_quote(tid) if tid else {}
    first[sym] = raw
    print(f'{sym:<6} overnight={raw.get("overnight")} pPrice={raw.get("pPrice")} '
          f'close={raw.get("close")} tradeTime={raw.get("tradeTime")} status={raw.get("status")}')

print('\n等待 60s 后二次采样...')
time.sleep(60)

changed = []
for sym in SYMS:
    tid = webull_quote.resolve_ticker_id(sym)
    raw = webull_quote._fetch_quote(tid) if tid else {}
    before, after = first[sym].get('pPrice'), raw.get('pPrice')
    same_as_close = str(after) == str(raw.get('close'))
    if before != after:
        changed.append(sym)
    print(f'{sym:<6} {before} -> {after}  {"变化" if before != after else "未变"}'
          f'{"  [等于收盘价]" if same_as_close else ""}')

print(f'\n结论：{len(changed)}/{len(SYMS)} 只 pPrice 在 60s 内变化 -> '
      f'{"夜盘价有效" if changed else "疑似停更，需降级"}')
```

- [ ] **Step 2: 执行**

Run: `cd /d/Git/stock && PYTHONIOENCODING=utf-8 python scripts/_verify_overnight.py`
Expected: `get_us_session() = overnight`；各票 `overnight=1`；60s 后至少一只 `pPrice` 变化

- [ ] **Step 3: 人工核对页面**

打开 http://127.0.0.1:5000/watch ，确认：美股状态条显示 `🌑 暗盘`；summary 表美股行涨跌% 下方小字为 `暗盘 $价格 ±x.xx%`；页面每 60s 仍在刷新。

- [ ] **Step 4: 若验证不通过则降级**

仅在 Step 2 显示 `pPrice` 全部未变化且等于收盘价时执行。

把 `app/services/webull_quote.py` 里 `fetch_one` 的这两行：

```python
            if quote and session == 'overnight' and not raw.get('overnight'):
                logger.debug(f'[Webull] {symbol} 时钟判夜盘但 overnight=0')
```

改为：

```python
            if quote and session == 'overnight' and not raw.get('overnight'):
                return symbol, None
```

即夜盘时段只信 Webull 自报的 `overnight=1`，否则不给价（前端 `ext` 为 null，只剩状态条的「暗盘」标签）。补一条测试到 `tests/test_webull_quote.py` 的 `TestGetExtendedQuotes`：

```python
    def test_overnight_requires_flag_when_degraded(self, monkeypatch):
        monkeypatch.setattr(webull_quote, 'resolve_ticker_id', lambda symbol: 1)
        monkeypatch.setattr(webull_quote, '_fetch_quote',
                            lambda ticker_id: {'pPrice': '10', 'pChRatio': '0', 'overnight': 0})
        assert webull_quote.get_extended_quotes(['NVDA'], 'overnight') == {}
```

跑 `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_webull_quote.py -v` 确认通过。

- [ ] **Step 5: 删除临时脚本并提交结论**

```bash
cd /d/Git/stock && rm -f scripts/_verify_overnight.py && cat > .git/MSG.txt <<'MSG'
chore(watch): 夜盘语义实测通过，暗盘价接入生效

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>
MSG
rtk git add app/services/webull_quote.py tests/test_webull_quote.py && rtk git commit -F .git/MSG.txt
```

若 Step 4 触发了降级，message 改为「夜盘 pPrice 停更，暗盘降级为仅显示时段标签」并说明。若无文件改动（验证直接通过且未改代码），跳过提交，仅向用户报告结论。

---

## 验收清单

- [ ] `get_us_session` 四态 + 周五晚 / 周日晚 / 半日市三个边界有测试覆盖
- [ ] Webull 模块字段映射、tickerId 缓存、失败跳过有测试覆盖
- [ ] 缓存按 session 隔离，盘前价不串入盘中 / 盘后
- [ ] `marketState=CLOSED` 不再产出盘后陈价
- [ ] `/watch/market-status` 美股四态文案正确，A 股港股「交易中」未受影响
- [ ] 前端暗盘时段继续轮询、标签显示「暗盘」
- [ ] Slack 三种标题正确，盘中不推
- [ ] 全仓「暗盘」一词仅指夜盘
- [ ] `rtk python -m pytest tests/ -q` 全绿
- [ ] Task 8 实测在真实夜盘窗口完成（或明确标注「待窗口验证」）
