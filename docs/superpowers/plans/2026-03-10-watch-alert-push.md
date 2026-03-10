# 盯盘推送告警 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为盯盘助手新增四类实时推送告警（整数价格、支撑/压力位、九转信号、锚点价格），通过 Slack 推送。

**Architecture:** 新建 `WatchAlertService` 作为信号检测核心，维护价格/九转/锚点状态和冷却机制。两个新策略 `watch_alert`（60秒轮询）和 `watch_anchor`（每日开盘前AI计算阈值）通过现有 EventBus → NotificationManager → Slack 链路推送信号。

**Tech Stack:** Flask, APScheduler, 智谱 GLM（锚点阈值计算）, Slack Webhook

**Spec:** `docs/superpowers/specs/2026-03-10-watch-alert-push-design.md`

---

## Chunk 1: WatchAlertService 核心检测逻辑

### Task 1: 创建 WatchAlertService 基础框架

**Files:**
- Create: `app/services/watch_alert_service.py`

- [ ] **Step 1: 创建 WatchAlertService 类骨架**

```python
"""盯盘推送告警服务 — 四类信号检测 + 冷却 + 状态管理"""
import json
import logging
import os
import pickle
from datetime import datetime, timedelta
from app.strategies.base import Signal

logger = logging.getLogger(__name__)

COOLDOWN_SECONDS = int(os.environ.get('WATCH_ALERT_COOLDOWN_SECONDS', '300'))
APPROACH_PCT = float(os.environ.get('WATCH_ALERT_APPROACH_PCT', '0.5'))
DEFAULT_THRESHOLD_PCT = float(os.environ.get('WATCH_ALERT_DEFAULT_THRESHOLD_PCT', '3.0'))

ANCHOR_FILE = os.path.join('data', 'memory_cache', '_watch_alert', 'anchors.pkl')


class WatchAlertService:

    def __init__(self):
        self._prev_prices = {}
        self._prev_td_counts = {}
        self._prev_td_pending = {}
        self._anchors = {}
        self._cooldown = {}
        self._load_anchors()

    def _is_cooled_down(self, key: str) -> bool:
        last = self._cooldown.get(key)
        if last and (datetime.now() - last).total_seconds() < COOLDOWN_SECONDS:
            return False
        return True

    def _set_cooldown(self, key: str):
        self._cooldown[key] = datetime.now()

    def _load_anchors(self):
        try:
            if os.path.exists(ANCHOR_FILE):
                with open(ANCHOR_FILE, 'rb') as f:
                    self._anchors = pickle.load(f)
                logger.info(f'[盯盘告警] 恢复锚点数据: {len(self._anchors)} 只股票')
        except Exception as e:
            logger.error(f'[盯盘告警] 加载锚点失败: {e}')
            self._anchors = {}

    def _save_anchors(self):
        try:
            os.makedirs(os.path.dirname(ANCHOR_FILE), exist_ok=True)
            tmp = ANCHOR_FILE + '.tmp'
            with open(tmp, 'wb') as f:
                pickle.dump(self._anchors, f)
            os.replace(tmp, ANCHOR_FILE)
        except Exception as e:
            logger.error(f'[盯盘告警] 保存锚点失败: {e}')

    def set_anchors(self, anchor_data: dict):
        """由 WatchAnchorStrategy 调用，设置锚点和阈值

        anchor_data: {code: {'price': float, 'threshold_pct': float}}
        """
        self._anchors.update(anchor_data)
        self._save_anchors()
        logger.info(f'[盯盘告警] 更新锚点: {list(anchor_data.keys())}')
```

- [ ] **Step 2: 提交骨架**

```bash
git add app/services/watch_alert_service.py
git commit -m "feat: WatchAlertService 基础框架 — 状态管理+冷却+锚点持久化"
```

---

### Task 2: 整数价格穿越检测

**Files:**
- Modify: `app/services/watch_alert_service.py`

- [ ] **Step 1: 添加整数价格检测方法**

在 `WatchAlertService` 类中添加：

