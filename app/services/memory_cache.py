"""内存缓存服务

多级缓存架构的第一层，提供快速的内存级缓存。
支持 LRU 淘汰策略、智能过期时间、pickle 本地序列化持久化。
"""
import atexit
import logging
import os
import pickle
import threading
import time
from collections import OrderedDict
from datetime import datetime, timedelta
from typing import Any, Optional

from app.services.trading_calendar import TradingCalendarService

logger = logging.getLogger(__name__)

# 持久化文件路径
_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
_CACHE_FILE = os.path.join(_CACHE_DIR, 'memory_cache.pkl')


class MemoryCache:
    """内存缓存（单例）

    特性：
    - LRU 淘汰策略
    - 智能过期：交易时段30分钟，收盘后8小时
    - 线程安全
    - pickle 本地序列化持久化
    - 命中率统计
    """

    _instance = None
    _lock = threading.Lock()

    MAX_ENTRIES = 5000          # 最大缓存条目
    TRADING_TTL = 1800          # 交易时段 TTL（30分钟）
    CLOSED_TTL = 28800          # 收盘后 TTL（8小时）
    STABLE_TTL = 86400          # 稳定数据 TTL（24小时，已验证的DB缓存数据）
    PERSIST_INTERVAL = 60       # 自动持久化间隔（1分钟）

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
        self._dirty = False
        self._persist_timer = None

        self._load_from_disk()
        self._start_persist_timer()
        atexit.register(self._save_to_disk)

    def _load_from_disk(self):
        """启动时从 pickle 文件恢复缓存"""
        if not os.path.exists(_CACHE_FILE):
            return

        try:
            with open(_CACHE_FILE, 'rb') as f:
                data = pickle.load(f)

            if not isinstance(data, OrderedDict):
                return

            # 过滤掉已过期的条目
            now = datetime.now()
            valid = OrderedDict()
            for key, entry in data.items():
                expire_time = entry.get('expire_time')
                if expire_time and now < expire_time:
                    valid[key] = entry

            self._cache = valid
            logger.info(f"[内存缓存] 从磁盘恢复 {len(valid)} 条缓存（丢弃 {len(data) - len(valid)} 条过期）")
        except Exception as e:
            logger.warning(f"[内存缓存] 磁盘缓存加载失败: {e}")
            self._cache = OrderedDict()

    def _save_to_disk(self):
        """将缓存持久化到 pickle 文件"""
        with self._cache_lock:
            if not self._dirty and os.path.exists(_CACHE_FILE):
                return

            # 只保存未过期的条目
            now = datetime.now()
            valid = OrderedDict()
            for key, entry in self._cache.items():
                expire_time = entry.get('expire_time')
                if expire_time and now < expire_time:
                    valid[key] = entry

            if not valid and not os.path.exists(_CACHE_FILE):
                return

        try:
            os.makedirs(_CACHE_DIR, exist_ok=True)

            tmp_file = _CACHE_FILE + '.tmp'
            with open(tmp_file, 'wb') as f:
                pickle.dump(valid, f, protocol=pickle.HIGHEST_PROTOCOL)

            # 原子替换
            if os.path.exists(_CACHE_FILE):
                os.replace(tmp_file, _CACHE_FILE)
            else:
                os.rename(tmp_file, _CACHE_FILE)

            self._dirty = False
            logger.debug(f"[内存缓存] 已持久化 {len(valid)} 条缓存到磁盘")
        except Exception as e:
            logger.warning(f"[内存缓存] 持久化失败: {e}")
            # 清理临时文件
            tmp_file = _CACHE_FILE + '.tmp'
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except OSError:
                    pass

    def _start_persist_timer(self):
        """启动定时持久化"""
        def _persist_loop():
            while True:
                time.sleep(self.PERSIST_INTERVAL)
                if self._dirty:
                    self._save_to_disk()

        t = threading.Thread(target=_persist_loop, daemon=True)
        t.start()

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
        from app.utils.market_identifier import MarketIdentifier
        market = MarketIdentifier.identify(code) or 'A'

        if TradingCalendarService.is_after_close(market):
            return self.CLOSED_TTL

        return self.TRADING_TTL

    def _evict_if_needed(self):
        """智能淘汰（已持有锁）

        优先淘汰非稳定数据（LRU顺序），保护已验证的DB缓存数据
        """
        while len(self._cache) >= self.MAX_ENTRIES:
            evict_key = None
            for key, entry in self._cache.items():
                if not entry.get('stable'):
                    evict_key = key
                    break
            if evict_key is None:
                evict_key = next(iter(self._cache))
            del self._cache[evict_key]

    def get(self, code: str, cache_type: str) -> Optional[Any]:
        """获取缓存"""
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

            # 访问时提升为stable（频繁访问的数据值得保留）
            if not entry.get('stable'):
                access_count = entry.get('access_count', 0) + 1
                entry['access_count'] = access_count
                if access_count >= 3:
                    entry['stable'] = True

            self._cache.move_to_end(key)
            self._hit_count += 1

            return entry['data']

    def set(self, code: str, cache_type: str, data: Any, ttl: int = None, stable: bool = False):
        """设置缓存

        Args:
            stable: 标记为稳定数据（已验证的DB缓存/收盘后数据），使用24小时TTL且淘汰优先级低
        """
        if data is None:
            return

        key = self._make_key(code, cache_type)

        if ttl is None:
            ttl = self.STABLE_TTL if stable else self._calculate_ttl(code)

        expire_time = datetime.now() + timedelta(seconds=ttl)

        with self._cache_lock:
            self._evict_if_needed()

            self._cache[key] = {
                'data': data,
                'expire_time': expire_time,
                'created_at': datetime.now(),
                'stable': stable,
                'access_count': 0
            }
            self._cache.move_to_end(key)
            self._dirty = True

    def get_batch(self, codes: list, cache_type: str) -> dict:
        """批量获取缓存"""
        result = {}
        for code in codes:
            data = self.get(code, cache_type)
            if data is not None:
                result[code] = data
        return result

    def set_batch(self, data_dict: dict, cache_type: str, ttl: int = None, stable: bool = False):
        """批量设置缓存"""
        for code, data in data_dict.items():
            self.set(code, cache_type, data, ttl, stable)
        # 批量写入后异步持久化
        if len(data_dict) >= 3 and self._dirty:
            threading.Thread(target=self._save_to_disk, daemon=True).start()

    def invalidate(self, code: str = None, cache_type: str = None):
        """使缓存失效"""
        with self._cache_lock:
            if code is None and cache_type is None:
                self._cache.clear()
                self._dirty = True
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
                self._dirty = True
                logger.debug(f"[内存缓存] 清除 {len(keys_to_delete)} 条缓存")

    def get_stats(self) -> dict:
        """获取缓存统计"""
        with self._cache_lock:
            total = self._hit_count + self._miss_count
            hit_rate = (self._hit_count / total * 100) if total > 0 else 0

            expired_count = sum(1 for e in self._cache.values() if self._is_expired(e))
            stable_count = sum(1 for e in self._cache.values() if e.get('stable'))

            return {
                'entries': len(self._cache),
                'max_entries': self.MAX_ENTRIES,
                'stable_entries': stable_count,
                'hit_count': self._hit_count,
                'miss_count': self._miss_count,
                'hit_rate': round(hit_rate, 2),
                'expired_count': expired_count,
                'persistent': True,
                'cache_file': _CACHE_FILE
            }

    def cleanup_expired(self) -> int:
        """清理过期条目"""
        with self._cache_lock:
            keys_to_delete = [
                key for key, entry in self._cache.items()
                if self._is_expired(entry)
            ]

            for key in keys_to_delete:
                del self._cache[key]

            if keys_to_delete:
                self._dirty = True
                logger.debug(f"[内存缓存] 清理 {len(keys_to_delete)} 条过期缓存")

            return len(keys_to_delete)

    def reset_stats(self):
        """重置统计计数"""
        with self._cache_lock:
            self._hit_count = 0
            self._miss_count = 0

    def flush(self):
        """手动触发持久化"""
        self._save_to_disk()


# 单例实例
memory_cache = MemoryCache()
