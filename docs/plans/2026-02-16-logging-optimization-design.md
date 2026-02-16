# 后台日志优化 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 统一37个文件的日志格式、精简控制台噪音、添加耗时/数据源上下文追踪、实现日志轮转。

**Architecture:** 新增 `log_operation` 上下文管理器自动记录耗时；统一 `[模块.操作]` 方括号标记格式；将过细的 INFO 降级为 DEBUG；FileHandler 改为 RotatingFileHandler。

**Tech Stack:** Python logging, logging.handlers.RotatingFileHandler

---

## 模块名映射表（所有 Task 共用）

| 代码文件 | 日志标记前缀 |
|---------|------------|
| unified_stock_data.py | `数据服务` |
| preload.py | `预加载` |
| briefing_preload.py | `简报预加载` |
| heavy_metals_preload.py | `走势预加载` |
| futures.py | `期货` |
| briefing.py (routes) | `简报` |
| briefing.py (services) | `简报服务` |
| alert.py (routes) | `预警` |
| heavy_metals.py (routes) | `走势看板` |
| wyckoff.py | `威科夫` |
| position.py (services) | `持仓` |
| position.py (routes) | `持仓路由` |
| load_balancer.py | `负载均衡` |
| memory_cache.py | `内存缓存` |
| circuit_breaker.py | `熔断器` |
| data_source_providers.py | `数据源` |
| notification.py | `通知` |
| signal_detector.py | `信号检测` |
| signal_cache.py | `信号缓存` |
| backtest.py | `回测` |
| earnings.py | `财报` |
| trading_calendar.py | `交易日历` |
| market_session.py | `市场时段` |
| cache_validator.py | `缓存验证` |
| ocr.py | `OCR` |
| trade.py | `交易` |
| stock_meta.py | `StockMeta` |
| cockroach_migration.py | `CockroachDB迁移` |
| migration.py | `数据迁移` |
| ai_analyzer.py | `AI分析` |
| fed_rate.py | `美联储利率` |
| db_retry.py | `DB重试` |
| market_identifier.py | `市场识别` |
| portfolio_advice.py | `持仓建议` |
| daily_record.py (routes) | `每日记录` |
| stock_detail.py (routes) | `股票详情` |

## 日志级别规范（所有 Task 共用）

- **DEBUG**: 缓存命中/未命中细节、单只股票获取成功/失败、字段级诊断
- **INFO**: 操作开始/完成（含耗时+统计）、关键状态变化
- **WARNING**: 降级、重试、数据不完整、非致命失败
- **ERROR**: 操作失败，必须带 `exc_info=True`

精简原则：每个操作最多 "开始 + 完成" 两条 INFO，中间过程用 DEBUG。

---

### Task 1: 基础设施 — log_utils.py + __init__.py

**Files:**
- Create: `app/utils/log_utils.py`
- Modify: `app/__init__.py:101-141`

**Step 1: 创建 `app/utils/log_utils.py`**

```python
import time
import logging
from contextlib import contextmanager


@contextmanager
def log_operation(logger, tag, level=logging.INFO, **start_kwargs):
    """自动记录操作耗时的上下文管理器

    用法:
        with log_operation(logger, "数据服务.实时价格") as op:
            result = fetch()
            op.set_message(f"成功 {len(result)}只")
        # 自动输出: [数据服务.实时价格] 完成: 成功 5只, 耗时 2.3s

        # 简单用法（无自定义消息）:
        with log_operation(logger, "预加载.指数"):
            preload()
        # 自动输出: [预加载.指数] 完成, 耗时 1.1s
    """
    class _Op:
        def __init__(self):
            self.message = None
            self.suppressed = False

        def set_message(self, msg):
            self.message = msg

        def suppress_completion(self):
            """调用此方法可抑制自动完成日志（由调用方手动输出）"""
            self.suppressed = True

    op = _Op()
    start = time.perf_counter()
    try:
        yield op
    except Exception:
        elapsed = time.perf_counter() - start
        logger.error(f"[{tag}] 失败, 耗时 {elapsed:.2f}s", exc_info=True)
        raise
    else:
        if not op.suppressed:
            elapsed = time.perf_counter() - start
            if op.message:
                logger.log(level, f"[{tag}] 完成: {op.message}, 耗时 {elapsed:.2f}s")
            else:
                logger.log(level, f"[{tag}] 完成, 耗时 {elapsed:.2f}s")
```

**Step 2: 修改 `app/__init__.py` 的 `setup_logging()`**

