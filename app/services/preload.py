import re
import logging
from datetime import datetime, date, time, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from app import db
from app.models.preload import PreloadStatus
from app.models.wyckoff import WyckoffAutoResult
from app.models.index_trend_cache import IndexTrendCache
from app.models.metal_trend_cache import MetalTrendCache
from app.services.position import PositionService
from app.services.wyckoff import WyckoffAutoService

logger = logging.getLogger(__name__)

# 交易时间范围
TRADING_START = time(9, 30)
TRADING_END = time(15, 0)

# 指数代码映射
INDEX_CODES = {
    'sh000001': '000001.SS',  # 上证指数
    'sz399001': '399001.SZ',  # 深证成指
    'sz399006': '399006.SZ',  # 创业板指
    'sh000300': '000300.SS',  # 沪深300
}

# 创业板ETF用于计算涨跌幅（yfinance对创业板指数历史数据支持有限）
CHINEXT_ETF_CODE = '159915.SZ'

# 金属代码映射
METAL_CODES = {
    'gold': 'GC=F',    # 黄金期货
    'silver': 'SI=F',  # 白银期货
    'copper': 'HG=F',  # 铜期货
}


class PreloadService:
    """每日数据预加载服务"""

    @staticmethod
    def is_trading_time() -> bool:
        """检查是否在交易时间内"""
        now = datetime.now().time()
        return TRADING_START <= now <= TRADING_END

    @staticmethod
    def check_preload_status(target_date: date) -> dict:
        """检查指定日期的预加载状态

        Returns:
            {
                'status': 'none' | 'pending' | 'running' | 'completed' | 'failed',
                'total_count': int,
                'success_count': int,
                'failed_count': int,
                'is_trading_time': bool,
            }
        """
        record = PreloadStatus.query.filter_by(preload_date=target_date).first()
        is_trading = PreloadService.is_trading_time()

        if not record:
            return {
                'status': 'none',
                'total_count': 0,
                'success_count': 0,
                'failed_count': 0,
                'is_trading_time': is_trading
            }

        # 检查是否有中断的 running 状态（超过10分钟未更新）
        if record.status == 'running' and record.started_at:
            elapsed = datetime.now() - record.started_at
            if elapsed.total_seconds() > 600:  # 10分钟超时
                logger.warning(f"预加载任务超时: date={target_date}")
                record.status = 'failed'
                db.session.commit()

        return {
            'status': record.status,
            'total_count': record.total_count,
            'success_count': record.success_count,
            'failed_count': record.failed_count,
            'is_trading_time': is_trading
        }

    @staticmethod
    def get_preload_progress(target_date: date) -> dict:
        """获取预加载进度信息

        Returns:
            {
                'status': str,
                'current': int,       # 当前处理数量
                'total': int,         # 总数量
                'current_stock': str, # 当前处理的股票
            }
        """
        record = PreloadStatus.query.filter_by(preload_date=target_date).first()

        if not record:
            return {'status': 'none', 'current': 0, 'total': 0, 'current_stock': None}

        return {
            'status': record.status,
            'current': record.success_count + record.failed_count,
            'total': record.total_count,
            'current_stock': record.current_stock,
        }

    @staticmethod
    def start_preload(target_date: date) -> dict:
        """启动预加载流程

        Returns:
            {
                'success': bool,
                'message': str,
                'total': int,
            }
        """
        # 检查是否已在运行
        existing = PreloadStatus.query.filter_by(preload_date=target_date).first()
        if existing and existing.status == 'running':
            return {'success': False, 'message': '预加载正在进行中', 'total': existing.total_count}

        # 获取最新持仓股票列表
        latest_date = PositionService.get_latest_date()
        if not latest_date:
            return {'success': False, 'message': '无持仓数据', 'total': 0}

        positions = PositionService.get_snapshot(latest_date)
        if not positions:
            return {'success': False, 'message': '无持仓数据', 'total': 0}

        # 过滤有效的6位股票代码
        stock_list = []
        for p in positions:
            code = p.stock_code
            if code and re.match(r'^[0-9]{6}$', code):
                stock_list.append({'code': code, 'name': p.stock_name})

        if not stock_list:
            return {'success': False, 'message': '无有效股票代码', 'total': 0}

        total_count = len(stock_list)

        # 创建或更新预加载状态记录
        if existing:
            existing.status = 'running'
            existing.total_count = total_count
            existing.success_count = 0
            existing.failed_count = 0
            existing.current_stock = None
            existing.started_at = datetime.now()
            existing.completed_at = None
        else:
            record = PreloadStatus(
                preload_date=target_date,
                status='running',
                total_count=total_count,
                success_count=0,
                failed_count=0,
                started_at=datetime.now(),
            )
            db.session.add(record)

        db.session.commit()
        logger.info(f"预加载启动: date={target_date}, stocks={total_count}")

        # 逐个处理股票（便于更新进度）
        success_count = 0
        failed_count = 0

        for item in stock_list:
            code = item['code']
            name = item['name']

            # 更新当前处理的股票
            PreloadService._update_current_stock(target_date, f"{name}({code})")

            # 执行分析
            result = WyckoffAutoService.analyze_single(code, name)

            if result.get('status') == 'success':
                success_count += 1
            else:
                failed_count += 1

            # 更新进度
            PreloadService._update_progress(target_date, success_count, failed_count)

        # 标记完成
        final_status = 'completed' if failed_count == 0 else 'completed'  # 即使有失败也标记完成
        PreloadService._mark_completed(target_date, final_status)

        logger.info(f"预加载完成: date={target_date}, success={success_count}, failed={failed_count}")

        return {
            'success': True,
            'message': f'预加载完成，成功 {success_count} 只，失败 {failed_count} 只',
            'total': total_count,
            'success_count': success_count,
            'failed_count': failed_count,
        }

    @staticmethod
    def _update_current_stock(target_date: date, stock_info: str):
        """更新当前处理的股票"""
        record = PreloadStatus.query.filter_by(preload_date=target_date).first()
        if record:
            record.current_stock = stock_info
            db.session.commit()

    @staticmethod
    def _update_progress(target_date: date, success_count: int, failed_count: int):
        """更新进度"""
        record = PreloadStatus.query.filter_by(preload_date=target_date).first()
        if record:
            record.success_count = success_count
            record.failed_count = failed_count
            db.session.commit()

    @staticmethod
    def _mark_completed(target_date: date, status: str = 'completed'):
        """标记完成"""
        record = PreloadStatus.query.filter_by(preload_date=target_date).first()
        if record:
            record.status = status
            record.current_stock = None
            record.completed_at = datetime.now()
            db.session.commit()

    @staticmethod
    def get_cached_results(target_date: date) -> list:
        """获取缓存的分析结果"""
        results = WyckoffAutoResult.query.filter_by(analysis_date=target_date).all()
        return [r.to_dict() for r in results]

    # ============ 指数预加载 ============

    @staticmethod
    def preload_indices(target_date: date, days: int = 60) -> dict:
        """预加载指数数据（通过统一服务）

        Returns:
            {
                'success': bool,
                'success_count': int,
                'failed_count': int,
                'results': dict
            }
        """
        from app.services.unified_stock_data import unified_stock_data_service

        results = {}
        success_count = 0
        failed_count = 0

        try:
            # 通过统一服务获取指数数据
            indices_data = unified_stock_data_service.get_indices_data(target_date, force_refresh=True)

            for local_code, data in indices_data.items():
                results[local_code] = {
                    'price': data.get('current_price', 0),
                    'change': data.get('change', 0),
                    'change_pct': data.get('change_percent', 0),
                }
                success_count += 1
                logger.info(f"指数 {local_code} 预加载成功")

        except Exception as e:
            logger.error(f"指数预加载失败: {e}")
            failed_count = len(INDEX_CODES)

        return {
            'success': failed_count == 0,
            'success_count': success_count,
            'failed_count': failed_count,
            'results': results,
        }

    # ============ 金属预加载 ============

    @staticmethod
    def preload_metals(target_date: date, days: int = 60) -> dict:
        """预加载金属数据（通过统一服务）

        Returns:
            {
                'success': bool,
                'success_count': int,
                'failed_count': int,
                'results': dict
            }
        """
        from app.services.unified_stock_data import unified_stock_data_service

        results = {}
        success_count = 0
        failed_count = 0

        yf_codes = list(METAL_CODES.values())

        try:
            # 通过统一服务获取金属数据
            trend_data = unified_stock_data_service.get_trend_data(yf_codes, days, force_refresh=True)

            # 构建 yf_code 到 local_code 的映射
            yf_to_local = {v: k for k, v in METAL_CODES.items()}

            for stock_data in trend_data.get('stocks', []):
                stock_code = stock_data['stock_code']
                local_code = yf_to_local.get(stock_code, stock_code)
                data_list = stock_data.get('data', [])

                if data_list:
                    latest = data_list[-1]
                    results[local_code] = {
                        'price': latest['close'],
                    }
                    success_count += 1
                    logger.info(f"金属 {local_code} 预加载成功")
                else:
                    failed_count += 1

        except Exception as e:
            logger.error(f"金属预加载失败: {e}")
            failed_count = len(METAL_CODES)

        return {
            'success': failed_count == 0,
            'success_count': success_count,
            'failed_count': failed_count,
            'results': results,
        }

    # ============ 获取指数最新数据 ============

    @staticmethod
    def get_indices_data(target_date: date = None) -> dict:
        """获取指数最新数据

        委托给 UnifiedStockDataService 统一缓存服务
        """
        from app.services.unified_stock_data import unified_stock_data_service

        if target_date is None:
            target_date = date.today()

        name_map = {
            'sh000001': '上证指数',
            'sz399001': '深证成指',
            'sz399006': '创业板指',
            'sh000300': '沪深300',
        }

        # 通过统一缓存服务获取指数数据
        indices_data = unified_stock_data_service.get_indices_data(target_date)

        # 转换为原有格式
        results = {}
        for code, data in indices_data.items():
            results[code] = {
                'name': data.get('name', name_map.get(code, code)),
                'price': data.get('current_price', 0),
                'change': data.get('change', 0),
                'change_pct': data.get('change_percent', 0),
            }

        return results

    # ============ 统一预加载 ============

    @staticmethod
    def preload_all_data(target_date: date) -> dict:
        """预加载所有数据（股票+指数+金属）

        Returns:
            {
                'success': bool,
                'message': str,
                'stocks': { success_count, failed_count },
                'indices': { success_count, failed_count },
                'metals': { success_count, failed_count },
            }
        """
        logger.info(f"开始全量预加载: date={target_date}")

        # 预加载指数
        indices_result = PreloadService.preload_indices(target_date)

        # 预加载金属
        metals_result = PreloadService.preload_metals(target_date)

        # 预加载股票（使用现有方法）
        stocks_result = PreloadService.start_preload(target_date)

        total_success = (
            indices_result['success_count'] +
            metals_result['success_count'] +
            stocks_result.get('success_count', 0)
        )
        total_failed = (
            indices_result['failed_count'] +
            metals_result['failed_count'] +
            stocks_result.get('failed_count', 0)
        )

        return {
            'success': total_failed == 0,
            'message': f'预加载完成，成功 {total_success}，失败 {total_failed}',
            'stocks': {
                'success_count': stocks_result.get('success_count', 0),
                'failed_count': stocks_result.get('failed_count', 0),
            },
            'indices': {
                'success_count': indices_result['success_count'],
                'failed_count': indices_result['failed_count'],
                'data': indices_result['results'],
            },
            'metals': {
                'success_count': metals_result['success_count'],
                'failed_count': metals_result['failed_count'],
                'data': metals_result['results'],
            },
        }

    # ============ 获取预加载股票代码 ============

    @staticmethod
    def get_all_stock_codes() -> list:
        """获取所有需要预加载的股票代码（持仓）"""
        stock_set = set()

        # 获取持仓股票
        latest_date = PositionService.get_latest_date()
        if latest_date:
            positions = PositionService.get_snapshot(latest_date)
            for p in positions:
                if p.stock_code and re.match(r'^[0-9]{6}$', p.stock_code):
                    stock_set.add((p.stock_code, p.stock_name))

        return [{'code': code, 'name': name} for code, name in stock_set]

    @staticmethod
    def start_preload_extended(target_date: date, max_workers: int = 15) -> dict:
        """扩展版预加载（更高并发）

        Returns:
            {
                'success': bool,
                'message': str,
                'total': int,
                'success_count': int,
                'failed_count': int,
                'failed_stocks': list,
            }
        """
        from flask import current_app

        # 检查是否已在运行
        existing = PreloadStatus.query.filter_by(preload_date=target_date).first()
        if existing and existing.status == 'running':
            return {'success': False, 'message': '预加载正在进行中', 'total': existing.total_count}

        # 获取所有股票（持仓+自选）
        stock_list = PreloadService.get_all_stock_codes()

        if not stock_list:
            return {'success': False, 'message': '无股票需要预加载', 'total': 0}

        total_count = len(stock_list)

        # 创建或更新预加载状态记录
        if existing:
            existing.status = 'running'
            existing.total_count = total_count
            existing.success_count = 0
            existing.failed_count = 0
            existing.current_stock = None
            existing.started_at = datetime.now()
            existing.completed_at = None
        else:
            record = PreloadStatus(
                preload_date=target_date,
                status='running',
                total_count=total_count,
                success_count=0,
                failed_count=0,
                started_at=datetime.now(),
            )
            db.session.add(record)

        db.session.commit()
        logger.info(f"扩展预加载启动: date={target_date}, stocks={total_count}, workers={max_workers}")

        # 使用线程池并发处理
        success_count = 0
        failed_count = 0
        failed_stocks = []
        app = current_app._get_current_object()

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    WyckoffAutoService.analyze_single,
                    item['code'],
                    item.get('name', ''),
                    app
                ): item
                for item in stock_list
            }

            for future in as_completed(futures):
                item = futures[future]
                try:
                    result = future.result()
                    if result.get('status') == 'success':
                        success_count += 1
                    else:
                        failed_count += 1
                        failed_stocks.append({
                            'code': item['code'],
                            'name': item.get('name', ''),
                            'error': result.get('error_msg', '未知错误'),
                        })
                except Exception as e:
                    failed_count += 1
                    failed_stocks.append({
                        'code': item['code'],
                        'name': item.get('name', ''),
                        'error': str(e),
                    })

                # 更新进度
                PreloadService._update_progress(target_date, success_count, failed_count)

        # 标记完成
        PreloadService._mark_completed(target_date, 'completed')

        logger.info(f"扩展预加载完成: date={target_date}, success={success_count}, failed={failed_count}")

        return {
            'success': True,
            'message': f'预加载完成，成功 {success_count} 只，失败 {failed_count} 只',
            'total': total_count,
            'success_count': success_count,
            'failed_count': failed_count,
            'failed_stocks': failed_stocks,
        }
