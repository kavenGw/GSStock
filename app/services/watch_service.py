import json
import logging
from datetime import date, datetime

from app import db
from app.config.stock_codes import WATCH_CODES
from app.models.watch_list import WatchAnalysis

logger = logging.getLogger(__name__)


class WatchService:
    """盯盘助手服务"""

    @staticmethod
    def get_watch_list() -> list[dict]:
        """获取盯盘列表（来自 WATCH_CODES 配置）"""
        return [{'id': i, 'stock_code': e['code'], 'stock_name': e['name'],
                 'market': e['market'], 'added_at': None}
                for i, e in enumerate(WATCH_CODES, 1)]

    @staticmethod
    def get_watch_codes() -> list[str]:
        """获取盯盘列表的股票代码"""
        return [e['code'] for e in WATCH_CODES]

    @staticmethod
    def get_market_map() -> dict:
        """{股票代码: 市场}"""
        return {e['code']: e['market'] for e in WATCH_CODES}

    @staticmethod
    def get_watched_markets() -> list[str]:
        """获取盯盘列表涉及的市场（按优先级排序）"""
        priority = ['A', 'US', 'HK', 'KR', 'TW', 'JP']
        markets = {e['market'] for e in WATCH_CODES if e['market']}
        return [m for m in priority if m in markets] + [m for m in markets if m not in priority]

    @staticmethod
    def get_today_analysis(stock_code: str, period: str = None) -> dict | None:
        """获取今日AI分析结果"""
        today = date.today()
        if period:
            analysis = WatchAnalysis.query.filter_by(
                stock_code=stock_code, analysis_date=today, period=period
            ).first()
            if not analysis:
                return None
            return {
                'stock_code': analysis.stock_code,
                'period': analysis.period,
                'support_levels': json.loads(analysis.support_levels) if analysis.support_levels else [],
                'resistance_levels': json.loads(analysis.resistance_levels) if analysis.resistance_levels else [],
                'summary': analysis.analysis_summary,
                'signal': analysis.signal or '',
                'detail': json.loads(analysis.analysis_detail) if analysis.analysis_detail else {},
                'created_at': analysis.created_at.strftime('%H:%M') if analysis.created_at else '',
            }
        else:
            analyses = WatchAnalysis.query.filter_by(
                stock_code=stock_code, analysis_date=today
            ).all()
            if not analyses:
                return None
            result = {}
            for a in analyses:
                result[a.period] = {
                    'support_levels': json.loads(a.support_levels) if a.support_levels else [],
                    'resistance_levels': json.loads(a.resistance_levels) if a.resistance_levels else [],
                    'summary': a.analysis_summary,
                    'signal': a.signal or '',
                    'detail': json.loads(a.analysis_detail) if a.analysis_detail else {},
                    'created_at': a.created_at.strftime('%H:%M') if a.created_at else '',
                }
            return result

    @staticmethod
    def save_analysis(stock_code: str, period: str, support_levels: list,
                      resistance_levels: list, summary: str,
                      signal: str = '', detail: dict = None):
        """保存AI分析结果（upsert，处理并发竞争）"""
        today = date.today()
        detail_json = json.dumps(detail, ensure_ascii=False) if detail else None
        existing = WatchAnalysis.query.filter_by(
            stock_code=stock_code, analysis_date=today, period=period
        ).first()
        if existing:
            existing.support_levels = json.dumps(support_levels)
            existing.resistance_levels = json.dumps(resistance_levels)
            existing.analysis_summary = summary
            existing.signal = signal
            existing.analysis_detail = detail_json
            db.session.commit()
            return
        try:
            analysis = WatchAnalysis(
                stock_code=stock_code, analysis_date=today, period=period,
                support_levels=json.dumps(support_levels),
                resistance_levels=json.dumps(resistance_levels),
                analysis_summary=summary,
                signal=signal,
                analysis_detail=detail_json,
            )
            db.session.add(analysis)
            db.session.commit()
        except Exception:
            db.session.rollback()
            existing = WatchAnalysis.query.filter_by(
                stock_code=stock_code, analysis_date=today, period=period
            ).first()
            if existing:
                existing.support_levels = json.dumps(support_levels)
                existing.resistance_levels = json.dumps(resistance_levels)
                existing.analysis_summary = summary
                existing.signal = signal
                existing.analysis_detail = detail_json
                db.session.commit()

    @staticmethod
    def get_all_today_analyses() -> dict:
        """获取所有盯盘股票的今日分析结果"""
        today = date.today()
        analyses = WatchAnalysis.query.filter_by(analysis_date=today).all()
        result = {}
        for a in analyses:
            if a.stock_code not in result:
                result[a.stock_code] = {}
            result[a.stock_code][a.period] = {
                'support_levels': json.loads(a.support_levels) if a.support_levels else [],
                'resistance_levels': json.loads(a.resistance_levels) if a.resistance_levels else [],
                'summary': a.analysis_summary,
                'signal': a.signal or '',
                'detail': json.loads(a.analysis_detail) if a.analysis_detail else {},
                'created_at': a.created_at.strftime('%H:%M') if a.created_at else '',
            }
        return result
