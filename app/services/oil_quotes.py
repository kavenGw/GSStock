import math
from datetime import timezone

from app.services.oil_alert_service import trading_date


def fetch_oil_quote(ticker, code, daily, fetched_at):
    intraday = ticker.history(period='5d', interval='1m')
    if intraday.empty or intraday.index.tz is None:
        return None
    timestamp = intraday.index[-1].to_pydatetime().astimezone(timezone.utc)
    day = trading_date(timestamp.replace(tzinfo=None))
    previous = daily[[value.date().isoformat() < day for value in daily.index]]
    if previous.empty:
        return None
    prev_close = float(previous.iloc[-1]['Close'])
    price = float(intraday.iloc[-1]['Close'])
    if not all(math.isfinite(value) and value > 0 for value in (price, prev_close)):
        return None
    return {
        'code': code, 'name': code, 'market': 'US',
        'current_price': round(price, 2),
        'change': round(price - prev_close, 2),
        'change_percent': (price / prev_close - 1) * 100,
        'prev_close': prev_close,
        'last_fetch_time': fetched_at,
        'quote_time': timestamp.isoformat(),
        'trading_date': day,
        '_is_degraded': False,
    }