将 FileHandler 改为 RotatingFileHandler，添加第三方库噪音抑制：

```python
from logging.handlers import RotatingFileHandler

def setup_logging(app):
    """配置应用日志系统"""
    log_dir = app.config.get('LOG_DIR', 'data/logs')
    os.makedirs(log_dir, exist_ok=True)

    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # app.log - 所有日志（轮转: 5MB x 3）
    file_handler = RotatingFileHandler(
        os.path.join(log_dir, 'app.log'),
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # error.log - 仅错误（轮转: 2MB x 3）
    error_handler = RotatingFileHandler(
        os.path.join(log_dir, 'error.log'),
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    # 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # 配置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_handler)
    root_logger.addHandler(console_handler)

    # 第三方库噪音抑制
    logging.getLogger('yfinance').setLevel(logging.CRITICAL)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
```

**Step 3: 验证应用可启动**

Run: `cd D:\Git\stock && python -c "from app import create_app; app = create_app(); print('OK')"`
Expected: OK

**Step 4: Commit**

```bash
git add app/utils/log_utils.py app/__init__.py
git commit -m "feat: 添加 log_operation 耗时追踪工具 + 日志轮转 + 第三方库噪音抑制"
```

---

### Task 2: unified_stock_data.py — 实时价格 + 通用方法

**Files:**
- Modify: `app/services/unified_stock_data.py`

改动范围：`_retry_fetch`、`_get_expired_cache`、`get_realtime_prices` 及其子方法 `_fetch_a_share_prices`、`_fetch_other_prices`。

**规则：**

1. 所有方括号标记改为 `[数据服务.xxx]` 格式
2. `[实时价格]` → `[数据服务.实时价格]`
3. `[降级]` → `[数据服务.降级]`
4. `[内存缓存]` → `[数据服务.缓存]`（内存缓存细节降 DEBUG）
5. `[快照]` / `[快照命中]` → `[数据服务.快照]`
6. `[获取]` → `[数据服务.获取]`（保持 DEBUG）
7. `[只读模式]` → `[数据服务.只读]`
8. 数据源具体获取日志（东方财富→/新浪→/腾讯→/yfinance→）保持 INFO，加 `[数据服务.实时价格]` 前缀
9. 单只股票获取成功/失败保持 DEBUG
10. `_get_expired_cache` 中无标记的 → 加 `[数据服务.降级]`
11. `_retry_fetch` 中无标记的 → 加 `[数据服务.重试]`
12. 缺少 `exc_info=True` 的 error 日志补上

**改动样例（行号基于当前代码）：**

```python
# 行 192: 无标记 → 加标记
# 旧: logger.warning(f"数据源 {source} 获取失败: {e}")
# 新: logger.warning(f"[数据服务.负载均衡] 数据源 {source} 获取失败: {e}")

# 行 311: 无标记 → 加标记
# 旧: logger.warning(f"股票 {stock_code} 重试{max_retries}次后仍失败: ...")
# 新: logger.warning(f"[数据服务.重试] {stock_code} {max_retries}次后仍失败: ...")

# 行 382: 标记规范化
# 旧: logger.info(f"[降级] {stock_code} ...")
# 新: logger.info(f"[数据服务.降级] {stock_code} ...")

# 行 385: error 补 exc_info
# 旧: logger.warning(f"获取过期缓存失败 {stock_code}: {e}")
# 新: logger.warning(f"[数据服务.降级] 获取过期缓存失败 {stock_code}: {e}")

# 行 412: 标记规范化
# 旧: logger.info(f"[实时价格] 开始获取: ...")
# 新: logger.info(f"[数据服务.实时价格] 开始获取: ...")

# 行 428: 保持 DEBUG + 标记规范化
# 旧: logger.debug(f"[内存缓存] 命中 {memory_hit_count}只")
# 新: logger.debug(f"[数据服务.缓存] 内存命中 {memory_hit_count}只")

# 行 431: 标记规范化
# 旧: logger.info(f"[实时价格] 完成: ...")
# 新: logger.info(f"[数据服务.实时价格] 完成: ...")

# 行 518: 标记规范化 + 数据源分布
# 旧: logger.info(f"[实时价格] 完成{readonly_msg}: 请求 {len(stock_codes)}只, 成功 {len(result)}只 (内存命中 {memory_hit_count}, DB命中 {db_hit_count})")
# 新: logger.info(f"[数据服务.实时价格] 完成{readonly_msg}: 请求 {len(stock_codes)}只, 成功 {len(result)}只 (内存{memory_hit_count}, DB{db_hit_count})")

# 行 655/657/695/715/717/742/755/807: 快照/数据源日志统一前缀
# 旧: logger.info(f"[快照] 东方财富A股数据已缓存: ...")
# 新: logger.info(f"[数据服务.快照] 东方财富A股: {len(stock_map)}只")

# 旧: logger.info(f"[实时价格] {today} 东方财富 → {names} ({len(result)}只)")
# 新: logger.info(f"[数据服务.实时价格] 东方财富 → {names} ({len(result)}只)")
```

