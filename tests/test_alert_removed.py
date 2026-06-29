import importlib
import pytest


def test_alert_bp_not_exported():
    import app.routes as routes
    importlib.reload(routes)
    assert not hasattr(routes, 'alert_bp')


def test_alert_module_gone():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module('app.routes.alert')


def test_backtest_service_present():
    """backtest.py 被 stock_detail 的 wyckoff 回测端点使用，不应随 alert 页删除。"""
    mod = importlib.import_module('app.services.backtest')
    assert hasattr(mod, 'BacktestService')
