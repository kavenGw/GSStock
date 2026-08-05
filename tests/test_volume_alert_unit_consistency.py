"""volume_alert 单位契约与 sanity gate 单元测试

锁定：
1. A股 OHLC/realtime 所有源 volume 单位归一化到"手"
2. volume_alert 比值异常 / 今日bar残缺 sanity gate
3. VOLUME_UNIT_SCHEMA_VERSION 缓存失效检测机制
"""
import ast
import os
import logging
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SERVICE_FILE = ROOT / 'app' / 'services' / 'unified_stock_data.py'


# ============ 1. 单位归一化源码契约锁定 ============

from app.services.unified_stock_data import VOLUME_SOURCE_UNITS, _normalize_volume


def test_lots_source_passthrough_for_a_share():
    """原生「手」的源，A 股不做转换"""
    assert _normalize_volume(25060238, 'tencent_qt', 'A') == 25060238
    assert _normalize_volume('17534731', 'tencent_fqkline', 'A') == 17534731
    assert _normalize_volume(12345, 'eastmoney_ak_hist', 'A') == 12345


def test_shares_source_divides_100_for_a_share():
    """原生「股」的源，A 股必须 // 100 归一到「手」"""
    assert _normalize_volume(2506023803, 'sina_daily', 'A') == 25060238
    assert _normalize_volume(1753473070, 'sina_daily', 'A') == 17534730
    assert _normalize_volume(2506023803, 'yfinance', 'A') == 25060238
    assert _normalize_volume(1234567, 'sina_spot', 'A') == 12345


def test_non_a_market_always_passthrough():
    """港股/美股契约就是「股」，任何源都原样返回"""
    assert _normalize_volume(2506023803, 'yfinance', 'US') == 2506023803
    assert _normalize_volume(2506023803, 'yfinance', 'HK') == 2506023803
    assert _normalize_volume(9876543, 'tencent_qt', 'HK') == 9876543


def test_empty_values_return_none():
    """空值语义：调用点自行决定填 0 还是 None"""
    assert _normalize_volume(None, 'sina_daily', 'A') is None
    assert _normalize_volume('', 'sina_daily', 'A') is None
    assert _normalize_volume(float('nan'), 'yfinance', 'A') is None
    assert _normalize_volume('abc', 'yfinance', 'A') is None


def test_zero_is_preserved_not_none():
    """0 是合法成交量（停牌/一字板），不能被当成空值"""
    assert _normalize_volume(0, 'sina_daily', 'A') == 0
    assert _normalize_volume(0.0, 'tencent_qt', 'A') == 0


def test_unregistered_source_raises_keyerror():
    """未登记的源必须炸，不允许静默走默认单位"""
    with pytest.raises(KeyError):
        _normalize_volume(100, 'some_new_source', 'A')


def test_all_registered_units_are_valid():
    """映射表只允许 lots / shares 两种取值"""
    assert set(VOLUME_SOURCE_UNITS.values()) <= {'lots', 'shares'}


# ============ 2. VOLUME_UNIT_SCHEMA_VERSION 机制 ============

def test_schema_version_constant_defined():
    """VOLUME_UNIT_SCHEMA_VERSION 常量存在且为 4"""
    from app.services.unified_stock_data import VOLUME_UNIT_SCHEMA_VERSION
    assert VOLUME_UNIT_SCHEMA_VERSION == 4


