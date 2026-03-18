# 盯盘告警系统增强 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将告警系统从 1 种扩展为 7 种告警类型，移除确认延迟和冷却，复用 AI 分析输出驱动告警参数。

**Architecture:** 扩展 7d 分析 prompt 输出 `alert_params`，代码计算 `volume_baseline`。重写 `WatchAlertService` 为 7 个 checker 方法 + `_fired` 日级去重。策略层加载 AI 参数并增加 TD 15 分钟节流。

**Tech Stack:** Python, Flask, SQLAlchemy, 智谱 GLM, TDSequentialService, TradingCalendarService

**Spec:** `docs/superpowers/specs/2026-03-18-watch-alert-enhance-design.md`

---

## Task 1: 扩展 7d 分析 Prompt 输出 alert_params

**Files:**
- Modify: `app/llm/prompts/watch_analysis.py:38-59`

- [ ] **Step 1: 修改 `build_7d_analysis_prompt`，在 JSON 输出要求中追加 `alert_params`**

在函数返回的 prompt 字符串中，JSON 模板部分追加 `alert_params` 字段。同时在指令文本中说明 `target_prices` 不要与 `support_levels`/`resistance_levels` 重复：

```python
def build_7d_analysis_prompt(stock_name: str, stock_code: str,
                              ohlc_data: list, current_price: float) -> str:
    data_lines = []
    for d in ohlc_data[-7:]:
        data_lines.append(f"{d['date']}: O={d['open']} H={d['high']} L={d['low']} C={d['close']} V={d.get('volume', 'N/A')}")
    data_text = "\n".join(data_lines)

    return f"""分析 {stock_name}({stock_code}) 的短期趋势，当前价格 {current_price}。

近7日K线数据：
{data_text}

请返回JSON（不要markdown代码块包裹）：
{{
  "support_levels": [短期支撑位1, 支撑位2],
  "resistance_levels": [短期阻力位1, 阻力位2],
  "signal": "buy或sell或hold或watch",
  "signal_text": "买入或卖出或持有或观望",
  "summary": "80字以内的短期趋势分析，含量价关系和方向判断",
  "ma_levels": {{"ma5": 数值, "ma20": 数值, "ma60": 数值或null}},
  "price_range": {{"low": 建议买入下限, "high": 建议卖出上限}},
  "alert_params": {{
    "target_prices": [
      {{"price": 目标价, "direction": "above或below", "reason": "原因"}}
    ],
    "change_threshold_pct": 根据近期波动率计算的涨跌幅告警阈值百分比,
    "volume_anomaly_ratio": 成交量异动倍率（相对近期日均量）
  }}
}}

alert_params说明：
- target_prices：关键突破目标价，不要与support_levels/resistance_levels重复，仅设定超出常规支撑阻力的关键位
- change_threshold_pct：根据近7日波动率设定合理的涨跌幅告警阈值（通常2-5%）
- volume_anomaly_ratio：成交量异动倍率，通常1.5-3.0"""
```

- [ ] **Step 2: Commit**

```bash
git add app/llm/prompts/watch_analysis.py
git commit -m "feat: 7d分析prompt扩展alert_params输出"
```

---

## Task 2: watch_analysis_service 存储 alert_params + 计算 volume_baseline

**Files:**
- Modify: `app/services/watch_analysis_service.py:95-107`

- [ ] **Step 1: 修改 `analyze_stocks` 中 7d 分支的 detail 构造**

在 `period == '7d'` 时，从 LLM 响应中提取 `alert_params`，用代码计算 `volume_baseline`（7 日平均成交量），clamp `change_threshold_pct` 到 1%-10%，然后存入 `detail`。

找到 `WatchService.save_analysis(...)` 调用处（约第 95-107 行），将 `detail` 构造改为：

