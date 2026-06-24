# CLAUDE.md rules 重构设计

> 日期：2026-06-24
> 范围：`.claude/rules/` 整套 rule 文件的拆分 / 整理 / 完善 + CLAUDE.md 路由表 + 外部引用同步
> 组织轴：task-trigger（「改 X 前读 Y」），激进重做边界但保留触发哲学

## 目标

四个诉求一次到位：

1. **拆分**：把混轴超载文件按主题切开（`data-architecture.md` 150 行 / `dev-conventions.md` 81 行 / `docs-and-portfolio.md` 93 行）
2. **整理**：跨文件重复内容收敛到唯一源，其余留 `> 见 X` 指针
3. **完善**：质量归一化（统一 header、触发描述露出高频坑），**不发明新规则**
4. **修路由**：重写 CLAUDE.md 路由表 + 同步所有外部深链

非目标：发明无证据的新 rule；改 `data-fetch-conventions.md` 文件名（保名省深链连带改）。

## 最终文件清单（12 个）

| 文件 | 来源 | 状态 |
|---|---|---|
| `stock-data-cache.md` | data-architecture.md 缓存/API 部分 | 改名+瘦身 |
| `stock-data-model.md` | data-architecture.md 入库部分 + dev-conventions 双DB/代码配置 | NEW |
| `data-fetch-conventions.md` | 原样 | 保名，仅消重 A+H 段 |
| `notifications.md` | notification-formatting.md + data-architecture 推送语义 | 改名+扩容 |
| `news-and-research.md` | 原样 | 保名，GITHUB_RELEASE_REPOS 收为唯一源 |
| `esports.md` | 原样 | 保名，补 cross-ref |
| `watch.md` | 原样 | 保名 |
| `supply-chain.md` | 原样 | 保名 |
| `docs-conventions.md` | docs-and-portfolio.md 写作规范部分 | NEW |
| `portfolio-valuations.md` | docs-and-portfolio.md skill 行为部分 | NEW |
| `dev-environment.md` | dev-conventions.md 环境/工作流部分 | 改名+瘦身 |
| `llm.md` | 原样 | 保名，补 header |

被删除的旧文件名：`data-architecture.md`、`dev-conventions.md`、`docs-and-portfolio.md`、`notification-formatting.md`。

## 内容归属（逐块映射）

### `data-architecture.md`(150) 拆三路

- **→ `stock-data-cache.md`**：`_SafeJsonProvider` JSON 安全序列化；统一股票数据 API 全部（MarketIdentifier / 两层缓存架构 / 缓存刷新策略 / TTL 表 / SmartCacheStrategy / Volume 单位契约 / VOLUME_UNIT_SCHEMA_VERSION / A 股行情数据特征(节假日/一字涨停) / 数据源 / 策略数据协作 / 核心组件 UnifiedStockDataService·CacheValidator·UnifiedStockCache / 统一数据格式 / 调用链路）
- **→ `stock-data-model.md`**：数据模型(按日期快照,`(date,stock_code)`唯一)；Stock 表约定；多账户合并；OCR 流程；模块级单例 Flask context 陷阱；启动数据种子(seeds 铁律)
- **→ `notifications.md`**：数据获取服务失败语义二分（None vs 空 dict + exc_info）；新闻推送多分支去重（InterestPipeline）

### `dev-conventions.md`(81) 拆三路

- **→ `stock-data-model.md`**：数据存储（双 DB stock.db/private.db + memory_cache + uploads）；股票代码配置（FUTURES/INDEX/CATEGORY_CODES）
- **→ `dev-environment.md`**：Windows 坑点全部（编码/PYTHONIOENCODING/作用域/管道吞stdout/后台日志/crawl4ai进度条/create_app开销/只读DB巡检/表名查sqlite_master/wc-l/heredoc/rtk env顺序/Bash cwd持久）；开发规范（测试目录布局/一次性脚本不入库/sys.path/配置变更同步三处/amend重验HEAD/并行session抢git index）；安装第三方仓库→改为 cross-ref 指 news-and-research
- **→ CLAUDE.md 概述**：技术栈（合并补充 RapidOCR/Twelve Data/Polygon/PyTorch 等细节，删独立段）

