# 同花顺金融数据 API 接入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把同花顺（HiThink Fuyao）A 股数据 API 接为实时快照主源、估值口径新能力、三表与能力指标主源，同时服务 app 运行时与投研 skill 采证。

**Architecture:** 新建 `app/services/hithink/`，一个 HTTP 底座（`client.py`）+ 两个消费面（`provider.py` 取价、`financials.py` 报表）。主链路仅改两处：`unified_stock_data._fetch_a_share_prices` 加一个同构闭包、`load_balancer` 的 A 股优先级。未配 key 时 `is_available()` 为 `False`，全部分支跳过，行为与接入前一致。

**Tech Stack:** Python 3.10 / Flask / requests / pytest。零新增第三方依赖（`requests` 已在用）。

**Spec:** `docs/superpowers/specs/2026-09-04-hithink-api-integration-design.md`

## Global Constraints

- Base URL：`https://fuyao.aicubes.cn`，所有端点 **GET**，鉴权头 **`X-api-key`**
- 成功判据：`HTTP 200` **且** 响应体 `code == 0`。只看 HTTP 状态码不够
- 错误码分类：`1xxx`–`2xxx` 调用方可修（缺参/格式/无权限）→ **不重试**；`4001` 限流 → **退避重试**；`5xxx` 服务端 → **有界重试**
- 标的代码用完整 thscode：`600519.SH` / `000001.SZ`
- 空值用 `null`，**不自动补零**
- 时间戳是**毫秒级** Unix
- 环境变量名固定为 `HITHINK_FINANCE_API_KEY`，只从 `os.environ` 读，**绝不写进代码或 git**
- 同花顺 snapshot 的 `volume` 单位是**股**；本仓 A 股契约单位是**手**
- 测试**不打真网**，全部用 fixture mock
- 本项改 `app/`，按本仓分支策略**开独立 git worktree**，不在 main 上动
- 测试平铺 `tests/test_*.py`，不建子目录
- 跑测试命令：`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest ... -v`（env 赋值必须在 `rtk` 之前）

## File Structure

| 文件 | 职责 |
|---|---|
| `app/services/hithink/__init__.py` | 导出 `HithinkClient` / `HithinkError` / `get_client` |
| `app/services/hithink/client.py` | 唯一碰 HTTP 的地方：Session、鉴权头、信封解包、错误码分类重试、thscode 归一、`is_available()` |
| `app/services/hithink/provider.py` | `HithinkProvider(DataSourceProvider)`：快照+估值双端点合并、字段映射、volume 归一、日 K fallback |
| `app/services/hithink/financials.py` | 三表 / indicators / valuations + 按报告期的文件缓存 |
| `tests/fixtures/hithink/*.json` | 2026-09-04 实测真实响应，供全部测试 mock |
| `tests/test_hithink_client.py` | 底座测试 |
| `tests/test_hithink_provider.py` | 取价面测试 |
| `tests/test_hithink_financials.py` | 报表面测试 |
| `tests/test_hithink_integration.py` | 主链路接入 + 安全阀回归 |

**修改**：
- `app/services/unified_stock_data.py` — `VOLUME_SOURCE_UNITS` 加一行；`_fetch_a_share_prices` 加闭包、改优先级参数
- `app/services/load_balancer.py` — `MARKET_SOURCES['A']` 与 `A_SHARE_PRIMARY` / `A_SHARE_SECONDARY`
- `app/services/data_source_providers.py` — `DATA_SOURCE_REGISTRY['A']` 与 `DataSourceFactory.get_provider` 注册表
- `CLAUDE.md` / `README.md` / `.env.sample` — 环境变量三处同步

## 对 Spec 的一处偏离（已确认）

Spec §4.2 写 `primary_sources = ['hithink', 'tencent']`。但 `fetch_with_priority_balancing` 的主源阶段是在多个健康主源间**轮询分摊代码**（`healthy_primary[i % len(healthy_primary)]`），那样写会把一半代码分给腾讯，不是「主源」语义。

**实际实现**：`primary_sources=['hithink']`、`secondary_sources=['tencent', 'sina', 'eastmoney']`。secondary 阶段是**按顺序逐个补投**直到取全，正好实现「同花顺主源、失败立刻降级腾讯、再降新浪/东财、最后 yfinance 兜底」。

---

### Task 1: HTTP 底座 —— thscode 归一与信封解包

**Files:**
- Create: `app/services/hithink/__init__.py`
- Create: `app/services/hithink/client.py`
- Create: `tests/fixtures/hithink/snapshot.json`
- Create: `tests/fixtures/hithink/valuations.json`
- Create: `tests/fixtures/hithink/income_annual.json`
- Create: `tests/fixtures/hithink/indicators.json`
- Test: `tests/test_hithink_client.py`
- Modify: `.env.sample`, `README.md`, `CLAUDE.md`

**Interfaces:**
- Consumes: 无（首个任务）
- Produces:
  - `class HithinkError(Exception)`，属性 `code: int`、`message: str`、`request_id: str | None`
  - `to_thscode(code: str) -> str`
  - `from_thscode(thscode: str) -> str`
  - `class HithinkClient`，方法 `is_available() -> bool`、`get(path: str, params: dict) -> dict`（返回信封里的 `data` 字段）
  - `get_client() -> HithinkClient`（模块级单例）

- [ ] **Step 1: 落 fixture —— 2026-09-04 实测真实响应**

创建 `tests/fixtures/hithink/snapshot.json`：

```json
{
  "code": 0,
  "message": "success",
  "request_id": "901949c090234c9fb069d5d0c47c4900",
  "data": {
    "timestamp": 1788499220000,
    "total": 2,
    "item": [
      {"thscode": "600519.SH", "ticker": "600519", "volume": 3418300, "turnover": 4527667800,
       "last_price": 1330.33, "price_change": 31.45, "price_change_ratio_pct": 2.421317,
       "open_price": 1295.88, "high_price": 1338.86, "low_price": 1295.6, "prev_price": 1298.88},
      {"thscode": "000001.SZ", "ticker": "000001", "volume": 54134044, "turnover": 645069670,
       "last_price": 11.9, "price_change": 0.02, "price_change_ratio_pct": 0.16835,
       "open_price": 11.86, "high_price": 12, "low_price": 11.85, "prev_price": 11.88}
    ]
  }
}
```

创建 `tests/fixtures/hithink/valuations.json`：

```json
{
  "code": 0,
  "message": "success",
  "request_id": "be7d3037f7a84edc84be1347139e7027",
  "data": {
    "timestamp": 1788499220000,
    "total": 1,
    "item": [
      {"thscode": "600519.SH", "ticker": "600519", "name": "贵州茅台",
       "pe_ttm": 20.421708, "pe_mrq": 18.678544, "pb_mrq": 6.618895,
       "ps_ttm": 9.599605, "pcf_ttm": 13.963949}
    ]
  }
}
```

创建 `tests/fixtures/hithink/income_annual.json`：