def test_clear_volume_related_cache_removes_pkl(tmp_path, monkeypatch):
    """_clear_volume_related_cache 应删除 ohlc_*/price/index pkl，保留其他"""
    from app.services import unified_stock_data as usd

    monkeypatch.chdir(tmp_path)
    cache_dir = tmp_path / 'data' / 'memory_cache'
    cache_dir.mkdir(parents=True)
    stock_dir = cache_dir / '600519'
    stock_dir.mkdir()
    (stock_dir / 'ohlc_60.pkl').write_bytes(b'dummy')
    (stock_dir / 'ohlc_5.pkl').write_bytes(b'dummy')
    (stock_dir / 'price.pkl').write_bytes(b'dummy')
    (stock_dir / 'index.pkl').write_bytes(b'dummy')
    (stock_dir / 'quarterly_earnings.pkl').write_bytes(b'keep')

    # 直接调用（无 app context，DB 清理会跳过，仅清 pkl）
    usd.UnifiedStockDataService._instance = None
    service = usd.UnifiedStockDataService.__new__(usd.UnifiedStockDataService)
    service._clear_volume_related_cache()

    assert not (stock_dir / 'ohlc_60.pkl').exists()
    assert not (stock_dir / 'ohlc_5.pkl').exists()
    assert not (stock_dir / 'price.pkl').exists()
    assert not (stock_dir / 'index.pkl').exists()
    assert (stock_dir / 'quarterly_earnings.pkl').exists()


def test_check_cache_schema_version_writes_version_on_mismatch(tmp_path, monkeypatch):
    """版本文件缺失或不匹配时触发清理并写入新版本号"""
    from app.services import unified_stock_data as usd

    monkeypatch.chdir(tmp_path)
    cache_dir = tmp_path / 'data' / 'memory_cache'
    cache_dir.mkdir(parents=True)
    stock_dir = cache_dir / '600519'
    stock_dir.mkdir()
    (stock_dir / 'ohlc_60.pkl').write_bytes(b'dummy')
    (cache_dir / '.schema_version').write_text('1')

    usd.UnifiedStockDataService._instance = None
    service = usd.UnifiedStockDataService.__new__(usd.UnifiedStockDataService)
    service._check_cache_schema_version()

    # ohlc_60.pkl 已被清理
    assert not (stock_dir / 'ohlc_60.pkl').exists()
    # 版本号升级为 2
    assert (cache_dir / '.schema_version').read_text().strip() == str(usd.VOLUME_UNIT_SCHEMA_VERSION)


def test_check_cache_schema_version_skips_when_matched(tmp_path, monkeypatch):
    """版本匹配时跳过清理"""
    from app.services import unified_stock_data as usd

    monkeypatch.chdir(tmp_path)
    cache_dir = tmp_path / 'data' / 'memory_cache'
    cache_dir.mkdir(parents=True)
    stock_dir = cache_dir / '600519'
    stock_dir.mkdir()
    (stock_dir / 'ohlc_60.pkl').write_bytes(b'keep')
    (cache_dir / '.schema_version').write_text(str(usd.VOLUME_UNIT_SCHEMA_VERSION))

    usd.UnifiedStockDataService._instance = None
    service = usd.UnifiedStockDataService.__new__(usd.UnifiedStockDataService)
    service._check_cache_schema_version()

    # 缓存保留
    assert (stock_dir / 'ohlc_60.pkl').exists()


# ============ 3. volume_alert sanity gate ============

@pytest.fixture
def strategy_deps(monkeypatch):
    """通用 mock 工厂：返回可配置的 trend/realtime，并屏蔽交易日校验"""
    from app.strategies.volume_alert import __init__ as va_mod

    class _Stub:
        trend = {'stocks': []}
        realtime = {}

    stub = _Stub()

    def fake_get_watch_codes():
        return [s['stock_code'] for s in stub.trend.get('stocks', [])]

    class FakeUSD:
        def __init__(self):
            pass
        def get_trend_data(self, codes, days=5, force_refresh=False):
            return stub.trend
        def get_realtime_prices(self, codes, force_refresh=False):
            return stub.realtime

    class FakeCal:
        @staticmethod
        def is_trading_day(market, today):
            return True

    class FakeMI:
        @staticmethod
        def is_a_share(code):
            return True

    # 策略内 local import，patch 目标模块
    monkeypatch.setattr('app.services.watch_service.WatchService.get_watch_codes', fake_get_watch_codes, raising=False)
    monkeypatch.setattr('app.services.trading_calendar.TradingCalendarService', FakeCal, raising=False)
    monkeypatch.setattr('app.services.unified_stock_data.UnifiedStockDataService', FakeUSD, raising=False)
    monkeypatch.setattr('app.utils.market_identifier.MarketIdentifier', FakeMI, raising=False)

    return stub