### `docs-and-portfolio.md`(93) 拆两路

- **→ `docs-conventions.md`**：docs 目录约定；一级 sector 枚举；跨板块 sector 归属准则；锂电/储能归 energy；Frontmatter 约定(5 类 doc_type + conviction_date date 对象坑)；跨文档引用 related_docs；Lint 脚本(含 Windows+并发坑)
- **→ `portfolio-valuations.md`**：持仓再平衡报告输出；docs 是选股池；估值汇总页/valuations；A+H 双重上市口径铁律(唯一源)；ADR+港股 fungible 对比

## 跨文件重复 → 唯一源

| 重复内容 | 唯一源 | 其余处理 |
|---|---|---|
| A+H 估值口径铁律 | `portfolio-valuations.md` | `data-fetch-conventions.md` 只留「H 口径市值自洽校验算法」（取数细节）；docs/SKILL 留 `> 见 portfolio-valuations.md` |
| GITHUB_RELEASE_REPOS 同步 | `news-and-research.md` | `dev-environment.md` 留一行 cross-ref |
| Windows PYTHONIOENCODING | `dev-environment.md` | `docs-conventions.md` lint 坑留 `> 编码坑见 dev-environment.md` |
| 失败语义 exc_info | `notifications.md` | `esports.md`/news 留 cross-ref |

## 完善（归一化，不新增内容）

1. 每个文件统一 `> 何时读 / 不必读` header（补 `llm.md` 等缺失的）
2. CLAUDE.md 路由表触发描述露出埋没的高频坑：「并行 session 抢 git index」「worldcup 已并入 esports」「cache_only 首屏秒开」
3. 消重后统一 `> 见 X` 指针格式

## 外部引用同步

**必改（live 资产）**：

- `.claude/skills/stock-deep-redo/SKILL.md`：
  - L43 归属准则 → `docs-conventions.md`
  - L106 「电池厂是锂买方」→ `docs-conventions.md`
  - L133 目录/frontmatter/lint/related_docs → `docs-conventions.md`
  - L134 「data-architecture.md（缓存）」→ `stock-data-cache.md`
  - L135 「dev-conventions.md（Windows…）」→ `dev-environment.md`
  - L39 「data-fetch-conventions.md 港股节」→ 保名不改（A+H 自洽校验算法仍在该文件）
- `CLAUDE.md` 路由表：重写 12 条 + 修触发描述

**path-only（历史档，仅改路径不动正文）**：

- `docs/superpowers/specs/2026-06-21-估值页板块排序联动-design.md` → `portfolio-valuations.md`
- `docs/superpowers/plans/2026-06-24-minerals-page.md` → `docs-conventions.md`

**无需改**：`.claude/skills/stock-deep-redo/references/playbook.md`（指 data-fetch，保名）；`graphify-out/*.json`（图谱缓存自动重建）

## 验收标准

- 12 个 rule 文件存在，4 个旧文件名已删（`git mv` 或新建+删）
- 每个文件有统一 header；无跨文件重复正文（重复点只剩唯一源 + 指针）
- `grep -rn "data-architecture\|dev-conventions\|docs-and-portfolio\|notification-formatting" .claude/ docs/ CLAUDE.md` 仅命中 graphify 缓存（或零命中）
- CLAUDE.md 路由表 12 条与实际文件一一对应
- 重构后任取一个「改 X 前」场景，能从路由表唯一定位到该读的文件

## 风险

- 内容搬迁易漏段：拆分时逐块对照本设计「内容归属」清单核验，确保 150+81+93 行无遗漏
- 深链改漏：完成后跑验收 grep 兜底
- 并行 session 抢 git index：`git add` 与 `git commit` 同一条命令链，精确路径不用 `-A`
