"""analyze_stocks realtime 分支：超龄旧价的股跳过 LLM 分析不入库"""
from datetime import datetime, timedelta

from app.services.watch_analysis_service import WatchAnalysisService
from app.services.watch_service import WatchService
from app.services.unified_stock_data import unified_stock_data_service
from app.llm.router import llm_router


class FakeProvider:
    def __init__(self):
        self.called_for = []

    def chat(self, messages, max_tokens=500):
        self.called_for.append(max_tokens)
        return '{"signal": "hold", "summary": "s", "support_levels": [], "resistance_levels": []}'


def _run(monkeypatch, prices):
    codes = list(prices)
    intraday = {'stocks': [{'stock_code': c, 'data': [{'time': '09:30', 'price': 1.0}]}
                           for c in codes]}
    monkeypatch.setattr(WatchService, 'get_watch_codes', staticmethod(lambda: codes))
    monkeypatch.setattr(WatchService, 'get_market_map',
                        staticmethod(lambda: {c: 'A' for c in codes}))
    monkeypatch.setattr(WatchService, 'get_all_today_analyses', staticmethod(lambda: {}))
    saved = []
    monkeypatch.setattr(WatchService, 'save_analysis',
                        staticmethod(lambda **kw: saved.append(kw['stock_code'])))
    monkeypatch.setattr(unified_stock_data_service, 'get_realtime_prices',
                        lambda c, **kw: prices)
    monkeypatch.setattr(unified_stock_data_service, 'get_trend_data',
                        lambda c, days: {'stocks': []})
    monkeypatch.setattr(unified_stock_data_service, 'get_intraday_data',
                        lambda c, **kw: intraday)
    monkeypatch.setattr(llm_router, 'route', lambda name: FakeProvider())
    WatchAnalysisService.analyze_stocks('realtime')
    return saved


def test_stale_price_skips_llm_analysis(monkeypatch):
    prices = {
        'FRESH': {'current_price': 10.0, 'name': 'F',
                  'last_fetch_time': datetime.now().isoformat()},
        'STALE': {'current_price': 20.0, 'name': 'S',
                  'last_fetch_time': (datetime.now() - timedelta(minutes=10)).isoformat()},
    }
    assert _run(monkeypatch, prices) == ['FRESH']


def test_degraded_price_skips_llm_analysis(monkeypatch):
    prices = {
        'FRESH': {'current_price': 10.0, 'name': 'F',
                  'last_fetch_time': datetime.now().isoformat()},
        'DEGRADED': {'current_price': 20.0, 'name': 'D', '_is_degraded': True,
                     'last_fetch_time': datetime.now().isoformat()},
    }
    assert _run(monkeypatch, prices) == ['FRESH']
