from app.utils.market_identifier import MarketIdentifier


def test_kospi_index_identified_as_kr():
    assert MarketIdentifier.identify('^KS11') == 'KR'
    assert MarketIdentifier.identify('^KQ11') == 'KR'


def test_us_index_still_us():
    assert MarketIdentifier.identify('^GSPC') == 'US'
    assert MarketIdentifier.identify('^NDX') == 'US'


def test_kospi_to_yfinance_unchanged():
    assert MarketIdentifier.to_yfinance('^KS11') == '^KS11'
