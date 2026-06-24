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
