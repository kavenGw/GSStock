from datetime import datetime, timedelta, timezone

from flask import Flask

from app.services.esports_monitor_service import EsportsMonitorService

_CST = timezone(timedelta(hours=8))


def _svc():
    return EsportsMonitorService(Flask(__name__))


def test_prematch_worldcup_routes_to_channel(monkeypatch):
    calls = []
    from app.services import notification
    monkeypatch.setattr(notification.NotificationService, 'send_slack',
                        staticmethod(lambda m, c, blocks=None: calls.append((m, c))))
    _svc()._push_pre_match_notification('worldcup', 'm1', '巴西 vs 中国',
                                        'WorldCup', '08:00')
    assert len(calls) == 1
    msg, channel = calls[0]
    assert channel == 'news_worldcup'
    assert msg.startswith('⚽')
    assert '[' not in msg.split('|')[0]  # 无 league 前缀
    assert '巴西 vs 中国' in msg


def test_poll_worldcup_in_progress_pushes_score(monkeypatch):
    calls = []
    from app.services import notification
    monkeypatch.setattr(notification.NotificationService, 'send_slack',
                        staticmethod(lambda m, c, blocks=None: calls.append((m, c))))
    live = {'m1': {'home': '巴西', 'away': '中国', 'home_score': 1,
                   'away_score': 0, 'status': 'in_progress', 'status_detail': "67'",
                   'pens': None, 'home_winner': False, 'away_winner': False}}
    monkeypatch.setattr(
        'app.services.worldcup_service.WorldCupService.get_worldcup_live_scores',
        staticmethod(lambda: live),
    )
    # 清理可能残留的比分状态
    import app.services.esports_monitor_service as mod
    with mod._score_state_lock:
        mod._score_state.clear()

    future = datetime.now(_CST) + timedelta(hours=1)
    _svc()._poll_match('worldcup', 'm1', '巴西 vs 中国', 'WorldCup', future)
    assert len(calls) == 1
    msg, channel = calls[0]
    assert channel == 'news_worldcup'
    assert msg.startswith('⚽') and '*巴西 1*' in msg