```python
                detail_data = {
                    'signal_text': parsed.get('signal_text', ''),
                    'ma_levels': parsed.get('ma_levels', {}),
                    'price_range': parsed.get('price_range', {}),
                }
                if period == '7d':
                    alert_params = parsed.get('alert_params', {})
                    # clamp change_threshold_pct 到 1%-10%
                    raw_pct = alert_params.get('change_threshold_pct', 5.0)
                    try:
                        alert_params['change_threshold_pct'] = max(1.0, min(10.0, float(raw_pct)))
                    except (TypeError, ValueError):
                        alert_params['change_threshold_pct'] = 5.0
                    # clamp volume_anomaly_ratio 到 1.0-5.0
                    raw_ratio = alert_params.get('volume_anomaly_ratio', 2.0)
                    try:
                        alert_params['volume_anomaly_ratio'] = max(1.0, min(5.0, float(raw_ratio)))
                    except (TypeError, ValueError):
                        alert_params['volume_anomaly_ratio'] = 2.0
                    # 代码计算 volume_baseline（7日平均成交量）
                    trend_stock = trend_map.get(code, {})
                    ohlc_for_vol = trend_stock.get('data', [])
                    volumes = [d.get('volume', 0) for d in ohlc_for_vol[-7:] if d.get('volume')]
                    alert_params['volume_baseline'] = sum(volumes) / len(volumes) if volumes else 0
                    detail_data['alert_params'] = alert_params

                WatchService.save_analysis(
                    stock_code=code,
                    period=period,
                    support_levels=parsed.get('support_levels', []),
                    resistance_levels=parsed.get('resistance_levels', []),
                    summary=parsed.get('summary', ''),
                    signal=parsed.get('signal', ''),
                    detail=detail_data,
                )
```

- [ ] **Step 2: Commit**

```bash
git add app/services/watch_analysis_service.py
git commit -m "feat: 存储alert_params并计算volume_baseline"
```

---

## Task 3: 重写 WatchAlertService — 去重基础 + check_intraday_extreme

**Files:**
- Modify: `app/services/watch_alert_service.py` (全文重写)

- [ ] **Step 1: 重写整个文件，建立新的类骨架 + _fired 去重 + check_intraday_extreme**

移除旧的 `_cooldown`、`COOLDOWN_SECONDS`、`BREAKTHROUGH_CONFIRM_MINUTES`。保留单例模式和日内极值追踪，但去掉确认延迟逻辑。