```python
    @staticmethod
    def _get_integer_step(price: float) -> int:
        if price < 10:
            return 1
        elif price < 100:
            return 10
        elif price < 1000:
            return 100
        else:
            return 100

    def _check_integer_price(self, code: str, name: str, prev_price: float, curr_price: float) -> list[Signal]:
        if curr_price <= 0 or prev_price <= 0:
            return []
        signals = []
        step = self._get_integer_step(curr_price)
        lo = min(prev_price, curr_price)
        hi = max(prev_price, curr_price)

        level = (int(lo) // step + 1) * step
        while level <= hi:
            level_f = float(level)
            if lo < level_f <= hi:
                key = f"integer:{code}:{level}"
                if self._is_cooled_down(key):
                    direction = '↑' if curr_price > prev_price else '↓'
                    signals.append(Signal(
                        strategy='watch_alert',
                        priority='MEDIUM',
                        title=f'{name}({code}) {"突破" if direction == "↑" else "跌破"} {level} 整数关口 {direction}',
                        detail=f'当前 {curr_price:.2f}',
                        data={'stock_code': code, 'alert_type': 'integer', 'detail': str(level)},
                    ))
                    self._set_cooldown(key)
            level += step
        return signals
```

- [ ] **Step 2: 提交**

```bash
git add app/services/watch_alert_service.py
git commit -m "feat: 整数价格穿越检测 — 按价格档位自动判断步长"
```

---

### Task 3: 支撑/压力位接近与穿越检测

**Files:**
- Modify: `app/services/watch_alert_service.py`

- [ ] **Step 1: 添加关键位置检测方法**

在 `WatchAlertService` 类中添加：

```python
    def _check_key_levels(self, code: str, name: str, prev_price: float, curr_price: float,
                          support_levels: list, resistance_levels: list) -> list[Signal]:
        signals = []

        for level in support_levels:
            if not level:
                continue
            # 接近预警
            distance_pct = abs(curr_price - level) / level * 100
            if distance_pct <= APPROACH_PCT:
                key = f"approach:{code}:support:{level:.2f}"
                if self._is_cooled_down(key):
                    signals.append(Signal(
                        strategy='watch_alert',
                        priority='MEDIUM',
                        title=f'{name}({code}) 接近支撑位 {level:.2f}',
                        detail=f'当前 {curr_price:.2f}（距离 {distance_pct:.1f}%）',
                        data={'stock_code': code, 'alert_type': 'approach', 'detail': f'support:{level:.2f}'},
                    ))
                    self._set_cooldown(key)
            # 穿越检测：从上方跌破
            if prev_price >= level > curr_price:
                key = f"cross:{code}:support:{level:.2f}"
                if self._is_cooled_down(key):
                    signals.append(Signal(
                        strategy='watch_alert',
                        priority='HIGH',
                        title=f'{name}({code}) 跌破支撑位 {level:.2f} ↓',
                        detail=f'当前 {curr_price:.2f}',
                        data={'stock_code': code, 'alert_type': 'cross', 'detail': f'support:{level:.2f}'},
                    ))
                    self._set_cooldown(key)

        for level in resistance_levels:
            if not level:
                continue
            distance_pct = abs(curr_price - level) / level * 100
            if distance_pct <= APPROACH_PCT:
                key = f"approach:{code}:resist:{level:.2f}"
                if self._is_cooled_down(key):
                    signals.append(Signal(
                        strategy='watch_alert',
                        priority='MEDIUM',
                        title=f'{name}({code}) 接近压力位 {level:.2f}',
                        detail=f'当前 {curr_price:.2f}（距离 {distance_pct:.1f}%）',
                        data={'stock_code': code, 'alert_type': 'approach', 'detail': f'resist:{level:.2f}'},
                    ))
                    self._set_cooldown(key)
            if prev_price <= level < curr_price:
                key = f"cross:{code}:resist:{level:.2f}"
                if self._is_cooled_down(key):
                    signals.append(Signal(
                        strategy='watch_alert',
                        priority='HIGH',
                        title=f'{name}({code}) 突破压力位 {level:.2f} ↑',
                        detail=f'当前 {curr_price:.2f}',
                        data={'stock_code': code, 'alert_type': 'cross', 'detail': f'resist:{level:.2f}'},
                    ))
                    self._set_cooldown(key)

        return signals
```

- [ ] **Step 2: 提交**

```bash
git add app/services/watch_alert_service.py
git commit -m "feat: 支撑/压力位接近与穿越检测"
```

---

### Task 4: 九转信号变化检测

**Files:**
- Modify: `app/services/watch_alert_service.py`

- [ ] **Step 1: 添加九转信号检测方法**

在 `WatchAlertService` 类中添加：

