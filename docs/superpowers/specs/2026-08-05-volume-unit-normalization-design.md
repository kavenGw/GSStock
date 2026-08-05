# Volume 单位归一集中化 — 设计文档

日期：2026-08-05
状态：待实施

## 背景

2026-08-05 16:30 的 `volume_alert` 推送出现量纲错误，且不止一只：

```
🟡 [volume_alert] 京东方A(000725) 放量43%
今日 2,506,023,803 > 昨日 1,753,473,070 | 涨跌 +6.04%
```

契约规定 A 股 volume 单位为「手」，京东方 A 当日真实成交 25,060,238 手 / 17,534,731 手（昨），推送值是其 100 倍——即「股」口径未归一。

## 根因

`app/services/unified_stock_data.py:2048`（`_fetch_trend_from_sina`）：

```python
'volume': int(row['volume']) if row.get('volume') else 0
```

新浪 `stock_zh_a_daily` 原生返回「股」，此处缺 `// 100`。实测 000725：

| 日期 | 新浪（股） | 东财/腾讯（手） | 推送显示 |
|---|---|---|---|
| 2026-08-04 | 1,753,473,070 | 17,534,731 | 1,753,473,070 ❌ |
| 2026-08-05 | 2,506,023,803 | 25,060,238 | 2,506,023,803 ❌ |

同文件的增量路径 `_fetch_incremental_trend_data`（1786 行）与新浪实时快照（845 行）都有 `// 100`，唯独批量走势路径漏掉。

**同类缺陷（第二处）**：yfinance A 股兜底路径同样返回「股」而未归一，实测 `000725.SZ` 的 `Volume` 与新浪逐日相等（2,506,023,803）。涉及 `_fetch_a_share_prices.fetch_from_yfinance`（900）、`_fetch_trend_from_yfinance`（2251）、`_parse_yf_dataframe`（2383）、`_fetch_incremental_trend_data` 的 yfinance 分支（1869）、`_fetch_realtime_prices.fetch_single`（696）。

**为何间歇性暴露**：腾讯是所有 A 股取数路径的首选源，新浪 / yfinance 仅在腾讯失败或熔断时启用。漏归一的分支平时不执行，一旦降级就是整批股票同时 100 倍偏差——与本次「不止一个」的现象吻合。

**本次百分比为何仍正确**：今日与昨日 bar 同源（都走新浪），比值不受量纲影响，43% 是对的，错的只是绝对值。真正的高危场景是**跨源混用**——`volume_alert` 用 realtime（腾讯，手）合成今日 bar、用 OHLC（新浪，股）取昨日时，比值差 100 倍，会被策略里 `ratio > 30` 的 sanity gate **静默 `continue`**，表现为漏报而非错报，只在日志留痕。

**为何要做结构性修复**：这是同类 bug 第三次（前两次见 commit `13edcde`、`VOLUME_UNIT_SCHEMA_VERSION` 1→2 那次）。单位事实目前散落在约 20 个 fetch 落点的行内注释里，注释是唯一约束，新增数据源或改写解析时必然再次踩中。

## 设计

### 一、单点归一 helper

在 `unified_stock_data.py` 顶部、紧邻 `VOLUME_UNIT_SCHEMA_VERSION` 处新增：

```python
# 各数据源 volume 原生单位（'lots'=手 / 'shares'=股）
VOLUME_SOURCE_UNITS = {
    'tencent_qt': 'lots',           # A 股 qt.gtimg.cn [6]（港股 r_hk 为股，由 market 分支处理）
    'tencent_fqkline': 'lots',
    'tencent_mkline': 'lots',
    'sina_spot': 'shares',
    'sina_daily': 'shares',
    'eastmoney_ak_hist': 'lots',    # ak.stock_zh_a_hist
    'eastmoney_push2his': 'lots',
    'eastmoney_spot': 'lots',       # ak.stock_zh_a_spot_em
    'eastmoney_hist_min': 'lots',
    'eastmoney_intraday': 'lots',   # ak.stock_intraday_em 的「手数」列
    'etf_fund_hist': 'lots',        # ak.fund_etf_hist_em
    'yfinance': 'shares',
}


def _normalize_volume(raw, source: str, market: str):
    """归一到契约单位：A 股=手，港股/美股=股。

    source 未登记时直接抛 KeyError —— 宁可启动即失败，也不静默按错误单位入库。
    raw 为 None / 空值时返回 None，由调用点决定填 0 还是 None（保持各落点现有语义）。
    """
```

行为规则：

- `market == 'A'` 且源单位为 `shares` → `// 100`
- `market == 'A'` 且源单位为 `lots` → 原样
- `market != 'A'`（HK / US）→ **一律原样**。现有契约就是股：腾讯 `r_hk` 返回股、yfinance 港美返回股，均无需转换
- `source` 不在映射表中 → `KeyError`（防止新增源静默走默认分支）
- `raw` 为 `None` / 空字符串 / `NaN` → 返回 `None`

单位契约本身不变，只是把「源单位是什么」这一事实从注释提升为可执行的数据。

