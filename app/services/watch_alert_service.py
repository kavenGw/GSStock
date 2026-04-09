"""盯盘告警服务 — 7种检测器 + 日级去重"""
import logging
import os
from datetime import datetime, timedelta

from app.strategies.base import Signal

logger = logging.getLogger(__name__)


class WatchAlertService:

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._fired = {}
            cls._instance._intraday_extremes = {}
            cls._instance._prev_prices = {}
            cls._instance._prev_ma_side = {}
            cls._instance._extreme_cooldown = {}
            cls._instance._last_trading_date = None
        return cls._instance

    def _reset_if_new_day(self):
        today = datetime.now().strftime('%Y-%m-%d')
        if self._last_trading_date != today:
            self._fired = {}
            self._intraday_extremes = {}
            self._prev_prices = {}
            self._prev_ma_side = {}
            self._extreme_cooldown = {}
            self._last_trading_date = today

    def _has_fired(self, key: str) -> bool:
        today = datetime.now().strftime('%Y-%m-%d')
        return key in self._fired.get(today, set())

    def _mark_fired(self, key: str):
        today = datetime.now().strftime('%Y-%m-%d')
        self._fired.setdefault(today, set()).add(key)

    def _make_signal(self, name: str, code: str, title: str, detail: str, data: dict) -> Signal:
        return Signal(
            strategy='watch_alert',
            priority='HIGH',
            title=f'{name}({code}) {title}',
            detail=detail,
            data={'stock_code': code, **data},
        )

    def check_alerts(self, prices: dict, name_map: dict,
                     alert_params_map: dict = None,
                     td_results: dict = None,
                     trading_minutes: dict = None) -> list[Signal]:
        """主检测入口

        prices: {code: {current_price, change_percent, volume, high, low, ...}}
        name_map: {code: stock_name}
        alert_params_map: {code: {target_prices, change_threshold_pct, volume_baseline, volume_anomaly_ratio, support_levels, resistance_levels, ma_levels}}
        td_results: {code: {direction, count, completed}} 或 None
        trading_minutes: {code: {elapsed, total}} 或 None
        """
        self._reset_if_new_day()
        alert_params_map = alert_params_map or {}
        td_results = td_results or {}
        trading_minutes = trading_minutes or {}
        signals = []

        for code, data in prices.items():
            curr = data.get('current_price')
            if curr is None:
                continue
            name = name_map.get(code, code)
            params = alert_params_map.get(code, {})

            signals.extend(self._check_intraday_extreme(code, name, data))

            td = td_results.get(code)
            if td:
                signals.extend(self._check_td_sequential(code, name, curr, td))

            if not params:
                continue
            signals.extend(self._check_target_price(code, name, curr, params))
            signals.extend(self._check_support_resistance(code, name, curr, params))
            signals.extend(self._check_ma_crossover(code, name, curr, params))
            signals.extend(self._check_volume_anomaly(code, name, data, params, trading_minutes.get(code)))

        self._prev_prices = {c: p.get('current_price') for c, p in prices.items() if p.get('current_price')}
        return signals

    def _check_intraday_extreme(self, code: str, name: str, data: dict) -> list[Signal]:
        signals = []
        curr = data.get('current_price')
        api_high = data.get('high')
        api_low = data.get('low')

        ext = self._intraday_extremes.get(code)
        if ext is None:
            self._intraday_extremes[code] = {
                'high': api_high if api_high and api_high > curr else curr,
                'low': api_low if api_low and api_low < curr else curr,
            }
            return signals

        if api_high and api_high > ext['high'] and api_high > curr:
            ext['high'] = api_high
        if api_low and api_low < ext['low'] and api_low < curr:
            ext['low'] = api_low

        cooldown_minutes = int(os.environ.get('WATCH_ALERT_COOLDOWN_MINUTES', '5'))
        now = datetime.now()

        if curr > ext['high']:
            level = ext['high']
            cooldown_key = f"extreme:{code}:high"
            last_fired = self._extreme_cooldown.get(cooldown_key)
            if not last_fired or now - last_fired >= timedelta(minutes=cooldown_minutes):
                signals.append(self._make_signal(name, code,
                    f'当前 {curr:.2f} > 前高 {level:.2f}',
                    '',
                    {'alert_type': 'intraday_extreme', 'direction': 'high', 'level': level}))
                self._extreme_cooldown[cooldown_key] = now
            ext['high'] = curr

        if curr < ext['low']:
            level = ext['low']
            cooldown_key = f"extreme:{code}:low"
            last_fired = self._extreme_cooldown.get(cooldown_key)
            if not last_fired or now - last_fired >= timedelta(minutes=cooldown_minutes):
                signals.append(self._make_signal(name, code,
                    f'当前 {curr:.2f} < 前低 {level:.2f}',
                    '',
                    {'alert_type': 'intraday_extreme', 'direction': 'low', 'level': level}))
                self._extreme_cooldown[cooldown_key] = now
            ext['low'] = curr

        return signals

    def _check_target_price(self, code: str, name: str, curr: float, params: dict) -> list[Signal]:
        signals = []
        for tp in params.get('target_prices', []):
            price = tp.get('price')
            direction = tp.get('direction')
            reason = tp.get('reason', '')
            if not price or not direction:
                continue
            key = f"target:{code}:{price}"
            if self._has_fired(key):
                continue
            if direction == 'above' and curr >= price:
                signals.append(self._make_signal(name, code,
                    f'当前 {curr:.2f} > 目标 {price}',
                    reason,
                    {'alert_type': 'target_price', 'direction': 'above', 'level': price}))
                self._mark_fired(key)
            elif direction == 'below' and curr <= price:
                signals.append(self._make_signal(name, code,
                    f'当前 {curr:.2f} < 目标 {price}',
                    reason,
                    {'alert_type': 'target_price', 'direction': 'below', 'level': price}))
                self._mark_fired(key)
        return signals

    def _check_support_resistance(self, code: str, name: str, curr: float, params: dict) -> list[Signal]:
        signals = []
        tolerance = 0.005

        support_levels = sorted([l for l in params.get('support_levels', []) if l], reverse=True)
        resistance_levels = sorted([l for l in params.get('resistance_levels', []) if l])

        for level in support_levels:
            key = f"sr:{code}:{level}"
            if self._has_fired(key):
                continue
            if abs(curr - level) / level <= tolerance:
                if curr < level:
                    label, direction = '跌破支撑', 'support_break'
                elif curr > level:
                    label, direction = '测试支撑', 'support_hold'
                else:
                    label, direction = '触及支撑', 'support_hold'
                detail = self._sr_detail(curr, level, direction, support_levels, resistance_levels)
                signals.append(self._make_signal(name, code,
                    f'{label} {level} | 当前 {curr:.2f}',
                    detail,
                    {'alert_type': 'support_resistance', 'direction': direction, 'level': level}))
                self._mark_fired(key)

        for level in resistance_levels:
            key = f"sr:{code}:{level}"
            if self._has_fired(key):
                continue
            if abs(curr - level) / level <= tolerance:
                if curr > level:
                    label, direction = '突破阻力', 'resistance_break'
                elif curr < level:
                    label, direction = '测试阻力', 'resistance_test'
                else:
                    label, direction = '触及阻力', 'resistance_test'
                detail = self._sr_detail(curr, level, direction, support_levels, resistance_levels)
                signals.append(self._make_signal(name, code,
                    f'{label} {level} | 当前 {curr:.2f}',
                    detail,
                    {'alert_type': 'support_resistance', 'direction': direction, 'level': level}))
                self._mark_fired(key)

        return signals

    def _sr_detail(self, curr: float, level: float, direction: str,
                   support_levels: list, resistance_levels: list) -> str:
        """生成支撑/阻力告警的上下文：下一关键位 + 距离百分比"""
        if direction == 'support_break':
            nxt = next((s for s in support_levels if s < level), None)
            if nxt:
                dist = (nxt - curr) / curr * 100
                return f"下方支撑 {nxt}({dist:+.1f}%)"
            return "下方无支撑"
        if direction == 'resistance_break':
            nxt = next((r for r in resistance_levels if r > level), None)
            if nxt:
                dist = (nxt - curr) / curr * 100
                return f"上方阻力 {nxt}({dist:+.1f}%)"
            return "上方无阻力"
        if direction == 'support_hold':
            nxt = next((r for r in resistance_levels if r > curr), None)
            if nxt:
                dist = (nxt - curr) / curr * 100
                return f"上方阻力 {nxt}({dist:+.1f}%)"
        if direction == 'resistance_test':
            nxt = next((s for s in support_levels if s < curr), None)
            if nxt:
                dist = (nxt - curr) / curr * 100
                return f"下方支撑 {nxt}({dist:+.1f}%)"
        return ''

    def _check_ma_crossover(self, code: str, name: str, curr: float, params: dict) -> list[Signal]:
        signals = []
        ma_levels = params.get('ma_levels', {})
        if not ma_levels:
            return signals

        prev_sides = self._prev_ma_side.get(code, {})
        curr_sides = {}

        for ma_type, ma_val in ma_levels.items():
            if not ma_val:
                continue
            side = 'above' if curr > ma_val else 'below'
            curr_sides[ma_type] = side

            prev_side = prev_sides.get(ma_type)
            if prev_side is None:
                continue
            if side == prev_side:
                continue

            direction = 'up' if side == 'above' else 'down'
            key = f"ma:{code}:{ma_type}:{direction}"
            if self._has_fired(key):
                continue

            cmp = '>' if direction == 'up' else '<'
            label = '上穿' if direction == 'up' else '下穿'
            signals.append(self._make_signal(name, code,
                f'{label} 当前 {curr:.2f} {cmp} {ma_type.upper()} {ma_val:.2f}',
                '',
                {'alert_type': 'ma_crossover', 'ma_type': ma_type, 'direction': direction, 'level': ma_val}))
            self._mark_fired(key)

        self._prev_ma_side[code] = curr_sides
        return signals

    def _check_volume_anomaly(self, code: str, name: str, data: dict, params: dict,
                               minutes_info: dict = None) -> list[Signal]:
        signals = []
        baseline = params.get('volume_baseline', 0)
        ratio = params.get('volume_anomaly_ratio', 2.0)
        volume = data.get('volume')
        if not baseline or not volume or not minutes_info:
            return signals

        elapsed = minutes_info.get('elapsed', 0)
        total = minutes_info.get('total', 1)
        if elapsed <= 0 or total <= 0:
            return signals

        normalized = volume / (elapsed / total)

        if normalized >= baseline * ratio:
            key = f"volume:{code}"
            if not self._has_fired(key):
                signals.append(self._make_signal(name, code,
                    f'成交量 {int(normalized):,} > 日均 {int(baseline):,} ({normalized/baseline:.1f}x)',
                    '',
                    {'alert_type': 'volume_anomaly', 'normalized_volume': normalized, 'baseline': baseline}))
                self._mark_fired(key)
        return signals

    def _check_td_sequential(self, code: str, name: str, curr: float, td: dict) -> list[Signal]:
        signals = []
        count = td.get('count', 0)
        direction = td.get('direction')
        completed = td.get('completed', False)
        if not completed or count != 9 or not direction:
            return signals

        key = f"td:{code}:{direction}"
        if self._has_fired(key):
            return signals

        label = '买入' if direction == 'buy' else '卖出'
        signals.append(self._make_signal(name, code,
            f'TD九转{label}信号 | 当前 {curr:.2f}',
            '',
            {'alert_type': 'td_sequential', 'direction': direction, 'count': 9}))
        self._mark_fired(key)
        return signals
