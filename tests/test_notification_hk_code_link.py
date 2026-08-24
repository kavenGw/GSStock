"""港股代码在 Slack 推送里不得被 autolink 成域名

`0358.HK` 形如域名（.hk 是有效 TLD），Slack 会自动转成 http://0358.hk 超链接。
出口层统一改写成 `HK 0358`，text 与 blocks 两条路径都要覆盖。
"""
from app.services.notification import NotificationService as N


def test_sanitize_rewrites_hk_suffix_to_prefix():
    assert N._sanitize_hk_codes('江西铜业(0358.HK) 中报披露') == '江西铜业(HK 0358) 中报披露'


def test_sanitize_handles_multiple_and_five_digit_codes():
    out = N._sanitize_hk_codes('腾讯控股(0700.HK) 紫金矿业(2899.HK) 某股(01810.HK)')
    assert out == '腾讯控股(HK 0700) 紫金矿业(HK 2899) 某股(HK 01810)'


def test_sanitize_leaves_plain_text_and_urls_untouched():
    src = '贵州茅台(600519) <https://github.com/foo/releases|v1.2.3> www.example.hk'
    assert N._sanitize_hk_codes(src) == src


def test_send_slack_sanitizes_text_payload(monkeypatch):
    sent = {}
    monkeypatch.setattr(N, '_post_slack', staticmethod(lambda data: sent.update(data) or True))

    N.send_slack('江西铜业(0358.HK) 今天发布财报')

    assert sent['text'] == '江西铜业(HK 0358) 今天发布财报'


def test_send_slack_sanitizes_nested_blocks(monkeypatch):
    sent = {}
    monkeypatch.setattr(N, '_post_slack', staticmethod(lambda data: sent.update(data) or True))

    blocks = [
        N._block_header('📅 未来7天事件'),
        N._block_section('  今天  江西铜业(0358.HK) 中报披露'),
        N._block_divider(),
        N._block_fields(['腾讯控股(0700.HK) `+1.20%`', '贵州茅台(600519) `-0.30%`']),
    ]
    N.send_slack('江西铜业(0358.HK)', blocks=blocks)

    assert sent['blocks'][1]['text']['text'] == '  今天  江西铜业(HK 0358) 中报披露'
    assert sent['blocks'][3]['fields'][0]['text'] == '腾讯控股(HK 0700) `+1.20%`'
    assert sent['blocks'][3]['fields'][1]['text'] == '贵州茅台(600519) `-0.30%`'
    assert sent['blocks'][2] == {'type': 'divider'}
