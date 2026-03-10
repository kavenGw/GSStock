# 九转信号分钟级走势支持

## 概述

在盯盘助手中为九转信号（TD Sequential）增加1分钟级别的计算和图表标注，与现有日线信号并存。

## 现状

- TD Sequential 仅基于60日日线OHLC数据计算
- 分时数据（1分钟K线）已通过 `get_intraday_data()` 获取，但未用于TD计算
- 图表左下角显示日线TD状态标签，卡片头部显示badge

## 设计

### 后端

**TDSequentialService 调整**：
- history 条目支持 `time` 字段（分钟级）和 `date` 字段（日线级）
- history 条目增加 `price` 字段（对应时间点的 close 价），供前端定位 markPoint Y坐标

**chart-data 接口**（`watch.py`）：
- `period=intraday` 时，对1分钟OHLC数据调用 `TDSequentialService.calculate()`
- 返回新字段 `td_sequential_intraday`，格式同日线但 history 用 `time` 而非 `date`
- 现有 `td_sequential`（日线）保持不变，两者并存于响应中

**响应格式**：
```json
{
  "td_sequential": { "direction": "buy", "count": 7, "completed": false, "history": [...] },
  "td_sequential_intraday": {
    "direction": "sell",
    "count": 3,
    "completed": false,
    "history": [
      {"time": "09:35", "direction": "sell", "count": 1, "price": 1802.5},
      {"time": "09:42", "direction": "sell", "count": 2, "price": 1805.0}
    ]
  }
}
```

### 前端图表标注

**ECharts markPoint 渲染**：
- 将 `td_sequential_intraday.history` 中每个计数点渲染为数字标注
- coord: `[time, price]`，数字为 count（1-9）
- 买入：绿色（#16a34a），标在线下方
- 卖出：红色（#dc2626），标在线上方
- 计数 ≥7 时数字加粗
- 计数 = 9 时加背景圆圈，更醒目

**Badge**：不变，仍只显示日线信号。

### 缓存与刷新

- 分钟级TD信号不单独缓存，每次 chart-data 请求时实时计算
- 前端 `WatchCache` 新增 `tdSequentialIntraday` 字段，随 sessionStorage 持久化
- 刷新跟随现有60秒 chart-data 周期，无额外定时器

## 不涉及的变更

- 无新API端点
- 无新数据库表或缓存表
- 无新配置项或环境变量
- 日线TD信号逻辑不变
