"""每日简报策略 — 汇总市场数据生成日报"""
import logging
from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)


class DailyBriefingStrategy(Strategy):
    name = "daily_briefing"
    description = "每日简报（市场概况+持仓+预警）"
    schedule = "0 8 * * *"
    needs_llm = False

    def scan(self) -> list[Signal]:
        from datetime import date
        from app.services.notification import NotificationService

        is_weekend = date.today().weekday() >= 5

        if is_weekend:
            self._scan_weekend()
        else:
            self._scan_weekday()

        return []

    def _scan_weekday(self):
        from app.services.notification import NotificationService

        self._refresh_signal_cache()

        try:
            results = NotificationService.push_daily_report()
            if results.get('slack'):
                logger.info('[每日简报] 推送成功')
                self._setup_esports_monitors()
            else:
                logger.warning('[每日简报] 推送失败或未配置')
        except Exception as e:
            logger.error(f'[每日简报] 推送失败: {e}')

        self._push_pullback_alert()

    def _scan_weekend(self):
        from app.services.notification import NotificationService

        try:
            results = NotificationService.push_daily_extras()
            if results.get('slack'):
                logger.info('[每日简报] 周末推送成功')
            elif not results.get('skipped'):
                logger.info('[每日简报] 周末无新内容')
        except Exception as e:
            logger.error(f'[每日简报] 周末推送失败: {e}')

        self._setup_esports_monitors()

    @staticmethod
    def _setup_esports_monitors():
        try:
            from flask import current_app
            from app.services.esports_monitor_service import EsportsMonitorService
            EsportsMonitorService(current_app._get_current_object()).setup_match_monitors()
        except Exception as e:
            logger.error(f'[每日简报] 赛事监控创建失败: {e}')

    @staticmethod
    def _refresh_signal_cache():
        """更新所有关注 A 股的信号缓存"""
        from app.services.notification import NotificationService
        from app.services.signal_cache import SignalCacheService
        from app.services.position import PositionService
        from app.utils.market_identifier import MarketIdentifier

        try:
            codes, name_map = NotificationService._get_all_watched_codes()
            a_codes = [c for c in codes if MarketIdentifier.is_a_share(c)]
            if not a_codes:
                return

            from datetime import date
            trend_data = PositionService.get_trend_data(a_codes, date.today(), days=365)
            if trend_data and trend_data.get('stocks'):
                SignalCacheService.update_signals_from_trend_data(trend_data, name_map)
                logger.info(f'[每日简报] 信号缓存更新完成: {len(a_codes)}只A股')
        except Exception as e:
            logger.error(f'[每日简报] 信号缓存更新失败: {e}')

    @staticmethod
    def _push_pullback_alert():
        """推送高点回退排行"""
        from app.services.value_dip import ValueDipService
        from app.services.notification import NotificationService

        try:
            stocks = ValueDipService.get_pullback_ranking()
            significant = [s for s in stocks if s['pullback_pct'] <= -5]
            if not significant:
                logger.info('[每日简报] 无显著高点回退')
                return

            message = DailyBriefingStrategy._format_pullback_message(significant)
            NotificationService.send_slack(message, 'news_daily')
            logger.info(f'[每日简报] 高点回退推送: {len(significant)} 只')
        except Exception as e:
            logger.error(f'[每日简报] 高点回退推送失败: {e}')

    @staticmethod
    def _format_pullback_message(stocks: list) -> str:
        lines = ['📉 *高点回退提醒*（90日高点）\n']
        for s in stocks:
            lines.append(
                f"  · {s['name']}（{s['market']}）"
                f" 现价{s['price']} / 高点{s['high']}"
                f" → *{s['pullback_pct']}%*"
            )
        return '\n'.join(lines)