```python
    def _check_td_sequential(self, code: str, name: str, curr_price: float,
                             td_result: dict) -> list[Signal]:
        signals = []
        if not td_result or not td_result.get('direction'):
            self._prev_td_pending.pop(code, None)
            self._prev_td_counts[code] = {'direction': None, 'count': 0}
            return signals

        direction = td_result['direction']
        count = td_result['count']
        completed = td_result.get('completed', False)
        prev = self._prev_td_counts.get(code, {'direction': None, 'count': 0})
        dir_cn = '买入' if direction == 'buy' else '卖出'

        # count=9 立即推送
        if completed and not (prev.get('direction') == direction and prev.get('count') == 9):
            key = f"td:{code}:{direction}:9"
            if self._is_cooled_down(key):
                signals.append(Signal(
                    strategy='watch_alert',
                    priority='HIGH',
                    title=f'{name}({code}) 九转{dir_cn}信号完成 9/9 ✓',
                    detail=f'当前 {curr_price:.2f}',
                    data={'stock_code': code, 'alert_type': 'td', 'detail': f'{direction}:9'},
                ))
                self._set_cooldown(key)
            self._prev_td_pending.pop(code, None)

        # count>=7 需连续两次确认
        elif count >= 7 and not completed:
            was_below_7 = prev.get('count', 0) < 7 or prev.get('direction') != direction
            pending = self._prev_td_pending.get(code)

            if pending and pending.get('direction') == direction and pending.get('count') >= 7:
                # 第二次确认，推送
                key = f"td:{code}:{direction}:{count}"
                if self._is_cooled_down(key):
                    signals.append(Signal(
                        strategy='watch_alert',
                        priority='MEDIUM',
                        title=f'{name}({code}) 九转{dir_cn}信号 {count}/9',
                        detail=f'当前 {curr_price:.2f}',
                        data={'stock_code': code, 'alert_type': 'td', 'detail': f'{direction}:{count}'},
                    ))
                    self._set_cooldown(key)
                self._prev_td_pending.pop(code, None)
            elif was_below_7:
                # 第一次出现，记录待确认
                self._prev_td_pending[code] = {'direction': direction, 'count': count}
        else:
            self._prev_td_pending.pop(code, None)

        self._prev_td_counts[code] = {'direction': direction, 'count': count}
        return signals
```

- [ ] **Step 2: 提交**

```bash
git add app/services/watch_alert_service.py
git commit -m "feat: 九转信号变化检测 — 连续两次确认抗噪"
```

---

### Task 5: 锚点价格累计波动检测

**Files:**
- Modify: `app/services/watch_alert_service.py`

- [ ] **Step 1: 添加锚点价格检测方法**

在 `WatchAlertService` 类中添加：

```python
    def _check_anchor_price(self, code: str, name: str, curr_price: float) -> list[Signal]:
        signals = []
        anchor = self._anchors.get(code)
        if not anchor:
            return signals

        anchor_price = anchor['price']
        threshold_pct = anchor.get('threshold_pct', DEFAULT_THRESHOLD_PCT)
        if not anchor_price or anchor_price == 0:
            return signals

        change_pct = (curr_price - anchor_price) / anchor_price * 100

        if abs(change_pct) >= threshold_pct:
            key = f"anchor:{code}"
            if self._is_cooled_down(key):
                direction = '上涨' if change_pct > 0 else '下跌'
                signals.append(Signal(
                    strategy='watch_alert',
                    priority='HIGH',
                    title=f'{name}({code}) 累计{direction} {abs(change_pct):.1f}%（超过阈值 {threshold_pct}%）',
                    detail=f'锚点 {anchor_price:.2f} → 当前 {curr_price:.2f}',
                    data={'stock_code': code, 'alert_type': 'anchor', 'detail': f'{change_pct:+.1f}%'},
                ))
                self._set_cooldown(key)
                # 重置锚点
                self._anchors[code]['price'] = curr_price
                self._save_anchors()

        return signals
```

- [ ] **Step 2: 提交**

```bash
git add app/services/watch_alert_service.py
git commit -m "feat: 锚点价格累计波动检测 — 超阈值推送并重置锚点"
```

---

### Task 6: check_alerts 主入口方法

**Files:**
- Modify: `app/services/watch_alert_service.py`

- [ ] **Step 1: 添加 check_alerts 主方法**

在 `WatchAlertService` 类中添加：