def _make_ohlc(code, name, vols, today_str='2099-04-23'):
    """辅助：构造含 today bar 的 OHLC，vols 列表含今天，末尾即今天"""
    dates = [f'2099-04-{21 + i:02d}' for i in range(len(vols) - 1)] + [today_str]
    data = [{'date': d, 'open': 10, 'high': 11, 'low': 9, 'close': 10, 'volume': v, 'change_pct': 0}
            for d, v in zip(dates, vols)]
    return {'stock_code': code, 'stock_name': name, 'data': data}


def test_sanity_gate_rejects_extreme_ratio(strategy_deps, caplog, monkeypatch):
    """ratio > 30 的信号被丢弃并记录 WARN"""
    from datetime import date
    from app.strategies.volume_alert import VolumeAlertStrategy

    today_str = date.today().strftime('%Y-%m-%d')
    # 今日 vol=1000, 昨日 vol=1 → ratio=1000（异常）
    strategy_deps.trend = {
        'stocks': [_make_ohlc('600519', '贵州茅台', [1, 1, 1, 1, 1000], today_str)]
    }
    strategy_deps.realtime = {'600519': {'volume': 1000, 'change_pct': 1.0}}

    caplog.set_level(logging.WARNING)
    signals = VolumeAlertStrategy()._do_scan()

    assert signals == []
    assert any('比值异常跳过' in r.message for r in caplog.records)


def test_sanity_gate_rejects_partial_today_bar(strategy_deps, caplog, monkeypatch):
    """today_vol < 5日均量 1% 的信号被丢弃并记录 WARN"""
    from datetime import date
    from app.strategies.volume_alert import VolumeAlertStrategy

    today_str = date.today().strftime('%Y-%m-%d')
    # 前 3 日 2000, 昨日 100, 今日 10
    # ratio=10/100=0.1 不极端，但 5d 均量=(2000*3+100+10)/5=1222, 今日<12.22 → 触发 gate 2
    strategy_deps.trend = {
        'stocks': [_make_ohlc('600519', '贵州茅台', [2000, 2000, 2000, 100, 10], today_str)]
    }
    strategy_deps.realtime = {'600519': {'volume': 10, 'change_pct': -1.0}}

    caplog.set_level(logging.WARNING)
    signals = VolumeAlertStrategy()._do_scan()

    assert signals == []
    assert any('今日bar疑残缺跳过' in r.message for r in caplog.records)


def test_sanity_gate_accepts_normal_anomaly(strategy_deps, caplog):
    """合理范围的异动（2.67x）正常产出 signal"""
    from datetime import date
    from app.strategies.volume_alert import VolumeAlertStrategy

    today_str = date.today().strftime('%Y-%m-%d')
    # today=8000, prev=3000 → ratio=2.67（合理）；5d 均量约 3400，today 远高于 1%
    strategy_deps.trend = {
        'stocks': [_make_ohlc('600519', '贵州茅台', [3000, 3000, 4000, 3000, 8000], today_str)]
    }
    strategy_deps.realtime = {'600519': {'volume': 8000, 'change_pct': 3.0}}

    signals = VolumeAlertStrategy()._do_scan()

    assert len(signals) == 1
    assert signals[0].data['stock_code'] == '600519'
    # change_pct = (8000-3000)/3000 ≈ 1.667 → 放量 167%
    assert signals[0].data['volume_change_pct'] > 0


# ============ 4. 落点接入回归 ============

