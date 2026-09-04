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
