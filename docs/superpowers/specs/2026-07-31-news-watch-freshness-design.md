# news_watch 价格新鲜度闸门设计

日期：2026-07-31
原则：**宁愿不推送，也不要推送非实时的数据。**

## 背景与问题

`news_watch` 频道的盘中推送链路存在三个"非实时数据"口子（用户确认的痛点为 ① 与 ③）：

| # | 路径 | 现状缺口 |
|---|------|---------|
| ① | `watch_alert` 告警（每分钟） | 只过滤 `_is_degraded` 降级价；缓存 TTL 内（盘中 30 分钟）的旧价不算降级，preload 挂掉/退避后最长可拿 30 分钟前的价继续发告警 |
| ② | `watch_realtime` AI 实时分析（每 15 分钟） | `force_refresh=True` 取价失败时降级返回过期缓存（甚至昨日价），代码只查 `not current_price` 不查新鲜度，AI 基于旧数据生成分析并推送 |
| ③ | `push_realtime_analysis` 消息中的"现价" | 推送前重新取价但不带 force_refresh（30 分钟 TTL），显示的现价可能滞后或为降级旧价，无任何检查 |

**范围外**：每日简报盯盘部分（7d/30d 日级分析，本来就非实时语义）、前端 `/watch/prices`（页面自带 stale 标记）。

## 需求决策（用户已确认）

1. **新鲜度阈值 = 2 倍 preload 刷新周期**：A 股 >2 分钟、非 A（美/港/韩等）>6 分钟视为旧价。容忍一次 preload 失败，连续失败即静默。
2. **旧价被拦只记日志**，不向频道推降级提醒。
3. **AI 实时分析一并加门**：旧价的股直接跳过分析（省 LLM 调用），不只拦推送层。

## 方案（已选 A：盯盘域集中闸门）

新鲜度是盯盘域的策略要求，不是数据层的——收盘后 8 小时缓存 TTL 是 by design 的"旧"，估值页/简报等场景不应受影响。故闸门放盯盘域，`UnifiedStockDataService` 语义不动。

已否决：
- 方案 B（只在推送层加闸）：AI 烧完 token 才被拦；告警检测器基于旧价跑完会污染 `_fired` 去重状态。
- 方案 C（数据层按年龄自动打降级标记）：爆炸半径大，误伤非盘中消费方。

## 组件：`app/services/price_freshness.py`

纯函数、无状态、不依赖 DB：

```python
FRESHNESS_MULTIPLIER = 2
PRELOAD_INTERVAL_MINUTES = {'A': 1}   # 其余市场默认 3（对应 watch_preload 的 NON_A_REFRESH_EVERY）
DEFAULT_INTERVAL_MINUTES = 3

def max_age_seconds(market: str) -> int:
    # A → 120s；US/HK/KR/TW/JP 等一律 → 360s

def is_fresh(price_data: dict, market: str, now: datetime = None) -> bool:
    # 判定顺序（fail-closed，任一不满足即 False）：
    # 1. _is_degraded 为真 → False
    # 2. last_fetch_time 缺失或解析失败 → False
    # 3. now - last_fetch_time > max_age_seconds(market) → False

def filter_fresh_prices(prices: dict, market_map: dict, now: datetime = None) -> dict:
    # 批量过滤；market_map 缺失的 code 按非 A 默认 6min 兜底
    # 返回只含新鲜价的子集；被拦的由调用方记日志
```

要点：
- 判定依据是 `last_fetch_time`（**抓取时间**，价格 dict 自带的 ISO 时间戳），与 `datetime.now()` 同为本机 naive local time，直接比较、无时区换算。
- `_is_degraded` 检查保留：与超龄是两种独立的不推理由，双检查防御性更强。
- 阈值写死为常量，不做环境变量（YAGNI）。

## 三个接入点

### ① `watch_alert._filter_fresh`（`app/strategies/watch_alert/__init__.py:88`）

现有"只查 `_is_degraded`"改为调用 `filter_fresh_prices(prices, market_map)`；`market_map` 在 `scan()` 已有，透传即可。被拦股票沿用现有 `logger.info` 跳过日志并附数据年龄。效果：preload 挂掉/退避期间告警在 2 分钟后自动静默，恢复刷新后自动复活，无新增状态。

