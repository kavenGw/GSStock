def test_briefing_has_no_dangling_alert_import():
    """删 alert.py 后 briefing 不应再引用 app.routes.alert（曾导致财报预警端点 500）。"""
    import importlib, inspect
    b = importlib.import_module('app.services.briefing')
    assert 'from app.routes.alert' not in inspect.getsource(b)


def test_briefing_helpers_inlined():
    """get_categories / get_stocks_by_category 已内联进 briefing 模块。"""
    import app.services.briefing as b
    assert callable(getattr(b, 'get_categories', None))
    assert callable(getattr(b, 'get_stocks_by_category', None))