**Step: 验证**

Run: `cd D:\Git\stock && python -c "from app.services.unified_stock_data import UnifiedStockDataService; print('OK')"`

**Step: Commit**

```bash
git add app/services/unified_stock_data.py
git commit -m "refactor: 统一 unified_stock_data 实时价格日志标记格式"
```

---

### Task 3: unified_stock_data.py — 走势数据 + 指数 + PE + A股板块 + ETF + 收盘价

**Files:**
- Modify: `app/services/unified_stock_data.py`

改动范围：`get_trend_data` 系列、`get_indices_data`、`get_pe_data`、`_get_a_share_sectors`、`get_etf_nav`、`get_closing_prices`、`get_cached_quotes`。

**规则：**

1. `[走势数据]` → `[数据服务.走势]`
2. `[A股指数]` → `[数据服务.A股指数]`
3. `[PE数据]` → `[数据服务.PE]`
4. `[A股板块]` → `[数据服务.A股板块]`
5. `[ETF净值]` → `[数据服务.ETF净值]`
6. `[yfinance批量]` → `[数据服务.yfinance批量]`
7. `[收盘价]` → `[数据服务.收盘价]`
8. `[缓存报价]` → `[数据服务.缓存报价]`
9. `[增量]` → `[数据服务.增量]`（保持 DEBUG）
10. 无标记的 warning/error → 加对应的 `[数据服务.xxx]` 前缀
11. 单只股票获取日志保持 DEBUG

**改动样例：**

```python
# 行 925: 旧 [走势数据] → 新 [数据服务.走势]
# 行 1050: 旧 [走势数据] → 新 [数据服务.走势]
# 行 1146: 旧 [走势数据] → 新 [数据服务.走势]
# 行 1562: 旧 [走势数据] ETF → 新 [数据服务.走势] ETF
# 行 1620: 旧 [走势数据] 东方财富 → 新 [数据服务.走势] 东方财富
# 行 1680: 旧 [走势数据] 新浪 → 新 [数据服务.走势] 新浪
# 行 1755: 旧 [走势数据] 腾讯 → 新 [数据服务.走势] 腾讯
# 行 1847: 旧 [走势数据] yfinance → 新 [数据服务.走势] yfinance
# 行 2071/2115/2181: 旧 [PE数据] → 新 [数据服务.PE]
# 行 2374/2415: 旧 [A股指数] → 新 [数据服务.A股指数]
# 行 2487-2588: 旧 [A股板块] → 新 [数据服务.A股板块]
# 行 2614/2650: 旧 [ETF净值] → 新 [数据服务.ETF净值]
# 行 2781/2826: 旧 [收盘价] → 新 [数据服务.收盘价]
# 行 2848/2874: 旧 [缓存报价] → 新 [数据服务.缓存报价]
# 行 2924: 无标记 → 加 [数据服务.缓存]
```

**Step: 验证**

Run: `cd D:\Git\stock && python -c "from app.services.unified_stock_data import UnifiedStockDataService; print('OK')"`

**Step: Commit**

```bash
git add app/services/unified_stock_data.py
git commit -m "refactor: 统一 unified_stock_data 走势/指数/PE/板块日志标记"
```

---

### Task 4: 预加载集群 — preload.py + briefing_preload.py + heavy_metals_preload.py

**Files:**
- Modify: `app/services/preload.py`
- Modify: `app/services/briefing_preload.py`
- Modify: `app/services/heavy_metals_preload.py`

**preload.py 改动（10条日志）：**

