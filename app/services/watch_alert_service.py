"""盯盘推送告警服务 — 信号检测 + 冷却 + 状态管理"""
import logging
import os
from datetime import datetime, timedelta

from app.strategies.base import Signal

logger = logging.getLogger(__name__)

COOLDOWN_SECONDS = int(os.environ.get('WATCH_ALERT_COOLDOWN_SECONDS', '300'))
BREAKTHROUGH_CONFIRM_MINUTES = 10


class WatchAlertService:

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._prev_prices = {}
            cls._instance._cooldown = {}
            cls._instance._intraday_extremes = {}
            cls._instance._last_trading_date = None
        return cls._instance

    def _is_cooled_down(self, key: str) -> bool:
        last = self._cooldown.get(key)
        if last and (datetime.now() - last).total_seconds() < COOLDOWN_SECONDS:
            return False
        return True

    def _set_cooldown(self, key: str):
        self._cooldown[key] = datetime.now()

    def _reset_if_new_day(self):
        today = datetime.now().date()
        if self._last_trading_date != today:
            self._intraday_extremes = {}
            self._prev_prices = {}
            self._last_trading_date = today

    def check_alerts(self, prices: dict, name_map: dict) -> list[Signal]:
        """主检测入口

        prices: {code: {'current_price': float, ...}}
        name_map: {code: stock_name}
        """
        self._reset_if_new_day()
        signals = []
        signals.extend(self._check_intraday_breakthrough(prices, name_map))
        self._prev_prices = {code: p.get('current_price') for code, p in prices.items() if p.get('current_price')}
        return signals

    def _check_intraday_breakthrough(self, prices: dict, name_map: dict) -> list[Signal]:
        signals = []
        now = datetime.now()

        for code, data in prices.items():
            curr = data.get('current_price')
            if curr is None:
                continue

            api_high = data.get('high')
            api_low = data.get('low')

            ext = self._intraday_extremes.get(code)
            if ext is None:
                init_high = api_high if api_high else curr
                init_low = api_low if api_low else curr
                self._intraday_extremes[code] = {
                    'high': init_high, 'high_time': now,
                    'high_confirmed': bool(api_high and api_high > curr),
                    'low': init_low, 'low_time': now,
                    'low_confirmed': bool(api_low and api_low < curr),
                }
                continue

            name = name_map.get(code, code)

            # 用API日内最高/最低校准（应对服务重启/漏tick）
            # 仅当 api 极值 ≠ 当前价 时才校准，否则留给突破检测处理
            if api_high and api_high > ext['high'] and api_high > curr:
                ext['high'] = api_high
                ext['high_confirmed'] = True
            if api_low and api_low < ext['low'] and api_low < curr:
                ext['low'] = api_low
                ext['low_confirmed'] = True

            if not ext['high_confirmed'] and (now - ext['high_time']).total_seconds() >= BREAKTHROUGH_CONFIRM_MINUTES * 60:
                ext['high_confirmed'] = True
            if not ext['low_confirmed'] and (now - ext['low_time']).total_seconds() >= BREAKTHROUGH_CONFIRM_MINUTES * 60:
                ext['low_confirmed'] = True

            # 价格回撤到前次告警突破位以下 → 解除前高告警抑制
            if ext.get('high_alerted_level') and curr <= ext['high_alerted_level']:
                ext.pop('high_alerted_level', None)
            # 价格回升到前次告警突破位以上 → 解除前低告警抑制
            if ext.get('low_alerted_level') and curr >= ext['low_alerted_level']:
                ext.pop('low_alerted_level', None)

            # 突破前高
            if curr > ext['high']:
                if ext['high_confirmed'] and not ext.get('high_alerted_level'):
                    key = f"breakthrough:{code}:high"
                    if self._is_cooled_down(key):
                        level = ext['high']
                        signals.append(Signal(
                            strategy='watch_alert',
                            priority='HIGH',
                            title=f'{name}({code}) 突破盘中前高',
                            detail=f'{name}({code}) 突破盘中前高 {level:.2f} ↑ | 当前 {curr:.2f}',
                            data={
                                'stock_code': code,
                                'alert_type': 'breakthrough',
                                'direction': 'high',
                                'level': level,
                                'detail': f'突破盘中前高 {level:.2f} ↑ | 当前 {curr:.2f}',
                            },
                        ))
                        self._set_cooldown(key)
                        ext['high_alerted_level'] = level
                ext['high'] = curr
                ext['high_time'] = now
                ext['high_confirmed'] = False

            # 跌破前低
            if curr < ext['low']:
                if ext['low_confirmed'] and not ext.get('low_alerted_level'):
                    key = f"breakthrough:{code}:low"
                    if self._is_cooled_down(key):
                        level = ext['low']
                        signals.append(Signal(
                            strategy='watch_alert',
                            priority='HIGH',
                            title=f'{name}({code}) 跌破盘中前低',
                            detail=f'{name}({code}) 跌破盘中前低 {level:.2f} ↓ | 当前 {curr:.2f}',
                            data={
                                'stock_code': code,
                                'alert_type': 'breakthrough',
                                'direction': 'low',
                                'level': level,
                                'detail': f'跌破盘中前低 {level:.2f} ↓ | 当前 {curr:.2f}',
                            },
                        ))
                        self._set_cooldown(key)
                        ext['low_alerted_level'] = level
                ext['low'] = curr
                ext['low_time'] = now
                ext['low_confirmed'] = False

        return signals
