"""Redis 缓存服务

多级缓存架构的中间层，提供持久化的分布式缓存。
当配置了 Redis 时，作为内存缓存和数据库缓存之间的缓存层。
"""
import json
import logging
import threading
from datetime import datetime, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Redis 客户端实例
_redis_client = None
_redis_lock = threading.Lock()
_redis_available = None  # None = 未检测, True/False = 检测结果


def _get_redis_client():
    """获取 Redis 客户端（延迟初始化）"""
    global _redis_client, _redis_available

    if _redis_available is False:
        return None

    if _redis_client is not None:
        return _redis_client

    with _redis_lock:
        if _redis_client is not None:
            return _redis_client

        try:
            from flask import current_app
            redis_url = current_app.config.get('REDIS_URL')
            if not redis_url:
                _redis_available = False
                logger.info("[Redis缓存] 未配置 Redis，跳过")
                return None

            import redis
            timeout = current_app.config.get('REDIS_TIMEOUT', 5)
            _redis_client = redis.from_url(
                redis_url,
                socket_timeout=timeout,
                socket_connect_timeout=timeout,
                decode_responses=True
            )
            # 测试连接
            _redis_client.ping()
            _redis_available = True
            logger.info("[Redis缓存] 连接成功")
            return _redis_client
        except ImportError:
            _redis_available = False
            logger.warning("[Redis缓存] redis 包未安装")
            return None
        except Exception as e:
            _redis_available = False
            logger.warning(f"[Redis缓存] 连接失败: {e}")
            return None


def _get_key_prefix():
    """获取键前缀"""
    try:
        from flask import current_app
        return current_app.config.get('REDIS_KEY_PREFIX', 'gsstock:')
    except Exception:
        return 'gsstock:'


