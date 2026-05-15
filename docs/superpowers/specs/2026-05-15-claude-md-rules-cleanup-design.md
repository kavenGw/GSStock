# CLAUDE.md 与 rule 文件整理 — 设计

> 日期：2026-05-15
> 范围：`CLAUDE.md` + `.claude/rules/*.md`（9 个）
> 目标：去重 / 重组 / 删除过时 / 改善索引四合一

## 0. 决策摘要（已与用户拍板）

| 决策 | 选择 |
|---|---|
| CLAUDE.md「硬约束」区块 | 全部下沉到对应 rule，CLAUDE.md 只留索引 + 通用约定 2 行 |
| rule 文件边界 | 保留现有 9 个文件，只改内容 |
| 过时验证强度 | 信任判断直接删，路径引用类 spot-grep |

## 1. 目标态结构

```
CLAUDE.md (~35 行) — 纯导航
├── 项目概述（3 行 + 通用约定 1 行：响应中文 / 不写多余注释 / 不写 backup）
├── 启动 + 测试命令（含 rtk + UTF-8 + SCHEDULER_ENABLED=0 三件套，1 行提醒 rtk 链式 && 也要前缀）
├── Rules 路由表（保持当前「何时读 / 不必读」格式，9 行）
└── graphify 模块说明（保留不动）

.claude/rules/*.md (9 个) — 权威详情
└── 单一权威原则：每条规则只在 1 个文件有完整版
```

**单一权威示例**：
- Volume 单位契约 → 只在 `data-architecture.md`
- commit --amend SHA 校验 → 只在 `dev-conventions.md`
- stock_name 反查 → 只在 `data-fetch-conventions.md`

CLAUDE.md 不再复述任何上述细节。

## 2. CLAUDE.md 硬约束 10 条的下沉映射

| # | 条目摘要 | 去向 | 操作 |
|---|---|---|---|
| 1 | 响应中文 / 不写多余注释 / 不写 backup | **保留** CLAUDE.md "项目概述" 末行 | 通用约定，每会话必读 |
| 2 | rtk 前缀（链式 && 也要） | **保留** CLAUDE.md "启动命令"区 | 通用约定，每会话必读 |
| 3 | PYTHONIOENCODING=utf-8 SCHEDULER_ENABLED=0 | `dev-conventions.md` | 删 CLAUDE.md；rule 已 cover |
| 4 | Volume 单位 / VOLUME_UNIT_SCHEMA_VERSION | `data-architecture.md` | 删 CLAUDE.md |
| 5 | 缓存时区 / 禁用 date.today() | `data-architecture.md` | 删 CLAUDE.md + **补 rule 明示警告**（当前 rule 仅提 SmartCacheStrategy，未明示「禁用 date.today()」） |
| 6 | 私有数据库 / `__bind_key__='private'` | `dev-conventions.md` | 删 CLAUDE.md |
| 7 | Flask context 守卫 | `data-architecture.md` | 删 CLAUDE.md |
| 8 | stock_name 反查 | `data-fetch-conventions.md` | 删 CLAUDE.md |
| 9 | commit --amend 前 git rev-parse 校验 | `dev-conventions.md` | 删 CLAUDE.md |
| 10 | 新建分析文档前 Glob 历史档案 | `docs-and-portfolio.md` | 删 CLAUDE.md |

只有 #1 #2 留在 CLAUDE.md，因为它们**每个任务都必须遵守**；其余 8 条「改某模块时才相关」，按需加载更高效。

## 3. 各 rule 文件清理清单

### data-architecture.md（198 → 约 150 行）

**删除**：
- 「服务层模式」整段（仅一句"业务逻辑放在 services/"的废话）
- 调用链路 ASCII 树（约 35 行，全是 `X.method() → UnifiedStockDataService.get_trend_data()` 的低密度罗列）→ 压缩为 1 句「所有持仓/期货/盯盘/预加载/季报服务统一走 `UnifiedStockDataService` 的 `get_trend_data` / `get_realtime_prices` / `get_indices_data`」

**合并**：
- UnifiedStockDataService 「单例模式」在 2 处重复声明 → 合并
- JSON 实时价格示例 + 「API 返回结构契约」 → 整合为单节

