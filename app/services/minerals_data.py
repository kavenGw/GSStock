import logging

from app.config.minerals import MINERAL_BOARDS
from app.services.futures import FuturesService

logger = logging.getLogger(__name__)

_LITHIUM_DATE_COL = '日期'
_LITHIUM_CLOSE_COL = '收盘价'


def _fetch_lithium_raw(symbol='LC0'):
    """薄包装 akshare 碳酸锂主连，便于测试 monkeypatch。"""
    import akshare as ak
    return ak.futures_main_sina(symbol=symbol)


def fetch_lithium_futures_trend(days=30):
    """碳酸锂期货主连走势；成功返回 dict，失败/空返回 None。"""
    try:
        df = _fetch_lithium_raw()
    except Exception as e:
        logger.warning(f'[矿产] 碳酸锂期货取数失败: {type(e).__name__}: {e}', exc_info=True)
        return None
    if df is None or getattr(df, 'empty', True):
        return None
    date_col = _LITHIUM_DATE_COL if _LITHIUM_DATE_COL in df.columns else df.columns[0]
    close_col = _LITHIUM_CLOSE_COL if _LITHIUM_CLOSE_COL in df.columns else df.columns[-1]
    data = []
    for _, row in df.tail(days + 10).iterrows():
        try:
            close = float(row[close_col])
        except (TypeError, ValueError):
            continue
        data.append({'date': str(row[date_col])[:10], 'close': close})
    if not data:
        return None
    return {'stock_code': 'LC0', 'stock_name': '碳酸锂主连', 'data': data, 'source': 'akshare'}


def _single_from_custom(code, days):
    """走 FuturesService 取单期货走势的 stocks[0]，无数据返回 None。"""
    res = FuturesService.get_custom_trend_data([code], days)
    stocks = (res or {}).get('stocks') or []
    return stocks[0] if stocks else None


def get_board_futures(commodity, days=30):
    board = MINERAL_BOARDS[commodity]
    name = board['futures_name']
    if board['futures_source'] == 'akshare':
        trend = fetch_lithium_futures_trend(days)
        if trend:
            return {**trend, 'futures_name': name, 'is_fallback': False, 'note': None}
        fb = board.get('futures_fallback_code')
        if fb:
            s = _single_from_custom(fb, days)
            if s:
                return {'stock_code': fb, 'stock_name': s.get('stock_name', fb),
                        'data': s.get('data', []), 'futures_name': name,
                        'is_fallback': True, 'note': '碳酸锂期货数据暂缺，当前为代理指数'}
        return {'stock_code': board['futures_code'], 'stock_name': name, 'data': [],
                'futures_name': name, 'is_fallback': True, 'note': '碳酸锂期货数据暂缺'}
    s = _single_from_custom(board['futures_code'], days)
    data = s.get('data', []) if s else []
    return {'stock_code': board['futures_code'], 'stock_name': name, 'data': data,
            'futures_name': name, 'is_fallback': False, 'note': None}