```python
"""盯盘告警服务 — 7种检测器 + 日级去重"""
import logging
from datetime import datetime

from app.strategies.base import Signal

logger = logging.getLogger(__name__)


class WatchAlertService:

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._fired = {}          # {date_str: {fired_key, ...}}
            cls._instance._intraday_extremes = {}
            cls._instance._prev_prices = {}
            cls._instance._prev_ma_side = {}   # {code: {ma5: 'above'|'below', ...}}
            cls._instance._last_trading_date = None
        return cls._instance

    def _reset_if_new_day(self):
        today = datetime.now().strftime('%Y-%m-%d')
        if self._last_trading_date != today:
            self._fired = {}
            self._intraday_extremes = {}
            self._prev_prices = {}
            self._prev_ma_side = {}
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
            detail=f'{name}({code}) {detail}',
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

            # 不依赖AI参数的检测器，始终执行
            signals.extend(self._check_intraday_extreme(code, name, data))

            td = td_results.get(code)
            if td:
                signals.extend(self._check_td_sequential(code, name, curr, td))

            # 依赖AI参数的检测器，无参数则跳过
            if not params:
                continue
            signals.extend(self._check_target_price(code, name, curr, params))
            signals.extend(self._check_price_change(code, name, data, params))
            signals.extend(self._check_support_resistance(code, name, curr, params))
            signals.extend(self._check_ma_crossover(code, name, curr, params))
            signals.extend(self._check_volume_anomaly(code, name, data, params, trading_minutes.get(code)))

        self._prev_prices = {c: p.get('current_price') for c, p in prices.items() if p.get('current_price')}
        return signals

    # --- 检测器 1: 日内突破前高/前低 ---

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

        # API校准
        if api_high and api_high > ext['high'] and api_high > curr:
            ext['high'] = api_high
        if api_low and api_low < ext['low'] and api_low < curr:
            ext['low'] = api_low

        # 突破前高
        if curr > ext['high']:
            level = ext['high']
            key = f"extreme:{code}:{level:.2f}"
            if not self._has_fired(key):
                signals.append(self._make_signal(name, code,
                    f'突破盘中前高 {level:.2f}',
                    f'突破盘中前高 {level:.2f} ↑ | 当前 {curr:.2f}',
                    {'alert_type': 'intraday_extreme', 'direction': 'high', 'level': level}))
                self._mark_fired(key)
            ext['high'] = curr

        # 跌破前低
        if curr < ext['low']:
            level = ext['low']
            key = f"extreme:{code}:{level:.2f}"
            if not self._has_fired(key):
                signals.append(self._make_signal(name, code,
                    f'跌破盘中前低 {level:.2f}',
                    f'跌破盘中前低 {level:.2f} ↓ | 当前 {curr:.2f}',
                    {'alert_type': 'intraday_extreme', 'direction': 'low', 'level': level}))
                self._mark_fired(key)
            ext['low'] = curr

        return signals

    # --- 检测器 2: 目标价触达 ---

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
                    f'触达目标价 {price}',
                    f'上破目标价 {price} ↑ | 当前 {curr:.2f} | {reason}',
                    {'alert_type': 'target_price', 'direction': 'above', 'level': price}))
                self._mark_fired(key)
            elif direction == 'below' and curr <= price:
                signals.append(self._make_signal(name, code,
                    f'触达目标价 {price}',
                    f'下破目标价 {price} ↓ | 当前 {curr:.2f} | {reason}',
                    {'alert_type': 'target_price', 'direction': 'below', 'level': price}))
                self._mark_fired(key)
        return signals

    # --- 检测器 3: 涨跌幅阈值 ---

    def _check_price_change(self, code: str, name: str, data: dict, params: dict) -> list[Signal]:
        signals = []
        threshold = params.get('change_threshold_pct')
        change_pct = data.get('change_percent')
        if threshold is None or change_pct is None:
            return signals

        if change_pct >= threshold:
            key = f"change:{code}:up"
            if not self._has_fired(key):
                signals.append(self._make_signal(name, code,
                    f'涨幅达 {change_pct:.1f}%',
                    f'涨幅 {change_pct:.1f}% 超过阈值 {threshold:.1f}%',
                    {'alert_type': 'price_change', 'direction': 'up', 'change_pct': change_pct}))
                self._mark_fired(key)
        elif change_pct <= -threshold:
            key = f"change:{code}:down"
            if not self._has_fired(key):
                signals.append(self._make_signal(name, code,
                    f'跌幅达 {abs(change_pct):.1f}%',
                    f'跌幅 {abs(change_pct):.1f}% 超过阈值 {threshold:.1f}%',
                    {'alert_type': 'price_change', 'direction': 'down', 'change_pct': change_pct}))
                self._mark_fired(key)
        return signals

    # --- 检测器 4: 支撑/阻力位触及 ---

    def _check_support_resistance(self, code: str, name: str, curr: float, params: dict) -> list[Signal]:
        signals = []
        tolerance = 0.005  # ±0.5%

        for level in params.get('support_levels', []):
            if not level:
                continue
            key = f"sr:{code}:{level}"
            if self._has_fired(key):
                continue
            if abs(curr - level) / level <= tolerance:
                signals.append(self._make_signal(name, code,
                    f'触及支撑位 {level}',
                    f'价格 {curr:.2f} 触及支撑位 {level}',
                    {'alert_type': 'support_resistance', 'direction': 'support', 'level': level}))
                self._mark_fired(key)

        for level in params.get('resistance_levels', []):
            if not level:
                continue
            key = f"sr:{code}:{level}"
            if self._has_fired(key):
                continue
            if abs(curr - level) / level <= tolerance:
                signals.append(self._make_signal(name, code,
                    f'触及阻力位 {level}',
                    f'价格 {curr:.2f} 触及阻力位 {level}',
                    {'alert_type': 'support_resistance', 'direction': 'resistance', 'level': level}))
                self._mark_fired(key)

        return signals

    # --- 检测器 5: 均线突破 ---

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
                # 首次记录，不触发
                continue
            if side == prev_side:
                continue

            direction = 'up' if side == 'above' else 'down'
            key = f"ma:{code}:{ma_type}:{direction}"
            if self._has_fired(key):
                continue

            arrow = '↑' if direction == 'up' else '↓'
            label = '上穿' if direction == 'up' else '下穿'
            signals.append(self._make_signal(name, code,
                f'{label}{ma_type.upper()} {ma_val:.2f}',
                f'{label}{ma_type.upper()} {ma_val:.2f} {arrow} | 当前 {curr:.2f}',
                {'alert_type': 'ma_crossover', 'ma_type': ma_type, 'direction': direction, 'level': ma_val}))
            self._mark_fired(key)

        self._prev_ma_side[code] = curr_sides
        return signals

    # --- 检测器 6: 成交量异动 ---

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

        # 时间归一化：将累计成交量按比例推算全日量
        normalized = volume / (elapsed / total)

        if normalized >= baseline * ratio:
            key = f"volume:{code}"
            if not self._has_fired(key):
                signals.append(self._make_signal(name, code,
                    f'成交量异动 {normalized/baseline:.1f}倍',
                    f'成交量异动 | 归一化量 {int(normalized)} ≈ 日均 {int(baseline)} 的 {normalized/baseline:.1f} 倍',
                    {'alert_type': 'volume_anomaly', 'normalized_volume': normalized, 'baseline': baseline}))
                self._mark_fired(key)
        return signals

    # --- 检测器 7: TD九转完成 ---

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
            f'TD九转{label}信号完成',
            f'TD九转{label}信号完成（count=9）| 当前 {curr:.2f}',
            {'alert_type': 'td_sequential', 'direction': direction, 'count': 9}))
        self._mark_fired(key)
        return signals
```

