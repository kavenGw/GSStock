# 盯盘分时图最高/最低点标注 + 突破通知 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在盯盘分时图上用红/绿实心圆点标注当日最高/最低价，并在价格突破已确认的盘中前高/前低时通过 Slack 推送通知。

**Architecture:** 前端纯 JS 计算 high/low 并用 ECharts markPoint 渲染。后端在 `WatchAlertService` 中新增 `_check_intraday_breakthrough()` 方法，维护 `_intraday_extremes` 状态，10 分钟确认窗口后检测突破，作为第 5 类信号融入 watch-alert-push 架构。

**Tech Stack:** ECharts markPoint（前端），Flask + APScheduler（后端），Slack Webhook（推送）

**Spec:** `docs/superpowers/specs/2026-03-10-watch-intraday-highlow-design.md`

---

## Chunk 1: 前端图表标注

### Task 1: 在 renderChart() 中添加最高/最低点 markPoint

**Files:**
- Modify: `app/static/js/watch.js:596-727`（`renderChart()` 方法）

**背景：** `renderChart(code)` 方法中，分时数据在 `this.chartData[code]`（数组，每项含 `time` 和 `close`）。时间轴在 `fullAxis` 数组中，价格在 `prices` 数组中（与 fullAxis 一一对应，gap 用 null 填充）。现有 TD 九转标注通过 `_buildTDIntradayMarkPoints(code, fullAxis)` 返回 markPoint data 数组。

- [ ] **Step 1: 新增 `_buildHighLowMarkPoints(prices, fullAxis)` 方法**

在 `watch.js` 的 `_buildTDIntradayMarkPoints` 方法之后（约 line 801），添加新方法：

```javascript
    _buildHighLowMarkPoints(prices, fullAxis) {
        const markData = [];
        let highVal = -Infinity, lowVal = Infinity;
        let highIdx = -1, lowIdx = -1;

        for (let i = 0; i < prices.length; i++) {
            const p = prices[i];
            if (p == null) continue;
            if (p > highVal) { highVal = p; highIdx = i; }
            if (p < lowVal) { lowVal = p; lowIdx = i; }
        }

        if (highIdx === -1) return markData;

        const fmt = v => v >= 1000 ? v.toFixed(0) : v.toFixed(2);

        markData.push({
            coord: [highIdx, highVal],
            symbol: 'circle',
            symbolSize: 8,
            itemStyle: { color: '#dc3545' },
            label: {
                show: true,
                formatter: fmt(highVal),
                position: 'top',
                color: '#dc3545',
                fontSize: 10,
                fontWeight: 'bold',
                offset: [0, -2],
            },
        });

        if (lowIdx !== highIdx) {
            markData.push({
                coord: [lowIdx, lowVal],
                symbol: 'circle',
                symbolSize: 8,
                itemStyle: { color: '#28a745' },
                label: {
                    show: true,
                    formatter: fmt(lowVal),
                    position: 'bottom',
                    color: '#28a745',
                    fontSize: 10,
                    fontWeight: 'bold',
                    offset: [0, 2],
                },
            });
        }

        return markData;
    },
```

- [ ] **Step 2: 在 renderChart() 中合并 high/low markPoint 到 TD markPoint**

在 `renderChart()` 方法中，找到初始化路径（约 line 653）：

```javascript
        const tdMarkPoints = this._buildTDIntradayMarkPoints(code, fullAxis);
```

在其后添加：

```javascript
        const hlMarkPoints = this._buildHighLowMarkPoints(prices, fullAxis);
        const allMarkPoints = [...tdMarkPoints, ...hlMarkPoints];
```

然后将 `seriesList` 中的 `markPoint` 引用从 `tdMarkPoints` 改为 `allMarkPoints`：

```javascript
            markPoint: allMarkPoints.length > 0 ? { silent: true, data: allMarkPoints } : undefined,
```

- [ ] **Step 3: 在 renderChart() 更新路径中同样合并**

在 `renderChart()` 的更新路径（约 line 629-634），找到：

```javascript
            const tdMark = this._buildTDIntradayMarkPoints(code, fullAxis);
```

在其后添加：

```javascript
            const hlMark = this._buildHighLowMarkPoints(prices, fullAxis);
            const allMark = [...tdMark, ...hlMark];
```

然后将 `seriesUpdate` 中的 `markPoint` 引用从 `tdMark` 改为 `allMark`：

```javascript
                markPoint: allMark.length > 0 ? { silent: true, data: allMark } : { data: [] },
```

- [ ] **Step 4: 提交**

```bash
git add app/static/js/watch.js
git commit -m "feat: 盯盘分时图显示当日最高/最低价红绿标注点"
```

---

## Chunk 2: 后端突破检测

### Task 2: 在 WatchAlertService 中添加突破检测方法

