# volume_alert 扩展至港股 — 设计文档

日期：2026-08-06
状态：待实施

## 背景

2026-08-06 16:30 的 `volume_alert` 推送只出现长电科技(600584)一条，用户发现盯盘池里的泡泡玛特(9992.HK)从未出现在成交量异动推送中。

排查结论：**不是数据故障，是策略设计上就没覆盖港股。**

`app/strategies/volume_alert/__init__.py`：

```python
a_codes = [c for c in codes if MarketIdentifier.is_a_share(c)]
```

盯盘池 `WATCH_CODES` 共 21 只：A 股 8 只 / 港股 12 只 / 韩股 1 只（无美股）。这行把占比过半的港股全部过滤掉。泡泡玛特 `9992.HK` 在 `WATCH_CODES` 中 `market='HK'`，因此从未进入过扫描。

## 实测数据（2026-08-06 收盘后）

联网探针验证港股数据链路完好：

| 代码 | 名称 | 昨日 volume | 今日 volume | 变化 |
|---|---|---|---|---|
| 9992.HK | 泡泡玛特 | 6,638,049 | 19,505,349 | **+194%** |
| 0100.HK | MiniMax | 7,935,246 | 29,506,745 | **+272%**（涨 17.1%） |
| 0700.HK | 腾讯控股 | 25,662,478 | 21,802,077 | -15%（不触发） |
| 600584 | 长电科技 | 1,761,053 | 2,359,071 | +34%（已推送） |

关键观察：

- 港股 OHLC 今日 bar 当日 16:30 已出，无需走 realtime 合成分支
- realtime volume 与 OHLC 高度吻合（9992.HK：19,505,149 vs 19,505,349），**同源同单位，不存在跨源量纲风险**
- 最大比值 4.6x（0100.HK），落在现有 `ratio > 30` sanity gate 内
- realtime 的 `price` 字段为 `None`，但策略只用 `volume` 与 `change_percent`（有值），不受影响
- **今日本应推出两条港股信号，含用户所指的泡泡玛特**

同时发现：港股 trend 返回的 `stock_name` 是代码本身（`9992.HK`）而非中文名，直接开闸会产出 `9992.HK(9992.HK) 放量194%` 这样的标题。

## 设计

### 一、按市场分组扫描

`_do_scan` 中的市场过滤与交易日判断合并为逐市场处理：

```python
targets = {}          # {'A': [...], 'HK': [...]}
for c in WatchService.get_watch_codes():
    m = MarketIdentifier.identify(c)
    if m in ('A', 'HK') and TradingCalendarService.is_trading_day(m, date.today()):
        targets.setdefault(m, []).append(c)
```

这同时修掉一个隐性缺陷：现有代码开头是

```python
if not TradingCalendarService.is_trading_day('A', date.today()):
    return []
```

**A 股休市但港股开市的日子（复活节、佛诞、A 股独有长假等），港股会被一并砍掉。** 分组后各市场独立生效。

取数仍是一次 `get_trend_data` / `get_realtime_prices` 批量调用（把各市场 code 合并成一个列表传入），`UnifiedStockDataService` 内部已按市场路由数据源，无需策略层拆分。

`retry_codes` 分支不变：重试时传入的已是筛选过的具体代码，跳过上述分组逻辑直接使用。

### 二、排程

cron 维持 `30 16 * * 1-5`。A 股 15:00 收盘、港股 16:00 收盘 + 16:10 收市竞价结束，16:30 对两个市场都足够，不引入第二个 job。

### 三、单位标注

契约单位：A 股为「手」，港股为「股」（`VOLUME_SOURCE_UNITS` 归一层规定 `market != 'A'` 一律原样）。两市场混在同一 Slack 频道且量级差 100 倍，裸数字无法分辨口径。

`VOLUME_SOURCE_UNITS` 描述的是**源单位**，展示需要的是**契约单位**，是两个概念。为避免二源分歧，在 `app/services/unified_stock_data.py` 归一层旁边新增并导出：

```python
# 各市场 volume 契约单位（展示用中文标签）
CONTRACT_VOLUME_UNIT = {'A': '手', 'HK': '股', 'US': '股'}
```

策略 import 后拼接 detail：

```
今日 {today_vol:,.0f} {unit} {vol_cmp} 昨日 {prev_vol:,.0f} {unit} | 涨跌 {price_str}
```

推送效果：

```
🟡 [volume_alert] 长电科技(600584) 放量34%
今日 2,359,071 手 > 昨日 1,761,053 手 | 涨跌 +10.00%

🟡 [volume_alert] 泡泡玛特(9992.HK) 放量194%
今日 19,505,349 股 > 昨日 6,638,049 股 | 涨跌 -2.54%
```

单位事实仍只有 `unified_stock_data.py` 一处定义。

### 四、名称兜底

从 `WatchService.get_watch_list()` 构建 `{code: name}` 映射，取名优先级：

```
WATCH_CODES 中文名 → trend 的 stock_name → code
```

A 股行为不变（trend 本就返回中文名，但映射表命中优先，结果一致）。

### 五、阈值与 sanity gate

`VOLUME_CHANGE_THRESHOLD = 0.3` 港股与 A 股共用，不引入分市场参数。港股仅 12 只且多为大盘（腾讯、小米、泡泡玛特等），实测今日仅 2 只超线，噪音可控。跑一段时间后按实际推送频率再决定是否分市场调参。

两道 sanity gate 保持不变：

- `ratio > 30 or ratio < 1/30` → 跳过（量纲错乱/脏数据）
- 今日量 < 近 5 日均量 1% → 跳过（今日 bar 残缺）

实测港股最大比值 4.6x 落在闸内，无需为港股放宽。

### 六、重试

`_schedule_retry` 按 code 重试，与市场无关，逻辑不动。原先「A 股非交易日 → `_do_scan` 提前 return → 港股重试也失效」的问题由第一节的分组自然解决。

`missing_codes` 的错误推送文案不变。

### 七、测试

扩展 `tests/test_volume_alert_unit_consistency.py`，全部走 mock（不联网）：

1. **港股信号产出**：mock trend + realtime 返回港股数据，断言产出 Signal，且 detail 单位后缀为「股」
2. **A 股单位不回归**：同一批断言 A 股 detail 后缀为「手」
3. **名称兜底**：mock trend 的 `stock_name` 返回 `'9992.HK'`，断言 Signal title 为 `泡泡玛特(9992.HK) ...`
4. **交易日分歧**：mock `is_trading_day('A')=False` / `is_trading_day('HK')=True`，断言港股信号仍产出、A 股代码未进入取数列表
5. **两市场均休市**：断言返回 `[]` 且不发起取数调用

## 明确不做

- 美股 / 韩股扩展 —— 需独立 cron（美股收盘为北京时间凌晨）+ 夏令时与半日市处理，复杂度独立；且当前 `WATCH_CODES` 无美股，韩股仅 1 只，收益有限
- 分市场阈值参数化
- 把 `ratio > 30` 的静默 `continue` 改为显式错误推送（沿用 `2026-08-05-volume-unit-normalization-design.md` 的同名待办）

## 实施约定

改动落在 `app/` 代码，按 `dev-environment.md` 分支策略需开独立 git worktree 隔离，不在 main 直接改。

验收：

- `PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ -v` 全绿
- 下一个 A+港股共同交易日 16:30 的推送中出现港股条目，且 detail 单位后缀正确、标题为中文名
