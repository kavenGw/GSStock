import json
from pathlib import Path

from flask import Flask
import pytest


@pytest.fixture
def client():
    from app.routes import performance_bp
    app = Flask(__name__, template_folder=str(Path('app/templates').resolve()))
    app.config['TESTING'] = True
    app.register_blueprint(performance_bp)
    # 共享导航的其他模块只需 URL，不初始化数据库、OCR 或调度器。
    for endpoint in ('briefing.index', 'watch.index', 'calendar.index', 'news.index',
                     'news.identified_companies', 'heavy_metals.index', 'minerals.index',
                     'earnings_page.index', 'supply_chain.index', 'valuations.index', 'stock.manage',
                     'main.dashboard', 'daily_record.index', 'trade.index', 'profit.daily',
                     'profit.overall', 'rebalance.index'):
        app.add_url_rule(f'/stub/{endpoint}', endpoint=endpoint, view_func=lambda: '')
    with app.test_client() as client:
        yield client


def test_real_backfill_renders_all_eleven_companies(client):
    from bs4 import BeautifulSoup
    response = client.get('/performance/')
    assert response.status_code == 200
    page = BeautifulSoup(response.data, 'html.parser')
    rows = json.loads(page.select_one('#performanceData').string)
    current = [row for row in rows if row['period'] == '2026Q3']
    assert {
        '长鑫科技', '沪电股份', '普冉股份', '胜宏科技', '澜起科技', '兆易创新',
        '联讯仪器', '通富微电', '江丰电子', '兴森科技', '天孚通信',
    }.issubset({row['stock_name'] for row in current})
    assert all(row[metric] is not None for row in current for metric in ('revenue', 'adjusted_profit', 'inventory'))
    assert all(row[f'{metric}_qoq']['value'] is not None for row in current for metric in ('revenue', 'adjusted_profit', 'inventory'))
    assert page.select_one('#performancePeriod option')['value'] == max(row['period'] for row in rows)
    for row in current:
        research = client.get(row['research_url'])
        assert research.status_code == 200
        assert row['stock_name'].encode('utf-8') in research.data


def test_market_caps_endpoint_uses_researched_codes(client, monkeypatch):
    from app.routes import performance
    seen = {}

    def fake(codes):
        seen['codes'] = codes
        return {'market_caps': {'002916': {'market_cap': 1587.04}}, 'as_of': '2026-10-30 16:14'}

    monkeypatch.setattr(performance.MarketCapService, 'get_cny_market_caps', fake)
    response = client.get('/performance/market-caps')
    assert response.status_code == 200
    assert response.get_json()['market_caps']['002916']['market_cap'] == 1587.04
    assert {'002916', '02476'}.issubset(seen['codes'])


def test_market_caps_endpoint_reports_corrupt_data(client, monkeypatch):
    from app.routes import performance
    def fail(_):
        raise ValueError('bad record')
    monkeypatch.setattr(performance, 'load_companies', fail)
    assert client.get('/performance/market-caps').status_code == 503


def test_page_declares_valuation_columns(client):
    from bs4 import BeautifulSoup
    page = BeautifulSoup(client.get('/performance/').data, 'html.parser')
    assert {'market_cap', 'adjusted_pe'}.issubset({button['data-sort'] for button in page.select('[data-sort]')})
    assert page.select_one('#performanceData')['data-market-cap-url'] == '/performance/market-caps'


def test_missing_documents_return_404(client):
    for url in ('/performance/research/sectors/no-such.md', '/performance/research/../AGENTS.md'):
        assert client.get(url).status_code == 404


def test_corrupt_data_shows_error_instead_of_empty_success(client, monkeypatch):
    from app.routes import performance
    def fail(_):
        raise ValueError('bad record')
    monkeypatch.setattr(performance, 'load_companies', fail)
    response = client.get('/performance/')
    assert response.status_code == 503
    assert '校验失败'.encode('utf-8') in response.data
