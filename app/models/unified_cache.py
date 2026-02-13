"""统一股票数据缓存模型

用于存储所有股票数据的缓存，包括实时价格、OHLC走势数据、指数数据等。
支持智能TTL控制，根据交易时段动态调整缓存有效期。
"""
import json
import logging
from datetime import datetime, date
from sqlalchemy.exc import OperationalError
from app import db
from app.utils.db_retry import is_retryable_error, with_db_retry, MAX_RETRIES

logger = logging.getLogger(__name__)


class UnifiedStockCache(db.Model):
    """统一股票缓存模型"""
    __tablename__ = 'unified_stock_cache'

    id = db.Column(db.Integer, primary_key=True)
    stock_code = db.Column(db.String(20), nullable=False)
    cache_type = db.Column(db.String(20), nullable=False)  # 'price', 'ohlc_30', 'ohlc_60', 'index'
    cache_date = db.Column(db.Date, nullable=False)
    data_json = db.Column(db.Text, nullable=True)  # JSON格式数据
    last_fetch_time = db.Column(db.DateTime, nullable=True)  # 最后获取时间
    is_complete = db.Column(db.Boolean, default=False)  # 数据是否完整（收盘后的完整数据）
    data_end_date = db.Column(db.Date, nullable=True)  # 数据截止日期
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('stock_code', 'cache_type', 'cache_date', name='uq_unified_stock_cache'),
        db.Index('idx_unified_cache_code', 'stock_code'),
        db.Index('idx_unified_cache_type', 'cache_type'),
        db.Index('idx_unified_cache_date', 'cache_date'),
        db.Index('idx_unified_cache_fetch_time', 'last_fetch_time'),
        db.Index('idx_unified_cache_complete', 'is_complete'),
    )

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'stock_code': self.stock_code,
            'cache_type': self.cache_type,
            'cache_date': self.cache_date.isoformat() if self.cache_date else None,
            'data_json': self.data_json,
            'last_fetch_time': self.last_fetch_time.isoformat() if self.last_fetch_time else None,
            'is_complete': self.is_complete,
            'data_end_date': self.data_end_date.isoformat() if self.data_end_date else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def get_data(self) -> dict | list | None:
        """解析并返回缓存的JSON数据"""
        if not self.data_json:
            return None
        try:
            return json.loads(self.data_json)
        except (json.JSONDecodeError, TypeError):
            return None

    def set_data(self, data: dict | list, is_complete: bool = False,
                 data_end_date: date = None) -> None:
        """设置缓存数据

        Args:
            data: 缓存数据
            is_complete: 数据是否完整（收盘后的完整数据）
            data_end_date: 数据截止日期
        """
        self.data_json = json.dumps(data, ensure_ascii=False)
        self.last_fetch_time = datetime.now()
        self.is_complete = is_complete
        if data_end_date:
            self.data_end_date = data_end_date
        self.updated_at = datetime.now()

    @classmethod
    def get_cached_data(cls, stock_code: str, cache_type: str, cache_date: date = None) -> dict | list | None:
        """获取缓存数据

        Args:
            stock_code: 股票代码
            cache_type: 缓存类型 ('price', 'ohlc_30', 'ohlc_60', 'index')
            cache_date: 缓存日期，默认为当天

        Returns:
            缓存的数据，如果不存在则返回 None
        """
        if cache_date is None:
            cache_date = date.today()

        cache = cls.query.filter_by(
            stock_code=stock_code,
            cache_type=cache_type,
            cache_date=cache_date
        ).first()

        if cache:
            return cache.get_data()
        return None

    @classmethod
    @with_db_retry
    def set_cached_data(cls, stock_code: str, cache_type: str, data: dict | list,
                        cache_date: date = None, is_complete: bool = False,
                        data_end_date: date = None) -> 'UnifiedStockCache':
        """设置缓存数据（带CockroachDB重试）"""
        if cache_date is None:
            cache_date = date.today()

        cache = cls.query.filter_by(
            stock_code=stock_code,
            cache_type=cache_type,
            cache_date=cache_date
        ).first()

        if cache:
            cache.set_data(data, is_complete, data_end_date)
        else:
            cache = cls(
                stock_code=stock_code,
                cache_type=cache_type,
                cache_date=cache_date,
            )
            cache.set_data(data, is_complete, data_end_date)
            db.session.add(cache)

        db.session.commit()
        return cache

    @classmethod
    def get_batch_cached_data(cls, stock_codes: list, cache_type: str,
                               cache_date: date = None) -> dict:
        """批量获取缓存数据

        Args:
            stock_codes: 股票代码列表
            cache_type: 缓存类型
            cache_date: 缓存日期，默认为当天

        Returns:
            {stock_code: data} 字典
        """
        if cache_date is None:
            cache_date = date.today()

        caches = cls.query.filter(
            cls.stock_code.in_(stock_codes),
            cls.cache_type == cache_type,
            cls.cache_date == cache_date
        ).all()

        result = {}
        for cache in caches:
            data = cache.get_data()
            if data:
                result[cache.stock_code] = data
        return result

    @classmethod
    def set_batch_cached_data(cls, data_dict: dict, cache_type: str,
                               cache_date: date = None) -> None:
        """批量设置缓存数据

        Args:
            data_dict: {stock_code: data} 字典
            cache_type: 缓存类型
            cache_date: 缓存日期，默认为当天
        """
        if cache_date is None:
            cache_date = date.today()

        for stock_code, data in data_dict.items():
            cls.set_cached_data(stock_code, cache_type, data, cache_date)

    @classmethod
    def get_last_fetch_times(cls, stock_codes: list, cache_type: str,
                              cache_date: date = None) -> dict:
        """获取最后获取时间

        Args:
            stock_codes: 股票代码列表
            cache_type: 缓存类型
            cache_date: 缓存日期，默认为当天

        Returns:
            {stock_code: last_fetch_time} 字典
        """
        if cache_date is None:
            cache_date = date.today()

        caches = cls.query.filter(
            cls.stock_code.in_(stock_codes),
            cls.cache_type == cache_type,
            cls.cache_date == cache_date
        ).all()

        return {cache.stock_code: cache.last_fetch_time for cache in caches}

    @classmethod
    @with_db_retry
    def clear_cache(cls, stock_codes: list = None, cache_type: str = None,
                    cache_date: date = None) -> int:
        """清除缓存

        Args:
            stock_codes: 股票代码列表，为空则清除所有
            cache_type: 缓存类型，为空则清除所有类型
            cache_date: 缓存日期，为空则清除所有日期

        Returns:
            删除的记录数
        """
        query = cls.query
        if stock_codes:
            query = query.filter(cls.stock_code.in_(stock_codes))
        if cache_type:
            query = query.filter_by(cache_type=cache_type)
        if cache_date:
            query = query.filter_by(cache_date=cache_date)

        count = query.delete(synchronize_session=False)
        db.session.commit()
        return count

    @classmethod
    def get_complete_cache(cls, stock_codes: list, cache_type: str,
                           cache_date: date = None) -> dict:
        """获取已完整的缓存数据

        只返回 is_complete=True 的缓存

        Args:
            stock_codes: 股票代码列表
            cache_type: 缓存类型
            cache_date: 缓存日期，默认为当天

        Returns:
            {stock_code: data} 字典
        """
        if cache_date is None:
            cache_date = date.today()

        caches = cls.query.filter(
            cls.stock_code.in_(stock_codes),
            cls.cache_type == cache_type,
            cls.cache_date == cache_date,
            cls.is_complete == True
        ).all()

        result = {}
        for cache in caches:
            data = cache.get_data()
            if data:
                result[cache.stock_code] = data
        return result

    @classmethod
    @with_db_retry
    def mark_complete(cls, stock_code: str, cache_type: str,
                      cache_date: date = None, data_end_date: date = None) -> bool:
        """标记缓存数据为完整

        Args:
            stock_code: 股票代码
            cache_type: 缓存类型
            cache_date: 缓存日期
            data_end_date: 数据截止日期

        Returns:
            True 如果成功标记
        """
        if cache_date is None:
            cache_date = date.today()

        cache = cls.query.filter_by(
            stock_code=stock_code,
            cache_type=cache_type,
            cache_date=cache_date
        ).first()

        if not cache:
            return False

        cache.is_complete = True
        if data_end_date:
            cache.data_end_date = data_end_date
        cache.updated_at = datetime.now()
        db.session.commit()
        return True

    @classmethod
    def get_data_end_dates(cls, stock_codes: list, cache_type: str,
                           cache_date: date = None) -> dict:
        """批量获取数据截止日期

        Args:
            stock_codes: 股票代码列表
            cache_type: 缓存类型
            cache_date: 缓存日期，默认为当天

        Returns:
            {stock_code: data_end_date} 字典
        """
        if cache_date is None:
            cache_date = date.today()

        caches = cls.query.filter(
            cls.stock_code.in_(stock_codes),
            cls.cache_type == cache_type,
            cls.cache_date == cache_date
        ).all()

        return {cache.stock_code: cache.data_end_date for cache in caches
                if cache.data_end_date}

    @classmethod
    def get_cache_with_status(cls, stock_codes: list, cache_type: str,
                               cache_date: date = None) -> dict:
        """获取缓存数据及其状态

        Args:
            stock_codes: 股票代码列表
            cache_type: 缓存类型
            cache_date: 缓存日期

        Returns:
            {stock_code: {'data': data, 'is_complete': bool, 'last_fetch_time': datetime}}
        """
        if cache_date is None:
            cache_date = date.today()

        caches = cls.query.filter(
            cls.stock_code.in_(stock_codes),
            cls.cache_type == cache_type,
            cls.cache_date == cache_date
        ).all()

        result = {}
        for cache in caches:
            data = cache.get_data()
            if data:
                result[cache.stock_code] = {
                    'data': data,
                    'is_complete': cache.is_complete,
                    'last_fetch_time': cache.last_fetch_time,
                    'data_end_date': cache.data_end_date
                }
        return result
