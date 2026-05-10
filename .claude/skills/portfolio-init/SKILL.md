---
name: portfolio-init
description: 首次配置或主题权重大调时调用。从 docs/analysis/ 已分析的股票池中筛选 15-25 只重点池，按主题权重分配目标仓位（100 股倍数），写入 RebalanceConfig 和 StockWeight 表。v2: 评级与主题归属从 docs frontmatter 读取，HTML 报告含锚点导航 + 持仓盈亏 + 内联理由 + 文档链接。
---

# Portfolio Init — 首次持仓配置（v2）

## 何时使用

- 第一次跑配置（StockWeight 表为空 / 全部 selected=False）
- 主题权重大调（修改了 config.yaml）
- 季报集中发布后需要重新筛重点池

**日常再平衡不要用本 skill，用 `/portfolio-rebalance`。**

## v2 关键变化

- 评级（core/config/watch/exclude）+ 主题归属（themes[0]）+ 选股理由（thesis）从 `docs/analysis/*.md` 顶部 YAML frontmatter 读取
- SKILL.md 不再硬编码「主题 → 股票」对照表
- stock_code 反查统一为单个函数：frontmatter > stock 表 > supply_chain.py
- HTML 模板升级 v2：sticky 主题导航 + 持仓盈亏 + 内联理由 + 文档链接 + 迁移待办段
- 未补 frontmatter 的旧 docs：用 `config.yaml.migration_fallback` 兜底，不阻塞流程

## 工作流

### 第 0 步：读取配置 + schema 校验

1. 读共享配置 `.claude/skills/portfolio-init/config.yaml`，提取 `themes` / `rules` / `metadata_schema` / `migration_fallback` / `migration_exclude`

2. 读本地配置 `.claude/skills/portfolio-init/local-config.yaml`：
   - **如果文件不存在** → 立即报错并停止执行：
     ```
     ⚠️ 本地配置缺失。请按以下步骤创建：
     1. cp .claude/skills/portfolio-init/local-config.yaml.example .claude/skills/portfolio-init/local-config.yaml
     2. 编辑 local-config.yaml 把 portfolio.output_dir 填写为 HTML 报告输出绝对路径（建议在 git 工程外，如 D:\Git\GSStockHold 或 ~/portfolio）
     3. 重新运行 /portfolio-init
     ```
   - **如果 `portfolio.output_dir` 为空** → 报错提示填写后重试

3. 校验 / 准备 `output_dir`：不存在则自动 `mkdir -p`（Python `pathlib.Path(p).mkdir(parents=True, exist_ok=True)`）

4. **schema 完整性检查**：`migration_fallback` 的 key 集合必须 ⊆ `themes` 的 key 集合；不一致直接报错（防 typo）

### 第 1 步：确认总资产

1. 查 `data/private.db` 的 `rebalance_config` 表
2. 如果 `target_value` > 0 → 问用户："当前 RebalanceConfig.target_value=¥X，是否更新？"
3. 如果为 0 或用户确认更新 → 问用户："请确认目标总资产（账户实际总资产）"
4. 写入 `UPDATE rebalance_config SET target_value=?, updated_at=NOW()` 或 INSERT 一行

### 第 2 步：读最新持仓快照（含成本/盈亏）

```sql
SELECT date, stock_code, stock_name, quantity, total_amount, current_price
FROM positions
WHERE date = (SELECT MAX(date) FROM positions)
ORDER BY total_amount DESC;
```

对每只持仓股：
- `avg_cost = total_amount / quantity`
- 取实时价（同 §6 的 UnifiedStockDataService）
- `mv = quantity × realtime_price`
- `pnl = mv - total_amount`
- `pnl_pct = pnl / total_amount`

输出汇总：总市值 / 持仓股数 / 现金估算 = `target_value - 持仓市值`。

### 第 3 步：universe scan（统一函数）

伪代码：

