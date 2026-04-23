"""volume_alert 单位契约与 sanity gate 单元测试

锁定：
1. A股 OHLC/realtime 所有源 volume 单位归一化到"手"
2. volume_alert 比值异常 / 今日bar残缺 sanity gate
3. VOLUME_UNIT_SCHEMA_VERSION 缓存失效检测机制
"""
import os
import re
import sys
import logging
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).resolve().parent.parent
SERVICE_FILE = ROOT / 'app' / 'services' / 'unified_stock_data.py'


# ============ 1. 单位归一化源码契约锁定 ============

def test_sina_daily_hist_volume_divides_100():
    """新浪 stock_zh_a_daily 解析必须 // 100"""
    content = SERVICE_FILE.read_text(encoding='utf-8')
    # fetch_from_sina 日K：int(row['volume']) // 100
    assert re.search(
        r"int\(row\['volume'\]\)\s*//\s*100",
        content,
    ), "sina 日K volume 未做 // 100 归一化"


def test_tencent_fqkline_volume_divides_100():
    """腾讯 fqkline 日K 解析必须 / 100"""
    content = SERVICE_FILE.read_text(encoding='utf-8')
    # 腾讯 row[5] 处理需要有 / 100
    matches = re.findall(
        r"int\(float\(row\[5\]\)\s*/\s*100\)",
        content,
    )
    assert len(matches) >= 2, f"腾讯 fqkline 日K volume /100 出现次数不足，预期>=2，实际={len(matches)}"


def test_sina_spot_volume_divides_100():
    """新浪 stock_zh_a_spot 解析必须 // 100"""
    content = SERVICE_FILE.read_text(encoding='utf-8')
    # fetch_from_sina spot: int(row['成交量']) // 100
    assert re.search(
        r"int\(row\['成交量'\]\)\s*//\s*100",
        content,
    ), "sina spot 成交量未做 // 100 归一化"


def test_tencent_realtime_still_divides_100():
    """腾讯 qt.gtimg.cn realtime 必须保留 / 100（fields[6]）"""
    content = SERVICE_FILE.read_text(encoding='utf-8')
    assert re.search(
        r"int\(float\(fields\[6\]\)\s*/\s*100\)",
        content,
    ), "腾讯 realtime fields[6] 丢失 / 100 归一化"


def test_eastmoney_hist_volume_not_divided():
    """东财 akshare hist 返回手，不应 // 100（只有注释/无显式除法）"""
    content = SERVICE_FILE.read_text(encoding='utf-8')
    # 东财 fetch_from_eastmoney 日K的 `int(row['成交量'])` 不带 //100
    assert re.search(
        r"'volume':\s*int\(row\['成交量'\]\)\s+if\s+row\.get\('成交量'\)",
        content,
    ), "东财 akshare hist 的 volume 解析模式变更了"


# ============ 2. VOLUME_UNIT_SCHEMA_VERSION 机制 ============

def test_schema_version_constant_defined():
    """VOLUME_UNIT_SCHEMA_VERSION 常量存在且为 2"""
    from app.services.unified_stock_data import VOLUME_UNIT_SCHEMA_VERSION
    assert VOLUME_UNIT_SCHEMA_VERSION == 2


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
