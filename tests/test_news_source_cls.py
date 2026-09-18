"""财联社电报改走 /v1/roll/get_roll_list，须带 sign=md5(sha1(排序后 k=v&… 不编码))"""
import hashlib

from app.services.news_sources.cls import CLSSource, CLS_API, _sign


def test_sign_sorts_keys_and_double_hashes_without_urlencoding():
    params = {'sv': '8.7.9', 'app': 'CailianpressWeb', 'last_time': '', 'os': 'web'}
    qs = 'app=CailianpressWeb&last_time=&os=web&sv=8.7.9'
    expected = hashlib.md5(hashlib.sha1(qs.encode()).hexdigest().encode()).hexdigest()
    assert _sign(params) == expected


def test_fetch_latest_uses_roll_endpoint_and_parses_roll_data(monkeypatch):
    captured = {}

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {'errno': 0, 'data': {'roll_data': [
                {'id': 1, 'content': '甲', 'ctime': 100, 'level': 'B'},
                {'id': 2, 'content': '', 'title': '乙', 'ctime': 101, 'level': 'C'},
                {'id': 3, 'content': '', 'title': '', 'ctime': 102},
            ]}}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured.update(url=url, params=params)
        return Resp()

    monkeypatch.setattr('app.services.news_sources.cls.requests.get', fake_get)
    items = CLSSource().fetch_latest()

    assert captured['url'] == CLS_API == 'https://www.cls.cn/v1/roll/get_roll_list'
    assert captured['params']['sv'] == '8.7.9'
    assert captured['params']['sign'] == _sign({k: v for k, v in captured['params'].items() if k != 'sign'})
    assert [(i['source_id'], i['content'], i['score']) for i in items] == [('1', '甲', 2), ('2', '乙', 1)]


def test_fetch_latest_raises_on_api_errno(monkeypatch):
    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {'errno': '10012', 'msg': '签名错误'}

    monkeypatch.setattr('app.services.news_sources.cls.requests.get', lambda *a, **k: Resp())
    import pytest
    with pytest.raises(ValueError, match='签名错误'):
        CLSSource().fetch_latest()
