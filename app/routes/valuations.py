import logging
from collections import Counter
from typing import Optional

from flask import render_template, jsonify, request

from app.routes import valuations_bp
from app.services import unified_stock_data_service
from app.services.valuations_helpers import (
    VALUATIONS_PATH, load_valuations, _fetch_code, _extract_price, compute_margin, subsector_of,
)

logger = logging.getLogger(__name__)

RATING_RANK = {'core': 4, 'config': 3, 'watch': 2, 'exclude': 1}


def _date_rank(d) -> Optional[int]:
    """conviction_date（str 或 yaml 解析出的 date）归一为 YYYYMMDD 整数，非法/缺失返回 None。"""
    digits = str(d or '').replace('-', '')[:8]
    return int(digits) if len(digits) == 8 and digits.isdigit() else None


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


def _enrich(rows: list[dict], prices: dict, cat_map: Optional[dict] = None) -> list[dict]:
    cat_map = cat_map or {}
    out = []
    for r in rows:
        data = prices.get(r['stock_code']) or {}
        price = _extract_price(data)
        out.append({
            **r,
            'category': cat_map.get(r['stock_code']),
            'subsector': subsector_of(r),
            'current_price': price,
            'rating_rank': RATING_RANK.get(r.get('rating')),
            'date_rank': _date_rank(r.get('conviction_date')),
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

SUBSECTOR_LABELS = {
    'storage': '存储', 'design': '设计', 'equipment': '设备', 'optical': '光学',
    'power': '功率', 'mcu': 'MCU', 'optical-components': '光学元件', 'wafer': '晶圆',
    'pcb': 'PCB', 'packaging': '封装', 'sic-substrate': '碳化硅衬底', 'mems': 'MEMS',
    'photonics': '光子', 'foundry': '晶圆代工', 'laser-chip': '激光芯片', 'networking': '网络',
    'advanced-packaging': '先进封装', 'materials': '材料', 'components': '元器件', 'ems': 'EMS',
    'display': '显示', 'servers': '服务器', 'pc-server': 'PC服务器', 'power-electronics': '功率电子',
    'functional-materials': '功能材料', 'display-glass': '显示玻璃', 'precision-manufacturing': '精密制造',
    'pcb-equipment': 'PCB设备', 'thermal-management': '热管理', 'nonferrous': '有色',
    'copper-foil': '铜箔', 'chemicals': '化工', 'magnetic-materials': '磁材', 'ceramics': '陶瓷',
    'minor-metals': '小金属', 'superhard': '超硬材料', 'lithium': '锂', 'consumer-electronics': '消费电子',
    'sportswear': '运动服饰', 'beer': '啤酒', 'home-appliance': '家电', 'mobility': '出行',
    'local-services': '本地生活', 'restaurant': '餐饮', 'designer-toy': '潮玩', 'auto': '汽车',
    'furniture': '家居', 'auto-ev': '新能源车', 'ev': '电动车', 'power-equipment': '电力设备',
    'cable': '线缆', 'auto-parts': '汽车零部件', 'precision-components': '精密零件',
    'cleanroom-epc': '洁净室EPC', 'defense': '国防军工', 'music-streaming': '音乐流媒体',
    'digital-marketing': '数字营销', 'short-video': '短视频', 'online-literature': '网络文学',
    'shopping-guide': '导购', 'internet-platform': '互联网平台', 'solar': '光伏', 'battery': '电池',
    'waste-to-energy': '垃圾发电', 'cloud': '云计算', 'software': '软件', 'database': '数据库',
    'exchange': '交易所', 'securities': '证券', 'cro': 'CRO',
}


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
            raw = unified_stock_data_service.get_realtime_prices(list(fetch_map.values()), cache_only=True)
            prices = {orig: raw.get(fc) for orig, fc in fetch_map.items()}
        except Exception as e:
            logger.warning(f'[估值页] 取实时价失败，降级渲染: {type(e).__name__}: {e}', exc_info=True)
    cat_map = load_category_map()
    enriched = _enrich(rows, prices, cat_map)
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
