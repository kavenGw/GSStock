"""数据源负载均衡器

轮询分配任务到多个数据源，支持熔断后的任务重分配。
支持按市场(A股/美股/港股)进行不同的负载均衡策略。
"""
import logging
import threading
import time
from typing import Callable, Optional
from collections import defaultdict

from app.services.circuit_breaker import circuit_breaker

logger = logging.getLogger(__name__)


# 各市场数据源配置
MARKET_SOURCES = {
    'A': {
        'sources': ['tencent', 'sina', 'eastmoney'],
        'fallback': 'yfinance',
        'weights': {'tencent': 50, 'sina': 50, 'eastmoney': 0},  # 腾讯和新浪为主，东方财富为备用
        # 优先级模式配置：主数据源失败后再用备用数据源
        'priority_mode': True,
        'primary_sources': ['tencent', 'sina'],  # 主数据源：腾讯和新浪
        'secondary_sources': ['eastmoney'],  # 备用数据源：东方财富
    },
    'US': {
        'sources': ['yfinance', 'twelvedata', 'polygon'],
        'fallback': 'yfinance',
        'weights': {'yfinance': 70, 'twelvedata': 20, 'polygon': 10},
    },
    'HK': {
        'sources': ['yfinance', 'twelvedata'],
        'fallback': 'yfinance',
        'weights': {'yfinance': 75, 'twelvedata': 25},
    },
    'KR': {
        'sources': ['yfinance'],
        'fallback': 'yfinance',
        'weights': {'yfinance': 100},
    },
    'TW': {
        'sources': ['yfinance'],
        'fallback': 'yfinance',
        'weights': {'yfinance': 100},
    },
}


