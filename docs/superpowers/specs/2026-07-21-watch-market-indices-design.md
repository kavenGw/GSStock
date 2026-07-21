# 盯盘各市场分区加指数条

**日期**：2026-07-21
**状态**：设计已确认，待实现

## 背景

盯盘页（`app/templates/watch.html`）当前结构：

- 顶部一条**全局「基准标的」bar**（`#benchmarkBar`），横排展示 `BENCHMARK_CODES`（COMEX黄金 / COMEX白银 / 纳指100），不区分市场。
- 下方按市场（A / US / HK / KR…）分区展示盯盘个股（`WATCH_CODES`），每个分区有分时/7日大图 + summary 信号表。

需求：给 **A 股分区**加上证 / 创业板 / 科创50 三个指数，给 **韩股分区**加 KOSPI，作为该市场的情绪参照。

## 目标与非目标

**目标**：

- A 股、韩股分区顶部各出现一条指数 chip 行（名称 + 现价 + 当日涨跌幅）。
- 点击指数 chip 可展开看该指数的分时图。
- 全局基准 bar（金/银/纳指）保持不变。

**非目标**：

- 指数**不进**信号检测 / 极值告警（`watch_alert`）/ AI 分析链路——纯行情参照。
- 只做 A 和 KR 两个市场（US 已有纳指100 在全局 bar；HK 未要求）。
- 指数不进 7日/30日/90日切换，只有分时。

## 设计

### 1. 数据模型（config）

在 `app/config/stock_codes.py` 新增按市场键的常量，与 `BENCHMARK_CODES` 并列、互不干扰：

```python
MARKET_INDICES = {
    'A': [
        {'code': '000001.SS', 'name': '上证'},
        {'code': '399006.SZ', 'name': '创业板'},
        {'code': '000688.SS', 'name': '科创50'},   # STAR 50 指数
    ],
    'KR': [
        {'code': '^KS11', 'name': 'KOSPI'},
    ],
}
```

**关键取舍**：不把指数塞进 `WATCH_CODES`。`WATCH_CODES` 是告警扫描 / 信号检测 / AI 分析 / `get_watched_markets` 的共同权威源，塞进去每个消费者都要加 `is_index` 守卫，容易漏。单独常量最干净，也符合「指数不进信号/告警」的定位。

`000001.SS`（上证）和 `399006.SZ`（创业板指）已在现有 `INDEX_CODES` 中登记；`000688.SS`（科创50）为新增。

### 2. 后端取价

扩展现有 `/watch/prices` 路由（`app/routes/watch.py`），在返回里新增 `indices` 字段（按市场分组），走与 `benchmarks` 完全一致的 `get_prices_cached_only` 只读缓存路径，随价格 60s 轮询刷新。**不新增端点**。

返回结构：

```json
{
  "prices": [...],
  "benchmarks": [...],
  "indices": {
    "A":  [{"code": "000001.SS", "name": "上证", "price": ..., "change_pct": ...}, ...],
    "KR": [{"code": "^KS11", "name": "KOSPI", "price": ..., "change_pct": ...}]
  }
}
```

预加载（`watch_preload`）需把 `MARKET_INDICES` 的代码纳入 `force_refresh` 写缓存的集合，否则 chip 只读缓存会长期 stale。

### 3. 前端渲染

`app/static/js/watch.js`：

- `WatchState` 新增 `indices` 字段，`/watch/prices` 拉取后落存，localStorage 按需持久化（参考 benchmarks 的 `WatchStore.set('benchmarks', ...)`）。
- 在每个市场分区卡片（`market-section-${market}`）内、大图上方渲染一条指数 chip 行，复用 benchmark chip 的样式（名称 + 现价 + 涨跌幅，涨绿跌红，`price-up`/`price-down`/`price-flat`）。
- 只有 `MARKET_INDICES` 中存在的市场（A / KR）渲染该行；其他分区不变。
- chip 的 `name` / `code` 走 HTML 转义（与 summary 信号列一致的约定）。

### 4. 分时图交互

点击指数 chip → 复用现有 `/watch/chart-data?code=<code>&period=intraday`，把返回的分时数据渲染到**指数条正下方的一个可折叠 mini 面板**（再点收起，单开——点第二个指数切换到它）。与个股主图区分开，不干扰现有个股图选中逻辑。mini 面板复用现有 ECharts 分时渲染逻辑。

### 5. 已知风险（实现里必须验证/处理）

`MarketIdentifier.identify`（`app/utils/market_identifier.py`）当前只认 `.HK` 后缀 + 6 位纯数字 + 字母开头。指数代码存在识别歧义：

- `000001.SS` / `399006.SZ` / `000688.SS`：带 `.SS`/`.SZ` 后缀，需确认 `identify` 与 `get_intraday_data` / `get_realtime_prices` 能正确路由到 A 股腾讯源（`sh000001` / `sz399006` / `sh000688`）。
- `^KS11`：`^` 开头，`identify` 大概率返回 `None`，`/watch/chart-data` 里 `MarketIdentifier.identify(code) or 'A'` 会误落到 A，导致交易时段 / 取数源错误。需给 KOSPI 走 yfinance `^KS11` 的正确路由，并让 `chart_data` 的 `market` 推断对指数代码返回正确市场（A 指数→`A`，KOSPI→`KR`）。

**这是本设计最主要的实现不确定点**，实现第一步应先写一个只读验证脚本，确认这 4 个代码的实时价与分时数据都能取到，再动 UI。

## 涉及文件

- `app/config/stock_codes.py` — 新增 `MARKET_INDICES`
- `app/routes/watch.py` — `/watch/prices` 增 `indices` 返回
- `app/services/unified_stock_data.py` / `app/utils/market_identifier.py` — 视验证结果决定是否加指数代码路由分支
- `app/services/watch_preload*`（预加载）— 把指数代码纳入 force_refresh 集合
- `app/static/js/watch.js` — state + 渲染 + chip 点击展开分时
- `app/templates/watch.html` — 分区内指数条容器（如需静态骨架）
- `.claude/rules/watch.md` — 补文档

## 测试

- 后端：`/watch/prices` 返回含 `indices`、结构正确（路由层可用 Flask + register_blueprint 直接注入测，秒级）。
- 取数验证脚本（一次性，不入库）：确认 4 个指数代码实时价 + 分时可取。
- 前端：手动 smoke——A / KR 分区出现指数条，点击展开分时，全局 bar 不变。
