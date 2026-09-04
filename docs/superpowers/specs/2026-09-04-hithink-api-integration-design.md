# 同花顺（HiThink Fuyao）金融数据 API 接入设计

- 日期：2026-09-04
- 状态：设计已确认，待实现
- 上游文档：https://github.com/HiThink-Tech/Financial-API
- Base URL：`https://fuyao.aicubes.cn`

## 1. 背景与目标

现有 A 股取数体系依赖腾讯 HTTP（`qt.gtimg.cn`）、新浪、东方财富（akshare）三源，已知痛点：

- `ak.stock_zh_a_spot_em` / `stock_individual_info_em` 频繁被东财限流（RemoteDisconnected）
- 腾讯 `q=` 接口 `[41]/[42]` 年高低字段失真、`[47]/[48]` 实为涨跌停价，估值分位不可用
- `ak.stock_financial_abstract_ths` 是多年财务时序的唯一稳定接口，单点依赖
- 缺乏干净的估值口径（PE/PB/PS）来源

同花顺付费 API 提供官方 A 股行情、三表、财务指标、估值快照，且**不设累计调用次数上限**（仅要求避免高并发），优于 Twelve Data（800/天）与 Polygon（5/分）。

**目标**：将同花顺接为 A 股实时快照主源、估值口径新能力、三表与能力指标主源，同时服务 app 运行时与投研 skill 采证。

## 2. 能力边界（实测确认）

2026-09-04 用真实 key 探测四个端点，全部 `HTTP 200 / code == 0`。

### 2.1 可用

| 端点 | 批量 | 关键字段 |
|---|---|---|
| `GET /api/a-share/prices/snapshot` | ✓ `thscodes` | `last_price, prev_price, open/high/low_price, volume, turnover, price_change, price_change_ratio_pct`（**无中文名**） |
| `GET /api/a-share/valuations/snapshot` | ✓ `thscodes` | `name, pe_ttm, pe_mrq, pb_mrq, ps_ttm, pcf_ttm` |
| `GET /api/a-share/financials/income-statements` | 单只 | 绝对值（元）+ `fiscal_year, fiscal_period, period_end_ms, currency`，`limit` 取多期（1–20） |
| `GET /api/a-share/financials/balance-sheets` | 单只 | 15 字段 |
| `GET /api/a-share/financials/cash-flow-statements` | 单只 | 14 字段 |
| `GET /api/a-share/financials/indicators` | 单只 | `abilities` **数组**：growth / profitability / solvency / operation / cash-flow |
| `GET /api/a-share/prices/historical` | 单只 | 日 K，最长 10 年，`adjust` 参数 |

### 2.2 能力缺口（不假装能替代）

1. **无扣非净利润** —— income 端点字段里没有。本仓规则明写「盈利质量看扣非不看归母」，故**扣非继续走 akshare `stock_financial_abstract_ths`**。`indicators` 的 `index_deduct_weighted_avg_roe` 仅可侧面参考。
2. **无分钟 K / tick** —— 盯盘分时 K 继续走腾讯 `mkline`，不动。
3. **无海外行情** —— 美股 / 港股全链路完全不动（yfinance / TwelveData / Polygon）。
4. **复权只给原始分红拆股事件流**，需自行推导因子；腾讯 `fqkline` 直接给 qfq。故**日 K 仍以腾讯为主**，同花顺日 K 仅作 fallback，不自造复权轮子。

**实际替代面**：A 股实时快照（主源）+ 估值口径（新能力）+ 三表与能力指标（主源，扣非除外）。

## 3. 架构

新建 `app/services/hithink/`，一个 HTTP 底座 + 两个消费面。

### 3.1 `client.py` — 唯一碰 HTTP 的地方

职责：
- 持 `requests.Session` 复用连接，注入 `X-api-key` 头
- **信封解包**：成功判据是 `HTTP 200` **且** `code == 0`，仅看状态码不够；`code != 0` 抛 `HithinkError`（携带 `code` / `message` / `request_id`）
- **`4001` 限流退避**：指数退避有界重试；`5xxx` 同样有界重试；`1xxx`–`2xxx`（缺参/格式/无权限）不重试直接抛
- **thscode 归一**：`600519` / `sh600519` / `SH600519` ⇄ `600519.SH` 双向
- **`is_available()`**：未配 `HITHINK_FINANCE_API_KEY` 返回 `False`

`is_available()` 是**安全阀**：未配 key 时上游所有同花顺分支跳过，全仓行为与接入前逐字节一致。

### 3.2 `provider.py` — `HithinkProvider(DataSourceProvider)`

`name = 'hithink'`，`market = 'A'`。实现契约的 `get_realtime_price` / `get_batch_prices` / `get_historical_data`，注册进 `DataSourceFactory` 与 `load_balancer.MARKET_SOURCES['A']`，服务确实走 provider 抽象的消费者。

### 3.3 `financials.py` — 三表 / indicators / valuations

返回形状是多期报表数组，**故意不塞进 `DataSourceProvider`** —— 该抽象只有 `get_realtime_price` / `get_historical_data` 两个方法，硬塞会撑坏它。本层同时服务 skill 采证脚本与 app 运行时。

