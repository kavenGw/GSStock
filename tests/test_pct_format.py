"""涨跌幅统一着色渲染：红涨绿跌，emoji 紧贴百分比"""
import types

import pytest

from app.services.notification import NotificationService as N


class TestFmtPct:
    def test_up_uses_red_dot(self):
        assert N.fmt_pct(1.24) == '🔴+1.24%'

    def test_down_uses_green_dot(self):
        assert N.fmt_pct(-0.87) == '🟢-0.87%'

    def test_flat_uses_white_dot_without_sign(self):
        assert N.fmt_pct(0) == '⚪0.00%'

    def test_none_returns_dash(self):
        assert N.fmt_pct(None) == '—'

    def test_none_placeholder_overridable(self):
        assert N.fmt_pct(None, none='') == ''

    def test_digits_controls_precision(self):
        assert N.fmt_pct(5.12, digits=1) == '🔴+5.1%'

    def test_code_wraps_number_in_backticks(self):
        assert N.fmt_pct(-1.03, code=True) == '🟢`-1.03%`'

    def test_code_does_not_wrap_the_dash(self):
        assert N.fmt_pct(None, code=True) == '—'


class TestIndexItemColoring:
    def test_index_up_is_red_no_chart_emoji(self):
        out = N._fmt_index_item({'name': '上证指数', 'close': 3412.0, 'change_percent': 1.24})
        assert '🔴`+1.24%`' in out
        assert '📈' not in out and '📉' not in out

    def test_index_down_is_green(self):
        out = N._fmt_index_item({'name': '纳斯达克', 'close': 18220.0, 'change_percent': -0.87})
        assert '🟢`-0.87%`' in out

    def test_index_without_pct_has_no_dot(self):
        out = N._fmt_index_item({'name': '上证指数', 'close': 3412.0, 'change_percent': None})
        assert '🔴' not in out and '🟢' not in out and '⚪' not in out


class TestSectorColoring:
    def test_cn_and_us_sectors_get_dots(self, monkeypatch):
        from app.services import briefing as briefing_mod
        monkeypatch.setattr(briefing_mod.BriefingService, 'get_cn_sectors_data',
                            staticmethod(lambda: [{'name': '半导体', 'change_percent': 3.5, 'leader': '兆易创新'}]))
        monkeypatch.setattr(briefing_mod.BriefingService, 'get_us_sectors_data',
                            staticmethod(lambda: [{'name': '科技', 'change_percent': -1.2}]))
        out = N.format_sectors_summary()
        assert '🔴+3.50%' in out
        assert '🟢-1.20%' in out


class TestPremiumNotColored:
    """溢价/折价语义与红绿相反，不得按涨跌着色"""

    def test_etf_premium_keeps_signal_label_only(self, monkeypatch):
        from app.services import briefing as briefing_mod
        monkeypatch.setattr(briefing_mod.BriefingService, 'get_etf_premium_data',
                            staticmethod(lambda: {'etfs': [
                                {'name': '纳指ETF', 'premium_rate': 2.0, 'signal': 'sell'}]}))
        out = N.format_etf_premium_summary()
        assert '纳指ETF +2.00%🟢溢价过高' in out
        assert '🔴+2.00%' not in out

    def test_adr_premium_keeps_discount_tag(self, monkeypatch):
        from app.services import briefing as briefing_mod
        monkeypatch.setattr(briefing_mod.BriefingService, 'get_adr_premium_data',
                            staticmethod(lambda: {'pairs': [
                                {'name': '中芯国际', 'premium_rate': -3.0, 'delta': None}]}))
        out = N.format_adr_premium_summary()
        assert '中芯国际 -3.00%(折价)' in out
        assert '🟢-3.00%' not in out


class TestWatchAlertHeadlineNotDoubleDotted:
    """告警首行已有方向 emoji 作消息标识，百分比不得再加色块（一条目一个色块）"""

    def _alert(self, chg):
        return types.SimpleNamespace(
            priority='HIGH', name='兆易创新', code='603986', change_percent=chg,
            current_price=128.5, primary_line='突破阻力 128.00',
            secondary_lines=[], context_line='',
        )

    def _capture(self, monkeypatch, alert):
        sent = []
        monkeypatch.setattr(N, 'send_slack',
                            staticmethod(lambda msg, ch=None, blocks=None: sent.append(msg) or True))
        N.push_watch_alerts([alert])
        return sent[0]

    def test_leading_dot_only(self, monkeypatch):
        msg = self._capture(monkeypatch, self._alert(5.12))
        assert msg.startswith('🔴 *兆易创新(603986)* 128.5 +5.12%')
        assert msg.count('🔴') == 1

    def test_missing_pct_keeps_warning_dot(self, monkeypatch):
        msg = self._capture(monkeypatch, self._alert(None))
        assert msg.startswith('⚠️ *兆易创新(603986)*')
