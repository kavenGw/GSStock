---
paths:
  - "app/models/**"
  - "app/seeds/**"
  - "app/config/stock_codes.py"
---
# 数据模型与入库

> **何时读**：改 schema、Stock/StockCategory 表、写 seeds、多账户合并、OCR 入库、双 DB 选型、期货/指数代码配置

## 模型约定

- 持仓按日期存快照，`(date, stock_code)` 唯一。多账户合并：数量相加、成本加权平均。
- `Stock` 表 PK 是 `stock_code` 字符串，列 `(stock_code, stock_name, investment_advice, created_at, updated_at, tags)`；只存用户关注池，非全市场。`StockCategory.stock_code` 唯一 → 一股一类，跨板块引用只能在 advice 文案里描述。
- **seeds**：`app/seeds/` 放幂等数据 seed（区别于 `migrate_*` 改 schema），`create_app()` 里紧跟迁移调用。铁律：已存在的 `stock_name` / `investment_advice` / `StockCategory` 归属一律不覆盖，失败只 warning。
- **模块级单例陷阱**：`app/services/__init__.py` 的 `unified_stock_data_service = UnifiedStockDataService()` 在 import 期触发 `__init__`，无 app context；init 期访问 `db.session` / `<Model>.query` 必须 `has_app_context()` 守卫。
- OCR：图片上传 → Pillow 预处理 → RapidOCR(ONNX) 识别 → 正则解析代码/名称/数量/价格。

## 代码配置

期货/指数/分类常量在 `app/config/stock_codes.py`（`FUTURES_CODES` / `INDEX_CODES` / `CATEGORY_CODES` / `CATEGORY_NAMES` / `WATCH_CODES` / `MARKET_INDICES`）；股票代码从 `Stock` 与 `StockCategory` 表读，界面可编辑。

## 存储位置

- `data/stock.db` — 公共（股票池 / 新闻 / 缓存）
- `data/private.db` — `__bind_key__ = 'private'` 的模型：Position / RebalanceConfig / StockWeight / PositionPlan / DailySnapshot / Trade / Settlement / BankTransfer。直连查询连 `private.db`。
- `data/memory_cache/{code}/{cache_type}.pkl` — 内存缓存持久化；`uploads/` — 上传图片