**补充**：
- 「Volume 单位契约」或「缓存架构」章节补一句明示警告：缓存 lookup/save 一律走 `SmartCacheStrategy.get_effective_cache_date()`，**禁用 `date.today()`**（来自原 CLAUDE.md 硬约束 #5）

**待验证后处理**：
- 「Stock 表只存用户关注池（~50 条）」数字可疑 → 实施阶段 sqlite3 直连 count，>100 则改为「~N 条用户关注池（远小于全 A 股）」或直接去掉数字

### data-fetch-conventions.md（26 行）

不动。已是 8 条精华，硬约束 #8 已在。

### dev-conventions.md（85 → 约 75 行）

**删除**：
- 「运行单测」命令章节（与 CLAUDE.md "常用命令" 重复）

**压缩**：
- 「技术栈」列表 → 1-2 行单行表达
- 「股票代码配置」4 个常量名罗列 → 1 行 "详见 `app/config/stock_codes.py`"

**保留**：Windows 编码 / heredoc / 管道吞 stdout / create_app 副作用 等坑点（高价值，无替代）

### docs-and-portfolio.md

不动。`docs/superpowers/specs/2026-05-10-portfolio-shortlist-design.md` 路径已 verify 存在。

### esports.md（24 行）

**待验证后处理**：
- 「NBA晚间调度：每天18:00额外执行一次NBA监控设置」→ 实施阶段 grep `app/strategies/` 含 `18` 或 `nba` 的 cron 表达式；不存在则删该行

其余不动。

### llm.md（15 行）

不动。已极简。

### news-and-research.md（75 → 约 70 行）

**压缩**：
- 「动态发现逻辑（`app/services/plugin_discovery.py`）」4 行实现细节 → 1 行 "动态条目 key 加 `marketplace_` 前缀避免冲突；非 github 源 / JSON 损坏静默降级"

**保留**：「smoke test 空列表 != 代码坏」类细节高价值。

### notification-formatting.md（66 行）

不动。结构清晰。

### watch.md（23 行）

不动。

## 4. 验证步骤（实施阶段执行）

实施 plan 会包含 3 个 spot-grep 验证：

1. `sqlite3 data/stock.db "SELECT COUNT(*) FROM stocks;"` → 决定 data-architecture.md "~50 条" 改法
2. `Grep "0 18 \* \* \*" app/strategies/ app/services/` → 决定 esports.md "NBA 18:00" 是否删
3. `Glob docs/superpowers/specs/2026-05-10-portfolio-shortlist-design.md` → 已 verify 存在，跳过

## 5. 预估影响

| 项目 | Before | After | Δ |
|---|---:|---:|---:|
| CLAUDE.md | 63 行 | ~35 行 | -45% |
| data-architecture.md | 198 行 | ~150 行 | -24% |
| dev-conventions.md | 85 行 | ~75 行 | -12% |
| news-and-research.md | 75 行 | ~70 行 | -7% |
| 其余 6 个 rule | 113 行 | 113 行 | 0% |
| **合计** | **534 行** | **~443 行** | **-17%** |

**每会话节省**：CLAUDE.md 总是被加载 → 稳定省约 28 行/会话；rule 文件按需加载，节省随场景变化。

## 6. 非目标

- 不动 rule 文件边界（用户已拍板）
- 不动 `.claude/skills/` 下的 skill 定义
- 不动用户级 `~/.claude/CLAUDE.md`（含 RTK / OMC 部分）
- 不动 `docs/` 下任何已有内容
- 不做 rule 内部章节顺序的"美化"重排，只删合补

## 7. 风险

| 风险 | 应对 |
|---|---|
| 删除硬约束后某条规则在 rule 里覆盖度不够 | 实施前对照 mapping 表逐条 grep rule 文件内是否真有对应内容；不够则补 |
| spot-grep 误判（如 cron 表达式写法多样） | grep 两种以上表达式后再决定 |
| 用户级 / 项目级 CLAUDE.md 同时被加载导致 rtk 冗余 | 不处理 —— 用户级 CLAUDE.md 是用户私有 |

## 8. 后续动作

- spec 通过后 → invoke `superpowers:writing-plans` 出实施 plan
- 实施 plan 会拆为：①CLAUDE.md 重写 ②按 rule 文件逐个修改 ③验证 grep ④commit