```python
    def check_alerts(self) -> list[Signal]:
        from app.services.watch_service import WatchService
        from app.services.unified_stock_data import unified_stock_data_service
        from app.services.td_sequential import TDSequentialService
        from app.services.trading_calendar import TradingCalendarService

        codes = WatchService.get_watch_codes()
        if not codes:
            return []

        markets = WatchService.get_watched_markets()
        has_active = any(TradingCalendarService.is_market_open(m) for m in markets)
        if not has_active:
            return []

        signals = []

        # 获取实时价格
        try:
            prices = unified_stock_data_service.get_realtime_prices(codes)
        except Exception as e:
            logger.error(f'[盯盘告警] 获取价格失败: {e}')
            return []

        # 获取分析数据（支撑/压力位）
        all_analyses = WatchService.get_all_today_analyses()

        # 获取分时数据（九转信号）
        try:
            intraday = unified_stock_data_service.get_intraday_data(codes)
            intraday_map = {s['stock_code']: s['data'] for s in intraday.get('stocks', [])}
        except Exception as e:
            logger.warning(f'[盯盘告警] 获取分时数据失败: {e}')
            intraday_map = {}

        for code in codes:
            price_data = prices.get(code)
            if not price_data or not price_data.get('price'):
                continue

            curr_price = price_data['price']
            name = price_data.get('name', code)
            prev_price = self._prev_prices.get(code)

            if prev_price is not None and prev_price != curr_price:
                # 1. 整数价格穿越
                signals.extend(self._check_integer_price(code, name, prev_price, curr_price))

                # 2. 支撑/压力位
                stock_analyses = all_analyses.get(code, {})
                support_levels = []
                resistance_levels = []
                for period_data in stock_analyses.values():
                    if isinstance(period_data, dict):
                        sl = period_data.get('support_levels')
                        rl = period_data.get('resistance_levels')
                        if isinstance(sl, str):
                            sl = json.loads(sl) if sl else []
                        if isinstance(rl, str):
                            rl = json.loads(rl) if rl else []
                        support_levels.extend(sl or [])
                        resistance_levels.extend(rl or [])
                support_levels = list(set(support_levels))
                resistance_levels = list(set(resistance_levels))

                signals.extend(self._check_key_levels(
                    code, name, prev_price, curr_price, support_levels, resistance_levels
                ))

            # 3. 九转信号（不需要 prev_price 对比，用内部状态）
            ohlc_data = intraday_map.get(code, [])
            if len(ohlc_data) >= 5:
                td_result = TDSequentialService.calculate(ohlc_data)
                signals.extend(self._check_td_sequential(code, name, curr_price, td_result))

            # 4. 锚点价格
            signals.extend(self._check_anchor_price(code, name, curr_price))

            self._prev_prices[code] = curr_price

        if signals:
            logger.info(f'[盯盘告警] 产出 {len(signals)} 个信号')
        return signals
```

- [ ] **Step 2: 添加模块级单例**

在文件末尾添加：

```python
watch_alert_service = WatchAlertService()
```

- [ ] **Step 3: 提交**

```bash
git add app/services/watch_alert_service.py
git commit -m "feat: check_alerts 主入口 — 整合四类信号检测"
```

---

## Chunk 2: 策略 + LLM Prompt + 配置

### Task 7: 创建 WatchAlertStrategy

**Files:**
- Create: `app/strategies/watch_alert/__init__.py`

- [ ] **Step 1: 创建策略文件**

```python
"""盯盘告警策略 — 每分钟检测价格信号并推送"""
import logging
from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)


class WatchAlertStrategy(Strategy):
    name = "watch_alert"
    description = "盯盘告警（整数价格/支撑压力位/九转/锚点，每分钟检测）"
    schedule = "interval_minutes:1"
    needs_llm = False

    def scan(self) -> list[Signal]:
        from app.services.watch_alert_service import watch_alert_service

        try:
            return watch_alert_service.check_alerts()
        except Exception as e:
            logger.error(f'[盯盘告警] 检测异常: {e}')
            return []
```

- [ ] **Step 2: 提交**

```bash
git add app/strategies/watch_alert/__init__.py
git commit -m "feat: WatchAlertStrategy — 每分钟调度信号检测"
```

---

### Task 8: 创建锚点阈值 LLM Prompt

**Files:**
- Create: `app/llm/prompts/watch_anchor.py`

- [ ] **Step 1: 创建 prompt 文件**