### ② `WatchAnalysisService.analyze_stocks`（`app/services/watch_analysis_service.py:77`）

`raw_prices = get_realtime_prices(codes, force_refresh=True)` 之后，**仅当 `period == 'realtime'`** 加一步 `filter_fresh_prices(raw_prices, market_map)`（`market_map` 来自 `WatchService.get_market_map()`，②③ 同）。force_refresh 失败降级返回的昨日价被拦 → 该股跳过 AI 分析（省 LLM 调用），记入 `failed_codes` 日志。

- 7d/30d 不加门（日级语义 + 每日简报输入）。
- 分时数据只保留现有"非空"检查，不做末根 bar 年龄检查——午休/集合竞价时段无新 bar 会误判。

### ③ `push_realtime_analysis`（`app/services/notification.py:462`）

不改函数签名、不透传参数。内部取价改为：

```python
raw_prices = get_realtime_prices(all_codes, cache_only=True)
raw_prices = filter_fresh_prices(raw_prices, market_map)
```

并收紧规则：**code 不在新鲜价字典里 → 该股整块跳过不推**（现状是没价也照推支撑/压力行）。

推送层再查一遍而非复用分析时的价，理由：LLM 循环逐股带重试可能耗时数分钟，分析开始时取的价到推送时自身就超龄；期间 preload 一直在刷缓存，推送时 `cache_only` 读到的是最新价（内存读，零 API 开销），再过同一个闸门保证新鲜且语义一致。

## 边界情况

- **午休（A 股 11:30–13:00）**：`is_market_open` 为假，preload/alert/realtime 全不跑，闸门不参与。13:00 复盘首 tick 若 alert 先于 preload 跑，读到午休前超龄价 → 该 tick 静默，下一 tick 恢复。符合"宁可不推"，不特殊处理。
- **preload 指数退避（最长 8 tick）**：退避期间价格超龄 → 告警/分析静默，恢复后自动复活。这正是期望行为。
- **`last_fetch_time` 缺失/格式异常**：fail-closed 视为不新鲜，解析用 `try/except ValueError` 包住不抛异常。
- **market_map 缺 code**：按非 A 默认 6 分钟阈值兜底（宽松侧，避免市场识别缺失误杀）。
- **已知打折项——闸门保证"抓取新鲜"而非"报价新鲜"**：A 股备用源（东财/新浪）走 `_get_source_snapshot`，`_SNAPSHOT_TTL = 120`（`app/services/unified_stock_data.py`）——全市场快照缓存 2 分钟，但写进 price dict 的 `last_fetch_time` 是当前抓取时刻。腾讯主源故障、走备用源时，一条 `age=10s` 的 A 股价格其行情本身最旧可能是 2 分钟前，叠加 120s 闸门阈值，真实报价年龄最坏约 240s。这是既有架构限制（改 snapshot 语义爆炸半径过大），不在本次范围内修，仅留档。

## 错误处理与日志

三个接入点被拦时统一风格记日志（复用各自现有 logger），闸门纯函数本身不 log：

```
[盯盘告警] 跳过3只超龄旧价: ['600519(age=185s)', ...]
[盯盘AI] 600519 跳过realtime分析: 价格超龄(185s)
[盯盘实时] 推送跳过2只超龄旧价: [...]
```

## 测试（`tests/test_price_freshness.py` 平铺，不走 `create_app`）

1. `is_fresh`：A 股 119s 新鲜 / 121s 超龄；非 A 359s 新鲜 / 361s 超龄
2. `is_fresh`：`_is_degraded=True` → False（即使 `last_fetch_time` 很新）
3. `is_fresh`：`last_fetch_time` 缺失 / 乱格式 → False
4. `filter_fresh_prices`：混合市场批量过滤正确；market_map 缺 code 走 6min 默认
5. `watch_alert._filter_fresh`：静态方法直测，混入超龄价被剔除
6. `push_realtime_analysis` 门控：monkeypatch `get_realtime_prices` 返回含超龄价 + mock `send_slack`，断言超龄股的块未出现在推送文本中