```python
# 行 78: 加标记
# 旧: logger.warning(f"预加载任务超时: date={target_date}")
# 新: logger.warning(f"[预加载] 任务超时: date={target_date}")

# 行 159: 加标记
# 旧: logger.info(f"预加载启动: date={target_date}, stocks={total_count}")
# 新: logger.info(f"[预加载.持仓] 启动: stocks={total_count}")

# 行 187: 加标记
# 旧: logger.info(f"预加载完成: ...")
# 新: logger.info(f"[预加载.持仓] 完成: success={success_count}, failed={failed_count}")

# 行 261: 单只成功 → 降 DEBUG
# 旧: logger.info(f"指数 {local_code} 预加载成功")
# 新: logger.debug(f"[预加载.指数] {local_code} 成功")

# 行 264: 加标记 + exc_info
# 旧: logger.error(f"指数预加载失败: {e}")
# 新: logger.error(f"[预加载.指数] 失败: {e}", exc_info=True)

# 行 314: 单只成功 → 降 DEBUG
# 旧: logger.info(f"金属 {local_code} 预加载成功")
# 新: logger.debug(f"[预加载.金属] {local_code} 成功")

# 行 319: 加标记 + exc_info
# 旧: logger.error(f"金属预加载失败: {e}")
# 新: logger.error(f"[预加载.金属] 失败: {e}", exc_info=True)

# 行 379: 加标记
# 旧: logger.info(f"开始全量预加载: date={target_date}")
# 新: logger.info(f"[预加载.全量] 开始: date={target_date}")

# 行 494/540: 加标记
# 旧: logger.info(f"扩展预加载启动/完成: ...")
# 新: logger.info(f"[预加载.扩展] 启动/完成: ...")
```

**briefing_preload.py 改动（6条日志）：**

标记已是 `[简报预加载]`，格式基本正确。改动：
- 行 85: `logger.debug` 保持
- 行 87: `logger.warning` 保持

**heavy_metals_preload.py 改动（6条日志）：**

标记已是 `[预加载]`，改为 `[走势预加载]` 区分：
```python
# 行 31: [预加载] → [走势预加载]
# 行 39: [预加载] → [走势预加载]
# 行 44: 保持 DEBUG
# 行 48: 保持 WARNING
# 行 50: [预加载] → [走势预加载]
# 行 65: [预加载] → [走势预加载]
```

**Step: Commit**

```bash
git add app/services/preload.py app/services/briefing_preload.py app/services/heavy_metals_preload.py
git commit -m "refactor: 统一预加载集群日志标记 + 降噪"
```

---

### Task 5: 路由层 — alert.py + briefing.py + heavy_metals.py

**Files:**
- Modify: `app/routes/alert.py`
- Modify: `app/routes/briefing.py`
- Modify: `app/routes/heavy_metals.py`

**alert.py 改动（~15条日志）：**

标记已有 `[alert/data]` 等，改为 `[预警.数据]` 格式，手动计时改用 `log_operation`：

```python
# 导入
from app.utils.log_utils import log_operation

# /alert/data 路由：
# 删除手动 start_time = time.time() 和 elapsed 计算
# 改用:
# with log_operation(logger, "预警.数据") as op:
#     ... 业务逻辑 ...
#     op.set_message(f"获取 {len(result['ohlc_data'])} 只")

# 行 115: [alert/data] → [预警.数据]
# 行 132: [alert/data] → [预警.数据]
# 行 158: [alert/data] → [预警.数据]
# 行 174: [alert/data] → [预警.数据]
# 行 186: [alert/data] → [预警.数据]
# 行 190: 删除（由 log_operation 自动输出）
# 行 216: [alert/signals/refresh] → [预警.信号刷新]（改用 log_operation）
# 行 234: [alert/earnings] → [预警.财报]
# 行 254: 删除（由 log_operation 自动输出）
# 行 275: [backtest] → [预警.回测]
# 行 287: [backtest] → [预警.回测]
```

**briefing.py (routes) 改动（11条日志）：**

全部是无标记的 error 日志，统一加 `[简报.xxx]` 前缀：

```python
# 行 25: logger.error(f"[简报.股票数据] 获取失败: {e}", exc_info=True)
# 行 37: logger.error(f"[简报.PE] 获取失败: {e}", exc_info=True)
# 行 49: logger.error(f"[简报.财报] 获取失败: {e}", exc_info=True)
# 行 61: logger.error(f"[简报.指数] 获取失败: {e}", exc_info=True)
# 行 73: logger.error(f"[简报.期货] 获取失败: {e}", exc_info=True)
# 行 85: logger.error(f"[简报.ETF] 获取失败: {e}", exc_info=True)
# 行 103: logger.error(f"[简报.板块] 获取失败: {e}", exc_info=True)
# 行 115: logger.error(f"[简报.技术指标] 获取失败: {e}", exc_info=True)
# 行 126: logger.error(f"[简报.财报预警] 获取失败: {e}", exc_info=True)
# 行 146: logger.error(f"[简报.推送] 失败: {e}", exc_info=True)
# 行 168: logger.error(f"[简报.测试推送] 失败: {e}", exc_info=True)
```