```python
"""锚点波动阈值 AI 计算 Prompt"""

SYSTEM_PROMPT = "你是专业的量化分析师，擅长根据股票的历史波动率特征计算合理的价格波动告警阈值。"


def build_anchor_threshold_prompt(stocks_data: list[dict]) -> str:
    """构建批量计算阈值的 prompt

    stocks_data: [{'code': str, 'name': str, 'price': float, 'ohlc_30d': list}]
    """
    stock_sections = []
    for s in stocks_data:
        ohlc = s.get('ohlc_30d', [])
        ohlc_text = '\n'.join(
            f"  {d.get('date', '')}: O={d.get('open', 0):.2f} H={d.get('high', 0):.2f} "
            f"L={d.get('low', 0):.2f} C={d.get('close', 0):.2f}"
            for d in ohlc[-10:]
        )
        stock_sections.append(
            f"### {s['name']}({s['code']})\n"
            f"当前价格: {s['price']:.2f}\n"
            f"近10日K线:\n{ohlc_text}"
        )

    stocks_block = '\n\n'.join(stock_sections)

    return f"""请为以下股票计算合理的价格波动告警阈值（百分比）。

考虑因素：
- 近期日均波幅（ATR 特征）
- 股票的波动率特性（蓝筹 vs 成长股）
- 阈值应能捕捉有意义的价格变动，避免过于频繁的告警

{stocks_block}

请以JSON数组返回，不要包含markdown标记：
[
  {{"stock_code": "代码", "threshold_pct": 数值, "reasoning": "简要理由"}}
]

threshold_pct 范围：0.5 ~ 10.0"""
```

- [ ] **Step 2: 提交**

```bash
git add app/llm/prompts/watch_anchor.py
git commit -m "feat: 锚点波动阈值 LLM Prompt"
```

---

### Task 9: 创建 WatchAnchorStrategy

**Files:**
- Create: `app/strategies/watch_anchor/__init__.py`

- [ ] **Step 1: 创建策略文件**

```python
"""锚点阈值策略 — 每日开盘前 AI 计算波动阈值"""
import json
import logging
from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)


class WatchAnchorStrategy(Strategy):
    name = "watch_anchor"
    description = "每日开盘前计算锚点波动阈值"
    schedule = "0 9 * * 1-5"
    needs_llm = True

    def scan(self) -> list[Signal]:
        from app.services.watch_service import WatchService
        from app.services.watch_alert_service import watch_alert_service, DEFAULT_THRESHOLD_PCT
        from app.services.unified_stock_data import unified_stock_data_service
        from app.services.trading_calendar import TradingCalendarService
        from app.llm.router import llm_router
        from app.llm.prompts.watch_anchor import SYSTEM_PROMPT, build_anchor_threshold_prompt

        codes = WatchService.get_watch_codes()
        if not codes:
            return []

        markets = WatchService.get_watched_markets()
        will_open = any(
            TradingCalendarService.is_trading_day(m) for m in markets
        )
        if not will_open:
            return []

        # 获取实时价格和30日趋势数据
        try:
            prices = unified_stock_data_service.get_realtime_prices(codes)
            trends = unified_stock_data_service.get_trend_data(codes, days=30)
            trend_map = {t['stock_code']: t['data'] for t in trends.get('stocks', []) if t.get('data')}
        except Exception as e:
            logger.error(f'[锚点策略] 数据获取失败，使用默认阈值: {e}')
            self._set_default_anchors(codes, prices, watch_alert_service)
            return []

        # 构建 LLM 输入
        stocks_data = []
        for code in codes:
            price_info = prices.get(code)
            if not price_info or not price_info.get('price'):
                continue
            stocks_data.append({
                'code': code,
                'name': price_info.get('name', code),
                'price': price_info['price'],
                'ohlc_30d': trend_map.get(code, []),
            })

        if not stocks_data:
            return []

        # 调用 LLM
        anchor_data = {}
        provider = llm_router.route('watch_anchor')
        if provider:
            try:
                prompt = build_anchor_threshold_prompt(stocks_data)
                response = provider.chat([
                    {'role': 'system', 'content': SYSTEM_PROMPT},
                    {'role': 'user', 'content': prompt},
                ])
                cleaned = response.strip()
                if cleaned.startswith('```'):
                    cleaned = cleaned.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
                results = json.loads(cleaned)

                for item in results:
                    code = item.get('stock_code', '')
                    threshold = item.get('threshold_pct', DEFAULT_THRESHOLD_PCT)
                    # 范围校验
                    if not (0.5 <= threshold <= 10.0):
                        threshold = DEFAULT_THRESHOLD_PCT
                    price_info = prices.get(code)
                    if price_info and price_info.get('price'):
                        anchor_data[code] = {
                            'price': price_info['price'],
                            'threshold_pct': threshold,
                        }
                        logger.info(f'[锚点策略] {code} 阈值={threshold}% ({item.get("reasoning", "")})')
            except Exception as e:
                logger.error(f'[锚点策略] LLM 分析失败，使用默认阈值: {e}')

        # LLM 未覆盖的股票用默认阈值
        for s in stocks_data:
            if s['code'] not in anchor_data:
                anchor_data[s['code']] = {
                    'price': s['price'],
                    'threshold_pct': DEFAULT_THRESHOLD_PCT,
                }

        watch_alert_service.set_anchors(anchor_data)
        logger.info(f'[锚点策略] 更新 {len(anchor_data)} 只股票锚点')
        return []

    @staticmethod
    def _set_default_anchors(codes, prices, service):
        from app.services.watch_alert_service import DEFAULT_THRESHOLD_PCT
        anchor_data = {}
        for code in codes:
            price_info = prices.get(code) if prices else None
            if price_info and price_info.get('price'):
                anchor_data[code] = {
                    'price': price_info['price'],
                    'threshold_pct': DEFAULT_THRESHOLD_PCT,
                }
        if anchor_data:
            service.set_anchors(anchor_data)
