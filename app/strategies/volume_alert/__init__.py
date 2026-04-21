"""A股收盘成交量异动策略 — 盯盘股票量比超30%时推送"""
import logging
from datetime import date, datetime, timedelta
from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)

VOLUME_CHANGE_THRESHOLD = 0.3
RETRY_DELAY_MINUTES = 10


class VolumeAlertStrategy(Strategy):
    name = "volume_alert"
    description = "A股收盘成交量异动推送"
    schedule = "30 16 * * 1-5"  # 工作日16:30，等待数据源完成收盘结算
    needs_llm = False

    def scan(self, retry_codes: list = None) -> list[Signal]:
        try:
            return self._do_scan(retry_codes)
        except Exception as e:
            logger.error(f'[成交量异动] 扫描异常: {e}', exc_info=True)
            self._push_error(f'扫描异常: {e}')
            return []

    def _do_scan(self, retry_codes: list = None) -> list[Signal]:
        from app.services.trading_calendar import TradingCalendarService
        from app.services.watch_service import WatchService
        from app.services.unified_stock_data import UnifiedStockDataService
        from app.utils.market_identifier import MarketIdentifier

        if not TradingCalendarService.is_trading_day('A', date.today()):
            logger.info(f'[成交量异动] {date.today()} 非A股交易日，跳过扫描')
            return []

        if retry_codes:
            a_codes = retry_codes
            logger.info(f'[成交量异动] 重试 {len(a_codes)} 只: {a_codes}')
        else:
            codes = WatchService.get_watch_codes()
            a_codes = [c for c in codes if MarketIdentifier.is_a_share(c)]
        if not a_codes:
            return []

        data_service = UnifiedStockDataService()
        trend = data_service.get_trend_data(a_codes, days=5, force_refresh=True)
        realtime = data_service.get_realtime_prices(a_codes, force_refresh=True)

        today_str = date.today().strftime('%Y-%m-%d')
        signals = []
        missing_codes = []

        for stock in trend.get('stocks', []):
            code = stock.get('stock_code')
            name = stock.get('stock_name', code)
            ohlc = stock.get('data', [])
            if not ohlc or len(ohlc) < 2:
                continue

            last_date = ohlc[-1].get('date', '')
            rt = realtime.get(code) or {}

            if last_date != today_str:
                # OHLC 主源未出今日 bar，用 realtime 合成（腾讯 qt.gtimg.cn volume 已转"手"，与 OHLC 对齐）
                rt_vol = rt.get('volume')
                if rt_vol:
                    today_vol = rt_vol
                    prev_vol = ohlc[-1].get('volume', 0)  # 此时 ohlc[-1] 即昨日
                    price_change = rt.get('change_percent', rt.get('change_pct', 0)) or 0
                    logger.info(f"[成交量异动] {code} {name} 使用realtime合成今日bar: vol={today_vol:,}")
                else:
                    missing_codes.append(code)
                    logger.warning(f"[成交量异动] {code} {name} OHLC最新日期 {last_date} != 今天 {today_str}, realtime 无 volume")
                    continue
            else:
                today_vol = ohlc[-1].get('volume', 0)
                prev_vol = ohlc[-2].get('volume', 0)
                price_change = rt.get('change_pct', ohlc[-1].get('change_pct', 0))

            if not prev_vol or not today_vol:
                continue

            change_pct = (today_vol - prev_vol) / prev_vol
            if abs(change_pct) < VOLUME_CHANGE_THRESHOLD:
                continue

            direction = '放量' if change_pct > 0 else '缩量'
            pct_str = f"{abs(change_pct):.0%}"
            price_str = f"+{price_change:.2f}%" if price_change >= 0 else f"{price_change:.2f}%"

            vol_cmp = '>' if change_pct > 0 else '<'
            signals.append(Signal(
                strategy=self.name,
                priority='HIGH' if abs(change_pct) >= 0.5 else 'MEDIUM',
                title=f'{name}({code}) {direction}{pct_str}',
                detail=f"今日 {today_vol:,.0f} {vol_cmp} 昨日 {prev_vol:,.0f} | 涨跌 {price_str}",
                data={'stock_code': code, 'volume_change_pct': round(change_pct, 4)},
            ))

        if missing_codes and not retry_codes:
            self._schedule_retry(missing_codes)
        elif missing_codes and retry_codes:
            names = [s.get('stock_name', s.get('stock_code'))
                     for s in trend.get('stocks', [])
                     if s.get('stock_code') in missing_codes]
            self._push_error(f'重试仍缺失今日数据: {", ".join(names or missing_codes)}')

        if signals:
            logger.info(f'[成交量异动] 扫描 {len(a_codes)} 只, 产出 {len(signals)} 个信号')
        return signals

    def _schedule_retry(self, codes: list):
        from app.scheduler.engine import scheduler_engine
        from app.scheduler.event_bus import event_bus
        from apscheduler.triggers.date import DateTrigger

        run_time = datetime.now() + timedelta(minutes=RETRY_DELAY_MINUTES)

        def _retry_job():
            try:
                with scheduler_engine.app.app_context():
                    signals = self.scan(retry_codes=codes)
                    for sig in signals:
                        event_bus.publish(sig)
                    if signals:
                        logger.info(f'[成交量异动] 重试产出 {len(signals)} 个信号')
            except Exception as e:
                logger.error(f'[成交量异动] 重试异常: {e}', exc_info=True)
                with scheduler_engine.app.app_context():
                    self._push_error(f'重试异常: {e}')

        scheduler_engine.scheduler.add_job(
            _retry_job,
            trigger=DateTrigger(run_date=run_time),
            id='volume_alert_retry',
            replace_existing=True,
        )
        logger.info(f'[成交量异动] {len(codes)} 只数据缺失，{RETRY_DELAY_MINUTES}分钟后重试')

    @staticmethod
    def _push_error(msg: str):
        try:
            from app.services.notification import NotificationService
            NotificationService.send_slack(f'🔴 *[volume_alert]* {msg}', 'news_daily')
        except Exception:
            logger.error(f'[成交量异动] 错误推送失败: {msg}')