**heavy_metals.py (routes) 改动（12条日志）：**

标记已有 `[category-data]` 等，改为 `[走势看板.xxx]` 格式：

```python
# 行 104: [category-data] → [走势看板.分类数据]
# 行 115: [category-data] → [走势看板.分类数据]
# 行 129: [category-data] → [走势看板.信号缓存]（降 DEBUG）
# 行 131: [category-data] → [走势看板.信号缓存]（加 exc_info）
# 行 167: 无标记 → [走势看板.建议]
# 行 217: 无标记 → [走势看板.威科夫]（加 exc_info）
# 行 248: [category-data] → [走势看板.分类数据]
# 行 269: [category-trend-data] → [走势看板.走势数据]
# 行 280: [category-trend-data] → [走势看板.走势数据]
# 行 301: [信号检测] → [走势看板.信号检测]
# 行 369: 无标记 → [走势看板.建议]
# 行 419: 无标记 → [走势看板.威科夫]（加 exc_info）
```

**Step: Commit**

```bash
git add app/routes/alert.py app/routes/briefing.py app/routes/heavy_metals.py
git commit -m "refactor: 统一路由层日志标记 + alert 改用 log_operation"
```

---

### Task 6: 路由层 — stock_detail.py + daily_record.py + position.py

**Files:**
- Modify: `app/routes/stock_detail.py`
- Modify: `app/routes/daily_record.py`
- Modify: `app/routes/position.py`

**stock_detail.py 改动（11条日志）：**

全是无标记 error，统一加 `[股票详情.xxx]`：

```python
# 行 136: logger.error(f"[股票详情] 获取 {key} 数据失败: {e}", exc_info=True)
# 行 162: logger.error(f"[股票详情.技术指标] 计算失败: {e}", exc_info=True)
# 行 182: logger.error(f"[股票详情] 获取失败: {e}", exc_info=True)
# 行 201: logger.error(f"[股票详情.OHLC] 获取失败: {e}", exc_info=True)
# 行 246: logger.error(f"[股票详情.AI历史] 获取失败: {e}", exc_info=True)
# 行 269: logger.error(f"[股票详情.AI分析] {stock_code} 失败: {e}", exc_info=True)
# 行 289: logger.error(f"[股票详情.AI分析] 批量失败: {e}", exc_info=True)
# 行 312: logger.error(f"[股票详情.威科夫] {code} 失败: {e}", exc_info=True)
# 行 330: logger.error(f"[股票详情.威科夫回测] {code} 失败: {e}", exc_info=True)
# 行 346: logger.error(f"[股票详情.参考图] 获取失败: {e}", exc_info=True)
# 行 360: logger.error(f"[股票详情.威科夫历史] 获取失败: {e}", exc_info=True)
```

**daily_record.py 改动（9条日志）：**

全是无标记，统一加 `[每日记录.xxx]`：

```python
# 行 68: logger.error(f"[每日记录.OCR] {file.filename} 识别失败: {e}", exc_info=True)
# 行 142: logger.info(f"[每日记录] 保存: date={target_date_str}, positions={len(positions)}, trades={len(trades)}")
# 行 151: logger.error(f"[每日记录.持仓] 保存失败: {e}", exc_info=True)
# 行 163: 保存交易详情 → 降 DEBUG + 加标记
# 行 170: logger.error(f"[每日记录.交易] 保存失败: {e}", exc_info=True)
# 行 182: 保存银证转账 → 降 DEBUG + 加标记
# 行 184: logger.error(f"[每日记录.银证转账] 保存失败: {e}", exc_info=True)
# 行 196: 保存账户快照 → 降 DEBUG + 加标记
# 行 198: logger.error(f"[每日记录.账户快照] 保存失败: {e}", exc_info=True)
```

**position.py (routes) 改动（2条日志）：**

```python
# 行 177: logger.warning(f"[持仓路由] 获取股票走势数据失败: {e}")
# 行 185: logger.warning(f"[持仓路由] 获取期货走势数据失败: {e}")
```

**Step: Commit**

```bash
git add app/routes/stock_detail.py app/routes/daily_record.py app/routes/position.py
git commit -m "refactor: 统一路由层(详情/记录/持仓)日志标记"
```

---

### Task 7: 基础服务 — load_balancer.py + memory_cache.py + circuit_breaker.py + data_source_providers.py