```json
{
  "code": 0,
  "message": "success",
  "request_id": "63d29363453f4d248d9dde3f2923bbdc",
  "data": {
    "timestamp": 1767110400000,
    "item": [
      {"thscode": "600519.SH", "ticker": "600519", "period": "annual", "fiscal_year": 2025,
       "fiscal_period": "FY", "report_date_ms": 1776355200000, "period_end_ms": 1767110400000,
       "currency": "CNY", "operating_income": 168838102514.79, "operating_costs": 14892277570.91,
       "operating_expenses": 57370818034.33, "sales_fee": 7253499600.68, "manage_fee": 8320061659.66,
       "research_and_development_expenses": 190112246.58, "operating_profit": 114808950164.24,
       "interest_expenses": 175775959.12, "profit_total": 114755261605.08,
       "income_tax_expense": 29444936771.41, "net_profit": 85310324833.67,
       "parent_holder_net_profit": 82320067101.68, "basic_eps": 65.66},
      {"thscode": "600519.SH", "ticker": "600519", "period": "annual", "fiscal_year": 2024,
       "fiscal_period": "FY", "report_date_ms": 1776355200000, "period_end_ms": 1735574400000,
       "currency": "CNY", "operating_income": 170899152276.34, "operating_costs": 13789482367.98,
       "operating_expenses": 54523971452.57, "sales_fee": 5639300059.49, "manage_fee": 9315650060.38,
       "research_and_development_expenses": 218375472.87, "operating_profit": 119688579453.23,
       "interest_expenses": 105127802.03, "profit_total": 119638578194.46,
       "income_tax_expense": 30303850168.56, "net_profit": 89334728025.9,
       "parent_holder_net_profit": 86228146421.62, "basic_eps": 68.64}
    ]
  }
}
```

创建 `tests/fixtures/hithink/indicators.json`：

```json
{
  "code": 0,
  "message": "success",
  "request_id": "93a44775920c433a99dfe2a19ca76750",
  "data": {
    "thscode": "600519.SH",
    "report": "2025-4",
    "abilities": [
      {"ability": "growth", "indicators": [
        {"index_id": "calculate_operating_income_yoy_growth_ratio", "value": "-1.20600400"},
        {"index_id": "calculate_parent_holder_net_profit_yoy_growth_ratio", "value": "-4.53225500"}
      ]},
      {"ability": "profitability", "indicators": [
        {"index_id": "index_weighted_avg_roe", "value": "32.5300"},
        {"index_id": "index_deduct_weighted_avg_roe", "value": "32.5200"},
        {"index_id": "sale_gross_margin", "value": "91.1796"},
        {"index_id": "sale_net_interest_ratio", "value": "50.5279"}
      ]},
      {"ability": "solvency", "indicators": [
        {"index_id": "assets_debt_ratio", "value": "16.4154"},
        {"index_id": "earned_interest_multiple", "value": null}
      ]},
      {"ability": "operation", "indicators": [
        {"index_id": "total_assets_turnover_ratio", "value": "0.5602"}
      ]},
      {"ability": "cash-flow", "indicators": [
        {"index_id": "net_profit_cash_content", "value": "74.73536800"}
      ]}
    ]
  }
}
```

- [ ] **Step 2: 写失败测试**

创建 `tests/test_hithink_client.py`：

```python
import json
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from app.services.hithink.client import (
    HithinkClient, HithinkError, to_thscode, from_thscode,
)

FIXTURES = Path(__file__).parent / 'fixtures' / 'hithink'


def load_fixture(name):
    with open(FIXTURES / name, encoding='utf-8') as f:
        return json.load(f)


@pytest.mark.parametrize('raw,expected', [
    ('600519', '600519.SH'),
    ('sh600519', '600519.SH'),
    ('SH600519', '600519.SH'),
    ('600519.SH', '600519.SH'),
    ('600519.ss', '600519.SH'),
    ('000001', '000001.SZ'),
    ('sz000001', '000001.SZ'),
    ('300750', '300750.SZ'),
    ('688981', '688981.SH'),
])
def test_to_thscode(raw, expected):
    assert to_thscode(raw) == expected


@pytest.mark.parametrize('raw,expected', [
    ('600519.SH', '600519'),
    ('000001.SZ', '000001'),
])
def test_from_thscode(raw, expected):
    assert from_thscode(raw) == expected


def test_is_available_false_without_key():
    with patch.dict(os.environ, {}, clear=True):
        assert HithinkClient().is_available() is False


def test_is_available_true_with_key():
    with patch.dict(os.environ, {'HITHINK_FINANCE_API_KEY': 'sk-test'}, clear=True):
        assert HithinkClient().is_available() is True


def _mock_response(payload, status=200):
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload
    return resp


def test_get_unwraps_envelope_and_sends_auth_header():
    payload = load_fixture('snapshot.json')
    with patch.dict(os.environ, {'HITHINK_FINANCE_API_KEY': 'sk-test'}, clear=True):
        client = HithinkClient()
        with patch.object(client._session, 'get', return_value=_mock_response(payload)) as m:
            data = client.get('/api/a-share/prices/snapshot', {'thscodes': '600519.SH'})

    assert data['total'] == 2
    assert data['item'][0]['thscode'] == '600519.SH'
    assert m.call_args.kwargs['headers']['X-api-key'] == 'sk-test'


def test_get_raises_on_nonzero_code_even_with_http_200():
    payload = {'code': 2001, 'message': '无权限', 'request_id': 'req-1'}
    with patch.dict(os.environ, {'HITHINK_FINANCE_API_KEY': 'sk-test'}, clear=True):
        client = HithinkClient()
        with patch.object(client._session, 'get', return_value=_mock_response(payload)):
            with pytest.raises(HithinkError) as exc:
                client.get('/api/a-share/prices/snapshot', {})

    assert exc.value.code == 2001
    assert exc.value.request_id == 'req-1'


def test_get_raises_without_key():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(HithinkError):
            HithinkClient().get('/api/a-share/prices/snapshot', {})
```

- [ ] **Step 3: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_hithink_client.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'app.services.hithink'`

- [ ] **Step 4: 实现 client.py**

创建 `app/services/hithink/__init__.py`：

```python
from app.services.hithink.client import (
    HithinkClient, HithinkError, get_client, to_thscode, from_thscode,
)

__all__ = ['HithinkClient', 'HithinkError', 'get_client', 'to_thscode', 'from_thscode']
```

创建 `app/services/hithink/client.py`：

```python
"""同花顺（HiThink Fuyao）金融数据 API 底座

唯一碰 HTTP 的地方。成功判据是 HTTP 200 且信封 code == 0。
未配 HITHINK_FINANCE_API_KEY 时 is_available() 返回 False，上游分支全部跳过。
"""
import logging
import os
import threading

import requests

logger = logging.getLogger(__name__)

BASE_URL = 'https://fuyao.aicubes.cn'
ENV_KEY = 'HITHINK_FINANCE_API_KEY'
TIMEOUT = 15


