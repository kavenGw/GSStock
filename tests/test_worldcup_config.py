def test_channel_constant():
    from app.config.notification_config import CHANNEL_WORLDCUP
    assert CHANNEL_WORLDCUP == 'news_worldcup'


def test_worldcup_config_defaults(monkeypatch):
    monkeypatch.delenv('WORLDCUP_ENABLED', raising=False)
    monkeypatch.delenv('ESPORTS_WORLDCUP_MONITOR_INTERVAL', raising=False)
    import importlib
    import app.config.worldcup_config as wc
    importlib.reload(wc)
    assert wc.WORLDCUP_ENABLED is True
    assert wc.ESPORTS_WORLDCUP_MONITOR_INTERVAL == 5
    assert wc.WORLDCUP_MAX_DURATION_HOURS == 3
    assert wc.ESPN_SOCCER_WC_URL.endswith('soccer/fifa.world/scoreboard')
    assert wc.WORLDCUP_TEAM_NAMES.get('Brazil') == '巴西'
