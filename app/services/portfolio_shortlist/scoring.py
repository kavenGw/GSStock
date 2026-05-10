"""6 维度打分公式 — spec §3。

输入子分 ∈ [0, 1]（realized 维度 ∈ [-1, 1]），按各维度满分线性映射。
"""

from dataclasses import dataclass, asdict


_RATING_BASE = {'core': 50, 'config': 25}
_LOGIC_MAX = 15
_VALUATION_MAX = 10
_CATALYST_MAX = 10
_THEME_FIT_MAX = 5
_TECHNICAL_MAX = 10
_REALIZED_PENALTY = -20
_REALIZED_BONUS = 5


@dataclass
class ScoreBreakdown:
    total: float
    base: int
    logic: float
    valuation: float
    catalyst: float
    theme_fit: float
    realized: float
    technical: float

    def as_dict(self) -> dict:
        return asdict(self)


def _avg(d: dict, default: float = 0.5) -> float:
    if not d:
        return default
    vals = [v for v in d.values() if v is not None]
    return sum(vals) / len(vals) if vals else default


def score_stock(rating: str, summary: dict, technical: dict) -> ScoreBreakdown:
    if rating not in _RATING_BASE:
        raise ValueError(f'rating must be core or config, got {rating}')

    def sub(field: str) -> float:
        v = summary.get(field, ('', 0.5))
        return v[1] if isinstance(v, tuple) else 0.5

    base = _RATING_BASE[rating]
    logic = round(sub('logic') * _LOGIC_MAX, 2)
    valuation = round(sub('valuation') * _VALUATION_MAX, 2)
    catalyst = round(sub('catalyst') * _CATALYST_MAX, 2)
    theme_fit = round(sub('theme_fit') * _THEME_FIT_MAX, 2)

    realized_score = sub('realized_or_invalidated')
    if realized_score >= 0:
        realized = round(realized_score * _REALIZED_BONUS, 2)
    else:
        realized = round(realized_score * abs(_REALIZED_PENALTY), 2)

    technical_score = round(_avg(technical) * _TECHNICAL_MAX, 2)

    total = base + logic + valuation + catalyst + theme_fit + realized + technical_score

    return ScoreBreakdown(
        total=round(total, 2),
        base=base,
        logic=logic,
        valuation=valuation,
        catalyst=catalyst,
        theme_fit=theme_fit,
        realized=realized,
        technical=technical_score,
    )