class HithinkError(Exception):
    def __init__(self, message, code=None, request_id=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.request_id = request_id


def to_thscode(code: str) -> str:
    """任意形态 A 股代码 → thscode（600519.SH）。"""
    c = code.strip()
    up = c.upper()
    if up.endswith('.SH') or up.endswith('.SZ'):
        return up
    if up.endswith('.SS'):
        return f"{up[:-3]}.SH"
    if up.startswith('SH') or up.startswith('SZ'):
        return f"{up[2:]}.{up[:2]}"
    digits = ''.join(ch for ch in up if ch.isdigit())
    suffix = 'SH' if digits[:1] in ('6', '9') else 'SZ'
    return f"{digits}.{suffix}"


def from_thscode(thscode: str) -> str:
    """thscode → 裸 6 位代码。"""
    return thscode.strip().upper().split('.')[0]


class HithinkClient:
    def __init__(self):
        self._session = requests.Session()

    @property
    def api_key(self):
        return os.environ.get(ENV_KEY, '').strip()

    def is_available(self) -> bool:
        return bool(self.api_key)

    def get(self, path: str, params: dict) -> dict:
        if not self.is_available():
            raise HithinkError(f'{ENV_KEY} 未配置')

        url = f"{BASE_URL}{path}"
        resp = self._session.get(
            url, params=params,
            headers={'X-api-key': self.api_key},
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            raise HithinkError(f'HTTP {resp.status_code}', code=resp.status_code)

        payload = resp.json()
        code = payload.get('code')
        if code != 0:
            raise HithinkError(
                payload.get('message', '未知错误'),
                code=code,
                request_id=payload.get('request_id'),
            )
        return payload.get('data') or {}


_client = None
_lock = threading.Lock()


def get_client() -> HithinkClient:
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                _client = HithinkClient()
    return _client
```

- [ ] **Step 5: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_hithink_client.py -v`
Expected: 全部 PASS

- [ ] **Step 6: 三处配置同步**

`.env.sample` 在 Polygon 段之后加：

```
# 同花顺 HiThink Fuyao — A股行情/三表/估值（不设累计调用上限）
# 注册: https://fuyao.aicubes.cn/
# HITHINK_FINANCE_API_KEY=
```

`README.md` 的环境变量表加一行：`HITHINK_FINANCE_API_KEY` — 同花顺 A 股行情/财务/估值 API key，未配置则该数据源整体跳过，行为与接入前一致。

`CLAUDE.md` 项目概述那段的数据源列表，把「行情补充数据源 Twelve Data / Polygon」改为「行情补充数据源 同花顺 / Twelve Data / Polygon」。

- [ ] **Step 7: Commit**

```bash
git add app/services/hithink/ tests/test_hithink_client.py tests/fixtures/hithink/ .env.sample README.md CLAUDE.md && git commit -m "feat(hithink): HTTP 底座 —— 信封解包/thscode 归一/未配 key 安全阀"
```

---

### Task 2: 错误码分类与限流退避

**Files:**
- Modify: `app/services/hithink/client.py`
- Test: `tests/test_hithink_client.py`

**Interfaces:**
- Consumes: Task 1 的 `HithinkClient.get` / `HithinkError`
- Produces: `HithinkClient.get` 增加重试行为；模块常量 `MAX_RETRIES = 3`、`BACKOFF_BASE = 0.5`

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_hithink_client.py`：

```python
def _client_with_key():
    return HithinkClient()


def test_4001_retries_with_backoff_then_succeeds():
    rate_limited = {'code': 4001, 'message': '限流', 'request_id': 'r'}
    ok = load_fixture('snapshot.json')
    with patch.dict(os.environ, {'HITHINK_FINANCE_API_KEY': 'sk-test'}, clear=True):
        client = _client_with_key()
        responses = [_mock_response(rate_limited), _mock_response(ok)]
        with patch.object(client._session, 'get', side_effect=responses) as m:
            with patch('app.services.hithink.client.time.sleep') as sleep_mock:
                data = client.get('/api/a-share/prices/snapshot', {})

    assert data['total'] == 2
    assert m.call_count == 2
    assert sleep_mock.call_count == 1


def test_5xxx_retries_bounded_then_raises():
    err = {'code': 5001, 'message': '服务端异常', 'request_id': 'r'}
    with patch.dict(os.environ, {'HITHINK_FINANCE_API_KEY': 'sk-test'}, clear=True):
        client = _client_with_key()
        with patch.object(client._session, 'get', return_value=_mock_response(err)) as m:
            with patch('app.services.hithink.client.time.sleep'):
                with pytest.raises(HithinkError):
                    client.get('/api/a-share/prices/snapshot', {})

    assert m.call_count == 3


@pytest.mark.parametrize('code', [1001, 2001])
def test_client_side_errors_do_not_retry(code):
    err = {'code': code, 'message': '缺参', 'request_id': 'r'}
    with patch.dict(os.environ, {'HITHINK_FINANCE_API_KEY': 'sk-test'}, clear=True):
        client = _client_with_key()
        with patch.object(client._session, 'get', return_value=_mock_response(err)) as m:
            with pytest.raises(HithinkError):
                client.get('/api/a-share/prices/snapshot', {})

    assert m.call_count == 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_hithink_client.py -k "retries or do_not_retry" -v`
Expected: FAIL —— `4001` 不重试，`m.call_count == 1`

- [ ] **Step 3: 实现重试**

`client.py` 顶部加 `import time`，并加常量：

```python
MAX_RETRIES = 3
BACKOFF_BASE = 0.5


def _is_retryable(code) -> bool:
    """4001 限流与 5xxx 服务端异常可重试；1xxx-2xxx 调用方问题不重试。"""
    if code == 4001:
        return True
    return isinstance(code, int) and 5000 <= code < 6000
```

把 `get` 方法体改为：

```python
    def get(self, path: str, params: dict) -> dict:
        if not self.is_available():
            raise HithinkError(f'{ENV_KEY} 未配置')

        url = f"{BASE_URL}{path}"
        last_error = None

        for attempt in range(MAX_RETRIES):
            resp = self._session.get(
                url, params=params,
                headers={'X-api-key': self.api_key},
                timeout=TIMEOUT,
            )
            if resp.status_code != 200:
                raise HithinkError(f'HTTP {resp.status_code}', code=resp.status_code)

            payload = resp.json()
            code = payload.get('code')
            if code == 0:
                return payload.get('data') or {}

            last_error = HithinkError(
                payload.get('message', '未知错误'),
                code=code,
                request_id=payload.get('request_id'),
            )
            if not _is_retryable(code):
                raise last_error

            if attempt < MAX_RETRIES - 1:
                delay = BACKOFF_BASE * (2 ** attempt)
                logger.warning(f'[同花顺] code={code} 退避 {delay}s 后重试 ({attempt + 1}/{MAX_RETRIES})')
                time.sleep(delay)

        raise last_error
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_hithink_client.py -v`
Expected: PASS（全部）

- [ ] **Step 5: Commit**

```bash
git add app/services/hithink/client.py tests/test_hithink_client.py && git commit -m "feat(hithink): 错误码分类与 4001/5xxx 退避重试"
```

---

### Task 3: 财务面 —— 三表、指标、估值

**Files:**
- Create: `app/services/hithink/financials.py`
- Test: `tests/test_hithink_financials.py`

**Interfaces:**
- Consumes: Task 1–2 的 `get_client()` / `to_thscode` / `HithinkError`
- Produces:
  - `get_income_statements(code: str, period: str = 'annual', limit: int = 5) -> list[dict]`
  - `get_balance_sheets(code, period='annual', limit=5) -> list[dict]`
  - `get_cash_flow_statements(code, period='annual', limit=5) -> list[dict]`
  - `get_indicators(code: str, report: str) -> dict`（扁平化：`{index_id: float | None}`，另含 `_abilities: {ability: {index_id: value}}`）
  - `get_valuations(codes: list[str]) -> dict`（`{裸代码: {name, pe_ttm, pe_mrq, pb_mrq, ps_ttm, pcf_ttm}}`）

- [ ] **Step 1: 写失败测试**

创建 `tests/test_hithink_financials.py`：

```python
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.hithink import financials

FIXTURES = Path(__file__).parent / 'fixtures' / 'hithink'


def load_fixture(name):
    with open(FIXTURES / name, encoding='utf-8') as f:
        return json.load(f)


def test_income_statements_returns_periods_newest_first():
    data = load_fixture('income_annual.json')['data']
    with patch.object(financials, '_get', return_value=data) as m:
        rows = financials.get_income_statements('600519', period='annual', limit=2)

    assert [r['fiscal_year'] for r in rows] == [2025, 2024]
    assert rows[0]['operating_income'] == pytest.approx(168838102514.79)
    assert rows[0]['parent_holder_net_profit'] == pytest.approx(82320067101.68)
    assert m.call_args[0][1]['thscode'] == '600519.SH'
    assert m.call_args[0][1]['limit'] == 2


def test_income_statements_normalizes_bare_and_prefixed_codes():
    data = load_fixture('income_annual.json')['data']
    for raw in ('600519', 'sh600519', '600519.SH'):
        with patch.object(financials, '_get', return_value=data) as m:
            financials.get_income_statements(raw)
        assert m.call_args[0][1]['thscode'] == '600519.SH'


def test_indicators_flattens_abilities_array():
    data = load_fixture('indicators.json')['data']
    with patch.object(financials, '_get', return_value=data):
        ind = financials.get_indicators('600519', report='2025-4')

    # abilities 是数组不是字典，必须迭代
    assert ind['index_weighted_avg_roe'] == pytest.approx(32.53)
    assert ind['sale_gross_margin'] == pytest.approx(91.1796)
    assert ind['assets_debt_ratio'] == pytest.approx(16.4154)
    assert ind['calculate_operating_income_yoy_growth_ratio'] == pytest.approx(-1.206004)
    # null 保留为 None，不补零
    assert ind['earned_interest_multiple'] is None
    # 分组视图保留
    assert set(ind['_abilities']) == {
        'growth', 'profitability', 'solvency', 'operation', 'cash-flow'
    }
    assert ind['_abilities']['profitability']['index_deduct_weighted_avg_roe'] == pytest.approx(32.52)


def test_valuations_keyed_by_bare_code():
    data = load_fixture('valuations.json')['data']
    with patch.object(financials, '_get', return_value=data) as m:
        val = financials.get_valuations(['600519'])

    assert m.call_args[0][1]['thscodes'] == '600519.SH'
    assert val['600519']['name'] == '贵州茅台'
    assert val['600519']['pe_ttm'] == pytest.approx(20.421708)
    assert val['600519']['pb_mrq'] == pytest.approx(6.618895)


def test_valuations_empty_codes_short_circuits():
    with patch.object(financials, '_get') as m:
        assert financials.get_valuations([]) == {}
    m.assert_not_called()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_hithink_financials.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'app.services.hithink.financials'`

- [ ] **Step 3: 实现 financials.py**

```python
"""同花顺财务面：三表 / 能力指标 / 估值快照

失败不静默降级——取不到就抛。悄悄回落到旧口径的财务数字会直接写进建档，
比取不到危险得多。
"""
import logging

from app.services.hithink.client import get_client, to_thscode, from_thscode

logger = logging.getLogger(__name__)

_INCOME = '/api/a-share/financials/income-statements'
_BALANCE = '/api/a-share/financials/balance-sheets'
_CASHFLOW = '/api/a-share/financials/cash-flow-statements'
_INDICATORS = '/api/a-share/financials/indicators'
_VALUATIONS = '/api/a-share/valuations/snapshot'


def _get(path, params):
    return get_client().get(path, params)


def _to_float(v):
    """空值保留 None，不补零。"""
    if v is None or v == '':
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _statements(path, code, period, limit):
    data = _get(path, {'thscode': to_thscode(code), 'period': period, 'limit': limit})
    items = data.get('item') or []
    return sorted(items, key=lambda r: r.get('period_end_ms') or 0, reverse=True)


def get_income_statements(code, period='annual', limit=5):
    return _statements(_INCOME, code, period, limit)


def get_balance_sheets(code, period='annual', limit=5):
    return _statements(_BALANCE, code, period, limit)


def get_cash_flow_statements(code, period='annual', limit=5):
    return _statements(_CASHFLOW, code, period, limit)


def get_indicators(code, report):
    """report 形如 '2025-4'（4=年报，1-3=季报）。

    上游 abilities 是数组不是字典，必须迭代。
    """
    data = _get(_INDICATORS, {'thscode': to_thscode(code), 'report': report})
    flat = {}
    grouped = {}
    for block in data.get('abilities') or []:
        ability = block.get('ability')
        bucket = grouped.setdefault(ability, {})
        for ind in block.get('indicators') or []:
            val = _to_float(ind.get('value'))
            flat[ind['index_id']] = val
            bucket[ind['index_id']] = val
    flat['_abilities'] = grouped
    return flat


def get_valuations(codes):
    """批量估值快照，返回 {裸代码: {...}}。"""
    if not codes:
        return {}
    thscodes = ','.join(to_thscode(c) for c in codes)
    data = _get(_VALUATIONS, {'thscodes': thscodes})
    result = {}
    for item in data.get('item') or []:
        result[from_thscode(item['thscode'])] = {
            'name': item.get('name'),
            'pe_ttm': _to_float(item.get('pe_ttm')),
            'pe_mrq': _to_float(item.get('pe_mrq')),
            'pb_mrq': _to_float(item.get('pb_mrq')),
            'ps_ttm': _to_float(item.get('ps_ttm')),
            'pcf_ttm': _to_float(item.get('pcf_ttm')),
        }
    return result
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_hithink_financials.py -v`
Expected: 全部 PASS

- [ ] **Step 5: Commit**

```bash
git add app/services/hithink/financials.py tests/test_hithink_financials.py && git commit -m "feat(hithink): 三表/能力指标/估值快照（abilities 数组扁平化）"
```

---

### Task 4: 财务缓存 —— TTL 按报告期而非天数

**Files:**
- Modify: `app/services/hithink/financials.py`
- Test: `tests/test_hithink_financials.py`

**Interfaces:**
- Consumes: Task 3 的 `_get` / `get_income_statements` / `get_indicators`
- Produces: `_cache_path(kind: str, key: str) -> Path`、`_cached(kind, key, loader, ttl_seconds)`；模块常量 `CACHE_DIR`、`INFLIGHT_TTL = 6 * 3600`

**说明**：`get_valuations` **不缓存** —— 估值随价格逐笔变，缓存会给出过期 PE。只缓存三表与 indicators。

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_hithink_financials.py`：

```python
def test_disclosed_annual_report_cached_forever(tmp_path):
    data = load_fixture('income_annual.json')['data']
    with patch.object(financials, 'CACHE_DIR', tmp_path):
        with patch.object(financials, '_get', return_value=data) as m:
            first = financials.get_income_statements('600519', period='annual', limit=2)
            second = financials.get_income_statements('600519', period='annual', limit=2)

    assert m.call_count == 1
    assert first == second


def test_cache_key_separates_period_and_limit(tmp_path):
    data = load_fixture('income_annual.json')['data']
    with patch.object(financials, 'CACHE_DIR', tmp_path):
        with patch.object(financials, '_get', return_value=data) as m:
            financials.get_income_statements('600519', period='annual', limit=2)
            financials.get_income_statements('600519', period='annual', limit=5)
            financials.get_income_statements('600519', period='quarterly', limit=2)

    assert m.call_count == 3


def test_valuations_never_cached(tmp_path):
    data = load_fixture('valuations.json')['data']
    with patch.object(financials, 'CACHE_DIR', tmp_path):
        with patch.object(financials, '_get', return_value=data) as m:
            financials.get_valuations(['600519'])
            financials.get_valuations(['600519'])

    assert m.call_count == 2
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_hithink_financials.py -k cache -v`
Expected: FAIL —— `AttributeError: module ... has no attribute 'CACHE_DIR'`

- [ ] **Step 3: 实现缓存**

`financials.py` 顶部补 import 与常量：

```python
import hashlib
import json
import time
from pathlib import Path

CACHE_DIR = Path('data/cache/hithink')
INFLIGHT_TTL = 6 * 3600  # 在途报告期 6 小时
```

加缓存工具函数：

```python
def _cache_path(kind, key):
    digest = hashlib.md5(key.encode('utf-8')).hexdigest()[:16]
    return Path(CACHE_DIR) / kind / f'{digest}.json'


def _is_disclosed(payload):
    """已披露的历史报告期永不过期；在途/未来期给 6 小时。

    判据：最新一期的 period_end_ms 已经过去 —— 报表期已结束即视为已定稿。
    """
    rows = payload if isinstance(payload, list) else [payload]
    ends = [r.get('period_end_ms') for r in rows if isinstance(r, dict) and r.get('period_end_ms')]
    if not ends:
        return False
    return max(ends) / 1000 < time.time()


def _cached(kind, key, loader):
    path = _cache_path(kind, key)
    if path.exists():
        try:
            with open(path, encoding='utf-8') as f:
                entry = json.load(f)
            if entry.get('forever') or time.time() - entry['saved_at'] < INFLIGHT_TTL:
                return entry['payload']
        except (OSError, ValueError, KeyError):
            logger.warning(f'[同花顺.缓存] 读取失败，回源: {path}')

    payload = loader()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(
                {'saved_at': time.time(), 'forever': _is_disclosed(payload), 'payload': payload},
                f, ensure_ascii=False,
            )
    except OSError as e:
        logger.warning(f'[同花顺.缓存] 写入失败（不影响取数）: {e}')
    return payload
```

把 `_statements` 与 `get_indicators` 改为走缓存：

```python
def _statements(path, code, period, limit):
    ths = to_thscode(code)

    def loader():
        data = _get(path, {'thscode': ths, 'period': period, 'limit': limit})
        items = data.get('item') or []
        return sorted(items, key=lambda r: r.get('period_end_ms') or 0, reverse=True)

    return _cached('statements', f'{path}|{ths}|{period}|{limit}', loader)
```

`get_indicators` 的函数体改为：

```python
def get_indicators(code, report):
    """report 形如 '2025-4'（4=年报，1-3=季报）。

    上游 abilities 是数组不是字典，必须迭代。
    """
    ths = to_thscode(code)

    def loader():
        data = _get(_INDICATORS, {'thscode': ths, 'report': report})
        flat = {}
        grouped = {}
        for block in data.get('abilities') or []:
            ability = block.get('ability')
            bucket = grouped.setdefault(ability, {})
            for ind in block.get('indicators') or []:
                val = _to_float(ind.get('value'))
                flat[ind['index_id']] = val
                bucket[ind['index_id']] = val
        flat['_abilities'] = grouped
        return flat

    return _cached('indicators', f'{ths}|{report}', loader)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_hithink_financials.py -v`
Expected: PASS（全部）

- [ ] **Step 5: 确认缓存目录已被 gitignore**

Run: `git check-ignore -v data/cache/hithink/x.json`
Expected: 输出匹配的 `.gitignore` 规则。若无输出（未被忽略），在 `.gitignore` 追加 `data/cache/` 并说明。

- [ ] **Step 6: Commit**

```bash
git add app/services/hithink/financials.py tests/test_hithink_financials.py .gitignore && git commit -m "feat(hithink): 财务缓存 TTL 按报告期（已披露永不过期/在途 6h）"
```

---

### Task 5: 取价面 —— 快照与估值双端点合并

**Files:**
- Create: `app/services/hithink/provider.py`
- Modify: `app/services/unified_stock_data.py`（`VOLUME_SOURCE_UNITS` 加一行）
- Test: `tests/test_hithink_provider.py`

**Interfaces:**
- Consumes: Task 1–3 的 `get_client` / `to_thscode` / `from_thscode` / `financials.get_valuations`
- Produces:
  - `fetch_snapshot(codes: list[str], now_str: str) -> dict` —— `{裸代码: 价格 dict}`，键为 `code, name, current_price, change, change_percent, volume, high, low, open, prev_close, pe_ttm, pb, ps_ttm, last_fetch_time, market`
  - `class HithinkProvider(DataSourceProvider)`，`name = 'hithink'`、`market = 'A'`

**Volume 铁律**：同花顺 `volume` 单位是**股**，A 股契约是**手**，必须走 `_normalize_volume(v, 'hithink_snapshot', 'A')`（会 `// 100`）。裸赋值会让成交量静默差 100 倍，且量能只进图表不进告警阈值，几乎不会被发现。

- [ ] **Step 1: 登记 volume 单位**

`app/services/unified_stock_data.py` 的 `VOLUME_SOURCE_UNITS` 字典末尾（`'yfinance': 'shares',` 之后）加：

```python
    'hithink_snapshot': 'shares',   # 同花顺 /prices/snapshot volume（实测 600519 为股）
```

注意：`_normalize_volume` 对未登记的 source 抛 `KeyError`，这一步不做后面全挂。
`VOLUME_UNIT_SCHEMA_VERSION` **不需要 bump** —— 只新增了源，未改变任何既有源的单位契约，已入库缓存仍然有效。

- [ ] **Step 2: 写失败测试**

创建 `tests/test_hithink_provider.py`：

```python
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from app.services.hithink import provider

FIXTURES = Path(__file__).parent / 'fixtures' / 'hithink'


def load_fixture(name):
    with open(FIXTURES / name, encoding='utf-8') as f:
        return json.load(f)


SNAPSHOT_DATA = load_fixture('snapshot.json')['data']
VALUATION_DATA = load_fixture('valuations.json')['data']


def _patched_fetch(codes, now_str='2026-09-04 15:00:00'):
    """snapshot 走 _get，估值走 financials.get_valuations。"""
    from app.services.hithink import financials
    vals = {
        item['thscode'].split('.')[0]: {
            'name': item['name'], 'pe_ttm': item['pe_ttm'], 'pe_mrq': item['pe_mrq'],
            'pb_mrq': item['pb_mrq'], 'ps_ttm': item['ps_ttm'], 'pcf_ttm': item['pcf_ttm'],
        }
        for item in VALUATION_DATA['item']
    }
    with patch.object(provider, '_get', return_value=SNAPSHOT_DATA):
        with patch.object(financials, 'get_valuations', return_value=vals):
            return provider.fetch_snapshot(codes, now_str)


def test_field_mapping():
    r = _patched_fetch(['600519', '000001'])['600519']

    assert r['code'] == '600519'
    assert r['current_price'] == pytest.approx(1330.33)
    assert r['prev_close'] == pytest.approx(1298.88)
    assert r['open'] == pytest.approx(1295.88)
    assert r['high'] == pytest.approx(1338.86)
    assert r['low'] == pytest.approx(1295.6)
    assert r['change'] == pytest.approx(31.45)
    assert r['change_percent'] == pytest.approx(2.421317)
    assert r['market'] == 'A'
    assert r['last_fetch_time'] == '2026-09-04 15:00:00'


def test_volume_normalized_shares_to_lots():
    r = _patched_fetch(['600519'])['600519']
    # 上游 3418300 股 → A 股契约「手」= // 100
    assert r['volume'] == 34183


def test_valuation_merged_in():
    r = _patched_fetch(['600519'])['600519']
    assert r['name'] == '贵州茅台'
    assert r['pe_ttm'] == pytest.approx(20.421708)
    assert r['pb'] == pytest.approx(6.618895)
    assert r['ps_ttm'] == pytest.approx(9.599605)


def test_missing_valuation_degrades_to_code_as_name():
    """估值端点失败不能拖垮取价——价格是主产物。"""
    from app.services.hithink import financials
    with patch.object(provider, '_get', return_value=SNAPSHOT_DATA):
        with patch.object(financials, 'get_valuations', side_effect=Exception('boom')):
            r = provider.fetch_snapshot(['600519'], '2026-09-04 15:00:00')['600519']

    assert r['current_price'] == pytest.approx(1330.33)
    assert r['name'] == '600519'
    assert r['pe_ttm'] is None
    assert r['pb'] is None


def test_empty_codes_short_circuits():
    with patch.object(provider, '_get') as m:
        assert provider.fetch_snapshot([], '2026-09-04 15:00:00') == {}
    m.assert_not_called()
```

- [ ] **Step 3: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_hithink_provider.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'app.services.hithink.provider'`

- [ ] **Step 4: 实现 provider.py 的取价部分**

```python
"""同花顺取价面

snapshot 端点不返回中文名，valuations 端点返回 name 且同样支持批量，
故一次取价并发打两个端点再合并——补齐 name，并白拿 pe_ttm / pb / ps_ttm。
估值端点失败不拖垮取价：价格是主产物，估值降级为 None。
"""
import logging
from concurrent.futures import ThreadPoolExecutor

from app.services.data_source_providers import DataSourceProvider
from app.services.hithink.client import get_client, to_thscode, from_thscode

logger = logging.getLogger(__name__)

_SNAPSHOT = '/api/a-share/prices/snapshot'
_HISTORICAL = '/api/a-share/prices/historical'


def _get(path, params):
    return get_client().get(path, params)


def fetch_snapshot(codes, now_str):
    """批量取 A 股快照，返回 {裸代码: 价格 dict}。"""
    if not codes:
        return {}

    from app.services.hithink import financials
    from app.services.unified_stock_data import _normalize_volume

    thscodes = ','.join(to_thscode(c) for c in codes)

    with ThreadPoolExecutor(max_workers=2) as executor:
        snap_future = executor.submit(_get, _SNAPSHOT, {'thscodes': thscodes})
        val_future = executor.submit(financials.get_valuations, codes)

        data = snap_future.result()
        try:
            valuations = val_future.result()
        except Exception as e:
            logger.warning(f'[同花顺.估值] 合并失败，价格不受影响: {e}')
            valuations = {}

    result = {}
    for item in data.get('item') or []:
        code = from_thscode(item['thscode'])
        val = valuations.get(code) or {}
        result[code] = {
            'code': code,
            'name': val.get('name') or code,
            'current_price': item.get('last_price'),
            'change': item.get('price_change'),
            'change_percent': item.get('price_change_ratio_pct'),
            'volume': _normalize_volume(item.get('volume'), 'hithink_snapshot', 'A'),
            'high': item.get('high_price'),
            'low': item.get('low_price'),
            'open': item.get('open_price'),
            'prev_close': item.get('prev_price'),
            'pe_ttm': val.get('pe_ttm'),
            'pb': val.get('pb_mrq'),
            'ps_ttm': val.get('ps_ttm'),
            'last_fetch_time': now_str,
            'market': 'A',
        }

    if result:
        names = ', '.join(d['name'] for d in result.values())
        logger.info(f'[数据服务.实时价格] 同花顺 → {names} ({len(result)}只)')
    return result
```

- [ ] **Step 5: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_hithink_provider.py -v`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add app/services/hithink/provider.py app/services/unified_stock_data.py tests/test_hithink_provider.py && git commit -m "feat(hithink): 快照+估值双端点合并取价，volume 股→手归一"
```

---

### Task 6: HithinkProvider 类与工厂注册

**Files:**
- Modify: `app/services/hithink/provider.py`
- Modify: `app/services/data_source_providers.py`
- Test: `tests/test_hithink_provider.py`

**Interfaces:**
- Consumes: Task 5 的 `fetch_snapshot` / `_get`
- Produces: `HithinkProvider`，实现 `is_available()` / `get_realtime_price(symbol)` / `get_batch_prices(symbols)` / `get_historical_data(symbol, days)`；`DataSourceFactory.get_provider('hithink')` 可取到实例

> **实现前必须先确认字段名**：`/prices/historical` 的响应字段本计划**未经实测**（探测只覆盖了 snapshot / valuations / income-statements / indicators）。Step 1 的测试与 Step 3 的实现里 `trade_date_ms` / `open_price` / `high_price` / `low_price` / `close_price` / `volume` 是按 snapshot 端点的命名风格推定的。动手第一件事：用真实 key 打一次 `GET /api/a-share/prices/historical?thscode=600519.SH&start=<ms>&end=<ms>&adjust=forward`，把真实响应存为 `tests/fixtures/hithink/historical.json`，再据此校正测试与实现的字段名。若字段名不同，以实测为准并同步改两处。

**日 K 定位**：同花顺 `/prices/historical` 的复权只给原始分红拆股事件流，要自己推因子；腾讯 `fqkline` 直接给 qfq。故日 K **仅作 fallback**，`get_historical_data` 直接用 `adjust` 参数取，不自造复权轮子。

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_hithink_provider.py`：

```python
import os
from unittest.mock import patch as _patch

from app.services.data_source_providers import DataSourceFactory


def test_provider_unavailable_without_key():
    with _patch.dict(os.environ, {}, clear=True):
        assert provider.HithinkProvider().is_available() is False


def test_provider_available_with_key():
    with _patch.dict(os.environ, {'HITHINK_FINANCE_API_KEY': 'sk-test'}, clear=True):
        assert provider.HithinkProvider().is_available() is True


def test_factory_resolves_hithink():
    p = DataSourceFactory.get_provider('hithink')
    assert p is not None
    assert p.name == 'hithink'
    assert p.market == 'A'


def test_get_realtime_price_returns_single():
    with _patch.object(provider, 'fetch_snapshot',
                       return_value={'600519': {'code': '600519', 'current_price': 1330.33}}):
        r = provider.HithinkProvider().get_realtime_price('600519')
    assert r['current_price'] == pytest.approx(1330.33)


def test_get_realtime_price_returns_none_when_absent():
    with _patch.object(provider, 'fetch_snapshot', return_value={}):
        assert provider.HithinkProvider().get_realtime_price('600519') is None


def test_get_historical_data_maps_bars():
    hist = {'item': [
        {'trade_date_ms': 1767110400000, 'open_price': 1290.0, 'high_price': 1340.0,
         'low_price': 1280.0, 'close_price': 1330.33, 'volume': 3418300},
    ]}
    with _patch.object(provider, '_get', return_value=hist):
        out = provider.HithinkProvider().get_historical_data('600519', 30)

    assert out['stock_code'] == '600519'
    assert out['source'] == 'hithink'
    bar = out['data'][0]
    assert bar['close'] == pytest.approx(1330.33)
    assert bar['date'] == '2025-12-31'
    assert bar['volume'] == 34183  # 股 → 手
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_hithink_provider.py -k "provider or factory or historical" -v`
Expected: FAIL —— `AttributeError: module ... has no attribute 'HithinkProvider'`

- [ ] **Step 3: 实现 HithinkProvider**

`provider.py` 追加：

```python
class HithinkProvider(DataSourceProvider):
    """同花顺 A 股数据源。日 K 仅作 fallback——复权因子需自行推导，腾讯 fqkline 直接给 qfq。"""

    name = 'hithink'
    market = 'A'

    def is_available(self) -> bool:
        return get_client().is_available()

    def get_realtime_price(self, symbol: str):
        from datetime import datetime
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return fetch_snapshot([symbol], now_str).get(from_thscode(to_thscode(symbol)))

    def get_batch_prices(self, symbols: list) -> dict:
        from datetime import datetime
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return fetch_snapshot(symbols, now_str)

    def get_historical_data(self, symbol: str, days: int):
        from datetime import datetime, timedelta

        from app.services.unified_stock_data import _normalize_volume

        end_ms = int(datetime.now().timestamp() * 1000)
        start_ms = int((datetime.now() - timedelta(days=days * 2)).timestamp() * 1000)

        data = _get(_HISTORICAL, {
            'thscode': to_thscode(symbol),
            'start': start_ms,
            'end': end_ms,
            'adjust': 'forward',
        })
        items = data.get('item') or []
        if not items:
            return None

        bars = []
        prev_close = None
        for row in sorted(items, key=lambda r: r.get('trade_date_ms') or 0):
            close = row.get('close_price')
            change_pct = ((close - prev_close) / prev_close * 100) if (prev_close and close) else 0
            bars.append({
                'date': datetime.fromtimestamp(row['trade_date_ms'] / 1000).strftime('%Y-%m-%d'),
                'open': row.get('open_price'),
                'high': row.get('high_price'),
                'low': row.get('low_price'),
                'close': close,
                'volume': _normalize_volume(row.get('volume'), 'hithink_snapshot', 'A'),
                'change_pct': round(change_pct, 2),
            })
            prev_close = close

        return {
            'stock_code': from_thscode(to_thscode(symbol)),
            'stock_name': from_thscode(to_thscode(symbol)),
            'data': bars[-days:] if len(bars) > days else bars,
            'source': 'hithink',
        }
```

- [ ] **Step 4: 工厂与注册表接线**

`app/services/data_source_providers.py` 的 `DATA_SOURCE_REGISTRY['A']` 改为：

```python
    'A': {
        'sources': ['hithink', 'sina', 'tencent', 'eastmoney'],
        'fallback': 'yfinance'
    },
```

`DataSourceFactory.get_provider` 的映射字典改为（用惰性 import 避免循环依赖 —— `provider.py` 从本模块 import `DataSourceProvider`）：

```python
    @classmethod
    def get_provider(cls, name: str) -> Optional[DataSourceProvider]:
        """获取数据源提供器实例"""
        if name not in cls._instances:
            if name == 'hithink':
                from app.services.hithink.provider import HithinkProvider
                provider_class = HithinkProvider
            else:
                provider_class = {
                    'yfinance': YFinanceProvider,
                    'twelvedata': TwelveDataProvider,
                    'polygon': PolygonProvider,
                }.get(name)

            if provider_class:
                cls._instances[name] = provider_class()

        return cls._instances.get(name)
```

- [ ] **Step 5: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_hithink_provider.py -v`
Expected: 全部 PASS

- [ ] **Step 6: Commit**

```bash
git add app/services/hithink/provider.py app/services/data_source_providers.py tests/test_hithink_provider.py && git commit -m "feat(hithink): HithinkProvider 类与 DataSourceFactory 注册"
```

---

### Task 7: 主链路接入与安全阀回归

**Files:**
- Modify: `app/services/unified_stock_data.py:800-993`（`_fetch_a_share_prices`）
- Modify: `app/services/load_balancer.py:18-27, 66-67`
- Test: `tests/test_hithink_integration.py`

**Interfaces:**
- Consumes: Task 5 的 `fetch_snapshot`、Task 1 的 `get_client().is_available()`
- Produces: 无新公开接口；`_fetch_a_share_prices` 行为变更

**优先级语义**（对 spec §4.2 的偏离，见文首说明）：`primary_sources=['hithink']`、`secondary_sources=['tencent', 'sina', 'eastmoney']`。primary 阶段在多主源间**轮询分摊**，写两个会把一半代码分给腾讯；secondary 阶段**按顺序逐个补投**，正是要的降级链。

**安全阀**：未配 key 时 `fetch_from_hithink` 不注册进 `fetch_funcs`，`primary_sources` 回退为 `['tencent', 'sina']` —— 与接入前逐字节一致。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_hithink_integration.py`：

```python
import os
from unittest.mock import patch, MagicMock

from app.services.load_balancer import MARKET_SOURCES, LoadBalancer


def test_market_sources_a_prioritizes_hithink():
    cfg = MARKET_SOURCES['A']
    assert cfg['primary_sources'] == ['hithink']
    assert cfg['secondary_sources'] == ['tencent', 'sina', 'eastmoney']
    assert cfg['fallback'] == 'yfinance'


def test_a_share_primary_constants():
    assert LoadBalancer.A_SHARE_PRIMARY == ['hithink']
    assert LoadBalancer.A_SHARE_SECONDARY == ['tencent', 'sina', 'eastmoney']


def _run_fetch(env):
    """跑 _fetch_a_share_prices，捕获传给负载均衡器的参数。"""
    from datetime import date

    from app.services.unified_stock_data import UnifiedStockDataService

    captured = {}

    def fake_balance(stock_codes, fetch_funcs, primary_sources=None,
                     secondary_sources=None, fallback_func=None):
        captured['funcs'] = sorted(fetch_funcs)
        captured['primary'] = primary_sources
        captured['secondary'] = secondary_sources
        return {}

    svc = UnifiedStockDataService.__new__(UnifiedStockDataService)
    with patch.dict(os.environ, env, clear=True):
        with patch('app.services.unified_stock_data.load_balancer') as lb:
            lb.fetch_with_priority_balancing.side_effect = fake_balance
            svc._fetch_a_share_prices(['600519'], date(2026, 9, 4), '2026-09-04 15:00:00')
    return captured


def test_hithink_registered_as_sole_primary_when_key_present():
    c = _run_fetch({'HITHINK_FINANCE_API_KEY': 'sk-test'})
    assert 'hithink' in c['funcs']
    assert c['primary'] == ['hithink']
    assert c['secondary'] == ['tencent', 'sina', 'eastmoney']


def test_safety_valve_without_key_matches_pre_integration_behavior():
    """未配 key 时调用序列必须与接入前逐字节一致。"""
    c = _run_fetch({})
    assert c['funcs'] == ['eastmoney', 'sina', 'tencent']
    assert c['primary'] == ['tencent', 'sina']
    assert c['secondary'] == ['eastmoney']
```

- [ ] **Step 2: 跑测试确认失败**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_hithink_integration.py -v`
Expected: FAIL —— `assert ['tencent', 'sina'] == ['hithink']`

- [ ] **Step 3: 改 load_balancer.py**

`MARKET_SOURCES['A']` 改为：

```python
    'A': {
        'sources': ['hithink', 'tencent', 'sina', 'eastmoney'],
        'fallback': 'yfinance',
        'weights': {'hithink': 100, 'tencent': 0, 'sina': 0, 'eastmoney': 0},
        # 优先级模式：同花顺为主，失败依次降级腾讯/新浪/东财，最后 yfinance 兜底
        'priority_mode': True,
        'primary_sources': ['hithink'],
        'secondary_sources': ['tencent', 'sina', 'eastmoney'],
    },
```

`LoadBalancer` 类的两个常量（`load_balancer.py:66-67`）改为：

```python
    A_SHARE_PRIMARY = ['hithink']                              # 主数据源
    A_SHARE_SECONDARY = ['tencent', 'sina', 'eastmoney']       # 备用数据源（按序补投）
```

- [ ] **Step 4: 改 `_fetch_a_share_prices`**

在 `fetch_from_yfinance` 定义之后、`fetch_funcs = {` 之前，插入闭包：

```python
        def fetch_from_hithink(codes: list) -> dict:
            from app.services.hithink.provider import fetch_snapshot
            return fetch_snapshot(codes, now_str)
```

把结尾的 `fetch_funcs` 与均衡器调用（`unified_stock_data.py:981-993`）替换为：

```python
        # 优先级：同花顺为主 → 腾讯/新浪/东财按序补投 → yfinance 兜底
        # 未配 HITHINK_FINANCE_API_KEY 时同花顺整体跳过，回到接入前的腾讯/新浪主源
        from app.services.hithink.client import get_client as _hithink_client

        fetch_funcs = {
            'tencent': fetch_from_tencent,
            'sina': fetch_from_sina,
            'eastmoney': fetch_from_eastmoney,
        }

        if _hithink_client().is_available():
            fetch_funcs['hithink'] = fetch_from_hithink
            primary_sources = ['hithink']
            secondary_sources = ['tencent', 'sina', 'eastmoney']
        else:
            primary_sources = ['tencent', 'sina']
            secondary_sources = ['eastmoney']

        return load_balancer.fetch_with_priority_balancing(
            stock_codes,
            fetch_funcs,
            primary_sources=primary_sources,
            secondary_sources=secondary_sources,
            fallback_func=fetch_from_yfinance
        )
```

- [ ] **Step 5: 跑测试确认通过**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/test_hithink_integration.py -v`
Expected: 全部 PASS

- [ ] **Step 6: 跑全量回归**

Run: `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ > /tmp/pytest_out.txt 2>&1; grep -E "passed|failed|error" /tmp/pytest_out.txt`

crawl4ai 的进度条走 **stdout**，`2>/dev/null` 挡不住，必须重定向到文件再 grep，否则 `N passed` 摘要会被顶出可见区。

Expected: 无新增 failure / error；同花顺相关 4 个测试文件全绿。

- [ ] **Step 7: Commit**

```bash
git add app/services/unified_stock_data.py app/services/load_balancer.py tests/test_hithink_integration.py && git commit -m "feat(hithink): 接入 A 股取价主链路，未配 key 时行为不变"
```

---

## 完成后

按 `superpowers:finishing-a-development-branch` 收口 worktree。

**实盘冒烟**（合并前，需 `.env` 里有真实 key，会打真网）：

```bash
PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 python -c "from app.services.hithink.provider import fetch_snapshot; import json; print(json.dumps(fetch_snapshot(['600519','000001','300750'],'now'), ensure_ascii=False, indent=1))"
```

核对：`name` 是中文名、`volume` 是**手**（茅台日成交约 3–5 万手，若出现 300 万级说明归一没走到）、`pe_ttm` / `pb` 非空。
