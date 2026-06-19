"""每日赛事推送策略 — 路由层单测

验证：
1. 首轮全成功：仅推 Slack，不 enqueue
2. 部分联赛失败：成功联赛进入首推消息，失败联赛 enqueue
3. 全部 LoL 联赛失败（get_lol_schedule 返回 None）：不发首推，对所有 LOL_ALWAYS_SHOW 联赛 enqueue
4. NBA 失败：不推首条 NBA 消息，enqueue NBA
"""
from datetime import date, datetime, timedelta, timezone

import pytest

import app.services.esports_retry_queue as rq
from app.strategies.esports_daily_schedule import EsportsDailyScheduleStrategy


_CST = timezone(timedelta(hours=8))


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    rq._pending.clear()
    monkeypatch.setattr(rq, '_schedule_retry', lambda key: None)
    yield
    rq._pending.clear()


class _SlackCapture:
    def __init__(self):
        self.calls = []

    def __call__(self, message, channel, blocks=None):
        self.calls.append((message, channel))
        return True


def _patch_slack(monkeypatch):
    cap = _SlackCapture()
    from app.services import notification
    monkeypatch.setattr(notification.NotificationService, 'send_slack', staticmethod(cap))
    return cap


def test_lol_partial_success_pushes_first_and_enqueues_failures(monkeypatch):
    cap = _patch_slack(monkeypatch)
    fake_lol = {
        'LPL': {'today': [{'team1': 'WBG', 'team2': 'WE', 'start_time': '17:00'}], 'yesterday': []},
        'LCK': None,
        '先锋赛': None,
    }
    monkeypatch.setattr(
        'app.services.esports_service.EsportsService.get_lol_schedule',
        staticmethod(lambda today=None: fake_lol),
    )

    EsportsDailyScheduleStrategy._push_lol_today()

    # 首推只含 LPL
    assert len(cap.calls) == 1
    text = cap.calls[0][0]
    assert 'LPL' in text and 'WBG vs WE' in text
    assert 'LCK' not in text and '先锋赛' not in text
    assert '数据获取失败' not in text

    # LCK / 先锋赛 进入挂起队列
    today = datetime.now(_CST).date()
    assert rq._key(today, 'lol', 'LCK') in rq._pending
    assert rq._key(today, 'lol', '先锋赛') in rq._pending


def test_lol_all_failed_no_first_push_enqueues_always_show(monkeypatch):
    cap = _patch_slack(monkeypatch)
    monkeypatch.setattr(
        'app.services.esports_service.EsportsService.get_lol_schedule',
        staticmethod(lambda today=None: None),
    )

    EsportsDailyScheduleStrategy._push_lol_today()

    assert cap.calls == []
    today = datetime.now(_CST).date()
    from app.config.esports_config import LOL_ALWAYS_SHOW
    for league in LOL_ALWAYS_SHOW:
        assert rq._key(today, 'lol', league) in rq._pending


def test_lol_all_success_pushes_first_no_enqueue(monkeypatch):
    cap = _patch_slack(monkeypatch)
    fake_lol = {
        'LPL': {'today': [{'team1': 'A', 'team2': 'B', 'start_time': '17:00'}], 'yesterday': []},
        'LCK': {'today': [{'team1': 'T1', 'team2': 'GEN', 'start_time': '20:00'}], 'yesterday': []},
        '先锋赛': {'today': [], 'yesterday': []},
    }
    monkeypatch.setattr(
        'app.services.esports_service.EsportsService.get_lol_schedule',
        staticmethod(lambda today=None: fake_lol),
    )

    EsportsDailyScheduleStrategy._push_lol_today()

    assert len(cap.calls) == 1
    text = cap.calls[0][0]
    assert 'LPL' in text and 'LCK' in text and '先锋赛' in text and '今日无赛事' in text
    assert rq._pending == {}


def test_nba_failure_enqueues(monkeypatch):
    cap = _patch_slack(monkeypatch)
    monkeypatch.setattr(
        'app.services.esports_service.EsportsService.get_nba_schedule',
        staticmethod(lambda today=None: None),
    )

    EsportsDailyScheduleStrategy._push_nba_today()

    assert cap.calls == []
    today = datetime.now(_CST).date()
    assert rq._key(today, 'nba', 'NBA') in rq._pending


def test_worldcup_failure_enqueues(monkeypatch):
    cap = _patch_slack(monkeypatch)
    monkeypatch.setattr(
        'app.services.worldcup_service.WorldCupService.get_worldcup_schedule',
        staticmethod(lambda today=None: None),
    )
    EsportsDailyScheduleStrategy._push_worldcup_today()
    assert cap.calls == []
    today = datetime.now(_CST).date()
    assert rq._key(today, 'worldcup', 'WorldCup') in rq._pending


def test_worldcup_success_pushes(monkeypatch):
    cap = _patch_slack(monkeypatch)
    fake = {'today': [{'home': '巴西', 'away': '中国', 'start_time': '08:00'}],
            'yesterday': []}
    monkeypatch.setattr(
        'app.services.worldcup_service.WorldCupService.get_worldcup_schedule',
        staticmethod(lambda today=None: fake),
    )
    EsportsDailyScheduleStrategy._push_worldcup_today()
    assert len(cap.calls) == 1
    text, channel = cap.calls[0]
    assert channel == 'news_worldcup'
    assert '巴西 vs 中国' in text and '08:00' in text
    assert rq._pending == {}


def test_worldcup_empty_pushes_no_match(monkeypatch):
    cap = _patch_slack(monkeypatch)
    monkeypatch.setattr(
        'app.services.worldcup_service.WorldCupService.get_worldcup_schedule',
        staticmethod(lambda today=None: {'today': [], 'yesterday': []}),
    )
    EsportsDailyScheduleStrategy._push_worldcup_today()
    assert len(cap.calls) == 1
    assert '今日无比赛' in cap.calls[0][0]
