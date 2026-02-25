import json
import logging
from datetime import date, datetime

from app import db
from app.models.watch_list import WatchList, WatchAnalysis
from app.utils.market_identifier import MarketIdentifier

logger = logging.getLogger(__name__)


class WatchService:
    """盯盘助手服务"""

    @staticmethod
    def get_watch_list() -> list[dict]:
        """获取盯盘列表"""
        items = WatchList.query.order_by(WatchList.added_at.desc()).all()
        return [{'id': w.id, 'stock_code': w.stock_code, 'stock_name': w.stock_name,
                 'market': w.market, 'added_at': w.added_at.isoformat() if w.added_at else None} for w in items]

    @staticmethod
    def add_stock(stock_code: str, stock_name: str = '') -> dict:
        """添加股票到盯盘列表"""
        existing = WatchList.query.filter_by(stock_code=stock_code).first()
        if existing:
            return {'success': False, 'message': '该股票已在盯盘列表中'}

        market = MarketIdentifier.identify(stock_code) or 'A'
        item = WatchList(stock_code=stock_code, stock_name=stock_name, market=market)
        db.session.add(item)
        db.session.commit()
        return {'success': True, 'message': '添加成功'}

    @staticmethod
    def remove_stock(stock_code: str) -> dict:
        """从盯盘列表移除股票"""
        item = WatchList.query.filter_by(stock_code=stock_code).first()
        if not item:
            return {'success': False, 'message': '该股票不在盯盘列表中'}
        db.session.delete(item)
        db.session.commit()
        return {'success': True, 'message': '已移除'}

    @staticmethod
    def get_watch_codes() -> list[str]:
        """获取盯盘列表的股票代码"""
        items = WatchList.query.all()
        return [w.stock_code for w in items]

    @staticmethod
    def get_today_analysis(stock_code: str) -> dict | None:
        """获取今日AI分析结果"""
        today = date.today()
        analysis = WatchAnalysis.query.filter_by(
            stock_code=stock_code, analysis_date=today
        ).first()
        if not analysis:
            return None
        return {
            'stock_code': analysis.stock_code,
            'support_levels': json.loads(analysis.support_levels) if analysis.support_levels else [],
            'resistance_levels': json.loads(analysis.resistance_levels) if analysis.resistance_levels else [],
            'volatility_threshold': analysis.volatility_threshold,
            'summary': analysis.analysis_summary,
        }

    @staticmethod
    def save_analysis(stock_code: str, support_levels: list, resistance_levels: list,
                      volatility_threshold: float, summary: str):
        """保存AI分析结果"""
        today = date.today()
        existing = WatchAnalysis.query.filter_by(
            stock_code=stock_code, analysis_date=today
        ).first()
        if existing:
            existing.support_levels = json.dumps(support_levels)
            existing.resistance_levels = json.dumps(resistance_levels)
            existing.volatility_threshold = volatility_threshold
            existing.analysis_summary = summary
        else:
            analysis = WatchAnalysis(
                stock_code=stock_code, analysis_date=today,
                support_levels=json.dumps(support_levels),
                resistance_levels=json.dumps(resistance_levels),
                volatility_threshold=volatility_threshold,
                analysis_summary=summary,
            )
            db.session.add(analysis)
        db.session.commit()

    @staticmethod
    def get_all_today_analyses() -> dict:
        """获取所有盯盘股票的今日分析结果"""
        today = date.today()
        analyses = WatchAnalysis.query.filter_by(analysis_date=today).all()
        result = {}
        for a in analyses:
            result[a.stock_code] = {
                'support_levels': json.loads(a.support_levels) if a.support_levels else [],
                'resistance_levels': json.loads(a.resistance_levels) if a.resistance_levels else [],
                'volatility_threshold': a.volatility_threshold,
                'summary': a.analysis_summary,
            }
        return result