- [ ] **Step 2: Commit**

```bash
git add app/services/watch_alert_service.py
git commit -m "feat: 重写WatchAlertService，7种检测器+fired去重"
```

---

## Task 4: 扩展 WatchAlertStrategy — 加载 AI 参数 + TD 节流

**Files:**
- Modify: `app/strategies/watch_alert/__init__.py` (全文重写)

- [ ] **Step 1: 重写策略，增加 AI 参数加载、TD 15分钟计算、交易分钟数计算**

```python
"""盯盘告警策略 — 价格获取 + AI参数加载 + TD节流 + 7种检测"""
import logging
from datetime import datetime, time

from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)

# TD计算间隔（秒）
TD_CALC_INTERVAL = 15 * 60


class WatchAlertStrategy(Strategy):
    name = "watch_alert"
    description = "盯盘告警推送（每分钟检测）"
    schedule = "interval_minutes:1"
    needs_llm = False

    _last_td_calc = None
    _td_cache = {}
    _alert_params_cache = {}      # {date_str: {code: params}}

    def scan(self) -> list[Signal]:
        from app.models.watch_list import WatchList
        from app.services.trading_calendar import TradingCalendarService
        from app.services.watch_service import WatchService
        from app.services.watch_alert_service import WatchAlertService
        from app.config.stock_codes import BENCHMARK_CODES
        from app.utils.market_identifier import MarketIdentifier

        codes = WatchService.get_watch_codes()
        if not codes:
            return []

        markets = WatchService.get_watched_markets()
        has_active = any(TradingCalendarService.is_market_open(m) for m in markets)
        if not has_active:
            return []

        from app.services.unified_stock_data import UnifiedStockDataService
        data_service = UnifiedStockDataService()

        bench_codes = [b['code'] for b in BENCHMARK_CODES]
        all_codes = list(set(codes + bench_codes))

        a_codes = [c for c in all_codes if MarketIdentifier.is_a_share(c)]
        other_codes = [c for c in all_codes if c not in a_codes]

        prices = {}
        if a_codes:
            prices.update(data_service.get_realtime_prices(a_codes, force_refresh=True))
        if other_codes:
            prices.update(data_service.get_realtime_prices(other_codes))

        watch_prices = {c: prices[c] for c in codes if c in prices}
        items = WatchList.query.filter(WatchList.stock_code.in_(codes)).all()
        name_map = {w.stock_code: w.stock_name for w in items}

        # 加载AI告警参数（按日缓存）
        alert_params_map = self._load_alert_params(codes)

        # TD九转（15分钟节流）
        td_results = self._calc_td_if_due(codes, data_service)

        # 交易分钟数（用于成交量归一化）
        trading_minutes = self._calc_trading_minutes(codes, items, TradingCalendarService)

        service = WatchAlertService()
        signals = service.check_alerts(
            watch_prices, name_map,
            alert_params_map=alert_params_map,
            td_results=td_results,
            trading_minutes=trading_minutes,
        )

        if signals:
            logger.info(f'[盯盘告警] 产出 {len(signals)} 个信号')
        return signals

    def _load_alert_params(self, codes: list[str]) -> dict:
        """从DB读取当日7d分析的alert_params，按日缓存"""
        today = datetime.now().strftime('%Y-%m-%d')
        cache_entry = self._alert_params_cache.get(today)
        if cache_entry and cache_entry.get('_queried_codes', set()) >= set(codes):
            return cache_entry.get('params', {})

        from app.services.watch_service import WatchService
        all_analyses = WatchService.get_all_today_analyses()

        result = {}
        for code in codes:
            analysis_7d = all_analyses.get(code, {}).get('7d', {})
            detail = analysis_7d.get('detail', {})
            alert_params = detail.get('alert_params', {})
            if alert_params:
                # 把 support/resistance/ma_levels 也合入，供检测器使用
                alert_params['support_levels'] = analysis_7d.get('support_levels', [])
                alert_params['resistance_levels'] = analysis_7d.get('resistance_levels', [])
                alert_params['ma_levels'] = detail.get('ma_levels', {})
                result[code] = alert_params

        self._alert_params_cache = {today: {'params': result, '_queried_codes': set(codes)}}
        return result

    def _calc_td_if_due(self, codes: list[str], data_service) -> dict:
        """每15分钟计算一次TD九转"""
        now = datetime.now()
        if self._last_td_calc and (now - self._last_td_calc).total_seconds() < TD_CALC_INTERVAL:
            return self._td_cache

        from app.services.td_sequential import TDSequentialService
        trend = data_service.get_trend_data(codes, days=60)
        td_results = {}
        for stock in trend.get('stocks', []):
            code = stock.get('stock_code')
            ohlc = stock.get('data', [])
            if code and ohlc:
                td_results[code] = TDSequentialService.calculate(ohlc)

        self._last_td_calc = now
        self._td_cache = td_results
        return td_results

    @staticmethod
    def _calc_trading_minutes(codes: list[str], items: list, calendar_service) -> dict:
        """计算每只股票已过交易分钟数和全日总交易分钟数"""
        market_map = {w.stock_code: w.market for w in items}

        # A股交易时段: 09:30-11:30 + 13:00-15:00 = 240分钟
        # 美股: 09:30-16:00 = 390分钟
        # 港股: 09:30-16:00 = 390分钟
        TOTAL_MINUTES = {
            'A': 240, 'US': 390, 'HK': 390,
            'KR': 390, 'TW': 270, 'JP': 300,
        }

        # A股时段列表用于计算已过分钟
        SESSIONS = {
            'A': [(time(9, 30), time(11, 30)), (time(13, 0), time(15, 0))],
            'JP': [(time(9, 0), time(11, 30)), (time(12, 30), time(15, 0))],
        }

        result = {}
        for code in codes:
            market = market_map.get(code, 'A')
            total = TOTAL_MINUTES.get(market, 390)
            now_dt = calendar_service.get_market_now(market)
            now_t = now_dt.time()

            sessions = SESSIONS.get(market)
            if sessions:
                elapsed = 0
                for s_open, s_close in sessions:
                    if now_t >= s_close:
                        elapsed += (datetime.combine(now_dt.date(), s_close) - datetime.combine(now_dt.date(), s_open)).seconds // 60
                    elif now_t > s_open:
                        elapsed += (datetime.combine(now_dt.date(), now_t) - datetime.combine(now_dt.date(), s_open)).seconds // 60
            else:
                open_t, close_t = calendar_service.get_market_hours(market, now_dt.date())
                if open_t is None or close_t is None:
                    elapsed = 0
                elif now_t >= close_t:
                    elapsed = total
                elif now_t > open_t:
                    elapsed = (datetime.combine(now_dt.date(), now_t) - datetime.combine(now_dt.date(), open_t)).seconds // 60
                else:
                    elapsed = 0

            result[code] = {'elapsed': elapsed, 'total': total}
        return result
```

- [ ] **Step 2: Commit**

```bash
git add app/strategies/watch_alert/__init__.py
git commit -m "feat: 策略层加载AI参数、TD节流、交易分钟数"
```

---

## Task 5: 端到端验证

- [ ] **Step 1: 启动应用验证无报错**

```bash
cd D:/Git/stock && python -c "from app import create_app; app = create_app(); print('OK')"
```

- [ ] **Step 2: 验证 import 链路**

```bash
python -c "
from app.services.watch_alert_service import WatchAlertService
s = WatchAlertService()
# 空数据不应报错
signals = s.check_alerts({}, {})
assert signals == [], f'Expected empty, got {signals}'
print('WatchAlertService OK')
"
```

- [ ] **Step 3: 验证策略可实例化**

```bash
python -c "
from app.strategies.watch_alert import WatchAlertStrategy
s = WatchAlertStrategy()
print(f'Strategy: {s.name}, schedule: {s.schedule}')
print('WatchAlertStrategy OK')
"
```

- [ ] **Step 4: Commit（如有修复）**

```bash
git add -u
git commit -m "fix: 修复端到端验证发现的问题"
```
