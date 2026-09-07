from app.services.watch_analysis_service import WatchAnalysisService


def test_sanitize_levels_drops_wrong_side():
    parsed = {'support_levels': [59.54, 55.0, None], 'resistance_levels': [56.0, 63.75, 'x']}
    WatchAnalysisService._sanitize_levels(parsed, 56.87)
    assert parsed['support_levels'] == [55.0]
    assert parsed['resistance_levels'] == [63.75]


def test_sanitize_levels_noop_without_price():
    parsed = {'support_levels': [59.54], 'resistance_levels': [56.0]}
    WatchAnalysisService._sanitize_levels(parsed, 0)
    assert parsed['support_levels'] == [59.54]
