# 每日简报升级设计

## 目标

1. 修复卡片股价文本配色不清晰
2. 简报显示最近收盘价而非实时价
3. 新建 MarketStatusService 统一管理市场开市状态
4. 移除顶部更新时间、推送、刷新按钮

## 1. MarketStatusService

新建 `app/services/market_status.py`，单例模式。

**启动时初始化**：查询各市场（A/US/HK/KR/TW/JP）今日状态并缓存，当日有效。

**缓存结构**：
```python
_market_status = {
    'A': {'is_trading_day': bool, 'is_closed': bool, 'last_trading_date': date},
    'US': {...},
    ...
}
```

**核心方法**：
- `initialize()` — 启动时调用
- `get_price_date(market) -> date` — 返回应显示的价格日期
- `should_use_realtime(market) -> bool` — 盯盘助手用

**价格日期逻辑**：
- 交易日且已收盘 → today
- 交易日未收盘 → 上一交易日
- 非交易日 → 上一交易日

## 2. BriefingService 价格逻辑

`get_stocks_basic_data()` 改造：
- 按市场分组股票
- 每组用 `MarketStatusService.get_price_date(market)` 获取缓存日期
- 只取收盘价，移除实时价格获取和 refresh_async
- 移除 `force_refresh` 参数

## 3. UI 改动

**卡片配色**：
- 股价：`rgba(255,255,255,0.85)` 淡白色 + font-weight 600
- 涨幅：`#ff6b6b` 加深红
- 跌幅：`#51cf66` 加深绿

**移除**：
- 顶部更新时间显示
- 推送按钮
- 刷新按钮
- 对应 JS 逻辑和后端端点（`/api/notification/push`、`/api/notification/status`）
