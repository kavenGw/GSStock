# 每日简报升级 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 升级每日简报：修复卡片配色、显示收盘价而非实时价、新建 MarketStatusService、移除推送/刷新UI

**Architecture:** 新建 MarketStatusService 单例，启动时缓存各市场今日状态（是否交易日/是否已收盘/上一交易日）。BriefingService 按市场分组获取对应收盘价日期。UI 移除推送刷新，修复配色。

**Tech Stack:** Flask, TradingCalendarService, SmartCacheStrategy

---

### Task 1: 新建 MarketStatusService

**Files:**
- Create: `app/services/market_status.py`

**Step 1: 创建 MarketStatusService**

```python
"""市场状态服务 — 启动时缓存各市场今日开市状态"""
import logging
from datetime import date
from typing import Optional

from app.services.trading_calendar import TradingCalendarService
from app.services.market_session import SmartCacheStrategy

logger = logging.getLogger(__name__)

SUPPORTED_MARKETS = ['A', 'US', 'HK', 'KR', 'TW', 'JP']


class MarketStatusService:
    """市场状态服务（单例），启动时初始化，当日有效"""
    _instance = None
    _market_status: dict = {}
    _cache_date: Optional[date] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def initialize(self):
        """启动时调用，查询各市场今日状态"""
        today = date.today()
        if self._cache_date == today:
            return

        self._market_status = {}
        for market in SUPPORTED_MARKETS:
            market_now = TradingCalendarService.get_market_now(market)
            market_today = market_now.date()
            is_trading = TradingCalendarService.is_trading_day(market, market_today)
            is_closed = TradingCalendarService.is_after_close(market, market_now) if is_trading else False
            last_trading = TradingCalendarService.get_last_trading_day(market, market_today)

            self._market_status[market] = {
                'is_trading_day': is_trading,
                'is_closed': is_closed,
                'last_trading_date': last_trading,
                'market_date': market_today,
            }
            logger.info(f"[市场状态] {market}: 交易日={is_trading}, 已收盘={is_closed}, 上一交易日={last_trading}")

        self._cache_date = today
        logger.info(f"[市场状态] 初始化完成，缓存日期={today}")

    def _ensure_initialized(self):
        """确保已初始化且未跨天"""
        if self._cache_date != date.today():
            self.initialize()

    def get_price_date(self, market: str) -> date:
        """返回应显示的价格日期（最近收盘价日期）

        - 交易日且已收盘 → 今天
        - 交易日未收盘 → 上一交易日
        - 非交易日 → 上一交易日
        """
        self._ensure_initialized()
        status = self._market_status.get(market)
        if not status:
            return SmartCacheStrategy.get_effective_cache_date(market)

        if status['is_trading_day'] and status['is_closed']:
            return status['market_date']
        return status['last_trading_date']

    def should_use_realtime(self, market: str) -> bool:
        """是否应获取实时价格（盯盘助手用）"""
        self._ensure_initialized()
        status = self._market_status.get(market, {})
        return status.get('is_trading_day', False) and not status.get('is_closed', True)

    def get_status(self, market: str) -> dict:
        """获取市场完整状态"""
        self._ensure_initialized()
        return self._market_status.get(market, {})

    def get_all_status(self) -> dict:
        """获取所有市场状态"""
        self._ensure_initialized()
        return dict(self._market_status)


market_status_service = MarketStatusService()
```

**Step 2: 在 create_app 中初始化**

修改 `app/__init__.py`，在 `create_app()` 函数中 app context 内调用：

```python
from app.services.market_status import market_status_service
market_status_service.initialize()
```

添加位置：在 db 初始化之后、scheduler 之前。

**Step 3: Commit**

```bash
git add app/services/market_status.py app/__init__.py
git commit -m "feat: 新建 MarketStatusService — 启动时缓存各市场开市状态"
```

---

### Task 2: 改造 BriefingService 价格逻辑

**Files:**
- Modify: `app/services/briefing.py:99-184` (`get_stocks_basic_data`)

**Step 1: 改造 get_stocks_basic_data**

将现有的 `get_stocks_basic_data` 方法替换为按市场分组获取收盘价的逻辑：

