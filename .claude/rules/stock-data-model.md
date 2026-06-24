# 数据模型与入库

> **何时读**：改 schema、Stock/StockCategory 表、写 seeds、多账户合并、OCR 入库流程、双 DB（stock.db/private.db）选型、股票/期货/指数代码配置
> **不必读**：缓存/统一数据API（见 stock-data-cache.md）/ 取数源坑（见 data-fetch-conventions.md）

## 核心数据模型

**数据模型**：按日期保存持仓快照，`(date, stock_code)` 为唯一约束

**Stock 表约定**：PK 是 `stock_code` 字符串（非自增 id），列 `(stock_code, stock_name, investment_advice, created_at, updated_at, tags)`；库只存用户关注池（远小于全 A 股），不是全市场快照。新标的通过 `app/seeds/` 幂等注入。

**多账户合并**：同一股票多次出现时，数量相加，成本按加权平均计算

**OCR 流程**：图片上传 → Pillow 预处理 → Tesseract 识别 → 正则解析提取股票代码/名称/数量/价格

**模块级单例的 Flask context 陷阱**：`app/services/__init__.py` 的 `unified_stock_data_service = UnifiedStockDataService()` 在 import 期就会触发 `__init__`，此时无 Flask app context；任何访问 `db.session` 或 `<Model>.query` 的 init 期代码必须用 `has_app_context()` 守卫

**启动数据种子**：`app/seeds/` 放幂等数据 seed（区别于 `migrate_*` 改 schema），在 `create_app()` 里紧跟迁移调用。铁律：已存在的 `Stock.stock_name` / `investment_advice` / `StockCategory` 归属**一律不覆盖**，失败只记 warning 不抛出。`StockCategory.stock_code` 唯一约束 → 一只股票只能归属一个分类；跨板块引用（如 002916 深南电路在 PCB 同时被 CPU 产业链引用）只能保留现状并在 advice 文案里描述关联。

## 存储与代码配置

## 股票代码配置

期货、指数代码配置在 `app/config/stock_codes.py`，股票代码从数据库 `Stock` 和 `StockCategory` 表获取。

**配置项**：期货 / 指数 / 分类代码常量见 `app/config/stock_codes.py`（`FUTURES_CODES` / `INDEX_CODES` / `CATEGORY_CODES` / `CATEGORY_NAMES`）。

**股票代码管理**：
- 股票代码存储在 `Stock` 表，可通过界面编辑
- 股票分类存储在 `StockCategory` 表，关联 `Category` 表

## 数据存储

- 数据库：`data/stock.db`（公共：股票池 / 新闻 / 缓存）
- 私密数据库：`data/private.db`（带 `__bind_key__ = 'private'` 的模型 → Position / RebalanceConfig / StockWeight / PositionPlan / DailySnapshot / Trade / Settlement / BankTransfer）。直连查询用 `sqlite3.connect('data/private.db')`，不要连 `stock.db`
- 内存缓存持久化：`data/memory_cache/{stock_code}/{cache_type}.pkl`
- 上传图片：`uploads/`