**Files:**
- Modify: `app/services/load_balancer.py`
- Modify: `app/services/memory_cache.py`
- Modify: `app/services/circuit_breaker.py`
- Modify: `app/services/data_source_providers.py`

**load_balancer.py 改动（~30条日志）：**

标记已有 `[负载均衡]` 和 `[优先级负载]`，基本合规。改动：
- `[负载均衡]` 保持（已符合 `[模块]` 格式）
- `[优先级负载]` → `[负载均衡.优先级]`
- 无标记的 → 加 `[负载均衡]`

**memory_cache.py 改动（~13条日志）：**

标记已是 `[内存缓存]`，符合规范。改动：
- 保持 `[内存缓存]` 标记
- 行 112: info 保持（迁移完成是重要事件）
- 行 254: debug 保持
- 行 368: info 保持（清空是重要操作）
- 行 408/457/482: debug 保持

**circuit_breaker.py 改动（6条日志）：**

全是无标记，统一加 `[熔断器]`：

```python
# 行 66: logger.info(f"[熔断器] {platform} 冷却结束，进入试探")
# 行 87: logger.info(f"[熔断器] {platform} 恢复正常")
# 行 100: logger.warning(f"[熔断器] {platform} 试探失败，重新熔断")
# 行 107: logger.warning(f"[熔断器] {platform} 连续失败{...}次，熔断")
# 行 135: logger.info(f"[熔断器] {platform} 状态已重置")
# 行 138: logger.info("[熔断器] 所有平台状态已重置")
```

**data_source_providers.py 改动（8条日志）：**

标记已有部分 `[yfinance]`/`[twelvedata]`/`[polygon]`，改为统一格式：
- `[{self.name}]` → `[数据源.{self.name}]`
- `[yfinance]` → `[数据源.yfinance]`
- `[twelvedata]` → `[数据源.twelvedata]`
- `[polygon]` → `[数据源.polygon]`
- 全部保持 DEBUG

**Step: Commit**

```bash
git add app/services/load_balancer.py app/services/memory_cache.py app/services/circuit_breaker.py app/services/data_source_providers.py
git commit -m "refactor: 统一基础服务(负载均衡/缓存/熔断/数据源)日志标记"
```

---

### Task 8: 业务服务 — briefing.py(service) + earnings.py + wyckoff.py + notification.py + portfolio_advice.py

**Files:**
- Modify: `app/services/briefing.py`
- Modify: `app/services/earnings.py`
- Modify: `app/services/wyckoff.py`
- Modify: `app/services/notification.py`
- Modify: `app/services/portfolio_advice.py`

**briefing.py (services) 改动（9条日志）：**

```python
# 行 126: logger.error(f"[简报服务] 获取股票价格失败: {e}", exc_info=True)
# 行 135: logger.warning(f"[简报服务] 获取投资建议失败: {e}")
# 行 193: logger.warning(f"[简报服务] 获取PE数据失败: {e}")
# 行 217: logger.warning(f"[简报服务] 获取财报日期失败: {e}")
# 行 265: [指数数据] → [简报服务.指数]
# 行 378: [期货数据] → [简报服务.期货]
# 行 488: [美股板块] → [简报服务.美股板块]
# 行 716: logger.warning(f"[简报服务] 获取财报预警失败: {e}")
# 行 730: logger.warning(f"[简报服务] 获取走势数据失败: {e}")
```

**earnings.py 改动（12条日志）：**

```python
# 混合标记 → 统一 [财报.xxx]
# 行 110: logger.info(f"[财报.降级] {stock_code} 使用过期缓存")
# 行 113: logger.warning(f"[财报.降级] 获取过期缓存失败 {stock_code}: {e}")
# 行 123: [earnings] → [财报.降级]
# 行 153/175/200/204: 保持 DEBUG + 加 [财报]
# 行 185: [earnings/pe] → [财报.PE]
# 行 209: 加 [财报]
# 行 237: [earnings/pe] → [财报.PE]
# 行 353: [earnings/pe] → [财报.PE]
# 行 355: [earnings/pe] → [财报.PE]
```

**wyckoff.py 改动（10条日志）：**

