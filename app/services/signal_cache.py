"""
信号缓存服务 - 使用年数据计算买卖点信号并缓存
"""
import logging
from datetime import date, datetime, timedelta

from app import db
from app.models.signal_cache import SignalCache
from app.services.signal_detector import SignalDetector

logger = logging.getLogger(__name__)

# 信号计算所需最小天数
SIGNAL_CALC_DAYS = 365


class SignalCacheService:
    """买卖点信号缓存服务"""

    @staticmethod
    def get_signals_for_stock(stock_code: str, start_date: date = None, end_date: date = None) -> dict:
        """获取指定股票在日期范围内的信号

        Args:
            stock_code: 股票代码
            start_date: 开始日期（默认30天前）
            end_date: 结束日期（默认今天）

        Returns:
            {'buy_signals': [...], 'sell_signals': [...]}
        """
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        signals = SignalCache.query.filter(
            SignalCache.stock_code == stock_code,
            SignalCache.signal_date >= start_date,
            SignalCache.signal_date <= end_date
        ).all()

        buy_signals = []
        sell_signals = []

        for sig in signals:
            sig_dict = sig.to_dict()
            if sig.signal_type == 'buy':
                buy_signals.append(sig_dict)
            else:
                sell_signals.append(sig_dict)

        return {'buy_signals': buy_signals, 'sell_signals': sell_signals}

    @staticmethod
    def get_signals_for_stocks(stock_codes: list[str], start_date: date = None, end_date: date = None) -> dict:
        """获取多只股票在日期范围内的信号

        Args:
            stock_codes: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            {'buy_signals': [...], 'sell_signals': [...]}
        """
        if end_date is None:
            end_date = date.today()
        if start_date is None:
            start_date = end_date - timedelta(days=30)

        signals = SignalCache.query.filter(
            SignalCache.stock_code.in_(stock_codes),
            SignalCache.signal_date >= start_date,
            SignalCache.signal_date <= end_date
        ).all()

        buy_signals = []
        sell_signals = []

        for sig in signals:
            sig_dict = sig.to_dict()
            sig_dict['stock_code'] = sig.stock_code
            if sig.signal_type == 'buy':
                buy_signals.append(sig_dict)
            else:
                sell_signals.append(sig_dict)

        return {'buy_signals': buy_signals, 'sell_signals': sell_signals}

    @staticmethod
    def update_signals_for_stock(stock_code: str, stock_name: str, ohlc_data: list) -> dict:
        """更新单只股票的信号缓存

        Args:
            stock_code: 股票代码
            stock_name: 股票名称（用于信号返回值）
            ohlc_data: 年度OHLC数据列表

        Returns:
            {'buy_signals': [...], 'sell_signals': [...]}
        """
        if not ohlc_data or len(ohlc_data) < 5:
            logger.debug(f'[SignalCache] {stock_code} 数据不足: {len(ohlc_data) if ohlc_data else 0}条')
            return {'buy_signals': [], 'sell_signals': []}

        # 检测信号
        signals = SignalDetector.detect_all(ohlc_data)

        # 清除该股票旧的信号
        SignalCache.query.filter_by(stock_code=stock_code).delete()

        # 保存新信号到缓存
        for sig in signals.get('buy_signals', []):
            try:
                sig_date = datetime.strptime(sig['date'], '%Y-%m-%d').date() if sig.get('date') else None
            except ValueError:
                logger.warning(f'[SignalCache] {stock_code} 买点日期格式错误: {sig.get("date")}')
                continue
            if sig_date:
                cache = SignalCache(
                    stock_code=stock_code,
                    signal_date=sig_date,
                    signal_type='buy',
                    signal_name=sig.get('name', ''),
                    description=sig.get('description', '')
                )
                db.session.add(cache)
                sig['stock_name'] = stock_name

        for sig in signals.get('sell_signals', []):
            try:
                sig_date = datetime.strptime(sig['date'], '%Y-%m-%d').date() if sig.get('date') else None
            except ValueError:
                logger.warning(f'[SignalCache] {stock_code} 卖点日期格式错误: {sig.get("date")}')
                continue
            if sig_date:
                cache = SignalCache(
                    stock_code=stock_code,
                    signal_date=sig_date,
                    signal_type='sell',
                    signal_name=sig.get('name', ''),
                    description=sig.get('description', '')
                )
                db.session.add(cache)
                sig['stock_name'] = stock_name

        db.session.commit()

        logger.info(f'[SignalCache] {stock_code} 更新完成: 买点{len(signals["buy_signals"])}个, 卖点{len(signals["sell_signals"])}个')
        return signals

    @staticmethod
    def update_signals_from_trend_data(trend_data: dict, stock_name_map: dict = None) -> dict:
        """从走势数据更新信号缓存

        这是主要入口，接收年数据的 trend_data 并更新所有股票的信号缓存

        Args:
            trend_data: 包含 stocks 的走势数据 (应为年数据365天)
            stock_name_map: 股票代码到名称的映射（可选）

        Returns:
            {'buy_signals': [...], 'sell_signals': [...]}
        """
        if not trend_data or not trend_data.get('stocks'):
            return {'buy_signals': [], 'sell_signals': []}

        all_signals = {'buy_signals': [], 'sell_signals': []}

        for stock in trend_data['stocks']:
            stock_code = stock.get('stock_code', '')
            stock_name = stock.get('stock_name', '')
            if stock_name_map and stock_code in stock_name_map:
                stock_name = stock_name_map[stock_code]

            ohlc_data = stock.get('data', [])

            if ohlc_data and len(ohlc_data) >= 5:
                signals = SignalCacheService.update_signals_for_stock(
                    stock_code, stock_name, ohlc_data
                )
                all_signals['buy_signals'].extend(signals.get('buy_signals', []))
                all_signals['sell_signals'].extend(signals.get('sell_signals', []))

        return all_signals

    @staticmethod
    def get_cached_signals_with_names(stock_codes: list[str], stock_name_map: dict,
                                      start_date: date = None, end_date: date = None) -> dict:
        """获取缓存信号并附加股票名称

        Args:
            stock_codes: 股票代码列表
            stock_name_map: 股票代码到名称的映射
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            {'buy_signals': [...], 'sell_signals': [...]}
        """
        signals = SignalCacheService.get_signals_for_stocks(stock_codes, start_date, end_date)

        # 附加股票名称
        for sig in signals['buy_signals']:
            sig['stock_name'] = stock_name_map.get(sig.get('stock_code'), sig.get('stock_code', ''))

        for sig in signals['sell_signals']:
            sig['stock_name'] = stock_name_map.get(sig.get('stock_code'), sig.get('stock_code', ''))

        return signals

    @staticmethod
    def has_recent_cache(stock_code: str, days: int = 1) -> bool:
        """检查是否有最近的缓存记录

        Args:
            stock_code: 股票代码
            days: 检查最近多少天

        Returns:
            是否存在缓存
        """
        recent_date = date.today() - timedelta(days=days)
        count = SignalCache.query.filter(
            SignalCache.stock_code == stock_code,
            SignalCache.updated_at >= datetime.combine(recent_date, datetime.min.time())
        ).count()
        return count > 0

    @staticmethod
    def clear_cache(stock_code: str = None):
        """清除缓存

        Args:
            stock_code: 股票代码，为None时清除所有缓存
        """
        if stock_code:
            SignalCache.query.filter_by(stock_code=stock_code).delete()
        else:
            SignalCache.query.delete()
        db.session.commit()
