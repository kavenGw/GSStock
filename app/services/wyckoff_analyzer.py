"""威科夫量价分析核心算法 — 经典原理图6阶段12事件"""
from dataclasses import dataclass
from statistics import mean, stdev
from collections import defaultdict


@dataclass
class AnalysisResult:
    phase: str
    events: list
    advice: str
    support_price: float
    resistance_price: float
    current_price: float
    details: dict
    score: int = 0
    confidence: float = 0.5
    timeframe: str = 'daily'


# 阶段基础分
PHASE_SCORES = {
    'accumulation': 30, 'accumulation_markup': 35,
    'markup': 35, 'distribution': 12,
    'distribution_markdown': 8, 'markdown': 5,
}

# 事件加减分
EVENT_SCORES = {
    'spring': 12, 'SOS': 10, 'LPS': 8, 'test': 6,
    'SC': 4, 'AR': 3, 'ST': 2, 'PS': 1,
    'UTAD': -8, 'SOW': -10, 'LPSY': -6,
    'BC': -2, 'PSY': -1,
}


class WyckoffAnalyzer:

    def analyze(self, ohlcv_data: list, timeframe: str = 'daily') -> AnalysisResult:
        """分析单只股票的OHLCV数据

        Args:
            ohlcv_data: OHLCV数据列表，每项包含 date, open, high, low, close, volume，按日期升序
            timeframe: daily/weekly/monthly
        """
        if timeframe == 'weekly':
            ohlcv_data = self.aggregate_to_weekly(ohlcv_data)
        elif timeframe == 'monthly':
            ohlcv_data = self.aggregate_to_monthly(ohlcv_data)

        closes = [d['close'] for d in ohlcv_data]
        highs = [d['high'] for d in ohlcv_data]
        lows = [d['low'] for d in ohlcv_data]
        volumes = [d['volume'] for d in ohlcv_data]

        ma20 = self._ma(closes, 20)
        ma60 = self._ma(closes, 60)
        current_price = closes[-1]

        details = self._calc_details(closes, volumes, ma20, ma60)

        # 交易区间
        recent_closes = closes[-60:] if len(closes) >= 60 else closes
        range_high = self._percentile(recent_closes, 90)
        range_low = self._percentile(recent_closes, 10)

        # 阶段判断 → 事件检测 → 阶段修正
        phase = self._detect_phase(closes, volumes, highs, lows, ma20, ma60, details)
        events = self._detect_events(closes, volumes, highs, lows, range_high, range_low, phase)
        phase = self._refine_phase(phase, events, current_price, range_high, range_low)

        advice = self._generate_advice(phase, events)
        score = self._calc_score(phase, events, details)
        confidence = self._calc_confidence(events, phase)
        support, resistance = self._calc_levels(lows, highs, range_low, range_high, ma20, ma60)

        return AnalysisResult(
            phase=phase,
            events=events,
            advice=advice,
            support_price=round(support, 2),
            resistance_price=round(resistance, 2),
            current_price=round(current_price, 2),
            details=details,
            score=score,
            confidence=round(confidence, 2),
            timeframe=timeframe,
        )

    # ── 多周期聚合 ──

    @staticmethod
    def aggregate_to_weekly(daily_data: list) -> list:
        groups = defaultdict(list)
        for d in daily_data:
            iso = _parse_date(d['date']).isocalendar()
            key = (iso[0], iso[1])
            groups[key].append(d)
        return [_aggregate_group(bars) for bars in
                (groups[k] for k in sorted(groups))]

    @staticmethod
    def aggregate_to_monthly(daily_data: list) -> list:
        groups = defaultdict(list)
        for d in daily_data:
            dt = _parse_date(d['date'])
            groups[(dt.year, dt.month)].append(d)
        return [_aggregate_group(bars) for bars in
                (groups[k] for k in sorted(groups))]

    # ── 技术指标 ──

    @staticmethod
    def _ma(prices: list, period: int) -> float:
        if len(prices) < period:
            return mean(prices)
        return mean(prices[-period:])

    @staticmethod
    def _percentile(data: list, pct: int) -> float:
        s = sorted(data)
        idx = (len(s) - 1) * pct / 100
        lo = int(idx)
        hi = min(lo + 1, len(s) - 1)
        frac = idx - lo
        return s[lo] + (s[hi] - s[lo]) * frac

    def _calc_details(self, closes, volumes, ma20, ma60):
        current = closes[-1]
        c60 = closes[-60:] if len(closes) >= 60 else closes
        price_high, price_low = max(c60), min(c60)
        rng = price_high - price_low
        price_position = (current - price_low) / rng if rng > 0 else 0.5

        vol_5 = mean(volumes[-5:]) if len(volumes) >= 5 else mean(volumes)
        vol_20 = mean(volumes[-20:]) if len(volumes) >= 20 else mean(volumes)
        volume_ratio = vol_5 / vol_20 if vol_20 > 0 else 1.0

        recent = closes[-10:] if len(closes) >= 10 else closes
        volatility = (stdev(recent) / ma20) if ma20 > 0 and len(recent) >= 2 else 0

        p5 = closes[-6] if len(closes) >= 6 else closes[0]
        change_5d = (current - p5) / p5 * 100 if p5 > 0 else 0

        return {
            'ma20': round(ma20, 2),
            'ma60': round(ma60, 2),
            'price_position': round(price_position, 3),
            'volume_ratio': round(volume_ratio, 2),
            'volatility': round(volatility, 4),
            'change_5d': round(change_5d, 2),
        }

    # ── 阶段识别 ──

    def _detect_phase(self, closes, volumes, highs, lows, ma20, ma60, details):
        pp = details['price_position']
        vr = details['volume_ratio']
        vol = details['volatility']
        chg = details['change_5d']
        current = closes[-1]

        # 吸筹：低位 + 波动收窄 + 量比震荡
        if pp < 0.35 and vol < 0.03:
            return 'accumulation'

        # 派发：高位 + 放量滞涨
        if pp > 0.65 and vr > 1.2 and chg < 2:
            return 'distribution'

        # 上涨：均线多头 + 价格在 MA20 上方
        if ma20 > ma60 and current > ma20:
            return 'markup'

        # 下跌 / 默认
        return 'markdown'

    def _refine_phase(self, phase, events, current_price, range_high, range_low):
        """根据事件修正阶段"""
        event_set = set(events)

        if phase == 'accumulation':
            if ('SOS' in event_set or
                    ('spring' in event_set and 'test' in event_set) or
                    current_price > range_high):
                return 'accumulation_markup'

        if phase == 'distribution':
            if 'SOW' in event_set or current_price < range_low:
                return 'distribution_markdown'

        return phase

    # ── 事件检测 ──

    def _detect_events(self, closes, volumes, highs, lows, range_high, range_low, phase):
        events = []
        n = len(closes)
        if n < 5:
            return events

        vol_20 = mean(volumes[-20:]) if n >= 20 else mean(volumes)

        def vr(idx):
            return volumes[idx] / vol_20 if vol_20 > 0 else 1.0

        current = closes[-1]

        if phase in ('accumulation', 'accumulation_markup', 'markdown'):
            self._detect_accumulation_events(
                events, closes, volumes, highs, lows, range_high, range_low, vol_20, vr, n)

        if phase in ('distribution', 'distribution_markdown', 'markup'):
            self._detect_distribution_events(
                events, closes, volumes, highs, lows, range_high, range_low, vol_20, vr, n)

        return events

    def _detect_accumulation_events(self, events, closes, volumes, highs, lows,
                                    range_high, range_low, vol_20, vr, n):
        # PS: 下跌中放量支撑
        for i in range(max(n - 20, 1), n):
            if closes[i] < closes[i - 1] and vr(i) > 1.5:
                if i + 1 < n and closes[i + 1] >= closes[i]:
                    events.append('PS')
                    break

        # SC: 恐慌抛售（近20日单日跌幅>3% + 量比>2 + 随后2日反弹>2%）
        sc_idx = None
        for i in range(max(n - 20, 1), n - 2):
            day_drop = (closes[i - 1] - closes[i]) / closes[i - 1] * 100 if closes[i - 1] > 0 else 0
            if day_drop > 3 and vr(i) > 2.0:
                bounce = (closes[i + 2] - closes[i]) / closes[i] * 100 if closes[i] > 0 else 0
                if bounce > 2:
                    events.append('SC')
                    sc_idx = i
                    break

        # AR: SC后反弹（从SC低点反弹>3%）
        if sc_idx is not None:
            sc_low = lows[sc_idx]
            post_high = max(highs[sc_idx:min(sc_idx + 10, n)])
            if sc_low > 0 and (post_high - sc_low) / sc_low * 100 > 3:
                events.append('AR')

        # ST: 回测SC低点附近（±2%范围），量比<0.8
        if sc_idx is not None:
            sc_low = lows[sc_idx]
            for i in range(sc_idx + 3, min(sc_idx + 20, n)):
                if sc_low > 0 and abs(lows[i] - sc_low) / sc_low < 0.02 and vr(i) < 0.8:
                    events.append('ST')
                    break

        # spring: 近3日低点跌破 range_low 后当前价收回
        recent_low = min(lows[-3:]) if n >= 3 else lows[-1]
        if recent_low < range_low and closes[-1] > range_low:
            events.append('spring')

        # test: spring后缩量回踩不破spring低点
        if 'spring' in events and n >= 5:
            spring_low = min(lows[-3:])
            if vr(n - 1) < 0.7 and lows[-1] >= spring_low:
                events.append('test')

        # SOS: 放量突破 range_high
        if closes[-1] > range_high and vr(n - 1) > 1.5:
            events.append('SOS')

        # LPS: SOS后缩量回踩不破突破位
        if 'SOS' in events and n >= 5:
            for i in range(n - 3, n):
                if vr(i) < 0.8 and lows[i] >= range_high * 0.98:
                    events.append('LPS')
                    break

    def _detect_distribution_events(self, events, closes, volumes, highs, lows,
                                    range_high, range_low, vol_20, vr, n):
        # PSY: 上涨中放量抛压
        for i in range(max(n - 20, 1), n):
            if closes[i] > closes[i - 1] and vr(i) > 1.5:
                if i + 1 < n and closes[i + 1] <= closes[i]:
                    events.append('PSY')
                    break

        # BC: 近20日单日涨幅>3% + 量比>2 + 随后2日回落>2%
        for i in range(max(n - 20, 1), n - 2):
            day_rise = (closes[i] - closes[i - 1]) / closes[i - 1] * 100 if closes[i - 1] > 0 else 0
            if day_rise > 3 and vr(i) > 2.0:
                drop = (closes[i] - closes[i + 2]) / closes[i] * 100 if closes[i] > 0 else 0
                if drop > 2:
                    events.append('BC')
                    break

        # UTAD: 近3日高点突破 range_high 后当前价收回
        recent_high = max(highs[-3:]) if n >= 3 else highs[-1]
        if recent_high > range_high and closes[-1] < range_high:
            events.append('UTAD')

        # SOW: 跌破 range_low，量比>1.2，无法收回
        if closes[-1] < range_low and vr(n - 1) > 1.2:
            events.append('SOW')

        # LPSY: SOW后反弹幅度<前次反弹60%，量比<0.8
        if 'SOW' in events and n >= 10:
            bounces = []
            for i in range(max(n - 20, 2), n):
                if closes[i] > closes[i - 1] and closes[i - 1] < closes[i - 2]:
                    bounce_pct = (closes[i] - closes[i - 1]) / closes[i - 1] * 100 if closes[i - 1] > 0 else 0
                    bounces.append(bounce_pct)
            if len(bounces) >= 2 and bounces[-1] < bounces[-2] * 0.6 and vr(n - 1) < 0.8:
                events.append('LPSY')

    # ── 建议 ──

    def _generate_advice(self, phase, events):
        es = set(events)

        if phase == 'accumulation' and es & {'spring', 'SOS', 'test'}:
            return 'buy'
        if phase == 'accumulation_markup':
            return 'buy'
        if phase == 'markup' and 'LPS' in es:
            return 'hold'
        if phase == 'markup':
            return 'hold'
        if phase == 'distribution' and es & {'UTAD', 'LPSY'}:
            return 'sell'
        if phase == 'distribution_markdown':
            return 'sell'
        if phase == 'markdown':
            return 'watch'
        return 'watch'

    # ── 评分（0-100） ──

    def _calc_score(self, phase, events, details):
        phase_score = PHASE_SCORES.get(phase, 5)

        raw_event = sum(EVENT_SCORES.get(e, 0) for e in events)
        event_score = max(0, min(25, raw_event + 12))

        vr = details.get('volume_ratio', 1.0)
        if vr > 1.5:
            volume_score = 15
        elif vr > 1.2:
            volume_score = 12
        elif vr > 0.8:
            volume_score = 8
        else:
            volume_score = 3

        pp = details.get('price_position', 0.5)
        ma20, ma60 = details.get('ma20', 0), details.get('ma60', 0)
        if ma20 > ma60 and pp > 0.5:
            trend_score = 15
        elif ma20 > ma60:
            trend_score = 10
        elif ma20 < ma60 and pp < 0.3:
            trend_score = 3
        else:
            trend_score = 7

        raw = phase_score + event_score + volume_score + trend_score + 10
        return max(0, min(100, int(round(raw * 100 / 100))))

    # ── 置信度 ──

    def _calc_confidence(self, events, phase):
        base = 0.3
        base += len(events) * 0.08

        phase_match = {
            'accumulation': {'PS', 'SC', 'AR', 'ST', 'spring', 'test'},
            'accumulation_markup': {'SOS', 'LPS', 'spring', 'test'},
            'distribution': {'PSY', 'BC', 'UTAD'},
            'distribution_markdown': {'SOW', 'LPSY'},
        }
        expected = phase_match.get(phase, set())
        if expected:
            matched = len(set(events) & expected)
            base += matched * 0.1

        return min(0.95, base)

    # ── 支撑 / 阻力 ──

    def _calc_levels(self, lows, highs, range_low, range_high, ma20, ma60):
        low_20 = min(lows[-20:]) if len(lows) >= 20 else min(lows)
        support = min(low_20, range_low, ma60)

        high_20 = max(highs[-20:]) if len(highs) >= 20 else max(highs)
        resistance = max(high_20, range_high, ma20 * 1.05)

        return support, resistance


# ── 辅助函数 ──

def _parse_date(date_str):
    from datetime import datetime
    for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%Y%m%d'):
        try:
            return datetime.strptime(date_str, fmt)
        except (ValueError, TypeError):
            continue
    return datetime.strptime(str(date_str)[:10], '%Y-%m-%d')


def _aggregate_group(bars: list) -> dict:
    return {
        'date': bars[-1]['date'],
        'open': bars[0]['open'],
        'high': max(b['high'] for b in bars),
        'low': min(b['low'] for b in bars),
        'close': bars[-1]['close'],
        'volume': sum(b['volume'] for b in bars),
    }