### 二、全部落点改为显式声明源

`unified_stock_data.py` 中约 20 处 `'volume': ...` 表达式统一改写为 `'volume': _normalize_volume(raw, '<source_key>', market)`。落点与源的对应关系：

| 行 | 所在函数 | source key |
|---|---|---|
| 696 | `_fetch_realtime_prices.fetch_single` | `yfinance` |
| 797 | `_fetch_a_share_prices.fetch_from_eastmoney` | `eastmoney_spot` |
| 845 | `_fetch_a_share_prices.fetch_from_sina` | `sina_spot` |
| 900 | `_fetch_a_share_prices.fetch_from_yfinance` | `yfinance` ← 缺陷 |
| 999 | `_fetch_from_tencent` | `tencent_qt` |
| 1411 | `_fetch_intraday_a_share_tencent` | `tencent_mkline` |
| 1441 | `_fetch_intraday_a_share_hist` | `eastmoney_hist_min` |
| 1481 | `_fetch_intraday_a_share_tick` | `eastmoney_intraday` |
| 1510 | `_fetch_intraday_yfinance` | `yfinance` |
| 1721 | `_fetch_incremental_trend_data`（ETF 分支） | `etf_fund_hist` |
| 1759 | `_fetch_incremental_trend_data.fetch_from_eastmoney` | `eastmoney_ak_hist` |
| 1786 | `_fetch_incremental_trend_data.fetch_from_sina` | `sina_daily` |
| 1814 | `_fetch_incremental_trend_data.fetch_from_tencent` | `tencent_fqkline` |
| 1869 | `_fetch_incremental_trend_data`（yfinance 分支） | `yfinance` ← 缺陷 |
| 1921 | `_fetch_trend_from_etf` | `etf_fund_hist` |
| 1988 | `_fetch_trend_from_eastmoney` | `eastmoney_ak_hist` |
| 2048 | `_fetch_trend_from_sina` | `sina_daily` ← 缺陷（本次事故） |
| 2120 | `_fetch_trend_from_tencent` | `tencent_fqkline` |
| 2186 | `_fetch_trend_from_eastmoney_direct` | `eastmoney_push2his` |
| 2251 | `_fetch_trend_from_yfinance` | `yfinance` ← 缺陷 |
| 2383 | `_parse_yf_dataframe` | `yfinance` ← 缺陷 |

（行号为实施前快照，实施时以函数名定位。）

各落点原有的单位说明注释一并删除——单位事实已收进映射表，注释不再是唯一约束，留着反而会与映射表产生二源分歧。

**附带核查项**：`app/services/data_source_providers.py:89`（`get_realtime_price`）与 `:123`（`get_historical_data`）的 yfinance provider 存在同样形态。实施时先确认这两个方法是否会被 A 股代码调用；若会，同样接入归一层；若只服务美股，在方法 docstring 注明「仅美股，volume 为股」并留在原地。

### 三、缓存版本 bump

`VOLUME_UNIT_SCHEMA_VERSION` 由 `3` 改为 `4`。已有的 `_check_cache_schema_version` / `_clear_volume_related_cache` 机制会在启动时清理内存 pkl 与 `UnifiedStockCache` 中 `ohlc_*` / `price` / `index` 行，冲掉本次已被污染的股口径缓存数据。

### 四、测试

改造 `tests/test_volume_alert_unit_consistency.py`：

1. **表驱动单测**：`_normalize_volume` × 全部 12 个 source key × 三市场（A / HK / US），断言归一结果；覆盖 `None` / 空值 / `NaN` 输入；断言未登记 source 抛 `KeyError`。
2. **落点覆盖静态断言**：用 `ast` 解析 `unified_stock_data.py`，收集所有 `_normalize_volume(...)` 调用的第二个实参字面量，断言① 全部在 `VOLUME_SOURCE_UNITS` 中；② 文件内不再存在直接给 `'volume'` 赋 `int(...)` 而绕过 helper 的字典项。这条是防回归的关键——它保证下次新增数据源必须登记单位。
3. **跨源真值一致性**（联网）：同一 A 股代码同一交易日，腾讯 / 新浪 / 东财 / yfinance 四源归一后互差 < 1%。标 `@pytest.mark.network`，默认跳过，作为排查工具保留。

## 明确不做

- 运行时量纲哨兵（`volume × 100 × close` 与成交额交叉验证后告警）
- 把 `volume_alert` 中 `ratio > 30` 的静默 `continue` 改为推送错误告警

这两项能把「静默漏报」变成「显式可见」，价值独立于本次修复，留后续 spec。

## 实施约定

改动落在 `app/` 代码，按 `dev-environment.md` 分支策略需开独立 git worktree 隔离，不在 main 直接改。

验收：`PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 rtk python -m pytest tests/ -v` 全绿；重启应用确认启动日志出现 volume 缓存清理记录；下一个交易日 16:30 的 `volume_alert` 推送量级落在「手」口径（京东方 A 量级应为千万级而非十亿级）。
