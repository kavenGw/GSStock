"""数据源负载均衡器

轮询分配任务到多个数据源，支持熔断后的任务重分配。
"""
import logging
import threading
from typing import Callable

from app.services.circuit_breaker import circuit_breaker

logger = logging.getLogger(__name__)


class LoadBalancer:
    """数据源负载均衡器（单例）"""

    _instance = None
    _lock = threading.Lock()

    # A股数据源（按优先级排序：东方财富降为最后备选，减少熔断影响）
    A_SHARE_SOURCES = ['sina', 'tencent', 'eastmoney']

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
            logger.warning("所有数据源都已熔断")
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


# 单例实例
load_balancer = LoadBalancer()