def test_tencent_qt_parse_returns_lots(monkeypatch):
    """腾讯 q= 接口解析后 A 股 volume 为「手」（原值即手，不得再除）"""
    from app.services import unified_stock_data as usd

    raw_line = 'v_sz000725="51~京东方A~000725~5.97~5.63~5.59~25060238~0~0~5.97~' + '~'.join(['0'] * 60) + '";'

    class FakeResp:
        text = raw_line
        encoding = 'gbk'
        status_code = 200

    # requests 在 unified_stock_data 中是函数内 import（无模块级属性），
    # 必须 patch requests 模块本身，不能 patch usd.requests
    monkeypatch.setattr('requests.get', lambda *a, **k: FakeResp())

    usd.UnifiedStockDataService._instance = None
    service = usd.UnifiedStockDataService.__new__(usd.UnifiedStockDataService)
    result = service._fetch_from_tencent(['000725'], '2026-08-05 16:30:00')

    assert result['000725']['volume'] == 25060238


def test_sina_batch_trend_normalizes_shares_to_lots(monkeypatch):
    """回归 2026-08-05 事故：_fetch_trend_from_sina 曾漏 //100，
    京东方A 被推成 2,506,023,803（股）而非 25,060,238（手）"""
    import pandas as pd
    from datetime import date
    from app.services import unified_stock_data as usd

    df = pd.DataFrame(
        {
            'open': [5.46, 5.59],
            'high': [5.66, 6.03],
            'low': [5.43, 5.58],
            'close': [5.63, 5.97],
            'volume': [1753473070.0, 2506023803.0],
        },
        index=pd.to_datetime(['2026-08-04', '2026-08-05']),
    )

    class FakeAk:
        @staticmethod
        def stock_zh_a_daily(**kwargs):
            return df

    monkeypatch.setattr('app.services.akshare_client.ak', FakeAk, raising=False)

    usd.UnifiedStockDataService._instance = None
    service = usd.UnifiedStockDataService.__new__(usd.UnifiedStockDataService)
    results = service._fetch_trend_from_sina(
        ['000725'], 5, date(2026, 7, 30), date(2026, 8, 5),
        {'000725': '京东方A'}, {},
    )

    vols = [p['volume'] for p in results[0]['data']]
    assert vols == [17534730, 25060238], f"新浪批量走势未归一到手: {vols}"


# ============ 5. AST 静态断言：禁止绕过归一 helper ============

def _unwrap_volume_expr(node):
    """剥掉 `X or 0` / 三元表达式外壳，取出真正的取值表达式列表"""
    if isinstance(node, ast.BoolOp):
        out = []
        for v in node.values:
            out.extend(_unwrap_volume_expr(v))
        return out
    if isinstance(node, ast.IfExp):
        return _unwrap_volume_expr(node.body) + _unwrap_volume_expr(node.orelse)
    return [node]


def _is_constant_expr(node):
    """字面常量表达式不承载数据流，允许豁免不走 _normalize_volume。

    例：`'volume': 0` / `None` 占位；pandas 具名聚合 `.agg(volume=('手数', 'sum'))`
    里的 `('手数', 'sum')`——这是给结果列取名 'volume' 的元组字面量，
    不是从数据源取到的成交量数值。判据是「是否承载数据流」，不是「像不像元组/字面量」：
    只要元素全是字面常量就没有数据流经此处，可以放行；一旦出现变量/函数调用/属性访问，
    就说明有真实数值在流动，必须走 helper。
    """
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, (ast.Tuple, ast.List)):
        return all(isinstance(e, ast.Constant) for e in node.elts)
    return False


