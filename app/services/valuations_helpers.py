from pathlib import Path
from typing import Optional

import yaml

VALUATIONS_PATH = Path(__file__).resolve().parents[2] / 'docs' / 'stock-analytics' / 'valuations.yaml'


def _extract_price(data: dict) -> Optional[float]:
    price = data.get('price')
    if price is None:
        price = data.get('current_price')
    if not price:
        return None
    return float(price)


def _fetch_code(row: dict) -> str:
    code = row['stock_code']
    if row.get('market') != 'HK':
        return code
    digits = code.upper().removesuffix('.HK')
    if digits.isdigit():
        return f"{int(digits):04d}.HK"
    return code


def compute_margin(value: Optional[float], price: Optional[float]) -> Optional[float]:
    if value is None or not price:
        return None
    return value / price - 1


def load_valuations(path: Path = VALUATIONS_PATH) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding='utf-8'))
    if not isinstance(data, list):
        return []
    return [r for r in data if isinstance(r, dict) and r.get('stock_code')]


def subsector_of(row: dict) -> Optional[str]:
    """从 source_doc 路径提取二级 slug：sectors/<sector>/<subsector>/<file> → parts[2]，否则 None。"""
    parts = (row.get('source_doc') or '').split('/')
    if len(parts) >= 4 and parts[0] == 'sectors':
        return parts[2]
    return None


RATING_TO_QUALITY = {'core': 5, 'config': 4, 'watch': 3, 'exclude': 2}
QUALITY_FALLBACK = 3


def resolve_quality(row: dict) -> tuple[int, bool]:
    """返回 (星级 1-5, 是否由 rating 推算)。row['quality'] 为合法 1-5 整数→手动覆写；
    否则按 rating 映射，未知 rating 兜底 QUALITY_FALLBACK。"""
    q = row.get('quality')
    if isinstance(q, int) and not isinstance(q, bool) and 1 <= q <= 5:
        return q, False
    return RATING_TO_QUALITY.get(row.get('rating'), QUALITY_FALLBACK), True
