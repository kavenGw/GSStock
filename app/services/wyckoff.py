import os
import re
import json
import time
import logging
from datetime import datetime, date
from concurrent.futures import ThreadPoolExecutor, as_completed
from werkzeug.utils import secure_filename
from flask import current_app
from app import db
from app.models.wyckoff import WyckoffReference, WyckoffAnalysis, WyckoffAutoResult
from app.services.wyckoff_analyzer import WyckoffAnalyzer

logger = logging.getLogger(__name__)

# 文件存储路径
REFERENCE_DIR = 'data/wyckoff/reference'
ANALYSIS_DIR = 'data/wyckoff/analysis'

# 文件验证
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


class WyckoffService:
    @staticmethod
    def ensure_directories():
        """确保存储目录存在"""
        os.makedirs(REFERENCE_DIR, exist_ok=True)
        os.makedirs(ANALYSIS_DIR, exist_ok=True)

    @staticmethod
    def validate_file(file):
        """验证文件类型和大小，返回 (is_valid, error_message)"""
        if not file or file.filename == '':
            return False, '未选择文件'

        # 检查文件扩展名
        ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        if ext not in ALLOWED_EXTENSIONS:
            return False, '仅支持 JPG/PNG/GIF/WEBP 格式'

        # 检查文件大小
        file.seek(0, 2)
        size = file.tell()
        file.seek(0)
        if size > MAX_FILE_SIZE:
            return False, '文件大小不能超过 10MB'

        return True, None

    @staticmethod
    def save_reference(file, phase, description=None):
        """保存参考图"""
        logger.info(f"保存参考图: phase={phase}")

        valid, error = WyckoffService.validate_file(file)
        if not valid:
            return None, error

        WyckoffService.ensure_directories()

        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        ext = file.filename.rsplit('.', 1)[-1].lower()
        filename = f"{timestamp}_{secure_filename(file.filename)}"
        filepath = os.path.join(REFERENCE_DIR, filename)

        file.save(filepath)

        ref = WyckoffReference(
            phase=phase,
            description=description,
            image_path=filepath,
        )
        db.session.add(ref)
        db.session.commit()

        logger.info(f"参考图保存成功: id={ref.id}")
        return ref, None

    @staticmethod
    def get_references(phase=None):
        """获取参考图列表"""
        query = WyckoffReference.query
        if phase:
            query = query.filter_by(phase=phase)
        return query.order_by(WyckoffReference.created_at.desc()).all()

    @staticmethod
    def delete_reference(ref_id):
        """删除参考图"""
        ref = WyckoffReference.query.get(ref_id)
        if not ref:
            return False, '记录不存在'

        # 删除文件（忽略不存在的情况）
        if ref.image_path and os.path.exists(ref.image_path):
            os.remove(ref.image_path)

        db.session.delete(ref)
        db.session.commit()
        logger.info(f"参考图删除成功: id={ref_id}")
        return True, None

    @staticmethod
    def save_analysis(stock_code, analysis_date, file, phase, event=None, notes=None):
        """保存分析记录"""
        logger.info(f"保存分析记录: stock={stock_code}, date={analysis_date}, phase={phase}")

        valid, error = WyckoffService.validate_file(file)
        if not valid:
            return None, error

        WyckoffService.ensure_directories()

        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        ext = file.filename.rsplit('.', 1)[-1].lower()
        date_str = analysis_date.strftime('%Y%m%d') if isinstance(analysis_date, date) else analysis_date
        filename = f"{stock_code}_{date_str}_{timestamp}.{ext}"
        filepath = os.path.join(ANALYSIS_DIR, filename)

        file.save(filepath)

        analysis = WyckoffAnalysis(
            stock_code=stock_code,
            analysis_date=analysis_date if isinstance(analysis_date, date) else date.fromisoformat(analysis_date),
            phase=phase,
            event=event,
            notes=notes,
            image_path=filepath,
        )
        db.session.add(analysis)
        db.session.commit()

        logger.info(f"分析记录保存成功: id={analysis.id}")
        return analysis, None

    @staticmethod
    def get_analyses(stock_code=None):
        """获取分析记录列表"""
        query = WyckoffAnalysis.query
        if stock_code:
            query = query.filter_by(stock_code=stock_code)
        return query.order_by(WyckoffAnalysis.analysis_date.desc()).all()

    @staticmethod
    def get_latest_analysis(stock_code):
        """获取股票最新分析记录"""
        return WyckoffAnalysis.query.filter_by(stock_code=stock_code)\
            .order_by(WyckoffAnalysis.analysis_date.desc()).first()

    @staticmethod
    def get_batch_latest(stock_codes):
        """批量获取多个股票的最新分析"""
        result = {}
        for code in stock_codes:
            analysis = WyckoffService.get_latest_analysis(code)
            if analysis:
                result[code] = analysis.to_dict()
        return result

    @staticmethod
    def delete_analysis(analysis_id):
        """删除分析记录"""
        analysis = WyckoffAnalysis.query.get(analysis_id)
        if not analysis:
            return False, '记录不存在'

        # 删除文件
        if analysis.image_path and os.path.exists(analysis.image_path):
            os.remove(analysis.image_path)

        db.session.delete(analysis)
        db.session.commit()
        logger.info(f"分析记录删除成功: id={analysis_id}")
        return True, None