def _volume_dict_values(tree):
    """收集 unified_stock_data.py 中所有形态的 volume 赋值表达式：
    {'volume': <expr>} 字典字面量 / Model(volume=<expr>) 关键字参数 /
    d['volume'] = <expr> 下标赋值
    """
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for key, value in zip(node.keys, node.values):
                if isinstance(key, ast.Constant) and key.value == 'volume':
                    found.append((key.lineno, value))
        elif isinstance(node, ast.keyword):
            if node.arg == 'volume':
                found.append((node.value.lineno, node.value))
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if (isinstance(target, ast.Subscript)
                        and isinstance(target.slice, ast.Constant)
                        and target.slice.value == 'volume'):
                    found.append((node.lineno, node.value))
    return found


def test_all_volume_assignments_go_through_normalize_helper():
    """任何 'volume' 赋值都必须来自 _normalize_volume()，不得内联换算"""
    tree = ast.parse(SERVICE_FILE.read_text(encoding='utf-8'))
    offenders = []
    for lineno, value in _volume_dict_values(tree):
        for expr in _unwrap_volume_expr(value):
            if _is_constant_expr(expr):
                continue
            is_helper_call = (
                isinstance(expr, ast.Call)
                and isinstance(expr.func, ast.Name)
                and expr.func.id == '_normalize_volume'
            )
            if not is_helper_call:
                offenders.append(lineno)
    assert not offenders, (
        f"unified_stock_data.py 第 {sorted(set(offenders))} 行的 volume 绕过了 _normalize_volume()，"
        f"新增数据源必须在 VOLUME_SOURCE_UNITS 登记单位后走 helper"
    )


def test_all_used_source_keys_are_registered():
    """所有 _normalize_volume 调用点用到的 source 字面量都已登记"""
    tree = ast.parse(SERVICE_FILE.read_text(encoding='utf-8'))
    used = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == '_normalize_volume' and len(node.args) >= 2):
            src = node.args[1]
            assert isinstance(src, ast.Constant), (
                f"第 {node.lineno} 行 _normalize_volume 的 source 必须是字面量，不能是变量"
            )
            used.add(src.value)

    unknown = used - set(VOLUME_SOURCE_UNITS)
    assert not unknown, f"未登记的数据源: {unknown}"
    unused = set(VOLUME_SOURCE_UNITS) - used
    assert not unused, f"已登记但无调用点的数据源: {unused}"
    assert used == set(VOLUME_SOURCE_UNITS)


# ============ 6. 跨源真值一致性（联网，默认跳过）============

@pytest.mark.network
@pytest.mark.skipif(not os.environ.get('RUN_NETWORK_TESTS'), reason='需 RUN_NETWORK_TESTS=1 且联网')
def test_cross_source_volume_agreement():
    """同一 A 股同一交易日，各源归一后互差 < 1%。排查量纲问题的现场工具。"""
    from datetime import date, timedelta
    from app.services import unified_stock_data as usd

    code = '000725'
    today = date.today()
    start = today - timedelta(days=15)

    usd.UnifiedStockDataService._instance = None
    service = usd.UnifiedStockDataService.__new__(usd.UnifiedStockDataService)

    per_source = {}
    for name, fn in [
        ('tencent', service._fetch_trend_from_tencent),
        ('sina', service._fetch_trend_from_sina),
        ('eastmoney', service._fetch_trend_from_eastmoney),
        ('em_direct', service._fetch_trend_from_eastmoney_direct),
    ]:
        try:
            res = fn([code], 10, start, today, {code: code}, {})
        except Exception:
            continue
        if res:
            per_source[name] = {p['date']: p['volume'] for p in res[0]['data']}

    assert len(per_source) >= 2, f'可用源不足，无法交叉验证: {list(per_source)}'

    common = set.intersection(*(set(v) for v in per_source.values()))
    assert common, '各源无共同交易日'

    for d in sorted(common):
        vals = [per_source[s][d] for s in per_source if per_source[s][d]]
        if len(vals) < 2:
            continue
        assert max(vals) / min(vals) < 1.01, f'{d} 各源 volume 不一致: ' + str(
            {s: per_source[s][d] for s in per_source}
        )