```python
def scan_universe(docs_root, config):
    """扫 docs/analysis/**/*.md，返回 universe 列表 + 待迁移清单。"""
    raw_entries = []
    migration_pending = []

    for md in glob('docs/analysis/**/*.md'):
        fm = parse_frontmatter(md)  # YAML 头解析；失败返回 None

        if fm and 'stock_code' in fm:
            entry = {
                'stock_code': fm['stock_code'],
                'stock_name': fm['stock_name'],
                'themes': fm['themes'],          # array, themes[0] 主
                'rating': fm['rating'],
                'conviction_date': fm['conviction_date'],
                'thesis': fm.get('thesis', ''),
                'watch_reason': fm.get('watch_reason'),
                'exclude_reason': fm.get('exclude_reason'),
                'doc_path': md,
            }
            raw_entries.append(entry)
        else:
            # fallback：先查 migration_exclude，再查 migration_fallback.themes
            fb = fallback_from_filename(md, config)
            if fb:
                fb['doc_path'] = md
                fb['_fallback'] = True
                raw_entries.append(fb)
                migration_pending.append(md)
            # 完全无法识别（既非主题股也非排除股）→ 跳过

    # 按 stock_code 去重，conviction_date desc + 文件名字典序后者
    by_code = {}
    for entry in sorted(raw_entries,
                        key=lambda e: (e['conviction_date'], str(e['doc_path'])),
                        reverse=True):
        code = entry['stock_code']
        if code not in by_code:
            entry['related_docs'] = []
            by_code[code] = entry
        else:
            by_code[code]['related_docs'].append(entry['doc_path'])

    # 校验 themes[0] 必须在 config.themes 内
    valid_themes = set(config['themes'].keys())
    for entry in by_code.values():
        if entry['themes'][0] not in valid_themes:
            raise ValueError(f"未知主题 {entry['themes'][0]} in {entry['doc_path']}")

    return list(by_code.values()), migration_pending


def fallback_from_filename(md_path, config):
    """无 frontmatter 时按文件名关键词兜底。"""
    name = md_path.stem  # 去 .md
    # 1. 先查 migration_exclude
    for item in config['migration_exclude']:
        if item['keyword'] in name:
            return {'rating': 'exclude', 'exclude_reason': item['reason'],
                    'stock_name': item['keyword'],
                    'stock_code': resolve_stock_code(item['keyword']),
                    'themes': ['_fallback'],  # 占位，不参与主题分组
                    'conviction_date': extract_date_from_filename(md_path),
                    'thesis': ''}
    # 2. 再查 migration_fallback.themes
    for theme_key, theme_cfg in config['migration_fallback'].items():
        for kw in theme_cfg['keywords']:
            if kw in name:
                return {'rating': theme_cfg['default_rating'],
                        'stock_name': kw,
                        'stock_code': resolve_stock_code(kw),
                        'themes': [theme_key],
                        'conviction_date': extract_date_from_filename(md_path),
                        'thesis': ''}
    return None
```

`resolve_stock_code()` 反查链：

```python
def resolve_stock_code(name, frontmatter_entry=None):
    """frontmatter > data/stock.db > app/config/supply_chain.py."""
    if frontmatter_entry and frontmatter_entry.get('stock_code'):
        return frontmatter_entry['stock_code']

    # 查 stock 表（用 sqlite3 直连即可，不必 create_app）
    import sqlite3
    conn = sqlite3.connect('data/stock.db')
    row = conn.execute("SELECT stock_code FROM stock WHERE stock_name=?", (name,)).fetchone()
    if row:
        return row[0]

    # 查 supply_chain.py
    from app.config.supply_chain import SUPPLY_CHAIN_GRAPHS
    for graph in SUPPLY_CHAIN_GRAPHS.values():
        for layer in ('upstream', 'midstream', 'downstream'):
            for company in graph.get(layer, {}).get('companies', []):
                if company.get('name') == name:
                    return company.get('code')
    return None
```

找到 stock_code 后如果 stock 表没有，幂等 INSERT：