`indicators` 的 `abilities` 是**数组**，解析必须迭代，不可按字典取键。

## 4. 主链路改动（仅两处）

### 4.1 `unified_stock_data._fetch_a_share_prices`

新增 `fetch_from_hithink(codes)` 闭包，与现有 `fetch_from_eastmoney` / `fetch_from_sina` / `fetch_from_tencent` 同构。

**关键设计**：snapshot 不返回中文名，但 `valuations/snapshot` 返回 `name` 且同样支持批量 → **一次并发打两个端点再合并**，补齐 `name`，并白拿 `pe_ttm / pb_mrq / ps_ttm`，正好补上腾讯 `[39]/[46]` 与 `[41]/[42]` 的失真坑。

### 4.2 `load_balancer.MARKET_SOURCES['A']`

`primary_sources` 改为 `['hithink', 'tencent']`，`sina` / `eastmoney` 降为 `secondary_sources`。

**不动**：美股 / 港股全链路、盯盘分时 K、`Stock` 表 schema。

## 5. 数据契约与归一

### 5.1 Volume 单位（最易静默出错的一项）

同花顺 snapshot 的 `volume` 是**股**（实测 600519 为 3,418,300 股，× 1330.33 ≈ turnover 45.28 亿，自洽），腾讯 `q=` 的 `[6]` 是**手**。

在 `unified_stock_data.py` 的单位表加 `'hithink_snapshot': 'shares'`，取值一律走 `_normalize_volume(v, 'hithink_snapshot', 'A')`，**绝不裸赋值**。否则 A 股成交量静默差 100 倍，且量能只进图表不进告警阈值，几乎不会被发现。

### 5.2 字段映射

| 现有键 | 同花顺来源 |
|---|---|
| `current_price` | `snapshot.last_price` |
| `prev_close` / `open` / `high` / `low` | `snapshot.prev_price` / `open_price` / `high_price` / `low_price` |
| `change` / `change_percent` | `snapshot.price_change` / `price_change_ratio_pct` |
| `volume` | `snapshot.volume`（经 `_normalize_volume`） |
| `name` | `valuations.name` |
| `pe_ttm` / `pb` / `ps_ttm`（新增可选） | `valuations.pe_ttm` / `pb_mrq` / `ps_ttm` |

新增字段为**可选**，缺失即 `None`，不改变现有消费者行为。

### 5.3 失败语义二分

- **行情线**：任何 `HithinkError` / 超时 / `code != 0` → 记 warning 并**降级到腾讯**，对上层透明，**不设 `_is_degraded`**（拿到的是腾讯正常数据，不是过期缓存）。熔断沿用现有 `circuit_breaker`，不另造。
- **财务线**：**不静默降级**，取不到就抛，让采证脚本看见错误。悄悄回落到 akshare 旧口径的财务数字会直接写进建档，比取不到危险得多。

### 5.4 缓存

- **行情**：走现有 `SmartCacheStrategy` / `get_effective_cache_date(code)`，**不新造缓存层**。
- **财务**：轻量文件缓存，按 `(thscode, period, report)` 存 JSON 落 `data/cache/hithink/`。TTL 按报告期而非天数 —— 已披露年报永不过期，当期在途给 6 小时。不进 DB、不进 git。

## 6. 配置

新增单一环境变量 `HITHINK_FINANCE_API_KEY`，按本仓约定**同步三处**：`CLAUDE.md`、`README.md`、`.env.sample`。

Key 只从 `os.environ` 读，**任何情况下不写进代码或 git**（亦为同花顺官方硬性要求）。

> 安全提示：本次设计所用 key 曾在对话中明文出现，实施前应在同花顺后台重置一把新的再填入 `.env`。

## 7. 测试策略

TDD，测试先行，**不打真网**。2026-09-04 探测所得四份真实响应存为 fixture，全部 mock。

- `tests/test_hithink_client.py` — 信封解包；`code != 0` 抛错；`4001` 退避重试；`1xxx`–`2xxx` 不重试；thscode 三形态双向归一；未配 key 时 `is_available()` 为 `False`
- `tests/test_hithink_provider.py` — 字段映射逐项；`volume` 单位归一数值正确；两端点合并后 `name` 与 `pe_ttm` 就位
- `tests/test_hithink_financials.py` — `abilities` 数组迭代解析（非字典取键）；多期报表排序；缓存 TTL 按报告期分支
- **回归**：断言未配 key 时 `_fetch_a_share_prices` 的调用序列与接入前完全一致 —— 验证安全阀真的是安全阀

测试平铺于 `tests/test_*.py`，不建子目录。

## 8. 实施约束

- 本项改 `app/` 代码，按本仓分支策略**开独立 git worktree**，不在 main 上动
- 探测脚本属一次性脚本，不入库
- 官方 MCP 服务本次**不配**（已确认），如需后续单独提

## 9. 范围外

- 官方 Python SDK（`pip install -e ./python` 本地路径装，进不了 `requirements.txt`，会断 `update_and_run.sh` 的 Linux 部署）
- 官方 Node CLI 与 marketdb（DuckDB 本地库）
- MCP 托管服务
- 基金 / 涨跌停池 / 龙虎榜 / 热榜等特色数据（后续可另提）
