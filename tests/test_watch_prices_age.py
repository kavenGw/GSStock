from datetime import datetime, timedelta
from app.routes.watch import _price_age_seconds


def test_age_from_isoformat():
    ts = (datetime.now() - timedelta(seconds=90)).isoformat()
    age = _price_age_seconds({'last_fetch_time': ts})
    assert 85 <= age <= 95


def test_age_none_on_missing():
    assert _price_age_seconds({}) is None


def test_age_none_on_garbage():
    assert _price_age_seconds({'last_fetch_time': 'not-a-date'}) is None
