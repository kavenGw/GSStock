# 每日推送新增「ADR 跨市场溢价」设计

> 状态：已批准 · 日期：2026-07-21 · 频道：news_daily

## 目标

在 `daily_briefing` 每日推送里新增两条跨市场溢价：

- **TSMC 美台**：TSM（NYSE ADR）vs 2330.TW（台湾），1 ADR = 5 股，ratio=5
- **SK海力士 美韩**：SKHY（2026-07-09 挂牌的 Nasdaq 保荐 ADR）vs 000660.KS（首尔），1 ADS = 1/10 普通股，ratio=0.1
  - 原设想的 OTC 粉单 HXSCL/HXSCF 无 yfinance 报价，已弃用；改用挂牌保荐 ADR SKHY（流动性好，实测溢价 ~+22%）

粒度：**当前溢价% + 较昨日变化**。展示 + 喂 GLM 双路，完全照搬现有 ETF溢价（`format_etf_premium_summary`）的分层与接线。

## 口径

溢价% = `美股ADR价(USD)` / (`本土价(本币)` × `每ADR股数` × `USD每本币`) − 1

- 正 = 美股溢价，负 = 折价
- FX 用 yfinance `TWD=X` / `KRW=X`，其值是「每 1 USD 多少本币」（TWD≈32、KRW≈1380），故本币折 USD 需 **除以** 该值：`premium = us_price / (home_price × ratio / fx_rate) − 1`

**跨市场时间差**：8am（北京）推送时，美股 ADR = 昨夜收盘、台/韩 = 上一交易日收盘、亚洲尚未开盘 → 这是「收盘 vs 收盘」的溢价，天然反映 ADR 隔夜情绪，作为已知口径接受。

## 架构（沿用 BriefingService 双层：get_*_data 出数据 / format_* 出文案）

### 1. 配置层 — 新增 `app/config/adr_premium.py`

```python
ADR_PREMIUM_PAIRS = [
    {'key': 'tsmc',    'name': 'TSM',      'us': 'TSM',   'home': '2330.TW',   'ratio': 5,    'fx': 'TWD=X'},
    {'key': 'skhynix', 'name': 'SK海力士', 'us': 'HXSCL', 'home': '000660.KS', 'ratio': None, 'fx': 'KRW=X'},
]
```

- `ratio` = 每 1 ADR 对应几股本土股。TSM=5（公认）。
- **HXSCL ratio 待实测**：实施时先拉两边近几日现价，用中位反推 ratio，锁定后写死配置。列为 plan 的一次性核实任务。公司若调整 ADR 比例，需手更此配置（写入已知限制）。

### 2. 数据层 — `BriefingService.get_adr_premium_data() -> dict`

返回结构（照搬 ETF溢价）：

```python
{'pairs': [
  {'key','name','us_price','home_price','fx','ratio',
   'premium_rate': float|None,   # 当前溢价%
   'prev_premium': float|None,   # 昨日溢价%（读自 json）
   'delta': float|None,          # 今日 − 昨日，pct 点
   'error': str|None},
  ...
]}
```

- 取数：yfinance 一次批量拉 `[TSM, 2330.TW, HXSCL, 000660.KS, TWD=X, KRW=X]`，直连 yfinance，不走 A股腾讯链路。FX pair 首字母是字母 → MarketIdentifier 归 US → yfinance 支持 `TWD=X`/`KRW=X`。
- **降级铁律**：任一腿（尤其 HXSCL OTC 无价 / FX 缺）→ 该 pair `premium_rate=None` + 填 `error`，不抛异常、不污染另一 pair。

### 3. 持久化 — `data/adr_premium_prev.json`

对齐 `data/github_release_*_last_version.txt` 标记文件先例，零 schema 迁移（data/ 已 gitignore）。

```json
{"tsmc": {"date": "2026-07-20", "premium": 1.82},
 "skhynix": {"date": "2026-07-20", "premium": -0.31}}
```

- `get_adr_premium_data()` 内：读文件填 `prev_premium` → 算 `delta` → 算完当日值后写回。
- 幂等：`push_daily_report` 有 `has_daily_push` 日锁，一天一推，写回不污染 delta。
- 某腿当日无价（premium=None）→ **不覆盖**该 key 旧值，避免 OTC 断供清空基准。
- 跨自然日容错：存的 date ≠ 今天即当「昨日」用；周一读到上周五值语义仍成立（收盘 vs 收盘）。

### 4. 文案层 — `NotificationService.format_adr_premium_summary() -> str`

紧凑单行，独立挂在 msg3 市场段，紧跟 ETF溢价：

```
🌏 ADR溢价: TSM +1.82%(溢价)↑0.5pct | SK海力士 -0.31%(折价)↓0.2pct
```

- 方向标签：`premium ≥ 0` → `(溢价)`，`< 0` → `(折价)`。
- delta 箭头：`> 0` → `↑{|delta|:.1f}pct`（溢价扩大），`< 0` → `↓...`（收窄），`None`（首日/无昨值）→ 省略箭头。
- 某腿 `premium_rate=None` → 显 `TSM —`；两腿全废 → 返回 `''`（照搬其它 formatter 语义）。
- 数字 `{:+.2f}%`；delta 用绝对值配箭头。

### 5. 接线 — `push_daily_report` + GLM prompt

照搬 ETF溢价 双路，改动集中在 `push_daily_report`：

1. `adr_text = NotificationService.format_adr_premium_summary()`（与 `etf_text` 并列取一次）。
2. `market_lines` 里 `etf_text` 之后 append `adr_text` → 落 msg3 → 发 `news_daily`。
3. `all_data['adr_premium'] = adr_text` → GLM 核心观点可引用。同步改 `app/llm/prompts/daily_briefing.py` 的 `build_daily_briefing_prompt` 加 `adr_premium` 字段渲染。

## 测试 — `tests/test_adr_premium.py`

纯函数注入假数据，不走 create_app：

1. 公式正确性：给定 us/home/fx/ratio 断言 premium。
2. 降级：HXSCL 无价只废 SK 腿、TSM 正常。
3. delta 计算 + prev.json 读写 + 无昨值省略箭头。
4. `format_*` 全废返回空串。

## 已知限制

- 收盘 vs 收盘的天然时间差（8am 推送时亚洲未开盘）。
- 公司调整 ADR 比例时需手更 `ADR_PREMIUM_PAIRS.ratio`（SKHY 新挂牌，若后续做拆并需复核 1 ADS=1/10 口径）。
- SKHY 2026-07-09 才挂牌，`prev.json` 昨日基准需累积一日后 delta 才有值（首日无箭头，符合设计）。

## 改动清单

- 新增：`app/config/adr_premium.py`、`tests/test_adr_premium.py`
- 修改：`app/services/briefing.py`、`app/services/notification.py`、`app/llm/prompts/daily_briefing.py`
- 运行时数据文件：`data/adr_premium_prev.json`（自动生成，gitignore）
- 无新第三方依赖
