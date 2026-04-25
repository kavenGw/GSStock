"""LoL 赛程获取的异常路径与重试单元测试

锁定：
1. ConnectError / ReadTimeout 重试 _max_retries 次后返回 None
2. 第一次抛异常、第二次成功 → 返回正确数据
3. HTTP 5xx / 429 触发重试；HTTP 404 / 401 不重试
4. API 成功且 events 为空 → 返回 {'today': [], 'yesterday': []}（不是 None）
5. 异常分支日志带 exc_info / type / status
"""
from datetime import date
from unittest.mock import patch, MagicMock

import httpx
import pytest

from app.services.esports_service import EsportsService


_TODAY = date(2026, 4, 25)
_YESTERDAY = date(2026, 4, 24)


def _make_status_error(status_code, body='err body'):
    """构造 httpx.HTTPStatusError，附带 response."""
    request = httpx.Request('GET', 'https://example.com')
    response = httpx.Response(status_code, text=body, request=request)
    return httpx.HTTPStatusError('boom', request=request, response=response)


def _empty_response_json():
    return {'data': {'schedule': {'events': [], 'pages': {'older': None, 'newer': None}}}}


def _patch_sleep():
    return patch('app.services.esports_service.time.sleep', return_value=None)


# ============ 1. 连接异常重试 ============

def test_connect_error_retries_and_returns_none():
    """ConnectError 抛出 → 重试 _max_retries 次 → 返回 None"""
    with patch('app.services.esports_service.httpx.get',
               side_effect=httpx.ConnectError('dns fail')) as m, _patch_sleep() as s:
        result = EsportsService._fetch_lol_esports_schedule('123', _TODAY, _YESTERDAY)
    assert result is None
    # _max_retries=3 → attempt 0..3 共 4 次调用
    assert m.call_count == 4
    # 重试 3 次 → sleep 调用 3 次
    assert s.call_count == 3


def test_first_timeout_then_success_returns_data():
    """第 1 次 ReadTimeout，第 2 次成功 → 返回数据"""
    success_resp = MagicMock()
    success_resp.raise_for_status = MagicMock()
    success_resp.json.return_value = _empty_response_json()

    side = [httpx.ReadTimeout('slow'), success_resp]
    with patch('app.services.esports_service.httpx.get', side_effect=side), _patch_sleep():
        result = EsportsService._fetch_lol_esports_schedule('123', _TODAY, _YESTERDAY)
    assert result == {'today': [], 'yesterday': []}


# ============ 2. HTTP 状态码区分 ============

def test_http_429_retries():
    """HTTP 429 触发重试"""
    resp = MagicMock()
    resp.raise_for_status.side_effect = _make_status_error(429)
    with patch('app.services.esports_service.httpx.get', return_value=resp) as m, _patch_sleep():
        result = EsportsService._fetch_lol_esports_schedule('123', _TODAY, _YESTERDAY)
    assert result is None
    assert m.call_count == 4  # 4 次尝试


def test_http_500_retries():
    """HTTP 5xx 触发重试"""
    resp = MagicMock()
    resp.raise_for_status.side_effect = _make_status_error(503)
    with patch('app.services.esports_service.httpx.get', return_value=resp) as m, _patch_sleep():
        result = EsportsService._fetch_lol_esports_schedule('123', _TODAY, _YESTERDAY)
    assert result is None
    assert m.call_count == 4


def test_http_404_no_retry():
    """HTTP 404 不重试，立即返回 None"""
    resp = MagicMock()
    resp.raise_for_status.side_effect = _make_status_error(404)
    with patch('app.services.esports_service.httpx.get', return_value=resp) as m, _patch_sleep():
        result = EsportsService._fetch_lol_esports_schedule('123', _TODAY, _YESTERDAY)
    assert result is None
    assert m.call_count == 1


def test_http_401_no_retry():
    """HTTP 401 鉴权错不重试"""
    resp = MagicMock()
    resp.raise_for_status.side_effect = _make_status_error(401)
    with patch('app.services.esports_service.httpx.get', return_value=resp) as m, _patch_sleep():
        result = EsportsService._fetch_lol_esports_schedule('123', _TODAY, _YESTERDAY)
    assert result is None
    assert m.call_count == 1


# ============ 3. 空 events 不视为失败 ============

def test_empty_events_returns_empty_dict_not_none():
    """API 成功且 events 为空 → 返回 {'today': [], 'yesterday': []}（区别于 None）"""
    success_resp = MagicMock()
    success_resp.raise_for_status = MagicMock()
    success_resp.json.return_value = _empty_response_json()
    with patch('app.services.esports_service.httpx.get', return_value=success_resp):
        result = EsportsService._fetch_lol_esports_schedule('123', _TODAY, _YESTERDAY)
    assert result == {'today': [], 'yesterday': []}
    assert result is not None


# ============ 4. 日志携带 exc_info / 异常类型 ============

def test_log_includes_exc_info_on_final_failure(caplog):
    """重试耗尽后告警日志必须含异常 type 与 traceback"""
    import logging
    caplog.set_level(logging.WARNING, logger='app.services.esports_service')
    with patch('app.services.esports_service.httpx.get',
               side_effect=httpx.ConnectError('dns fail')), _patch_sleep():
        EsportsService._fetch_lol_esports_schedule('LCK_ID', _TODAY, _YESTERDAY)
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings, '必须有 WARNING 级别日志'
    rec = warnings[-1]
    assert 'LCK_ID' in rec.getMessage()
    assert 'ConnectError' in rec.getMessage()
    # exc_info=True 时 record.exc_info 不为 None
    assert rec.exc_info is not None


def test_log_includes_status_code_and_body_on_http_error(caplog):
    """HTTP 错最终失败日志必须含 status 与响应体"""
    import logging
    caplog.set_level(logging.WARNING, logger='app.services.esports_service')
    resp = MagicMock()
    resp.raise_for_status.side_effect = _make_status_error(404, body='Not Found xyz')
    with patch('app.services.esports_service.httpx.get', return_value=resp), _patch_sleep():
        EsportsService._fetch_lol_esports_schedule('LCK_ID', _TODAY, _YESTERDAY)
    warnings = [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert warnings
    msg = warnings[-1].getMessage()
    assert '404' in msg
    assert 'Not Found xyz' in msg
    assert 'LCK_ID' in msg
