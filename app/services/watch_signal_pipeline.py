"""盯盘信号管线中间层 — 同 tick 合并/分级/上下文增强（纯函数，无 DB/网络）"""
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

SIGNAL_WEIGHTS = {
    'td_sequential': 5,
    'target_price': 5,
    'support_break': 4,
    'resistance_break': 4,
    'intraday_momentum': 3,
    'ma_crossover': 3,
    'support_hold': 2,
    'resistance_test': 2,
    'intraday_extreme': 2,
    'volume_anomaly': 1,
}

_BULLISH = {'high', 'above', 'up', 'buy', 'resistance_break'}
_BEARISH = {'low', 'below', 'down', 'sell', 'support_break'}


@dataclass
class ConsolidatedAlert:
    code: str
    name: str
    priority: str
    direction: str
    primary_line: str
    secondary_lines: list = field(default_factory=list)
    context_line: str = ''
    change_percent: Optional[float] = None
    current_price: Optional[float] = None
    fired_signals: list = field(default_factory=list)


class WatchSignalPipeline:

    VOLUME_RATIO_CAP = 50.0

    @staticmethod
    def _direction_sign(direction: str) -> int:
        if direction in _BULLISH:
            return 1
        if direction in _BEARISH:
            return -1
        return 0

    @staticmethod
    def _weight(sig) -> float:
        return SIGNAL_WEIGHTS.get((sig.data or {}).get('alert_type'), 1)

    @staticmethod
    def _strip_prefix(title: str, name: str, code: str) -> str:
        pattern = rf'^[^(]*\({re.escape(code)}\) '
        match = re.match(pattern, title)
        if match:
            return title[match.end():]
        return title

    @staticmethod
    def _strip_current(line: str) -> str:
        return re.sub(r' \| 当前 [\d.]+$', '', line)

    @staticmethod
    def process(raw_signals, prices, params_map, name_map, trading_minutes=None):
        trading_minutes = trading_minutes or {}

        grouped = {}
        for sig in raw_signals:
            code = (sig.data or {}).get('stock_code')
            if not code:
                continue
            grouped.setdefault(code, []).append(sig)

        alerts = []
        for code, sigs in grouped.items():
            name = name_map.get(code, code)
            primary = max(sigs, key=WatchSignalPipeline._weight)
            primary_dir = (primary.data or {}).get('direction', '')
            primary_sign = WatchSignalPipeline._direction_sign(primary_dir)

            agg = WatchSignalPipeline._weight(primary)
            has_volume = False
            for s in sigs:
                if s is primary:
                    continue
                at = (s.data or {}).get('alert_type')
                if at == 'volume_anomaly':
                    has_volume = True
                    continue
                s_sign = WatchSignalPipeline._direction_sign((s.data or {}).get('direction', ''))
                if s_sign != 0 and s_sign == primary_sign:
                    agg += WatchSignalPipeline._weight(s) * 0.5
            if has_volume:
                agg += 1

            priority = 'HIGH' if agg >= 5 else ('MID' if agg >= 3 else 'LOW')

            primary_line = WatchSignalPipeline._strip_current(
                WatchSignalPipeline._strip_prefix(primary.title, name, code))
            secondary_lines = [
                WatchSignalPipeline._strip_current(
                    WatchSignalPipeline._strip_prefix(s.title, name, code))
                for s in sigs if s is not primary
            ]
            context_line = WatchSignalPipeline._build_context(code, prices, params_map, trading_minutes)

            alerts.append(ConsolidatedAlert(
                code=code, name=name, priority=priority, direction=primary_dir,
                primary_line=primary_line, secondary_lines=secondary_lines,
                context_line=context_line,
                change_percent=prices.get(code, {}).get('change_percent'),
                current_price=prices.get(code, {}).get('current_price'),
                fired_signals=[s.data for s in sigs],
            ))
        return alerts

    @staticmethod
    def _build_context(code, prices, params_map, trading_minutes):
        p = prices.get(code, {})
        params = params_map.get(code, {})
        parts = []

        baseline = params.get('volume_baseline', 0)
        volume = p.get('volume')
        if baseline and volume:
            tm = trading_minutes.get(code) or {}
            elapsed = tm.get('elapsed', 0)
            total = tm.get('total', 0)
            normalized = volume / (elapsed / total) if elapsed > 0 and total > 0 else volume
            ratio = normalized / baseline
            if ratio < WatchSignalPipeline.VOLUME_RATIO_CAP:
                parts.append(f'量比 {ratio:.1f}x')

        curr = p.get('current_price')
        if curr:
            resistances = sorted(l for l in params.get('resistance_levels', []) if l and l > curr)
            supports = sorted((l for l in params.get('support_levels', []) if l and l < curr), reverse=True)
            if resistances:
                r = resistances[0]
                parts.append(f'距上方阻力 {r}({(r - curr) / curr * 100:+.1f}%)')
            elif supports:
                s = supports[0]
                parts.append(f'距下方支撑 {s}({(s - curr) / curr * 100:+.1f}%)')

        return ' | '.join(parts)