```

- [ ] **Step 2: 提交**

```bash
git add app/strategies/watch_anchor/__init__.py
git commit -m "feat: WatchAnchorStrategy — 每日AI计算波动阈值，含降级兜底"
```

---

### Task 10: LLM 路由注册 + 配置更新

**Files:**
- Modify: `app/llm/router.py:9-21` (添加 watch_anchor 到 TASK_LAYER_MAP)
- Modify: `CLAUDE.md` (新增配置项文档)
- Modify: `README.md` (新增配置项文档)
- Modify: `.env.sample` (新增环境变量)

- [ ] **Step 1: 注册 watch_anchor 到 LLM 路由**

在 `app/llm/router.py` 的 `TASK_LAYER_MAP` 中添加一行：

```python
    'watch_anchor': LLMLayer.FLASH,
```

在 `'watch_analysis': LLMLayer.PREMIUM,` 之后添加。用 FLASH 层因为锚点阈值计算相对简单。

- [ ] **Step 2: 更新 CLAUDE.md 配置表**

在 CLAUDE.md 的「盯盘助手配置」环境变量表格中追加：

```markdown
| `WATCH_ALERT_COOLDOWN_SECONDS` | 告警信号冷却时间（秒） | `300` |
| `WATCH_ALERT_APPROACH_PCT` | 接近支撑/压力位阈值（%） | `0.5` |
| `WATCH_ALERT_DEFAULT_THRESHOLD_PCT` | 锚点默认阈值（LLM不可用时兜底） | `3.0` |
```

- [ ] **Step 3: 更新 README.md**

在 README.md 的环境变量配置表格中追加同样的三个告警配置项。

- [ ] **Step 4: 更新 .env.sample**

追加告警相关环境变量：

```env
# 盯盘告警推送
WATCH_ALERT_COOLDOWN_SECONDS=300
WATCH_ALERT_APPROACH_PCT=0.5
WATCH_ALERT_DEFAULT_THRESHOLD_PCT=3.0
```

- [ ] **Step 5: 提交**

```bash
git add app/llm/router.py CLAUDE.md README.md .env.sample
git commit -m "feat: 注册 watch_anchor LLM 路由 + 配置文档更新"
```

---

### Task 11: 验证

- [ ] **Step 1: 启动应用验证策略注册**

```bash
python -c "
from app import create_app
app = create_app()
with app.app_context():
    from app.strategies.registry import registry
    names = [s.name for s in registry.active]
    assert 'watch_alert' in names, f'watch_alert not found in {names}'
    assert 'watch_anchor' in names, f'watch_anchor not found in {names}'
    print(f'Strategies registered: {names}')
    print('All checks passed!')
"
```

- [ ] **Step 2: 验证锚点持久化**

```bash
python -c "
from app.services.watch_alert_service import watch_alert_service
watch_alert_service.set_anchors({'TEST': {'price': 100.0, 'threshold_pct': 3.0}})
import os, pickle
path = 'data/memory_cache/_watch_alert/anchors.pkl'
assert os.path.exists(path), 'Anchor file not created'
with open(path, 'rb') as f:
    data = pickle.load(f)
assert 'TEST' in data, f'TEST not in anchors: {data}'
print(f'Anchors persisted: {data}')
os.remove(path)
print('All checks passed!')
"
```

- [ ] **Step 3: 最终提交（如有修复）**

如验证中发现问题，修复后提交。