```sql
INSERT OR IGNORE INTO stock (stock_code, stock_name, created_at, updated_at)
VALUES (?, ?, datetime('now'), datetime('now'));
```

### 第 4 步：按主题分组（数据驱动）

```python
themes_universe = {tk: [] for tk in config['themes']}
exclude_pool = []
watch_pool = []
for entry in universe:
    if entry['rating'] == 'exclude':
        exclude_pool.append(entry)
    elif entry['rating'] == 'watch':
        watch_pool.append(entry)
        themes_universe[entry['themes'][0]].append(entry)  # watch 也归主题展示
    else:  # core / config
        themes_universe[entry['themes'][0]].append(entry)
```

**不再硬编码主题→股票表**。跨主题股以 `themes[0]` 计仓，其他 themes 仅在 HTML 表格的"附属主题"列展示（如「生益科技 主：CPU+封测+PCB / 附：AI算力」）。

### 第 5 步：评级（直接读 frontmatter）

`rating` 已在 §3 取出，无需再推理。watch / exclude 的具体保留原因取自 frontmatter 的 `watch_reason` / `exclude_reason` 枚举，HTML 渲染时映射 `metadata_schema` 的中文描述。

### 第 6 步：算目标仓位（B-动态规则）

对每个主题：
1. 主题市值 = `target_value × theme.weight`
2. 主题内核心股占 60-80%，配置股填剩余
3. **单股市值上限** = 主题市值 × `single_stock_max_pct_of_theme`（即主题权重的 50%）
4. 取实时价：调用 `UnifiedStockDataService.get_realtime_prices(codes)`
5. 目标股数 = `floor(单股目标市值 / 现价 / 100) × 100`
6. 如果目标股数 = 0，标"目标过小，建议提高总市值或调整权重"

实时价获取代码示例：

```python
import os
os.environ['SCHEDULER_ENABLED'] = '0'
from app import create_app
app = create_app()
with app.app_context():
    from app.services.unified_stock_data import UnifiedStockDataService
    svc = UnifiedStockDataService()
    prices = svc.get_realtime_prices(all_codes)
    for code, info in prices.items():
        print(code, info.get('name'), info.get('price'))
```

### 第 7 步：写库

```sql
DELETE FROM stock_weights;
INSERT INTO stock_weights (stock_code, weight, selected, updated_at)
VALUES (?, ?, ?, datetime('now'));
```

- 核心 / 配置：`selected=True`，`weight = 该股目标市值 / target_value`（**保留原始 float**，不要 round）
- 观察：`selected=False`，`weight=0`
- 排除：不入库

### 第 8 步：输出 markdown

按以下结构输出（直接打印到对话）：

```markdown
## 持仓首次配置（YYYY-MM-DD）

### 总资产
目标总市值 ¥X | 当前持仓 ¥X | 可用现金 ¥X

### 当前持仓快照
| 代码 | 名称 | 股数 | 成本价 | 现价 | 浮盈亏 | 浮盈亏% | 市值 |
|------|------|------|------|------|------|------|------|
| 600600 | 青岛啤酒 | 1000 | 58.20 | 62.46 | +¥4,260 | +7.3% | ¥62,460 |

### 重点池（共 N 只）

#### AI 算力（目标 30% / ¥X，单股上限 ¥X）
| 代码 | 名称 | 评级 | 主题占比 | 目标股数 | 现价 | 目标市值 | 选股理由 |
|------|------|------|---------|---------|------|---------|---------|
| 601138 | 工业富联↗ | 核心 | 38.9% | 800 | 63.28 | ¥50,624 | AI 服务器代工龙头，2026Q1 营收+45%（来自 buffett 2026-05-09）|

[其他主题同样格式]

### 观察池（共 N 只，selected=False，weight=0）
按主题分组，每条 1 行：
- 002636 金安国纪 (CPU+PCB) | watch:估值偏高 | 评级 04-30 | thesis 简短 ↗

### 排除池（共 N 只，不入库）
按 reason 分组：
- 主题外（5）：万华化学、巨化股份、昊华化学、药明康德、东吴证券
- 跨市场（2）：安踏体育、甲骨文

### 元数据迁移待办
N 个 docs 缺 frontmatter，已用 fallback 填默认值，建议补全：
- docs/analysis/2026-04-21-工业富联-buffett分析.md
  建议：rating=core, themes=[ai_compute], thesis="…"

### 下一步
运行 `/portfolio-rebalance` 生成首次建仓操作清单。
```