# 建议优先级
ADVICE_PRIORITY = {'buy': 1, 'sell': 2, 'hold': 3, 'watch': 4}


class WyckoffAutoService:
    """威科夫自动分析服务"""

    @staticmethod
    def _validate_stock_code(code: str) -> tuple:
        """验证股票代码格式，支持多市场

        Returns: (is_valid, error_message)
        """
        if not code:
            return False, "股票代码不能为空"

        # 支持多市场股票代码
        patterns = [
            r'^\d{6}$',           # A股: 6位数字
            r'^[A-Z]{1,5}$',      # 美股: 1-5位字母
            r'^\d{5}\.HK$',       # 港股: 5位数字+.HK
            r'^\d{4}\.TW$',       # 台股: 4位数字+.TW
            r'^\d{6}\.KS$',       # 韩股: 6位数字+.KS
        ]

        if not any(re.match(pattern, code, re.IGNORECASE) for pattern in patterns):
            return False, "股票代码格式不正确"
        return True, ""

    @staticmethod
    def _convert_stock_code(code: str) -> str:
        """转换为 yfinance 格式"""
        # 如果已经包含市场后缀，直接返回
        if '.' in code:
            return code.upper()

        # A股需要添加市场后缀
        if code.startswith('6') or code.startswith('5'):
            return f"{code}.SS"  # 上证（含ETF）
        elif code.startswith('0') or code.startswith('3'):
            return f"{code}.SZ"  # 深证

        # 美股等其他市场代码直接返回
        return code

    @staticmethod
    def _fetch_ohlcv(stock_code: str, days: int = 120) -> list:
        """获取 OHLCV 数据（通过统一服务）

        Args:
            stock_code: 股票代码
            days: 获取天数

        Returns:
            OHLCV 数据列表，每项包含 date, open, high, low, close, volume
        """
        from app.services.unified_stock_data import unified_stock_data_service

        try:
            result = unified_stock_data_service.get_trend_data([stock_code], days)
            stocks_data = result.get('stocks', [])

            if not stocks_data:
                logger.warning(f"{stock_code} 未获取到数据")
                return []

            stock_trend = stocks_data[0]
            data = []
            for dp in stock_trend.get('data', []):
                data.append({
                    'date': dp['date'],
                    'open': dp['open'],
                    'high': dp['high'],
                    'low': dp['low'],
                    'close': dp['close'],
                    'volume': dp.get('volume', 0),
                })

            return data

        except Exception as e:
            logger.error(f"获取 {stock_code} OHLCV数据失败: {e}")
            return []

    @staticmethod
    def analyze_single(stock_code: str, stock_name: str = '', app=None) -> dict:
        """分析单只股票

        Args:
            stock_code: 股票代码
            stock_name: 股票名称
            app: Flask 应用实例（用于线程池中建立上下文）

        Returns:
            分析结果字典
        """
        valid, error = WyckoffAutoService._validate_stock_code(stock_code)
        if not valid:
            return {
                'stock_code': stock_code,
                'stock_name': stock_name,
                'status': 'failed',
                'error_msg': error,
            }

        # 获取数据
        ohlcv_data = WyckoffAutoService._fetch_ohlcv(stock_code)

        if not ohlcv_data:
            return {
                'stock_code': stock_code,
                'stock_name': stock_name,
                'status': 'failed',
                'error_msg': '数据获取失败',
            }

        if len(ohlcv_data) < 60:
            return {
                'stock_code': stock_code,
                'stock_name': stock_name,
                'status': 'insufficient',
                'error_msg': f'数据不足（仅{len(ohlcv_data)}天）',
            }

        # 执行分析
        analyzer = WyckoffAnalyzer()
        result = analyzer.analyze(ohlcv_data)

        # 保存到数据库（需要应用上下文）
        def save_to_db():
            today = date.today()
            existing = WyckoffAutoResult.query.filter_by(
                analysis_date=today,
                stock_code=stock_code
            ).first()

            if existing:
                existing.phase = result.phase
                existing.events = json.dumps(result.events)
                existing.advice = result.advice
                existing.support_price = result.support_price
                existing.resistance_price = result.resistance_price
                existing.current_price = result.current_price
                existing.details = json.dumps(result.details)
                existing.status = 'success'
                existing.error_msg = None
            else:
                record = WyckoffAutoResult(
                    analysis_date=today,
                    stock_code=stock_code,
                    phase=result.phase,
                    events=json.dumps(result.events),
                    advice=result.advice,
                    support_price=result.support_price,
                    resistance_price=result.resistance_price,
                    current_price=result.current_price,
                    details=json.dumps(result.details),
                    status='success',
                )
                db.session.add(record)
            db.session.commit()

        # 如果传入了 app，在新上下文中执行数据库操作
        if app:
            with app.app_context():
                save_to_db()
        else:
            save_to_db()

        return {
            'stock_code': stock_code,
            'stock_name': stock_name,
            'phase': result.phase,
            'events': result.events,
            'advice': result.advice,
            'support_price': result.support_price,
            'resistance_price': result.resistance_price,
            'current_price': result.current_price,
            'details': result.details,
            'status': 'success',
        }

    @staticmethod
    def analyze_batch(stock_list: list) -> list:
        """批量分析股票

        Args:
            stock_list: [{'code': '600519', 'name': '贵州茅台'}, ...]

        Returns:
            分析结果列表，按建议优先级排序
        """
        results = []
        app = current_app._get_current_object()

        # 降低并发数，避免触发API限流
        with ThreadPoolExecutor(max_workers=2) as executor:
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
                result = future.result()
                results.append(result)

        # 批量获取PE数据并添加到结果中
        stock_codes = [item['code'] for item in stock_list]
        pe_data_map = WyckoffAutoService._get_batch_pe_data(stock_codes)
        for result in results:
            code = result.get('stock_code')
            if code and code in pe_data_map:
                result['pe_data'] = pe_data_map[code]
            else:
                result['pe_data'] = {'pe_ttm': None, 'pe_status': 'na', 'pe_display': '暂无数据'}

        # 排序
        return WyckoffAutoService._sort_results(results)

    @staticmethod
    def _get_batch_pe_data(stock_codes: list) -> dict:
        """批量获取PE数据

        Args:
            stock_codes: 股票代码列表

        Returns:
            {stock_code: pe_data} 字典
        """
        try:
            from app.services.earnings import EarningsService
            return EarningsService.get_pe_ratios(stock_codes)
        except Exception as e:
            logger.warning(f"批量获取PE数据失败: {e}")
            return {}

    @staticmethod
    def _enrich_with_pe_ratio(result: dict, stock_code: str) -> dict:
        """为分析结果添加市盈率数据

        Args:
            result: 原始分析结果字典
            stock_code: 股票代码

        Returns:
            添加了 pe_data 字段的结果字典
        """
        try:
            from app.services.earnings import EarningsService
            pe_data = EarningsService.get_pe_ratios([stock_code])
            if stock_code in pe_data:
                result['pe_data'] = pe_data[stock_code]
            else:
                result['pe_data'] = {'pe_ttm': None, 'pe_status': 'na', 'pe_display': '暂无数据'}
        except Exception as e:
            logger.warning(f"获取 {stock_code} PE数据失败: {e}")
            result['pe_data'] = {'pe_ttm': None, 'pe_status': 'na', 'pe_display': '暂无数据'}
        return result

    @staticmethod
    def _sort_results(results: list) -> list:
        """按优先级排序结果"""
        return sorted(results, key=lambda x: (
            ADVICE_PRIORITY.get(x.get('advice', 'watch'), 4),
            x.get('status') != 'success',
            x.get('stock_code', '')
        ))

    @staticmethod
    def get_auto_history(stock_code: str = None, start_date: date = None,
                         end_date: date = None) -> list:
        """获取历史分析记录

        Args:
            stock_code: 股票代码筛选
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            历史记录列表
        """
        query = WyckoffAutoResult.query

        if stock_code:
            query = query.filter_by(stock_code=stock_code)
        if start_date:
            query = query.filter(WyckoffAutoResult.analysis_date >= start_date)
        if end_date:
            query = query.filter(WyckoffAutoResult.analysis_date <= end_date)

        records = query.order_by(WyckoffAutoResult.analysis_date.desc()).all()
        return [r.to_dict() for r in records]