```python
# 全是无标记，统一加 [威科夫.xxx]
# 行 55: logger.info(f"[威科夫.参考图] 保存: phase={phase}")
# 行 79: 保存成功 → 降 DEBUG
# 行 103: 删除成功 → 降 DEBUG
# 行 109: logger.info(f"[威科夫.分析] 保存: stock={stock_code}")
# 行 137: 保存成功 → 降 DEBUG
# 行 177: 删除成功 → 降 DEBUG
# 行 244: logger.warning(f"[威科夫.数据] {stock_code} 未获取到数据")
# 行 262: logger.error(f"[威科夫.数据] {stock_code} OHLCV获取失败: {e}", exc_info=True)
# 行 388: logger.warning(f"[威科夫.PE] 批量获取失败: {e}")
# 行 410: logger.warning(f"[威科夫.PE] {stock_code} 获取失败: {e}")
```

**notification.py 改动（5条日志）：**

标记已是 `[Notification]`，改为中文：
```python
# [Notification] → [通知]
# 行 36: logger.warning('[通知.Slack] 未配置')
# 行 45: logger.error(f'[通知.Slack] 推送失败: {e}', exc_info=True)
# 行 52: logger.warning('[通知.邮件] 未配置')
# 行 68: logger.error(f'[通知.邮件] 推送失败: {e}', exc_info=True)
# 行 272: logger.warning(f'[通知.AI报告] 生成失败: {e}')
```

**portfolio_advice.py 改动（4条日志）：**

标记已是 `[持仓建议]`，符合规范，保持不变。

**Step: Commit**

```bash
git add app/services/briefing.py app/services/earnings.py app/services/wyckoff.py app/services/notification.py app/services/portfolio_advice.py
git commit -m "refactor: 统一业务服务(简报/财报/威科夫/通知/建议)日志标记"
```

---

### Task 9: 辅助服务 — trade + position(service) + ocr + ai_analyzer + fed_rate + signal_*

**Files:**
- Modify: `app/services/trade.py`
- Modify: `app/services/position.py`
- Modify: `app/services/ocr.py`
- Modify: `app/services/ai_analyzer.py`
- Modify: `app/services/fed_rate.py`
- Modify: `app/services/signal_detector.py`
- Modify: `app/services/signal_cache.py`
- Modify: `app/services/backtest.py`

**trade.py 改动（9条日志）：**

全是无标记，加 `[交易]`。CRUD 操作的 info → 降 DEBUG：
```python
# 行 18: logger.debug(f"[交易] 保存: {data.get('stock_code')} {data.get('trade_type')}")
# 行 32: 保存成功 → 降 DEBUG
# 行 58: 删除 → 降 DEBUG
# 行 65: 同步删除 → 降 DEBUG
# 行 78: 更新 → 降 DEBUG
# 行 97: 因交易更新删除 → 降 DEBUG
# 行 131: logger.warning(f"[交易.结算] 失败: {stock_code} - {check['reason']}")
# 行 169: logger.info(f"[交易.结算] 成功: {stock_code}, 盈亏={profit:.2f}")
# 行 359: logger.warning(f"[交易] 获取K线数据失败: {stock_code}: {e}")
```

**position.py (services) 改动（~15条日志）：**

`[merge]` 标记改为 `[持仓.合并]`，CRUD 细节降 DEBUG：
```python
# 行 30: [merge] → [持仓.合并] 开始（保持 INFO）
# 行 37-102: [merge] 中间过程 → 全部降 DEBUG + [持仓.合并]
# 行 111: [merge] 完成（保持 INFO）
# 行 124: logger.info(f"[持仓] 保存快照: date={target_date}, count={len(positions)}")
# 行 148: 保存成功 → 降 DEBUG
# 行 197: logger.warning(f"[持仓] 获取 {stock_code} OHLC失败: {e}")
```

**ocr.py 改动：**

标记大部分合理，统一加 `[OCR]` 前缀：
```python
# 行 135: logger.debug(f"[OCR] 图片缩放: ...")（降 DEBUG）
# 行 193: logger.info(f"[OCR] 后端: ...")
# 行 348/352/354: [OCR] 保持
# 行 371: logger.info(f"[OCR] 开始识别: {image_path}")
# 行 397/432/436: 加 [OCR] 前缀
# 行 665/691/721/725: 加 [OCR.交易] 前缀
```

**ai_analyzer.py 改动（6条日志）：**

全是无标记，加 `[AI分析]`：
```python
# 行 92: logger.error(f"[AI分析] {code} 失败: {e}", exc_info=True)
# 行 201: logger.error(f"[AI分析] 收集 {stock_code} 数据失败: {e}", exc_info=True)
# 行 333: logger.error(f"[AI分析] API错误: {e.response.status_code}", exc_info=True)
# 行 336: logger.error(f"[AI分析] 返回非JSON: ...")
# 行 339: logger.error(f"[AI分析] 失败: {e}", exc_info=True)
# 行 361: logger.warning(f"[AI分析] 缓存结果失败: {e}")
```

