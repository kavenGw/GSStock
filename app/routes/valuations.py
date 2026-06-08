import logging
from collections import Counter
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


def _fetch_code(row: dict) -> str:
    """港股 yaml code 形态不一（01810 / 09992.HK），yfinance 需 4 位补零的 1810.HK / 9992.HK。
    把港股数字部分统一归一为 4 位 + .HK；非港股原样。"""
    code = row['stock_code']
    if row.get('market') != 'HK':
        return code
    digits = code.upper().removesuffix('.HK')
    if digits.isdigit():
        return f"{int(digits):04d}.HK"
    return code


def compute_margin(value: Optional[float], price: Optional[float]) -> Optional[float]:
    """安全边际 = value / price - 1（正=上行空间，负=高估）。value 缺或 price 无效返回 None。"""
    if value is None or not price:
        return None
    return value / price - 1


def load_category_map() -> dict[str, str]:
    """返回 {stock_code: category_name}，来自 StockCategory join Category。
    app-context / 异常守卫：任何失败返回 {}（与取价失败降级同款，不让分类问题打挂整页）。"""
    try:
        from app.models.category import StockCategory
        return {
            sc.stock_code: sc.category.name
            for sc in StockCategory.query.all()
            if sc.category is not None
        }
    except Exception as e:
        logger.warning(f'[估值页] 取分类失败，降级无分类: {type(e).__name__}: {e}', exc_info=True)
        return {}


def load_valuations(path: Path = VALUATIONS_PATH) -> list[dict]:
    """读 valuations.yaml，返回 list[dict]；文件缺失/空返回 []。"""
    path = Path(path)
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding='utf-8'))
    if not isinstance(data, list):
        return []
    return [r for r in data if isinstance(r, dict) and r.get('stock_code')]


def _enrich(rows: list[dict], prices: dict, cat_map: Optional[dict] = None) -> list[dict]:
    cat_map = cat_map or {}
    out = []
    for r in rows:
        data = prices.get(r['stock_code']) or {}
        price = _extract_price(data)
        out.append({
            **r,
            'category': cat_map.get(r['stock_code']),
            'current_price': price,
            'margin_bear': compute_margin(r.get('bear'), price),
            'margin_base': compute_margin(r.get('base'), price),
            'margin_bull': compute_margin(r.get('bull'), price),
        })
    out.sort(key=lambda x: (x['margin_base'] is None, -(x['margin_base'] or 0)))
    return out


SECTOR_LABELS = {
    'semiconductor': '半导体',
    'electronics': '电子',
    'consumer': '消费',
    'materials': '材料',
    'energy': '能源',
    'healthcare': '医疗',
    'media': '媒体',
    'financial': '金融',
    'industrial': '工业',
    'ai-application': 'AI应用',
    'other': '其他',
}

CARVE_OUT_CATEGORIES = {'啤酒'}


def group_by_sector(rows: list[dict]) -> list[dict]:
    """分组：category 命中 CARVE_OUT_CATEGORIES 则用分类名作独立顶级组，否则按 sector。
    组按标的数降序（并列按 key 稳定），组内按 Base 安全边际降序（None 末位）。
    sector 缺失归入「未分类」组；未知 sector 回退原始值。"""
    buckets: dict[str, list] = {}
    for r in rows:
        cat = r.get('category')
        key = cat if cat in CARVE_OUT_CATEGORIES else (r.get('sector') or '__none__')
        buckets.setdefault(key, []).append(r)
    groups = []
    for key, items in buckets.items():
        items = sorted(items, key=lambda x: (x.get('margin_base') is None, -(x.get('margin_base') or 0)))
        if key in CARVE_OUT_CATEGORIES:
            label = key
        elif key == '__none__':
            label = '未分类'
        else:
            label = SECTOR_LABELS.get(key, key)
        for r in items:
            r['sector_label'] = label
        groups.append({'sector': key, 'label': label, 'count': len(items), 'rows': items})
    groups.sort(key=lambda g: (-g['count'], g['sector']))
    return groups


@valuations_bp.route('/')
def index():
    rows = load_valuations()
    fetch_map = {r['stock_code']: _fetch_code(r) for r in rows}
    prices = {}
    if fetch_map:
        try:
            raw = unified_stock_data_service.get_realtime_prices(list(fetch_map.values()))
            prices = {orig: raw.get(fc) for orig, fc in fetch_map.items()}
        except Exception as e:
            logger.warning(f'[估值页] 取实时价失败，降级渲染: {type(e).__name__}: {e}', exc_info=True)
    enriched = _enrich(rows, prices)
    groups = group_by_sector(enriched)
    market_counts = Counter(r.get('market') for r in enriched)
    return render_template(
        'valuations.html',
        groups=groups,
        market_counts=market_counts,
        total=len(enriched),
    )


@valuations_bp.route('/api/prices')
def api_prices():
    force = request.args.get('force') == '1'
    rows = load_valuations()
    fetch_map = {r['stock_code']: _fetch_code(r) for r in rows}
    raw = unified_stock_data_service.get_realtime_prices(list(fetch_map.values()), force_refresh=force) if fetch_map else {}
    prices = {orig: raw.get(fc) for orig, fc in fetch_map.items()}
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
