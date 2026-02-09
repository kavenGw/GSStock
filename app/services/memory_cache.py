"""内存缓存服务

多级缓存架构的第一层，提供快速的内存级缓存。
支持智能过期时间、按股票分目录持久化。
"""
import atexit
import logging
import os
import pickle
import threading
from datetime import datetime, timedelta
from typing import Any, Optional

from app.services.trading_calendar import TradingCalendarService

logger = logging.getLogger(__name__)

# 持久化目录路径
_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'memory_cache')
# 旧的单文件缓存路径（用于迁移）
_OLD_CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'memory_cache.pkl')


class MemoryCache:
    """内存缓存（单例）

    特性：
    - 智能过期：交易时段30分钟，收盘后8小时
    - 线程安全
    - 按股票分目录持久化，按数据类型分文件
    - 延迟flush：变更后5秒批量持久化
    - 命中率统计
    """

    _instance = None
    _lock = threading.Lock()

    TRADING_TTL = 1800          # 交易时段 TTL（30分钟）
    CLOSED_TTL = 28800          # 收盘后 TTL（8小时）
    FLUSH_DELAY = 5             # flush 延迟（5秒）

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
        self._cache: dict[str, dict] = {}
        self._cache_lock = threading.Lock()
        self._hit_count = 0
        self._miss_count = 0

        # 待持久化的股票代码和缓存类型
        self._pending_flush: set[tuple[str, str]] = set()
        self._flush_lock = threading.Lock()
        self._flush_timer: Optional[threading.Timer] = None

        self._migrate_old_cache()
        self._load_from_disk()
        atexit.register(self._flush_all_pending)

    def _get_stock_dir(self, code: str) -> str:
        """获取股票缓存目录"""
        # 将特殊字符替换为安全字符
        safe_code = code.replace('/', '_').replace('\\', '_').replace(':', '_')
        return os.path.join(_CACHE_DIR, safe_code)

    def _get_cache_file(self, code: str, cache_type: str) -> str:
        """获取缓存文件路径"""
        stock_dir = self._get_stock_dir(code)
        return os.path.join(stock_dir, f"{cache_type}.pkl")

    def _migrate_old_cache(self):
        """迁移旧的单文件缓存到新的目录结构"""
        if not os.path.exists(_OLD_CACHE_FILE):
            return

        try:
            with open(_OLD_CACHE_FILE, 'rb') as f:
                old_data = pickle.load(f)

            if not isinstance(old_data, dict):
                os.remove(_OLD_CACHE_FILE)
                return

            migrated_count = 0
            now = datetime.now()

            for key, entry in old_data.items():
                parts = key.split(':')
                if len(parts) != 2:
                    continue
                code, cache_type = parts

                # 跳过已过期的条目
                expire_time = entry.get('expire_time')
                if expire_time and now >= expire_time:
                    continue

                # 写入新的目录结构
                self._save_entry_to_disk(code, cache_type, entry)
                migrated_count += 1

            # 删除旧文件
            os.remove(_OLD_CACHE_FILE)
            logger.info(f"[内存缓存] 迁移完成：{migrated_count} 条缓存从旧格式迁移到新目录结构")

        except Exception as e:
            logger.warning(f"[内存缓存] 迁移旧缓存失败: {e}")
            # 尝试删除损坏的旧文件
            try:
                os.remove(_OLD_CACHE_FILE)
            except OSError:
                pass

    def _load_from_disk(self):
        """启动时从目录结构恢复缓存"""
        if not os.path.exists(_CACHE_DIR):
            return

        try:
            now = datetime.now()
            loaded_count = 0
            expired_count = 0

            for stock_folder in os.listdir(_CACHE_DIR):
                stock_dir = os.path.join(_CACHE_DIR, stock_folder)
                if not os.path.isdir(stock_dir):
                    continue

                for cache_file in os.listdir(stock_dir):
                    if not cache_file.endswith('.pkl'):
                        continue

                    cache_type = cache_file[:-4]  # 移除 .pkl 后缀
                    file_path = os.path.join(stock_dir, cache_file)

                    try:
                        with open(file_path, 'rb') as f:
                            entry = pickle.load(f)

                        expire_time = entry.get('expire_time')
                        if expire_time and now >= expire_time:
                            # 删除过期文件
                            os.remove(file_path)
                            expired_count += 1
                            continue

                        # 恢复股票代码（从目录名恢复特殊字符）
                        code = stock_folder.replace('_', '/')  # 简单恢复
                        key = self._make_key(code, cache_type)
                        self._cache[key] = entry
                        loaded_count += 1

                    except Exception as e:
                        logger.warning(f"[内存缓存] 加载缓存文件失败 {file_path}: {e}")
                        try:
                            os.remove(file_path)
                        except OSError:
                            pass

                # 清理空目录
                try:
                    if not os.listdir(stock_dir):
                        os.rmdir(stock_dir)
                except OSError:
                    pass

            logger.info(f"[内存缓存] 从磁盘恢复 {loaded_count} 条缓存（清理 {expired_count} 条过期）")

        except Exception as e:
            logger.warning(f"[内存缓存] 磁盘缓存加载失败: {e}")

    def _save_entry_to_disk(self, code: str, cache_type: str, entry: dict):
        """将单个缓存条目保存到磁盘"""
        try:
            stock_dir = self._get_stock_dir(code)
            os.makedirs(stock_dir, exist_ok=True)

            file_path = self._get_cache_file(code, cache_type)
            tmp_file = file_path + '.tmp'

            with open(tmp_file, 'wb') as f:
                pickle.dump(entry, f, protocol=pickle.HIGHEST_PROTOCOL)

            # 原子替换
            if os.path.exists(file_path):
                os.replace(tmp_file, file_path)
            else:
                os.rename(tmp_file, file_path)

        except Exception as e:
            logger.warning(f"[内存缓存] 持久化失败 {code}:{cache_type}: {e}")
            # 清理临时文件
            tmp_file = self._get_cache_file(code, cache_type) + '.tmp'
            if os.path.exists(tmp_file):
                try:
                    os.remove(tmp_file)
                except OSError:
                    pass

    def _delete_entry_from_disk(self, code: str, cache_type: str):
        """从磁盘删除缓存条目"""
        try:
            file_path = self._get_cache_file(code, cache_type)
            if os.path.exists(file_path):
                os.remove(file_path)

            # 清理空目录
            stock_dir = self._get_stock_dir(code)
            if os.path.exists(stock_dir) and not os.listdir(stock_dir):
                os.rmdir(stock_dir)

        except Exception as e:
            logger.warning(f"[内存缓存] 删除缓存文件失败 {code}:{cache_type}: {e}")

    def _schedule_flush(self, code: str, cache_type: str):
        """调度延迟flush"""
        with self._flush_lock:
            self._pending_flush.add((code, cache_type))

            # 如果已有定时器在运行，不需要重新创建
            if self._flush_timer is not None and self._flush_timer.is_alive():
                return

            # 创建新的定时器，5秒后执行flush
            self._flush_timer = threading.Timer(self.FLUSH_DELAY, self._do_flush)
            self._flush_timer.daemon = True
            self._flush_timer.start()

    def _do_flush(self):
        """执行flush操作"""
        with self._flush_lock:
            pending = self._pending_flush.copy()
            self._pending_flush.clear()
            self._flush_timer = None

        if not pending:
            return

        with self._cache_lock:
            for code, cache_type in pending:
                key = self._make_key(code, cache_type)
                entry = self._cache.get(key)
                if entry is not None:
                    self._save_entry_to_disk(code, cache_type, entry)

        logger.debug(f"[内存缓存] 已持久化 {len(pending)} 条缓存")

    def _flush_all_pending(self):
        """立即flush所有待持久化的数据（退出时调用）"""
        with self._flush_lock:
            if self._flush_timer is not None:
                self._flush_timer.cancel()
                self._flush_timer = None

        # 执行flush
        self._do_flush()

        # 额外保存所有内存中的数据
        with self._cache_lock:
            for key, entry in self._cache.items():
                parts = key.split(':')
                if len(parts) == 2:
                    code, cache_type = parts
                    self._save_entry_to_disk(code, cache_type, entry)

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
                # 异步删除磁盘文件
                threading.Thread(
                    target=self._delete_entry_from_disk,
                    args=(code, cache_type),
                    daemon=True
                ).start()
                return None

            self._hit_count += 1
            return entry['data']

    def set(self, code: str, cache_type: str, data: Any, ttl: int = None, stable: bool = False):
        """设置缓存

        Args:
            ttl: 自定义过期时间（秒），默认根据市场状态自动计算
            stable: 保留参数，向后兼容，不再使用
        """
        if data is None:
            return

        key = self._make_key(code, cache_type)

        if ttl is None:
            ttl = self._calculate_ttl(code)

        expire_time = datetime.now() + timedelta(seconds=ttl)

        with self._cache_lock:
            self._cache[key] = {
                'data': data,
                'expire_time': expire_time,
                'created_at': datetime.now()
            }

        # 调度延迟flush
        self._schedule_flush(code, cache_type)

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

    def invalidate(self, code: str = None, cache_type: str = None):
        """使缓存失效"""
        with self._cache_lock:
            if code is None and cache_type is None:
                # 清空所有缓存
                keys_to_delete = list(self._cache.keys())
                self._cache.clear()
                logger.info("[内存缓存] 已清空所有缓存")

                # 异步清理磁盘
                def cleanup_all():
                    try:
                        import shutil
                        if os.path.exists(_CACHE_DIR):
                            shutil.rmtree(_CACHE_DIR)
                    except Exception as e:
                        logger.warning(f"[内存缓存] 清理缓存目录失败: {e}")

                threading.Thread(target=cleanup_all, daemon=True).start()
                return

            keys_to_delete = []
            entries_to_delete = []

            for key in self._cache.keys():
                parts = key.split(':')
                if len(parts) != 2:
                    continue
                k_code, k_type = parts

                if code and cache_type:
                    if k_code == code and k_type == cache_type:
                        keys_to_delete.append(key)
                        entries_to_delete.append((k_code, k_type))
                elif code:
                    if k_code == code:
                        keys_to_delete.append(key)
                        entries_to_delete.append((k_code, k_type))
                elif cache_type:
                    if k_type == cache_type:
                        keys_to_delete.append(key)
                        entries_to_delete.append((k_code, k_type))

            for key in keys_to_delete:
                del self._cache[key]

            if keys_to_delete:
                logger.debug(f"[内存缓存] 清除 {len(keys_to_delete)} 条缓存")

                # 异步删除磁盘文件
                def cleanup_entries():
                    for c, t in entries_to_delete:
                        self._delete_entry_from_disk(c, t)

                threading.Thread(target=cleanup_entries, daemon=True).start()

    def get_stats(self) -> dict:
        """获取缓存统计"""
        with self._cache_lock:
            total = self._hit_count + self._miss_count
            hit_rate = (self._hit_count / total * 100) if total > 0 else 0

            expired_count = sum(1 for e in self._cache.values() if self._is_expired(e))

            # 统计磁盘缓存文件数
            disk_files = 0
            if os.path.exists(_CACHE_DIR):
                for stock_folder in os.listdir(_CACHE_DIR):
                    stock_dir = os.path.join(_CACHE_DIR, stock_folder)
                    if os.path.isdir(stock_dir):
                        disk_files += len([f for f in os.listdir(stock_dir) if f.endswith('.pkl')])

            return {
                'entries': len(self._cache),
                'disk_files': disk_files,
                'hit_count': self._hit_count,
                'miss_count': self._miss_count,
                'hit_rate': round(hit_rate, 2),
                'expired_count': expired_count,
                'cache_dir': _CACHE_DIR
            }

    def cleanup_expired(self) -> int:
        """清理过期条目"""
        with self._cache_lock:
            expired_entries = []
            for key, entry in self._cache.items():
                if self._is_expired(entry):
                    parts = key.split(':')
                    if len(parts) == 2:
                        expired_entries.append((key, parts[0], parts[1]))

            for key, code, cache_type in expired_entries:
                del self._cache[key]

            if expired_entries:
                logger.debug(f"[内存缓存] 清理 {len(expired_entries)} 条过期缓存")

                # 异步删除磁盘文件
                def cleanup_files():
                    for _, code, cache_type in expired_entries:
                        self._delete_entry_from_disk(code, cache_type)

                threading.Thread(target=cleanup_files, daemon=True).start()

            return len(expired_entries)

    def reset_stats(self):
        """重置统计计数"""
        with self._cache_lock:
            self._hit_count = 0
            self._miss_count = 0

    def flush(self):
        """手动触发持久化"""
        with self._cache_lock:
            for key, entry in self._cache.items():
                parts = key.split(':')
                if len(parts) == 2:
                    code, cache_type = parts
                    self._save_entry_to_disk(code, cache_type, entry)
        logger.debug(f"[内存缓存] 手动持久化完成")


# 单例实例
memory_cache = MemoryCache()
