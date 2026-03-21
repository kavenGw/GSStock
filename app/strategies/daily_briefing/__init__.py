"""每日简报策略 — 汇总市场数据生成日报"""
import logging
from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)


class DailyBriefingStrategy(Strategy):
    name = "daily_briefing"
    description = "每日简报（市场概况+持仓+预警）"
    schedule = "30 8 * * 1-5"
    needs_llm = False

    def scan(self) -> list[Signal]:
        from app.services.notification import NotificationService

        # 推送前先更新所有 A 股信号缓存（每天一次）
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

        self._push_value_dip_alert()
        return []

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
    def _push_value_dip_alert():
        """检测价值洼地并推送 Slack 提醒"""
        from app.services.value_dip import ValueDipService
        from app.services.notification import NotificationService

        try:
            dips = ValueDipService.detect_value_dips()
            if not dips:
                logger.info('[每日简报] 无价值洼地')
                return

            message = DailyBriefingStrategy._format_value_dip_message(dips)
            NotificationService.send_slack(message, 'news')
            logger.info(f'[每日简报] 价值洼地推送: {len(dips)} 条')
        except Exception as e:
            logger.error(f'[每日简报] 价值洼地推送失败: {e}')

    @staticmethod
    def _format_value_dip_message(dips: list) -> str:
        lines = ['⚠ *价值洼地提醒*\n']
        for dip in dips:
            period = dip['period']
            lines.append(
                f"{period}维度：{dip['sector_name']}"
                f"（{'+' if dip['sector_change'] >= 0 else ''}{dip['sector_change']}%）"
                f"显著落后板块均值"
                f"（{'+' if dip['avg_change'] >= 0 else ''}{dip['avg_change']}%）"
            )
            stock_parts = []
            for s in dip['stocks']:
                c = s['change']
                if c is not None:
                    stock_parts.append(f"  · {s['name']} {'+' if c >= 0 else ''}{c}%")
                else:
                    stock_parts.append(f"  · {s['name']} N/A")
            lines.append(''.join(stock_parts))
            lines.append('')
        return '\n'.join(lines).strip()