class RedisCache:
    """Redis 缓存服务（单例）

    特性：
    - 与 MemoryCache 相同的接口
    - 持久化存储
    - 分布式支持
    - 自动序列化/反序列化
    - 命中率统计
    """

    _instance = None
    _lock = threading.Lock()

    # 配置
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
        self._hit_count = 0
        self._miss_count = 0
        self._stats_lock = threading.Lock()

    def _get_client(self):
        """获取 Redis 客户端"""
        return _get_redis_client()

    def _make_key(self, code: str, cache_type: str) -> str:
        """生成缓存键"""
        prefix = _get_key_prefix()
        return f"{prefix}{code}:{cache_type}"

    def _calculate_ttl(self, code: str) -> int:
        """根据市场状态计算 TTL（秒）"""
        try:
            from app.utils.market_identifier import MarketIdentifier
            from app.services.trading_calendar import TradingCalendarService
            market = MarketIdentifier.identify(code) or 'A'

            # 收盘后使用长 TTL
            if TradingCalendarService.is_after_close(market):
                return self.CLOSED_TTL

            # 交易时段使用短 TTL
            return self.TRADING_TTL
        except Exception:
            return self.TRADING_TTL

    def is_available(self) -> bool:
        """检查 Redis 是否可用"""
        client = self._get_client()
        if client is None:
            return False
        try:
            client.ping()
            return True
        except Exception:
            return False

    def get(self, code: str, cache_type: str) -> Optional[Any]:
        """获取缓存

        Args:
            code: 股票代码
            cache_type: 缓存类型（price, ohlc_60 等）

        Returns:
            缓存数据或 None
        """
        client = self._get_client()
        if client is None:
            return None

        key = self._make_key(code, cache_type)

        try:
            data = client.get(key)
            if data is None:
                with self._stats_lock:
                    self._miss_count += 1
                return None

            with self._stats_lock:
                self._hit_count += 1

            return json.loads(data)
        except Exception as e:
            logger.debug(f"[Redis缓存] 获取失败 {key}: {e}")
            with self._stats_lock:
                self._miss_count += 1
            return None

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

        client = self._get_client()
        if client is None:
            return

        key = self._make_key(code, cache_type)

        if ttl is None:
            ttl = self._calculate_ttl(code)

        try:
            client.setex(key, ttl, json.dumps(data, ensure_ascii=False, default=str))
        except Exception as e:
            logger.debug(f"[Redis缓存] 设置失败 {key}: {e}")

    def get_batch(self, codes: list, cache_type: str) -> dict:
        """批量获取缓存

        Args:
            codes: 股票代码列表
            cache_type: 缓存类型

        Returns:
            {code: data} 命中的缓存数据
        """
        client = self._get_client()
        if client is None:
            return {}

        if not codes:
            return {}

        result = {}
        keys = [self._make_key(code, cache_type) for code in codes]

        try:
            # 使用 mget 批量获取
            values = client.mget(keys)

            for code, value in zip(codes, values):
                if value is not None:
                    try:
                        result[code] = json.loads(value)
                        with self._stats_lock:
                            self._hit_count += 1
                    except json.JSONDecodeError:
                        with self._stats_lock:
                            self._miss_count += 1
                else:
                    with self._stats_lock:
                        self._miss_count += 1

            return result
        except Exception as e:
            logger.debug(f"[Redis缓存] 批量获取失败: {e}")
            return {}

    def set_batch(self, data_dict: dict, cache_type: str, ttl: int = None):
        """批量设置缓存

        Args:
            data_dict: {code: data} 数据字典
            cache_type: 缓存类型
            ttl: 过期时间（秒）
        """
        client = self._get_client()
        if client is None:
            return

        if not data_dict:
            return

        try:
            # 使用 pipeline 批量设置
            pipe = client.pipeline()

            for code, data in data_dict.items():
                if data is None:
                    continue
                key = self._make_key(code, cache_type)
                code_ttl = ttl if ttl is not None else self._calculate_ttl(code)
                pipe.setex(key, code_ttl, json.dumps(data, ensure_ascii=False, default=str))

            pipe.execute()
        except Exception as e:
            logger.debug(f"[Redis缓存] 批量设置失败: {e}")

    def invalidate(self, code: str = None, cache_type: str = None):
        """使缓存失效

        Args:
            code: 股票代码，None 表示所有
            cache_type: 缓存类型，None 表示所有类型
        """
        client = self._get_client()
        if client is None:
            return

        prefix = _get_key_prefix()

        try:
            if code is None and cache_type is None:
                # 清空所有 gsstock: 前缀的键
                pattern = f"{prefix}*"
                keys = client.keys(pattern)
                if keys:
                    client.delete(*keys)
                logger.info(f"[Redis缓存] 已清空 {len(keys) if keys else 0} 条缓存")
            elif code and cache_type:
                # 删除特定键
                key = self._make_key(code, cache_type)
                client.delete(key)
            elif code:
                # 删除特定股票的所有缓存
                pattern = f"{prefix}{code}:*"
                keys = client.keys(pattern)
                if keys:
                    client.delete(*keys)
            elif cache_type:
                # 删除特定类型的所有缓存
                pattern = f"{prefix}*:{cache_type}"
                keys = client.keys(pattern)
                if keys:
                    client.delete(*keys)
        except Exception as e:
            logger.debug(f"[Redis缓存] 清除失败: {e}")

    def get_stats(self) -> dict:
        """获取缓存统计"""
        client = self._get_client()

        with self._stats_lock:
            total = self._hit_count + self._miss_count
            hit_rate = (self._hit_count / total * 100) if total > 0 else 0

            stats = {
                'available': client is not None,
                'hit_count': self._hit_count,
                'miss_count': self._miss_count,
                'hit_rate': round(hit_rate, 2)
            }

        if client is not None:
            try:
                prefix = _get_key_prefix()
                pattern = f"{prefix}*"
                keys = client.keys(pattern)
                stats['entries'] = len(keys) if keys else 0
            except Exception:
                stats['entries'] = -1

        return stats

    def reset_stats(self):
        """重置统计计数"""
        with self._stats_lock:
            self._hit_count = 0
            self._miss_count = 0


# 单例实例
redis_cache = RedisCache()
