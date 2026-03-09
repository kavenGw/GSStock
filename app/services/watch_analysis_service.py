"""盯盘AI分析服务"""
import json
import logging

from app import db
from app.services.watch_service import WatchService

logger = logging.getLogger(__name__)


class WatchAnalysisService:
    """盯盘AI分析 — 统一分析入口，供路由/策略/定时任务调用"""

    @staticmethod
    def analyze_stocks(period: str, force: bool = False) -> dict:
        from app.services.unified_stock_data import unified_stock_data_service
        from app.llm.router import llm_router
        from app.llm.prompts.watch_analysis import (
            SYSTEM_PROMPT, build_realtime_analysis_prompt,
            build_7d_analysis_prompt, build_30d_analysis_prompt,
        )

        codes = WatchService.get_watch_codes()
        if not codes:
            return {}

        trend_60d = unified_stock_data_service.get_trend_data(codes, days=60)
        trend_60d_map = {s['stock_code']: s for s in trend_60d.get('stocks', [])}

        if period != 'realtime' and not force:
            existing = WatchService.get_all_today_analyses()
            all_cached = all(existing.get(c, {}).get(period) for c in codes)
            if all_cached:
                return existing

        intraday_map = {}
        trend_map = {}
        if period == 'realtime':
            intraday = unified_stock_data_service.get_intraday_data(codes)
            intraday_map = {s['stock_code']: s for s in intraday.get('stocks', [])}

        if period in ('7d', '30d'):
            days = 7 if period == '7d' else 30
            trend = unified_stock_data_service.get_trend_data(codes, days=days)
            trend_map = {s['stock_code']: s for s in trend.get('stocks', [])}

        raw_prices = unified_stock_data_service.get_realtime_prices(codes)

        provider = llm_router.route('watch_analysis')
        if not provider:
            logger.warning('[盯盘AI] LLM 不可用，跳过分析')
            return WatchService.get_all_today_analyses()

        for code in codes:
            price_data = raw_prices.get(code, {})
            current_price = price_data.get('current_price', 0)
            stock_name = price_data.get('name', code)
            if not current_price:
                continue

            if period != 'realtime' and not force:
                existing_analysis = WatchService.get_today_analysis(code, period)
                if existing_analysis:
                    continue

            try:
                if period == 'realtime':
                    intraday_stock = intraday_map.get(code, {})
                    intraday_data = intraday_stock.get('data', [])
                    if not intraday_data:
                        continue
                    ohlc_60d = trend_60d_map.get(code, {}).get('data', [])
                    prompt = build_realtime_analysis_prompt(stock_name, code, intraday_data, current_price, ohlc_60d)
                elif period == '7d':
                    trend_stock = trend_map.get(code, {})
                    ohlc = trend_stock.get('data', [])
                    if not ohlc:
                        continue
                    prompt = build_7d_analysis_prompt(stock_name, code, ohlc, current_price)
                else:
                    trend_stock = trend_map.get(code, {})
                    ohlc = trend_stock.get('data', [])
                    if not ohlc:
                        continue
                    prompt = build_30d_analysis_prompt(stock_name, code, ohlc, current_price)

                response = provider.chat([
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': prompt},
                ])
                cleaned = response.strip()
                if cleaned.startswith('```'):
                    cleaned = cleaned.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
                parsed = json.loads(cleaned)
                WatchService.save_analysis(
                    stock_code=code,
                    period=period,
                    support_levels=parsed.get('support_levels', []),
                    resistance_levels=parsed.get('resistance_levels', []),
                    summary=parsed.get('summary', ''),
                    signal=parsed.get('signal', ''),
                    detail={
                        'signal_text': parsed.get('signal_text', ''),
                        'ma_levels': parsed.get('ma_levels', {}),
                        'price_range': parsed.get('price_range', {}),
                    },
                )
            except Exception as e:
                db.session.rollback()
                logger.error(f"[盯盘AI] {code} {period}分析失败: {e}")

        return WatchService.get_all_today_analyses()