```python
@staticmethod
def get_stocks_basic_data() -> dict:
    """获取基础股票数据（最近收盘价+投资建议）"""
    from app.services.unified_stock_data import unified_stock_data_service
    from app.services.market_status import market_status_service
    from app.services.market_session import SmartCacheStrategy, BatchCacheStrategy

    sorted_categories = sorted(STOCK_CATEGORIES.items(), key=lambda x: x[1]['order'])
    categories = [{'key': k, 'name': v['name']} for k, v in sorted_categories if k != 'other']
    stocks_by_category = {k: [] for k, _ in sorted_categories}

    # 按市场分组获取收盘价
    market_groups = {}
    for s in BRIEFING_STOCKS:
        market = s['market']
        if market not in market_groups:
            market_groups[market] = []
        market_groups[market].append(s['code'])

    prices = {}
    for market, codes in market_groups.items():
        price_date = market_status_service.get_price_date(market)
        try:
            market_prices = unified_stock_data_service.get_closing_prices(codes, cache_date=price_date)
            prices.update(market_prices)
        except Exception as e:
            logger.error(f"[简报服务.股票] 获取{market}市场价格失败: {e}", exc_info=True)
            db.session.rollback()

    from app.services.stock_meta import StockMetaService
    advice_map = {}
    try:
        meta_stocks = StockMetaService.get_meta().get('stocks', [])
        advice_map = {s['stock_code']: s['investment_advice'] for s in meta_stocks if s.get('stock_code') and s.get('investment_advice')}
    except Exception as e:
        logger.warning(f"[简报服务.股票] 获取投资建议失败: {e}")
        db.session.rollback()

    for stock_info in BRIEFING_STOCKS:
        code = stock_info['code']
        category = stock_info.get('category', 'other')
        price_data = prices.get(code)

        stock_item = {
            'code': code,
            'name': stock_info['name'],
            'market': stock_info['market'],
            'category': category,
            'close': None,
            'change_percent': None,
            'volume': None,
            'investment_advice': advice_map.get(code),
            'error': None
        }

        if price_data and price_data.get('current_price'):
            stock_item['close'] = price_data.get('current_price', 0)
            stock_item['change_percent'] = price_data.get('change_percent', 0)
            stock_item['volume'] = price_data.get('volume', 0)
        else:
            stock_item['error'] = '数据获取失败'

        stocks_by_category[category].append(stock_item)

    stocks_by_category = {k: v for k, v in stocks_by_category.items() if v}

    for category_key in stocks_by_category:
        stocks_by_category[category_key].sort(
            key=lambda x: x['change_percent'] if x['change_percent'] is not None else float('-inf'),
            reverse=True
        )

    categories = [c for c in categories if c['key'] in stocks_by_category]

    return {
        'categories': categories,
        'stocks': stocks_by_category,
    }
```

关键变化：
- 移除 `force_refresh` 参数
- 按市场分组，每组用 `market_status_service.get_price_date(market)` 作为缓存日期
- 移除 `refresh_async` 调用
- 移除 `last_update` 和 `partial` 返回字段

**Step 2: 检查 `get_closing_prices` 是否支持 `cache_date` 参数**

查看 `unified_stock_data_service.get_closing_prices()` 签名，确认是否接受 `cache_date` 参数。如果不支持，需要适配（在实现时确认）。

**Step 3: 更新路由**

修改 `app/routes/briefing.py:17-26`，移除 force 参数传递：

```python
@briefing_bp.route('/api/stocks')
def get_stocks():
    """基础股票数据（收盘价+投资建议）"""
    try:
        data = BriefingService.get_stocks_basic_data()
        return jsonify(data)
    except Exception as e:
        logger.error(f"[简报.股票数据] 获取失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
```

**Step 4: Commit**

```bash
git add app/services/briefing.py app/routes/briefing.py
git commit -m "refactor: 简报股票数据改为按市场获取收盘价"
```

---

### Task 3: 移除推送/刷新 UI 和后端端点

**Files:**
- Modify: `app/templates/briefing.html:313-319` (移除按钮)
- Modify: `app/static/js/briefing.js` (移除 refresh/push 方法和 lastUpdate 更新)
- Modify: `app/routes/briefing.py:130-167` (移除通知端点)

**Step 1: 移除 briefing.html 顶部按钮区域**

删除第 313-319 行附近的 lastUpdate span、推送按钮、刷新按钮。保留页面标题和副标题导航。

**Step 2: 移除 briefing.js 中的相关代码**

- 删除 `refresh()` 方法（约 266-293 行）
- 删除 `pushReport()` 方法（约 297-329 行）
- 删除 `loadStocks` 中更新 `lastUpdate` 的代码（约 127-128 行）

**Step 3: 移除路由端点**

从 `app/routes/briefing.py` 删除：
- `/api/notification/status` 端点（130-133 行）
- `/api/notification/push` 端点（136-147 行）
- `/api/notification/test` 端点（150-167 行）
- 移除顶部 `from app.services.notification import NotificationService`

**Step 4: Commit**

```bash
git add app/templates/briefing.html app/static/js/briefing.js app/routes/briefing.py
git commit -m "refactor: 移除每日简报推送/刷新功能"
```

---

### Task 4: 修复卡片配色

**Files:**
- Modify: `app/templates/briefing.html:58-66` (CSS)

**Step 1: 更新 CSS 样式**

修改 briefing.html 中的 `<style>` 部分：

```css
/* 核心数据 */
.bc-price {
    font-size: 1.1rem;
    font-weight: 600;
    line-height: 1.2;
    color: rgba(255, 255, 255, 0.85);
}
.bc-change {
    font-size: 0.95rem;
    font-weight: 600;
}

/* 颜色 — 加深对比度 */
.text-up { color: #ff6b6b !important; }
.text-down { color: #51cf66 !important; }
.text-flat { color: #868e96 !important; }
```

**Step 2: Commit**

```bash
git add app/templates/briefing.html
git commit -m "fix: 简报卡片股价配色 — 淡白色价格 + 加深涨跌色"
```
