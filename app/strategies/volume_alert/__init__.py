"""A股收盘成交量异动策略 — 盯盘股票量比超30%时推送"""
import logging
from datetime import date
from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)

VOLUME_CHANGE_THRESHOLD = 0.3


class VolumeAlertStrategy(Strategy):
    name = "volume_alert"
    description = "A股收盘成交量异动推送"
    schedule = "50 15 * * 1-5"  # 工作日15:50，A股收盘后留足数据结算时间
    needs_llm = False

    def scan(self) -> list[Signal]:
        from app.services.watch_service import WatchService
        from app.services.unified_stock_data import UnifiedStockDataService
        from app.utils.market_identifier import MarketIdentifier

        codes = WatchService.get_watch_codes()
        a_codes = [c for c in codes if MarketIdentifier.is_a_share(c)]
        if not a_codes:
            return []

        data_service = UnifiedStockDataService()
        trend = data_service.get_trend_data(a_codes, days=5, force_refresh=True)

        today_str = date.today().strftime('%Y-%m-%d')
        signals = []
        for stock in trend.get('stocks', []):
            code = stock.get('stock_code')
            name = stock.get('stock_name', code)
            ohlc = stock.get('data', [])
            if not ohlc or len(ohlc) < 2:
                continue

            # 校验最后一条数据是今天，防止数据源延迟导致推送错误日期
            last_date = ohlc[-1].get('date', '')
            if last_date != today_str:
                logger.warning(f"[成交量异动] {code} {name} OHLC最新日期 {last_date} != 今天 {today_str}，跳过")
                continue

            today_vol = ohlc[-1].get('volume', 0)
            prev_vol = ohlc[-2].get('volume', 0)
            if not prev_vol or not today_vol:
                continue

            change_pct = (today_vol - prev_vol) / prev_vol
            if abs(change_pct) < VOLUME_CHANGE_THRESHOLD:
                continue

            direction = '放量' if change_pct > 0 else '缩量'
            pct_str = f"{abs(change_pct):.0%}"
            price_change = ohlc[-1].get('change_pct', 0)
            price_str = f"+{price_change:.2f}%" if price_change >= 0 else f"{price_change:.2f}%"

            signals.append(Signal(
                strategy=self.name,
                priority='HIGH' if abs(change_pct) >= 0.5 else 'MEDIUM',
                title=f'{name}({code}) {direction}{pct_str}',
                detail=f"今日成交量 {today_vol:,.0f} | 昨日 {prev_vol:,.0f} | 涨跌 {price_str}",
                data={'stock_code': code, 'volume_change_pct': round(change_pct, 4)},
            ))

        if signals:
            logger.info(f'[成交量异动] 扫描 {len(a_codes)} 只, 产出 {len(signals)} 个信号')
        return signals
