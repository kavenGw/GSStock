import pytest

from app.services.portfolio_shortlist.scoring import score_stock, ScoreBreakdown


def make_summary(logic=0.8, valuation=0.7, catalyst=0.9, theme_fit=1.0, realized=0.0):
    return {
        'logic': ('强主线', logic),
        'valuation': ('PE 合理', valuation),
        'catalyst': ('Q2 财报锚', catalyst),
        'theme_fit': ('核心受益', theme_fit),
        'realized_or_invalidated': ('未失效', realized),
    }


def make_tech(ma20=1.0, vol=1.0, support=1.0, td=0.5, trend=1.0):
    return {
        'ma20_position': ma20,
        'volume_ratio': vol,
        'support_ok': support,
        'td_signal': td,
        'trend_direction': trend,
    }


def test_core_full_score():
    sb = score_stock('core', make_summary(1, 1, 1, 1, 0), make_tech(1, 1, 1, 1, 1))
    assert sb.base == 50
    assert sb.logic == 15
    assert sb.valuation == 10
    assert sb.catalyst == 10
    assert sb.technical == 10
    assert sb.realized == 0
    assert sb.theme_fit == 5
    assert sb.total == 50 + 15 + 10 + 10 + 10 + 5


def test_config_partial():
    sb = score_stock('config', make_summary(0.5, 0.6, 0.4, 0.5, 0.0), make_tech(0.5, 0.5, 0.5, 0.5, 0.5))
    assert sb.base == 25
    assert 0 < sb.total < 100


def test_realized_invalidated_penalty():
    sb = score_stock('core', make_summary(1, 1, 1, 1, -1.0), make_tech(1, 1, 1, 1, 1))
    assert sb.realized == -20
    sb_pos = score_stock('core', make_summary(1, 1, 1, 1, 1.0), make_tech(1, 1, 1, 1, 1))
    assert sb_pos.realized == 5


def test_watch_excluded_from_competition():
    with pytest.raises(ValueError, match='rating must be core or config'):
        score_stock('watch', make_summary(), make_tech())


def test_breakdown_dict_shape():
    sb = score_stock('core', make_summary(), make_tech())
    d = sb.as_dict()
    assert set(d.keys()) >= {'total', 'base', 'logic', 'valuation', 'catalyst',
                             'theme_fit', 'realized', 'technical'}
