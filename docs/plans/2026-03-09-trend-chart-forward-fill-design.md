# 走势看板数据线 Forward-Fill 设计

## 问题

走势看板混合显示不同市场（A股、美股、港股）股票时，各市场休市日不同，某些股票在特定日期无数据，前端用 `null` 填充导致 Chart.js 断线。

## 方案

在 `FuturesService` 的 `get_trend_data()` 和 `get_custom_trend_data()` 中，聚合数据后返回前执行 forward-fill。

### 算法

1. 收集所有股票交易日期并集，排序得到完整日期轴
2. 逐股票遍历，对缺失日期用最近交易日数据填充：
   - `open/high/low/close`：复制上一交易日 `close`
   - `change_pct`：保持上一交易日累计涨跌幅
   - `volume`：设为 0
3. 边界：股票在日期轴最前面缺数据时不填充

### 实现位置

`app/services/futures.py` 新增 `_forward_fill_missing_dates(results)` 私有方法，在两处返回前调用：
- `get_trend_data()` — 期货/重金属走势
- `get_custom_trend_data()` — 自定义分类走势

### 数据流

```
之前: 各股票数据(有缺口) → 前端 null → Chart.js 断线
之后: 各股票数据(有缺口) → _forward_fill → 完整数据 → 连续线条
```
