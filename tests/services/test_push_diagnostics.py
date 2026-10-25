import json
import logging
from unittest.mock import MagicMock

import pytest
from flask import Flask

from app.scheduler.engine import SchedulerEngine
from app.services import notification


@pytest.mark.parametrize('body, expected, marker', [
    ({'ok': True, 'ts': '123.456'}, True, '发送成功'),
    ({'ok': False, 'error': 'not_in_channel'}, False, 'not_in_channel'),
])
def test_slack_result_logs_without_payload(monkeypatch, caplog, body, expected, marker):
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps(body).encode()
    monkeypatch.setattr(notification, 'urlopen', lambda *args, **kwargs: response)
    monkeypatch.setattr(notification, 'SLACK_ENABLED', True)
    monkeypatch.setattr(notification, 'SLACK_BOT_TOKEN', 'secret-test-token')
    with caplog.at_level(logging.INFO):
        assert notification.NotificationService.send_slack('private-message', 'news_watch') is expected
    assert marker in caplog.text
    assert 'channel=news_watch' in caplog.text
    assert 'private-message' not in caplog.text
    assert 'secret-test-token' not in caplog.text


def test_slack_disabled_logs_reason_without_sending(monkeypatch, caplog):
    post = MagicMock()
    monkeypatch.setattr(notification, 'SLACK_ENABLED', False)
    monkeypatch.setattr(notification.NotificationService, '_post_slack', post)
    assert notification.NotificationService.send_slack('test', 'news_watch') is False
    post.assert_not_called()
    assert 'reason=slack_not_configured' in caplog.text


def test_slack_network_failure_is_redacted(monkeypatch, caplog):
    def fail(*args, **kwargs):
        raise TimeoutError('private-message secret-test-token')

    monkeypatch.setattr(notification, 'urlopen', fail)
    assert notification.NotificationService._post_slack({'channel': 'news_watch', 'text': 'test'}) is False
    assert 'error_type=TimeoutError' in caplog.text
    assert 'private-message' not in caplog.text
    assert 'secret-test-token' not in caplog.text


def test_zero_signal_scan_is_visible(monkeypatch, caplog):
    from app.strategies.registry import registry

    strategy = MagicMock()
    strategy.scan.return_value = []
    monkeypatch.setattr(registry, 'get', lambda name: strategy)
    engine = SchedulerEngine()
    engine.app = Flask(__name__)
    with caplog.at_level(logging.INFO):
        engine._run_strategy('watch_alert')
    strategy.scan.assert_called_once_with()
    assert '扫描开始 strategy=watch_alert' in caplog.text
    assert 'returned_signals=0' in caplog.text