**fed_rate.py 改动（5条日志）：**

全是无标记，加 `[美联储利率]`：
```python
# 行 159: logger.error(f"[美联储利率] 获取概率失败: {e}", exc_info=True)
# 行 179: logger.warning(f"[美联储利率] CME API 返回 {response.status_code}")
# 行 186: logger.warning(f"[美联储利率] 请求CME失败: {e}")
# 行 189: logger.warning(f"[美联储利率] 解析CME失败: {e}")
# 行 241: logger.error(f"[美联储利率] 解析异常: {e}", exc_info=True)
```

**signal_detector.py 改动（2条日志）：**

标记已是 `[SignalDetector]`，改中文：
```python
# 行 24: [SignalDetector] → [信号检测]
# 行 53: [SignalDetector] → [信号检测]
```

**signal_cache.py 改动（4条日志）：**

标记已是 `[SignalCache]`，改中文：
```python
# [SignalCache] → [信号缓存]
```

**backtest.py 改动（2条日志）：**

标记已是 `[Backtest]`，改中文：
```python
# [Backtest] → [回测]
```

**Step: Commit**

```bash
git add app/services/trade.py app/services/position.py app/services/ocr.py app/services/ai_analyzer.py app/services/fed_rate.py app/services/signal_detector.py app/services/signal_cache.py app/services/backtest.py
git commit -m "refactor: 统一辅助服务日志标记 + CRUD操作降噪"
```

---

### Task 10: 剩余文件 — 迁移/日历/缓存/DB重试/市场识别/StockMeta

**Files:**
- Modify: `app/services/cockroach_migration.py`
- Modify: `app/services/migration.py`
- Modify: `app/services/trading_calendar.py`
- Modify: `app/services/cache_validator.py`
- Modify: `app/services/market_session.py`
- Modify: `app/utils/db_retry.py`
- Modify: `app/utils/market_identifier.py`
- Modify: `app/services/stock_meta.py`

**cockroach_migration.py 改动（12条日志）：**

全是无标记/部分标记，统一加 `[CockroachDB迁移]`。

**migration.py 改动（12条日志）：**

全是无标记，加 `[数据迁移]`。

**trading_calendar.py 改动（6条日志）：**

全是无标记，加 `[交易日历]`。全部保持现有级别。

**cache_validator.py 改动（2条日志）：**

全是 DEBUG，加 `[缓存验证]`。

**market_session.py 改动（1条日志）：**

加 `[市场时段]`。

**db_retry.py 改动（4条日志）：**

标记已是 `[CockroachDB]`，改为 `[DB重试]`：
```python
# [CockroachDB] → [DB重试]
```

**market_identifier.py 改动（2条日志）：**

加 `[市场识别]`：
```python
# 行 40: logger.warning(f"[市场识别] 无效的股票代码: {code}")
# 行 78: logger.warning(f"[市场识别] 无法识别市场类型: {code}")
```

**stock_meta.py 改动（1条日志）：**

标记已是 `[StockMeta]`，保持不变。

**Step: Commit**

```bash
git add app/services/cockroach_migration.py app/services/migration.py app/services/trading_calendar.py app/services/cache_validator.py app/services/market_session.py app/utils/db_retry.py app/utils/market_identifier.py app/services/stock_meta.py
git commit -m "refactor: 统一剩余模块日志标记(迁移/日历/缓存/重试等)"
```

---

### Task 11: 最终验证 + 运行测试

**Step 1: 启动应用验证无报错**

Run: `cd D:\Git\stock && python -c "from app import create_app; app = create_app(); print('启动成功')"`
Expected: 启动成功（无 ImportError、无语法错误）

**Step 2: 检查日志文件输出**

Run: `cd D:\Git\stock && python -c "
from app import create_app
app = create_app()
with app.app_context():
    from app.services.unified_stock_data import UnifiedStockDataService
    svc = UnifiedStockDataService()
    print('服务初始化成功')
"`

检查 `data/logs/app.log` 确认日志格式正确。

**Step 3: 搜索遗留的不规范日志**

用 grep 搜索项目中是否还有不符合规范的日志：
- 搜索 `logger.error` 但不含 `exc_info` 的行
- 搜索 `logger.info` 或 `logger.warning` 不以 `[` 开头的行

修复遗留问题。

**Step: Final Commit**

```bash
git add -A
git commit -m "fix: 修复遗留的不规范日志"
```
