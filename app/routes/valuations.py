import logging
from pathlib import Path
from typing import Optional

import yaml
from flask import render_template, jsonify, request

from app.routes import valuations_bp
from app.services import unified_stock_data_service

logger = logging.getLogger(__name__)

VALUATIONS_PATH = Path(__file__).resolve().parents[2] / 'docs' / 'stock-analytics' / 'valuations.yaml'


def _extract_price(data: dict) -> Optional[float]:
    """防御读价：PriceData 用 'price'，内存缓存层可能用 'current_price'；0/None 均视为无效。"""
    price = data.get('price')
    if price is None:
        price = data.get('current_price')
    if not price:  # None 或 0
        return None
    return float(price)


def compute_margin(value: Optional[float], price: Optional[float]) -> Optional[float]:
    """安全边际 = value / price - 1（正=上行空间，负=高估）。value 缺或 price 无效返回 None。"""
    if value is None or not price:
        return None
    return value / price - 1


def load_valuations(path: Path = VALUATIONS_PATH) -> list[dict]:
    """读 valuations.yaml，返回 list[dict]；文件缺失/空返回 []。"""
    path = Path(path)
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding='utf-8'))
    if not isinstance(data, list):
        return []
    return [r for r in data if isinstance(r, dict) and r.get('stock_code')]


def _enrich(rows: list[dict], prices: dict) -> list[dict]:
    out = []
    for r in rows:
        data = prices.get(r['stock_code']) or {}
        price = _extract_price(data)
        out.append({
            **r,
            'current_price': price,
            'margin_bear': compute_margin(r.get('bear'), price),
            'margin_base': compute_margin(r.get('base'), price),
            'margin_bull': compute_margin(r.get('bull'), price),
        })
    out.sort(key=lambda x: (x['margin_base'] is None, -(x['margin_base'] or 0)))
    return out


@valuations_bp.route('/')
def index():
    rows = load_valuations()
    codes = [r['stock_code'] for r in rows]
    prices = {}
    if codes:
        try:
            prices = unified_stock_data_service.get_realtime_prices(codes)
        except Exception as e:
            logger.warning(f'[估值页] 取实时价失败，降级渲染: {type(e).__name__}: {e}', exc_info=True)
    return render_template('valuations.html', rows=_enrich(rows, prices))


@valuations_bp.route('/api/prices')
def api_prices():
    force = request.args.get('force') == '1'
    rows = load_valuations()
    codes = [r['stock_code'] for r in rows]
    prices = unified_stock_data_service.get_realtime_prices(codes, force_refresh=force) if codes else {}
    out = {}
    for r in rows:
        data = prices.get(r['stock_code']) or {}
        price = _extract_price(data)
        out[r['stock_code']] = {
            'current_price': price,
            'margin_bear': compute_margin(r.get('bear'), price),
            'margin_base': compute_margin(r.get('base'), price),
            'margin_bull': compute_margin(r.get('bull'), price),
        }
    return jsonify(out)