**Files:**
- Modify: `app/services/watch_alert_service.py`（如果已存在）
- Create: `app/services/watch_alert_service.py`（如果尚未创建）

**背景：** `watch-alert-push` 设计文档规划了 `WatchAlertService`，包含 4 类信号检测。该服务尚未实现。本 Task 创建服务骨架 + 突破检测方法。后续 watch-alert-push 计划执行时会扩展此文件添加其他 4 类信号。

**关键依赖：**
- `app/strategies/base.py` — `Signal` dataclass（`strategy, priority, title, detail, data, timestamp`）
- `app/services/watch_service.py` — `WatchService.get_watch_codes()` 返回 `list[str]`
- `UnifiedStockDataService().get_realtime_prices(codes)` — 返回 `{code: {'current_price': float, ...}}`
- `WatchList` 模型有 `stock_name` 字段

- [ ] **Step 1: 创建 WatchAlertService 骨架 + 突破检测**

创建 `app/services/watch_alert_service.py`：

```python
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
        """交易日切换时重置日内状态"""
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
        """检测盘中前高/前低突破"""
        signals = []
        now = datetime.now()

        for code, data in prices.items():
            curr = data.get('current_price')
            if curr is None:
                continue

            ext = self._intraday_extremes.get(code)
            if ext is None:
                self._intraday_extremes[code] = {
                    'high': curr, 'high_time': now, 'high_confirmed': False,
                    'low': curr, 'low_time': now, 'low_confirmed': False,
                }
                continue

            name = name_map.get(code, code)

            # 确认逻辑：10 分钟未被突破则确认
            if not ext['high_confirmed'] and (now - ext['high_time']).total_seconds() >= BREAKTHROUGH_CONFIRM_MINUTES * 60:
                ext['high_confirmed'] = True
            if not ext['low_confirmed'] and (now - ext['low_time']).total_seconds() >= BREAKTHROUGH_CONFIRM_MINUTES * 60:
                ext['low_confirmed'] = True

            # 突破前高
            if curr > ext['high']:
                if ext['high_confirmed']:
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
                ext['high'] = curr
                ext['high_time'] = now
                ext['high_confirmed'] = False

            # 跌破前低
            if curr < ext['low']:
                if ext['low_confirmed']:
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
                ext['low'] = curr
                ext['low_time'] = now
                ext['low_confirmed'] = False

        return signals
```

- [ ] **Step 2: 提交**

```bash
git add app/services/watch_alert_service.py
git commit -m "feat: WatchAlertService 骨架 + 盘中前高前低突破检测"
```

---

### Task 3: 创建 WatchAlertStrategy 调度策略

**Files:**
- Create: `app/strategies/watch_alert/__init__.py`

**背景：** 策略自动发现机制（`StrategyRegistry.discover()`）扫描 `app/strategies/` 下所有子目录的 `__init__.py`，找到继承 `Strategy` 的类并实例化。`schedule` 属性支持 cron 表达式（由 APScheduler 调度）。对于 interval 类型调度，使用 `interval_minutes` 属性。

- [ ] **Step 1: 检查现有策略的 interval 调度模式**

查看 `app/scheduler/` 中如何处理 `interval_minutes` 属性，确认 `interval_minutes:1` 的写法。

- [ ] **Step 2: 创建 watch_alert 策略目录和文件**

创建 `app/strategies/watch_alert/__init__.py`：

```python
"""盯盘推送告警策略 — 每分钟检测价格信号"""
import logging
from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)


class WatchAlertStrategy(Strategy):
    name = "watch_alert"
    description = "盯盘告警推送（每分钟检测）"
    schedule = "interval_minutes:1"
    needs_llm = False

    def scan(self) -> list[Signal]:
        from app.models.watch_list import WatchList
        from app.services.trading_calendar import TradingCalendarService
        from app.services.watch_service import WatchService
        from app.services.watch_alert_service import WatchAlertService

        codes = WatchService.get_watch_codes()
        if not codes:
            return []

        markets = WatchService.get_watched_markets()
        has_active = any(TradingCalendarService.is_market_open(m) for m in markets)
        if not has_active:
            return []

        # 获取实时价格
        from app.services.unified_stock_data import UnifiedStockDataService
        data_service = UnifiedStockDataService()
        prices = data_service.get_realtime_prices(codes)

        # 构建 name_map
        items = WatchList.query.filter(WatchList.stock_code.in_(codes)).all()
        name_map = {w.stock_code: w.stock_name for w in items}

        service = WatchAlertService()
        signals = service.check_alerts(prices, name_map)

        if signals:
            logger.info(f'[盯盘告警] 产出 {len(signals)} 个信号')
        return signals
```

- [ ] **Step 3: 提交**

```bash
git add app/strategies/watch_alert/__init__.py
git commit -m "feat: WatchAlertStrategy 每分钟调度盯盘突破检测"
```