class LoadBalancer:
    """数据源负载均衡器（单例）

    支持功能：
    - 按市场分配不同数据源
    - 加权轮询分配
    - 自适应权重调整（基于成功率）
    - 熔断后自动重分配
    """

    _instance = None
    _lock = threading.Lock()

    # A股数据源（按优先级排序：腾讯和新浪为主，东方财富为备用）
    A_SHARE_SOURCES = ['tencent', 'sina', 'eastmoney']
    A_SHARE_PRIMARY = ['tencent', 'sina']  # 主数据源
    A_SHARE_SECONDARY = ['eastmoney']  # 备用数据源

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
        self._round_robin_index = 0
        self._index_lock = threading.Lock()

        # 市场级别的轮询索引
        self._market_indices = defaultdict(int)

        # 数据源性能统计（用于自适应权重）
        self._source_stats = defaultdict(lambda: {
            'success': 0,
            'failure': 0,
            'total_time': 0.0,
            'last_update': 0,
        })

        # 动态权重缓存
        self._dynamic_weights = {}
        self._weights_lock = threading.Lock()

    def get_healthy_sources(self, sources: list = None) -> list:
        """获取健康的数据源列表"""
        if sources is None:
            sources = self.A_SHARE_SOURCES
        return [s for s in sources if circuit_breaker.is_available(s)]

    def distribute_tasks(self, stock_codes: list, sources: list = None) -> dict:
        """轮询分配任务到各数据源

        Args:
            stock_codes: 股票代码列表
            sources: 数据源列表，默认为A股数据源

        Returns:
            {source_name: [codes]} 分配结果
        """
        if sources is None:
            sources = self.A_SHARE_SOURCES

        healthy_sources = self.get_healthy_sources(sources)
        if not healthy_sources:
            logger.warning("[负载均衡] 所有数据源都已熔断")
            return {}

        result = {s: [] for s in healthy_sources}

        with self._index_lock:
            for code in stock_codes:
                source = healthy_sources[self._round_robin_index % len(healthy_sources)]
                result[source].append(code)
                self._round_robin_index += 1

        # 日志记录分配情况
        dist_info = ', '.join([f"{s}:{len(codes)}" for s, codes in result.items() if codes])
        logger.info(f"[负载均衡] 分配 {len(stock_codes)} 只: {dist_info}")

        return result

    def redistribute_failed(self, failed_codes: list, failed_source: str,
                           sources: list = None) -> dict:
        """重分配失败数据源的任务

        Args:
            failed_codes: 失败的股票代码列表
            failed_source: 失败的数据源名称
            sources: 可选的数据源列表

        Returns:
            {source_name: [codes]} 重分配结果
        """
        if sources is None:
            sources = self.A_SHARE_SOURCES

        # 排除失败的数据源
        remaining_sources = [s for s in sources if s != failed_source]
        healthy_sources = self.get_healthy_sources(remaining_sources)

        if not healthy_sources:
            logger.warning(f"[负载均衡] {failed_source} 失败后无可用数据源")
            return {}

        result = {s: [] for s in healthy_sources}

        with self._index_lock:
            for code in failed_codes:
                source = healthy_sources[self._round_robin_index % len(healthy_sources)]
                result[source].append(code)
                self._round_robin_index += 1

        dist_info = ', '.join([f"{s}:{len(codes)}" for s, codes in result.items() if codes])
        logger.info(f"[负载均衡] 重分配 {failed_source} 的 {len(failed_codes)} 只: {dist_info}")

        return result

    def fetch_with_balancing(self, stock_codes: list, fetch_funcs: dict,
                             fallback_func: Callable = None) -> dict:
        """使用负载均衡执行数据获取

        Args:
            stock_codes: 股票代码列表
            fetch_funcs: {source_name: fetch_function} 各数据源的获取函数
            fallback_func: 兜底函数（如yfinance），接收codes参数

        Returns:
            {stock_code: data} 获取结果
        """
        result = {}
        all_failed_codes = []

        # 初始分配
        distribution = self.distribute_tasks(stock_codes, list(fetch_funcs.keys()))

        if not distribution:
            # 所有数据源都熔断，直接使用兜底
            if fallback_func:
                logger.info(f"[负载均衡] 所有数据源熔断，使用兜底获取 {len(stock_codes)} 只")
                return fallback_func(stock_codes)
            return {}

        # 并行执行各数据源的任务
        from concurrent.futures import ThreadPoolExecutor, as_completed

        pending_redistributions = []  # (failed_source, failed_codes)

        with ThreadPoolExecutor(max_workers=len(distribution)) as executor:
            futures = {}
            for source, codes in distribution.items():
                if codes and source in fetch_funcs:
                    futures[executor.submit(fetch_funcs[source], codes)] = (source, codes)

            for future in as_completed(futures):
                source, codes = futures[future]
                try:
                    source_result = future.result()
                    if source_result:
                        result.update(source_result)
                        circuit_breaker.record_success(source)

                        # 检查哪些代码获取失败
                        failed_codes = [c for c in codes if c not in source_result]
                        if failed_codes:
                            pending_redistributions.append((source, failed_codes))
                    else:
                        # 整个数据源失败
                        circuit_breaker.record_failure(source)
                        pending_redistributions.append((source, codes))

                except Exception as e:
                    logger.warning(f"[负载均衡] {source} 执行异常: {e}")
                    circuit_breaker.record_failure(source)
                    pending_redistributions.append((source, codes))

        # 处理需要重分配的任务
        for failed_source, failed_codes in pending_redistributions:
            if not failed_codes:
                continue

            # 过滤已成功获取的代码
            still_failed = [c for c in failed_codes if c not in result]
            if not still_failed:
                continue

            # 重分配给其他健康数据源
            redistribution = self.redistribute_failed(still_failed, failed_source,
                                                      list(fetch_funcs.keys()))

            if redistribution:
                with ThreadPoolExecutor(max_workers=len(redistribution)) as executor:
                    futures = {}
                    for source, codes in redistribution.items():
                        if codes and source in fetch_funcs:
                            futures[executor.submit(fetch_funcs[source], codes)] = (source, codes)

                    for future in as_completed(futures):
                        source, codes = futures[future]
                        try:
                            source_result = future.result()
                            if source_result:
                                result.update(source_result)
                                circuit_breaker.record_success(source)
                            else:
                                circuit_breaker.record_failure(source)
                                all_failed_codes.extend(codes)
                        except Exception as e:
                            logger.warning(f"[负载均衡] 重分配 {source} 执行异常: {e}")
                            circuit_breaker.record_failure(source)
                            all_failed_codes.extend(codes)
            else:
                all_failed_codes.extend(still_failed)

        # 最终兜底：所有数据源都失败的代码
        final_failed = [c for c in all_failed_codes if c not in result]
        if final_failed and fallback_func:
            logger.info(f"[负载均衡] 兜底获取 {len(final_failed)} 只")
            fallback_result = fallback_func(final_failed)
            if fallback_result:
                result.update(fallback_result)

        return result

    def fetch_with_priority_balancing(self, stock_codes: list, fetch_funcs: dict,
                                       primary_sources: list = None,
                                       secondary_sources: list = None,
                                       fallback_func: Callable = None) -> dict:
        """使用优先级模式执行数据获取

        主数据源（腾讯/新浪）并行获取，失败的代码再用备用数据源（东方财富），最后yfinance兜底

        Args:
            stock_codes: 股票代码列表
            fetch_funcs: {source_name: fetch_function} 各数据源的获取函数
            primary_sources: 主数据源列表（默认腾讯和新浪）
            secondary_sources: 备用数据源列表（默认东方财富）
            fallback_func: 兜底函数（如yfinance）

        Returns:
            {stock_code: data} 获取结果
        """
        if primary_sources is None:
            primary_sources = self.A_SHARE_PRIMARY
        if secondary_sources is None:
            secondary_sources = self.A_SHARE_SECONDARY

        result = {}
        failed_codes = list(stock_codes)

        from concurrent.futures import ThreadPoolExecutor, as_completed

        # ============ 第一阶段：主数据源（腾讯/新浪）并行获取 ============
        healthy_primary = [s for s in primary_sources if circuit_breaker.is_available(s)]

        if healthy_primary:
            # 在主数据源之间轮询分配
            distribution = {s: [] for s in healthy_primary}
            with self._index_lock:
                for i, code in enumerate(stock_codes):
                    source = healthy_primary[i % len(healthy_primary)]
                    distribution[source].append(code)

            dist_info = ', '.join([f"{s}:{len(codes)}" for s, codes in distribution.items() if codes])
            logger.info(f"[负载均衡.优先级] 主数据源分配 {len(stock_codes)} 只: {dist_info}")

            with ThreadPoolExecutor(max_workers=len(healthy_primary)) as executor:
                futures = {}
                for source, codes in distribution.items():
                    if codes and source in fetch_funcs:
                        futures[executor.submit(fetch_funcs[source], codes)] = (source, codes)

                for future in as_completed(futures):
                    source, codes = futures[future]
                    try:
                        source_result = future.result()
                        if source_result:
                            result.update(source_result)
                            circuit_breaker.record_success(source)
                            # 更新失败列表
                            failed_codes = [c for c in failed_codes if c not in source_result]
                        else:
                            circuit_breaker.record_failure(source)
                            logger.warning(f"[负载均衡.优先级] 主数据源 {source} 返回空结果")
                    except Exception as e:
                        logger.warning(f"[负载均衡.优先级] 主数据源 {source} 执行异常: {e}")
                        circuit_breaker.record_failure(source)
        else:
            logger.warning("[负载均衡.优先级] 所有主数据源都已熔断")

        # ============ 第二阶段：备用数据源（东方财富）获取失败的 ============
        if failed_codes:
            healthy_secondary = [s for s in secondary_sources if circuit_breaker.is_available(s)]

            if healthy_secondary:
                logger.info(f"[负载均衡.优先级] 备用数据源获取剩余 {len(failed_codes)} 只: {', '.join(healthy_secondary)}")

                for source in healthy_secondary:
                    if not failed_codes:
                        break
                    if source not in fetch_funcs:
                        continue

                    try:
                        source_result = fetch_funcs[source](failed_codes)
                        if source_result:
                            result.update(source_result)
                            circuit_breaker.record_success(source)
                            failed_codes = [c for c in failed_codes if c not in source_result]
                            logger.info(f"[负载均衡.优先级] 备用数据源 {source} 获取成功 {len(source_result)} 只")
                        else:
                            circuit_breaker.record_failure(source)
                            logger.warning(f"[负载均衡.优先级] 备用数据源 {source} 返回空结果")
                    except Exception as e:
                        logger.warning(f"[负载均衡.优先级] 备用数据源 {source} 执行异常: {e}")
                        circuit_breaker.record_failure(source)
            else:
                logger.warning("[负载均衡.优先级] 所有备用数据源都已熔断")

        # ============ 第三阶段：yfinance 兜底 ============
        if failed_codes and fallback_func:
            logger.info(f"[负载均衡.优先级] yfinance 兜底获取 {len(failed_codes)} 只")
            try:
                fallback_result = fallback_func(failed_codes)
                if fallback_result:
                    result.update(fallback_result)
            except Exception as e:
                logger.warning(f"[负载均衡.优先级] yfinance 兜底异常: {e}")

        return result

    # ============ 市场特定负载均衡 ============

    def get_market_sources(self, market: str) -> list:
        """获取指定市场的数据源列表"""
        config = MARKET_SOURCES.get(market, MARKET_SOURCES.get('US'))
        return config.get('sources', ['yfinance'])

    def get_market_fallback(self, market: str) -> str:
        """获取指定市场的兜底数据源"""
        config = MARKET_SOURCES.get(market, MARKET_SOURCES.get('US'))
        return config.get('fallback', 'yfinance')

    def get_healthy_sources_for_market(self, market: str) -> list:
        """获取指定市场健康的数据源列表"""
        sources = self.get_market_sources(market)
        return [s for s in sources if circuit_breaker.is_available(s)]

    def get_source_weights(self, market: str) -> dict:
        """获取数据源权重（支持动态调整）"""
        cache_key = f"{market}_weights"

        with self._weights_lock:
            # 检查是否有动态权重缓存
            if cache_key in self._dynamic_weights:
                cached = self._dynamic_weights[cache_key]
                # 权重缓存1分钟
                if time.time() - cached['timestamp'] < 60:
                    return cached['weights']

            # 获取基础权重
            config = MARKET_SOURCES.get(market, MARKET_SOURCES.get('US'))
            base_weights = config.get('weights', {})

            # 根据成功率调整权重
            adjusted_weights = self._adjust_weights_by_stats(base_weights)

            # 缓存动态权重
            self._dynamic_weights[cache_key] = {
                'weights': adjusted_weights,
                'timestamp': time.time()
            }

            return adjusted_weights

    def _adjust_weights_by_stats(self, base_weights: dict) -> dict:
        """根据历史成功率调整权重"""
        adjusted = {}

        for source, base_weight in base_weights.items():
            stats = self._source_stats.get(source, {})
            success = stats.get('success', 0)
            failure = stats.get('failure', 0)
            total = success + failure

            if total >= 10:  # 至少10次请求后才调整
                success_rate = success / total
                # 成功率乘数：0.5x ~ 1.5x
                multiplier = 0.5 + success_rate
                adjusted[source] = int(base_weight * multiplier)
            else:
                adjusted[source] = base_weight

        # 确保至少有一个权重大于0
        if all(w == 0 for w in adjusted.values()):
            return base_weights

        return adjusted

    def record_source_result(self, source: str, success: bool, duration: float = 0.0):
        """记录数据源请求结果（用于动态调整权重）"""
        with self._weights_lock:
            stats = self._source_stats[source]
            if success:
                stats['success'] += 1
            else:
                stats['failure'] += 1
            stats['total_time'] += duration
            stats['last_update'] = time.time()

    def distribute_by_market(self, stock_codes: list, market: str) -> dict:
        """按市场进行加权轮询分配

        Args:
            stock_codes: 股票代码列表
            market: 市场类型 ('A', 'US', 'HK', 'KR', 'TW')

        Returns:
            {source_name: [codes]} 分配结果
        """
        healthy_sources = self.get_healthy_sources_for_market(market)
        if not healthy_sources:
            logger.warning(f"[负载均衡] {market}市场所有数据源都已熔断")
            return {}

        weights = self.get_source_weights(market)
        # 只保留健康数据源的权重
        active_weights = {s: weights.get(s, 10) for s in healthy_sources}
        total_weight = sum(active_weights.values())

        if total_weight == 0:
            # 均匀分配
            active_weights = {s: 1 for s in healthy_sources}
            total_weight = len(healthy_sources)

        result = {s: [] for s in healthy_sources}

        # 加权轮询分配
        with self._index_lock:
            for code in stock_codes:
                # 使用加权随机选择
                idx = self._market_indices[market] % total_weight
                cumulative = 0
                selected_source = healthy_sources[0]

                for source in healthy_sources:
                    cumulative += active_weights.get(source, 0)
                    if idx < cumulative:
                        selected_source = source
                        break

                result[selected_source].append(code)
                self._market_indices[market] += 1

        # 日志记录分配情况
        dist_info = ', '.join([f"{s}:{len(codes)}" for s, codes in result.items() if codes])
        logger.info(f"[负载均衡] {market}市场分配 {len(stock_codes)} 只: {dist_info}")

        return result

    def fetch_with_market_balancing(self, stock_codes: list, market: str,
                                     fetch_funcs: dict,
                                     fallback_func: Callable = None) -> dict:
        """使用市场特定负载均衡执行数据获取

        Args:
            stock_codes: 股票代码列表
            market: 市场类型 ('A', 'US', 'HK', 'KR', 'TW')
            fetch_funcs: {source_name: fetch_function} 各数据源的获取函数
            fallback_func: 兜底函数（如yfinance），接收codes参数

        Returns:
            {stock_code: data} 获取结果
        """
        result = {}
        all_failed_codes = []

        # 按市场进行加权分配
        distribution = self.distribute_by_market(stock_codes, market)

        if not distribution:
            # 所有数据源都熔断，直接使用兜底
            if fallback_func:
                logger.info(f"[负载均衡] {market}市场所有数据源熔断，使用兜底获取 {len(stock_codes)} 只")
                return fallback_func(stock_codes)
            return {}

        # 并行执行各数据源的任务
        from concurrent.futures import ThreadPoolExecutor, as_completed

        pending_redistributions = []  # (failed_source, failed_codes)

        with ThreadPoolExecutor(max_workers=len(distribution)) as executor:
            futures = {}
            start_times = {}

            for source, codes in distribution.items():
                if codes and source in fetch_funcs:
                    start_times[source] = time.time()
                    futures[executor.submit(fetch_funcs[source], codes)] = (source, codes)

            for future in as_completed(futures):
                source, codes = futures[future]
                duration = time.time() - start_times.get(source, time.time())

                try:
                    source_result = future.result()
                    if source_result:
                        result.update(source_result)
                        circuit_breaker.record_success(source)
                        self.record_source_result(source, True, duration)

                        # 检查哪些代码获取失败
                        failed_codes = [c for c in codes if c not in source_result]
                        if failed_codes:
                            pending_redistributions.append((source, failed_codes))
                    else:
                        # 整个数据源失败
                        circuit_breaker.record_failure(source)
                        self.record_source_result(source, False, duration)
                        pending_redistributions.append((source, codes))

                except Exception as e:
                    logger.warning(f"[负载均衡] {source} 执行异常: {e}")
                    circuit_breaker.record_failure(source)
                    self.record_source_result(source, False, duration)
                    pending_redistributions.append((source, codes))

        # 处理需要重分配的任务
        for failed_source, failed_codes in pending_redistributions:
            if not failed_codes:
                continue

            # 过滤已成功获取的代码
            still_failed = [c for c in failed_codes if c not in result]
            if not still_failed:
                continue

            # 获取剩余健康数据源
            remaining_sources = [s for s in self.get_market_sources(market) if s != failed_source]
            healthy_remaining = [s for s in remaining_sources if circuit_breaker.is_available(s)]

            if healthy_remaining:
                # 在剩余健康数据源间均匀分配
                redistribution = {s: [] for s in healthy_remaining}
                for i, code in enumerate(still_failed):
                    source = healthy_remaining[i % len(healthy_remaining)]
                    redistribution[source].append(code)

                dist_info = ', '.join([f"{s}:{len(codes)}" for s, codes in redistribution.items() if codes])
                logger.info(f"[负载均衡] {market}市场重分配 {failed_source} 的 {len(still_failed)} 只: {dist_info}")

                with ThreadPoolExecutor(max_workers=len(redistribution)) as executor:
                    futures = {}
                    for source, codes in redistribution.items():
                        if codes and source in fetch_funcs:
                            futures[executor.submit(fetch_funcs[source], codes)] = (source, codes)

                    for future in as_completed(futures):
                        source, codes = futures[future]
                        try:
                            source_result = future.result()
                            if source_result:
                                result.update(source_result)
                                circuit_breaker.record_success(source)
                                self.record_source_result(source, True, 0)
                            else:
                                circuit_breaker.record_failure(source)
                                self.record_source_result(source, False, 0)
                                all_failed_codes.extend(codes)
                        except Exception as e:
                            logger.warning(f"[负载均衡] {market}市场重分配 {source} 执行异常: {e}")
                            circuit_breaker.record_failure(source)
                            self.record_source_result(source, False, 0)
                            all_failed_codes.extend(codes)
            else:
                all_failed_codes.extend(still_failed)

        # 最终兜底：所有数据源都失败的代码
        final_failed = [c for c in all_failed_codes if c not in result]
        if final_failed and fallback_func:
            logger.info(f"[负载均衡] {market}市场兜底获取 {len(final_failed)} 只")
            fallback_result = fallback_func(final_failed)
            if fallback_result:
                result.update(fallback_result)

        return result

    def get_stats(self) -> dict:
        """获取负载均衡统计信息"""
        with self._weights_lock:
            stats = {}
            for source, data in self._source_stats.items():
                total = data['success'] + data['failure']
                stats[source] = {
                    'success': data['success'],
                    'failure': data['failure'],
                    'success_rate': round(data['success'] / total * 100, 2) if total > 0 else 0,
                    'avg_time': round(data['total_time'] / total, 3) if total > 0 else 0,
                }
            return stats

    def reset_stats(self):
        """重置统计信息"""
        with self._weights_lock:
            self._source_stats.clear()
            self._dynamic_weights.clear()
            self._market_indices.clear()
        logger.info("[负载均衡] 统计信息已重置")


# 单例实例
load_balancer = LoadBalancer()
