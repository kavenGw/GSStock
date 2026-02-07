"""内存缓存服务

多级缓存架构的第一层，提供快速的内存级缓存。
支持 LRU 淘汰策略和智能过期时间。
"""
import logging
import threading
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any, Optional

from app.services.trading_calendar import TradingCalendarService

logger = logging.getLogger(__name__)


class MemoryCache:
    """内存缓存（单例）

    特性：
    - LRU 淘汰策略
    - 智能过期：交易时段30分钟，收盘后到次日开盘
    - 线程安全
    - 命中率统计
    """

    _instance = None
    _lock = threading.Lock()

    # 配置
    MAX_ENTRIES = 500           # 最大缓存条目
    TRADING_TTL = 1800          # 交易时段 TTL（30分钟）
    CLOSED_TTL = 28800          # 收盘后 TTL（8小时）

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._cache: OrderedDict[str, dict] = OrderedDict()
        self._cache_lock = threading.Lock()
        self._hit_count = 0
        self._miss_count = 0

    def _make_key(self, code: str, cache_type: str) -> str:
        """生成缓存键"""
        return f"{code}:{cache_type}"

    def _is_expired(self, entry: dict) -> bool:
        """检查缓存是否过期"""
        expire_time = entry.get('expire_time')
        if not expire_time:
            return True
        return datetime.now() > expire_time

    def _calculate_ttl(self, code: str) -> int:
        """根据市场状态计算 TTL（秒）"""
        # 识别市场
        from app.utils.market_identifier import MarketIdentifier
        market = MarketIdentifier.identify(code) or 'A'

        # 收盘后使用长 TTL
        if TradingCalendarService.is_after_close(market):
            return self.CLOSED_TTL

        # 交易时段使用短 TTL
        return self.TRADING_TTL

    def _evict_if_needed(self):
        """LRU 淘汰（已持有锁）"""
        while len(self._cache) >= self.MAX_ENTRIES:
            # 移除最老的条目
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]

    def get(self, code: str, cache_type: str) -> Optional[Any]:
        """获取缓存

        Args:
            code: 股票代码
            cache_type: 缓存类型（price, ohlc_60 等）

        Returns:
            缓存数据或 None
        """
        key = self._make_key(code, cache_type)

        with self._cache_lock:
            entry = self._cache.get(key)

            if entry is None:
                self._miss_count += 1
                return None

            if self._is_expired(entry):
                del self._cache[key]
                self._miss_count += 1
                return None

            # LRU: 移到末尾
            self._cache.move_to_end(key)
            self._hit_count += 1

            return entry['data']

    def set(self, code: str, cache_type: str, data: Any, ttl: int = None):
        """设置缓存

        Args:
            code: 股票代码
            cache_type: 缓存类型
            data: 缓存数据
            ttl: 过期时间（秒），None 则自动计算
        """
        if data is None:
            return

        key = self._make_key(code, cache_type)

        if ttl is None:
            ttl = self._calculate_ttl(code)

        expire_time = datetime.now() + timedelta(seconds=ttl)

        with self._cache_lock:
            self._evict_if_needed()

            self._cache[key] = {
                'data': data,
                'expire_time': expire_time,
                'created_at': datetime.now()
            }
            # LRU: 移到末尾
            self._cache.move_to_end(key)

    def get_batch(self, codes: list, cache_type: str) -> dict:
        """批量获取缓存

        Args:
            codes: 股票代码列表
            cache_type: 缓存类型

        Returns:
            {code: data} 命中的缓存数据
        """
        result = {}
        for code in codes:
            data = self.get(code, cache_type)
            if data is not None:
                result[code] = data
        return result

    def set_batch(self, data_dict: dict, cache_type: str, ttl: int = None):
        """批量设置缓存

        Args:
            data_dict: {code: data} 数据字典
            cache_type: 缓存类型
            ttl: 过期时间（秒）
        """
        for code, data in data_dict.items():
            self.set(code, cache_type, data, ttl)

    def invalidate(self, code: str = None, cache_type: str = None):
        """使缓存失效

        Args:
            code: 股票代码，None 表示所有
            cache_type: 缓存类型，None 表示所有类型
        """
        with self._cache_lock:
            if code is None and cache_type is None:
                # 清空所有
                self._cache.clear()
                logger.info("[内存缓存] 已清空所有缓存")
                return

            keys_to_delete = []
            for key in self._cache.keys():
                parts = key.split(':')
                if len(parts) != 2:
                    continue
                k_code, k_type = parts

                if code and cache_type:
                    if k_code == code and k_type == cache_type:
                        keys_to_delete.append(key)
                elif code:
                    if k_code == code:
                        keys_to_delete.append(key)
                elif cache_type:
                    if k_type == cache_type:
                        keys_to_delete.append(key)

            for key in keys_to_delete:
                del self._cache[key]

            if keys_to_delete:
                logger.debug(f"[内存缓存] 清除 {len(keys_to_delete)} 条缓存")

    def get_stats(self) -> dict:
        """获取缓存统计"""
        with self._cache_lock:
            total = self._hit_count + self._miss_count
            hit_rate = (self._hit_count / total * 100) if total > 0 else 0

            # 统计过期条目
            expired_count = sum(1 for e in self._cache.values() if self._is_expired(e))

            return {
                'entries': len(self._cache),
                'max_entries': self.MAX_ENTRIES,
                'hit_count': self._hit_count,
                'miss_count': self._miss_count,
                'hit_rate': round(hit_rate, 2),
                'expired_count': expired_count
            }

    def cleanup_expired(self) -> int:
        """清理过期条目

        Returns:
            清理的条目数
        """
        with self._cache_lock:
            keys_to_delete = [
                key for key, entry in self._cache.items()
                if self._is_expired(entry)
            ]

            for key in keys_to_delete:
                del self._cache[key]

            if keys_to_delete:
                logger.debug(f"[内存缓存] 清理 {len(keys_to_delete)} 条过期缓存")

            return len(keys_to_delete)

    def reset_stats(self):
        """重置统计计数"""
        with self._cache_lock:
            self._hit_count = 0
            self._miss_count = 0


# 单例实例
memory_cache = MemoryCache()