注意 §8 markdown 不再有独立的「选取理由」列表段；理由直接进重点池表的「选股理由」列。

### 第 9 步：生成 HTML 报告（v2 模板）

把第 8 步内容渲染为 HTML，写到 `{output_dir}/portfolio-init-{YYYY-MM-DD}.html`（按日覆盖）。

**步骤**：

1. Read 模板 `.claude/skills/portfolio-init/report-template.html`（v2，含 `{NAV}` 占位符）
2. 渲染主题导航：
   ```html
   <nav class="theme-anchor">
   <a href="#overview">总览</a>
   <a href="#ai_compute">AI算力</a>
   <a href="#cpu_pcb">CPU+封测+PCB</a>
   <a href="#memory">存储涨价</a>
   <a href="#world_cup">世界杯</a>
   <a href="#gold_defense">黄金防御</a>
   <a href="#watch">观察池</a>
   <a href="#exclude">排除池</a>
   <a href="#migration">待迁移</a>
   </nav>
   ```
3. 渲染 body：
   - 持仓快照表：浮盈亏列 `<span class="gain-positive">+¥4,260</span>` / `<span class="gain-negative">-¥X</span>`
   - 重点池每个 `<h3 id="{theme_key}">` 加锚点
   - 评级列 `<span class="tag tag-core">核心</span>` 等
   - 选股理由列 `<td class="thesis-cell" title="{thesis 全文}">{thesis 截断 80 字}</td>`
   - 名称列 `<a class="doc-link" href="file:///{绝对路径}/docs/analysis/{conviction_doc}">{stock_name}</a>`
   - 观察池 `<h2 id="watch">`，每条加 `<span class="tag-reason">估值偏高</span>` 等中文映射（来自 `metadata_schema.watch_reason[reason]`）
   - 排除池 `<h2 id="exclude">`，按 reason 分组（reason→中文映射来自 `metadata_schema.exclude_reason[reason]`）
   - 迁移待办 `<h2 id="migration">`，每条 `<div class="migration-pending"><code>{path}</code> 建议：rating=…</div>`
4. 替换占位符：
   - `{TITLE}` → `持仓首次配置 - YYYY-MM-DD`
   - `{NAV}` → 上面的 nav HTML
   - `{CONTENT}` → 渲染好的 body
   - `{TIMESTAMP}` → `YYYY-MM-DD HH:MM`
   - `{KIND}` → `init`
5. Write 到 `{output_dir}/portfolio-init-{YYYY-MM-DD}.html`(**绝不写到 git 工程内 D:\Git\stock\**)
6. 输出末尾追加：「📄 HTML 报告：file:///{output_dir 的 URL 形式}/portfolio-init-YYYY-MM-DD.html」

## 异常处理

| 场景 | 处理 |
|------|------|
| `rebalance_config` 表不存在 | 报错提示先启动 app 让迁移跑 |
| `docs/analysis/` 全空 | 报错提示先做股票分析 |
| 实时价部分获取失败 | 用最近 cache 价并在表格价格列加 ⚠️ 注释 |
| `themes[0]` 未在 config.yaml.themes 中 | 报错并停（防 typo） |
| `migration_fallback` key ⊄ `themes` key | §0 schema 校验报错 |
| frontmatter YAML 解析失败 | 跳过该 doc，记 warning 进迁移待办，**不阻塞** |
| 同股 conviction_date 相同 | 取文件名字典序后者 |
| docs 提到但 stock_code 反查失败 | 在「待迁移」段标"代码缺失"，不入 StockWeight |
