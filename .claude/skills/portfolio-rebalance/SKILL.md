---
name: portfolio-rebalance
description: 日常再平衡分析。读最新持仓 + 已固化的目标权重，算 target/current 差额，输出 BUY/SELL/HOLD 操作建议（100 股倍数）+ 主题偏离 + 关键事件。支持 --dry-run 不写库。v2: 主题归属从 docs frontmatter 读，HTML 报告含锚点导航 + SELL 表盈亏列 + 内联理由。
---

# Portfolio Rebalance — 日常再平衡（v2）

## 何时使用

- 每日盘后想知道是否要调仓
- 看到大事件想立刻知道影响
- 持仓刚更新（OCR 上传后）

**首次配置 / 主题大调用 `/portfolio-init`，本 skill 假设 StockWeight 已就绪。**

## v2 关键变化

- 主题归属从 `docs/analysis/*.md` 顶部 YAML frontmatter 读取（与 `/portfolio-init` 共享）
- 名称回填统一函数 `stock_meta_lookup(code)`，修 000021 显示成代码而非「深科技」的 bug
- HTML 升级 v2 模板：sticky 主题导航 + 行级锚点跳转 + SELL 表加成本/盈亏列
- 操作清单的「理由」改为 BUY/SELL 表新增「理由」列（取 frontmatter.thesis），删独立列表段

## 参数

- 默认：写库 + 输出 markdown + 生成 HTML
- `--dry-run`：只输出 markdown + HTML，不写 PositionPlan

## 工作流

### 第 0 步：检查前置条件 + 读取配置

1. 检查 StockWeight：
   ```sql
   SELECT COUNT(*) FROM stock_weights WHERE selected = 1;
   ```
   如果 = 0 → 报错并提示 "StockWeight 为空，请先运行 `/portfolio-init`"。

2. 读共享配置 `.claude/skills/portfolio-init/config.yaml` 取 `rules` / `themes` / `metadata_schema` / `migration_fallback` / `migration_exclude`

3. 读本地配置 `.claude/skills/portfolio-init/local-config.yaml`：
   - 不存在 → 报错提示创建后重试
   - `portfolio.output_dir` 为空 → 报错提示填写后重试
   - 路径不存在 → `mkdir -p`

### 第 1 步：读基础数据

```sql
-- 目标总市值
SELECT target_value FROM rebalance_config LIMIT 1;

-- 已固化的目标权重
SELECT stock_code, weight FROM stock_weights WHERE selected = 1;

-- 最新持仓快照
SELECT stock_code, stock_name, quantity, total_amount, current_price
FROM positions
WHERE date = (SELECT MAX(date) FROM positions);
```

### 第 2 步：取实时价

```python
import os
os.environ['SCHEDULER_ENABLED'] = '0'
from app import create_app
app = create_app()
with app.app_context():
    from app.services.unified_stock_data import UnifiedStockDataService
    svc = UnifiedStockDataService()
    all_codes = list(set(weight_codes + position_codes))
    prices = svc.get_realtime_prices(all_codes)
```

实时价失败的股票：用 cache 价（`UnifiedStockCache` 表 cache_type='price' 最新行）+ 标 ⚠️。

### 第 3 步：universe scan + stock_meta_lookup（修 000021 bug）

复用 `/portfolio-init` 的 universe scan 三个函数（`scan_universe` / `fallback_from_filename` / `resolve_stock_code`），inline 复制保持完全同步：

```python
def scan_universe(docs_root, config):
    """扫 docs/analysis/**/*.md，返回 universe 列表 + 待迁移清单。"""
    raw_entries = []
    migration_pending = []

    for md in glob('docs/analysis/**/*.md'):
        fm = parse_frontmatter(md)  # 解析文件开头 --- 之间的 YAML；无 --- 或解析失败返回 None

        if fm and 'stock_code' in fm:
            entry = {
                'stock_code': fm['stock_code'],
                'stock_name': fm['stock_name'],
                'themes': fm['themes'],
                'rating': fm['rating'],
                'conviction_date': fm['conviction_date'],
                'thesis': fm.get('thesis', ''),
                'watch_reason': fm.get('watch_reason'),
                'exclude_reason': fm.get('exclude_reason'),
                'doc_path': md,
            }
            raw_entries.append(entry)
        else:
            fb = fallback_from_filename(md, config)
            if fb:
                fb['doc_path'] = md
                fb['_fallback'] = True
                raw_entries.append(fb)
                migration_pending.append(md)

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

    # 校验 themes[0] 必须在 config.themes 内（exclude 评级跳过：_fallback 是占位）
    valid_themes = set(config['themes'].keys())
    for entry in by_code.values():
        if entry['rating'] == 'exclude':
            continue
        if entry['themes'][0] not in valid_themes:
            raise ValueError(f"未知主题 {entry['themes'][0]} in {entry['doc_path']}")

    return list(by_code.values()), migration_pending


def fallback_from_filename(md_path, config):
    """无 frontmatter 时按文件名关键词兜底。"""
    name = md_path.stem
    for item in config['migration_exclude']:
        if item['keyword'] in name:
            return {'rating': 'exclude', 'exclude_reason': item['reason'],
                    'stock_name': item['keyword'],
                    'stock_code': resolve_stock_code(item['keyword']),
                    'themes': ['_fallback'],
                    'conviction_date': extract_date_from_filename(md_path),  # 从文件名前缀 'YYYY-MM-DD-' 提取日期字符串；无前缀返回 '1970-01-01'
                    'thesis': ''}
    for theme_key, theme_cfg in config['migration_fallback'].items():
        for kw in theme_cfg['keywords']:
            if kw in name:
                return {'rating': theme_cfg['default_rating'],
                        'stock_name': kw,
                        'stock_code': resolve_stock_code(kw),
                        'themes': [theme_key],
                        'conviction_date': extract_date_from_filename(md_path),  # 从文件名前缀 'YYYY-MM-DD-' 提取日期字符串；无前缀返回 '1970-01-01'
                        'thesis': ''}
    return None


def resolve_stock_code(name, frontmatter_entry=None):
    """frontmatter > data/stock.db > app/config/supply_chain.py."""
    if frontmatter_entry and frontmatter_entry.get('stock_code'):
        return frontmatter_entry['stock_code']

    import sqlite3
    conn = sqlite3.connect('data/stock.db')
    row = conn.execute("SELECT stock_code FROM stock WHERE stock_name=?", (name,)).fetchone()
    if row:
        return row[0]

    from app.config.supply_chain import SUPPLY_CHAIN_GRAPHS
    for graph in SUPPLY_CHAIN_GRAPHS.values():
        for layer in ('upstream', 'midstream', 'downstream'):
            for company in graph.get(layer, {}).get('companies', []):
                if company.get('name') == name:
                    return company.get('code')
    return None
```

新增 `stock_meta_lookup(code)`：

```python
_meta_cache = None  # 模块级缓存，避免重复扫 docs

def stock_meta_lookup(code):
    """统一查股票元数据：frontmatter > stock 表 > positions 表 > 兜底。
    返回 dict: {stock_name, theme_key, theme_name, thesis, doc_path}。
    缺名时记 warning，绝不返回 code 占位（修 '000021 000021' bug 的核心）。
    """
    global _meta_cache
    if _meta_cache is None:
        universe, _ = scan_universe('docs/analysis', config)
        _meta_cache = {e['stock_code']: e for e in universe}

    if code in _meta_cache:
        e = _meta_cache[code]
        tk = e['themes'][0]
        is_real_theme = tk in config['themes']
        return {'stock_name': e['stock_name'],
                'theme_key': tk if is_real_theme else None,
                'theme_name': config['themes'][tk]['name'] if is_real_theme else '-',
                'thesis': e.get('thesis', ''),
                'doc_path': e['doc_path']}

    # frontmatter 没有 → 查 stock 表
    import sqlite3
    conn = sqlite3.connect('data/stock.db')
    row = conn.execute("SELECT stock_name FROM stock WHERE stock_code=?", (code,)).fetchone()
    if row and row[0]:
        logger.warning(f"stock_meta_lookup: {code} 在 stock 表找到名 '{row[0]}' 但缺 frontmatter，建议补 docs frontmatter")
        return {'stock_name': row[0], 'theme_key': None, 'theme_name': '-',
                'thesis': '', 'doc_path': None}

    # 查 positions 表 stock_name（OCR 上传时录入）
    conn2 = sqlite3.connect('data/private.db')
    row = conn2.execute("SELECT stock_name FROM positions WHERE stock_code=? ORDER BY date DESC LIMIT 1",
                        (code,)).fetchone()
    if row and row[0]:
        logger.warning(f"stock_meta_lookup: {code} 仅在 positions 找到名 '{row[0]}'，强烈建议补 stock 表 + docs frontmatter")
        return {'stock_name': row[0], 'theme_key': None, 'theme_name': '-',
                'thesis': '', 'doc_path': None}

    # 全部找不到 → 用 code 兜底但显式 warning
    logger.warning(f"stock_meta_lookup: {code} 全部三处反查失败，HTML 将显示 code 占位")
    return {'stock_name': code, 'theme_key': None, 'theme_name': '-',
            'thesis': '', 'doc_path': None}
```

**所有 §3-§8 渲染表格行的代码以及 §9 HTML 模板填充必须用 `stock_meta_lookup(code).get('stock_name')`**，不要再走老路径 `stocks_dict.get(code, {}).get('name', code)`。

### 第 4 步：算 diff

对每只重点池股票：
1. `current_value` = quantity × 实时价（不在持仓表则 0）
2. `target_value_stock` = `target_value × weight`
3. `diff = target_value_stock - current_value`
4. 操作判定：
   - `abs(diff) < rebalance_threshold_value`（默认 ¥2,000）→ `operation='hold'`，shares=0
   - `diff > rebalance_threshold_value` → `operation='buy'`，`shares = floor(diff / 现价 / 100 + 1e-6) × 100`
   - `diff < -rebalance_threshold_value` → `operation='sell'`，`shares = ceil(abs(diff) / 现价 / 100 - 1e-6) × 100`，但不能超过当前持有数

对持仓表中存在但**不在重点池**的股票：
- 标记「建议清仓」（如美国50 ETF 残值）
- 不计入主题统计，但在输出单独列出

### 第 5 步：算主题偏离（按 frontmatter themes[0]）

按 `stock_meta_lookup(code)['theme_key']` 分组重点池：
- 主题目标 = `target_value × theme.weight`
- 主题当前 = sum(主题内每只股的 current_value)
- 主题缺口 = 主题目标 - 主题当前
- 偏离比 = 主题缺口 / target_value
- abs(偏离比) > `theme_drift_threshold`（默认 5%）→ 标红 ⚠️

theme_key=None 的股票（兜底失败）不计入任何主题。

### 第 6 步：扫近期事件

1. **docs/analysis/ 近 7 天文档**

用 Glob 扫 `docs/analysis/**/*.md`，按文件名前缀 `YYYY-MM-DD-` 解析日期，筛今日往前 7 天内。读每个文档头部 200 字，提取关键词「业绩说明会」「新增产能」「涨价」「投产」「中标」「财报联动」，形成 5-10 条事件清单。

2. **news_item 近 3 天，命中目标池**

```sql
SELECT n.title, n.link, n.published_at
FROM news_item n
JOIN identified_company ic ON ic.news_id = n.id
WHERE ic.stock_code IN (重点池 codes)
  AND n.published_at >= datetime('now', '-3 days')
ORDER BY n.published_at DESC
LIMIT 20;
```

筛 5-10 条最相关的，附在事件清单。

### 第 7 步：写库（除非 --dry-run）

```sql
DELETE FROM position_plans;

INSERT INTO position_plans (stock_code, stock_name, target_value, current_value,
                             diff, operation, shares, weight, updated_at)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'));
```

`stock_name` 字段统一用 `stock_meta_lookup(code)['stock_name']`。

### 第 8 步：输出 markdown

```markdown
## 持仓再平衡建议（YYYY-MM-DD HH:MM）

### 总览
总资产 ¥X | 持仓市值 ¥X (X.X%) | 可用现金 ¥X (X.X%)
偏离阈值：单股 ±¥2,000，主题 ±5%

### 主题偏离
| 主题 | 目标权重 | 目标市值 | 当前市值 | 缺口 | 偏离 |
|------|---------|---------|---------|------|------|

### 个股操作清单

#### 🟢 BUY（共 N 笔，合计 ¥X）
| 代码 | 名称 | 主题 | 现价 | 目标股数 | 当前股数 | 建议买 | 占用资金 | 理由 |
|------|------|------|------|---------|---------|------|---------|------|

#### 🔴 SELL（共 N 笔，合计 ¥X）
| 代码 | 名称 | 主题 | 现价 | 平均成本 | 目标股数 | 当前股数 | 建议卖 | 释放资金 | 预期盈亏 | 理由 |
|------|------|------|------|---------|---------|---------|------|---------|---------|------|

#### ⚪ HOLD（共 N 只）

#### ⚠️ 重点池外建议清仓
- 美国50 ETF（513850）：…

### 未来 1-2 周关注事件

### Web UI
http://127.0.0.1:5000/position-plan
```

注意：旧版的「理由」独立 `<ul>` 列表段移除，理由直接进 BUY / SELL 表的「理由」列。

### 第 9 步：生成 HTML 报告（v2 模板）

把第 8 步内容渲染为 HTML，写到 `{output_dir}/portfolio-rebalance-{YYYY-MM-DD-HHMM}.html`。

**步骤**：

1. Read 模板 `.claude/skills/portfolio-init/report-template.html`（共享）
2. 渲染主题导航（按 config['themes'] 字典顺序生成主题 anchor，固定追加 #overview / #drift / #buy / #sell / #hold / #cleanup / #events。当前 5 主题渲染示例）：
   ```html
   <nav class="theme-anchor">
   <a href="#overview">总览</a>
   <a href="#drift">主题偏离</a>
   <a href="#buy">BUY</a>
   <a href="#sell">SELL</a>
   <a href="#hold">HOLD</a>
   <a href="#cleanup">建议清仓</a>
   <a href="#events">关注事件</a>
   </nav>
   ```
3. 渲染 body：
   - 名称列统一 `stock_meta_lookup(code)['stock_name']`；当 `doc_path` 非 None 时用 `<a class="doc-link" href="file:///{project_root_url}/{doc_path}">{stock_name}</a>`，其中 `project_root_url = Path('.').resolve().as_posix()`（保证 file:// URL 用正斜杠）
   - SELL 表的「平均成本」「预期盈亏」列：从 positions.total_amount/quantity 算 avg_cost；预期盈亏 = (现价 - avg_cost) × 卖出股数；正用 `<span class="gain-positive">`，负用 `<span class="gain-negative">`
   - 主题偏离表 abs(偏离比)>5% 行用 `<span class="warn">⚠️ -8.2%</span>`
   - 操作清单理由列 `<td class="thesis-cell" title="{thesis 全文}">{thesis 截断 80 字}</td>`
   - HOLD 列表用 `<ul>` + `<span class="hold">`
   - 建议清仓 `<div class="warn-box" id="cleanup">`
4. 替换占位符：
   - `{TITLE}` → `持仓再平衡建议 - YYYY-MM-DD HH:MM`
   - `{NAV}` → 上面的 nav HTML
   - `{CONTENT}` → 渲染好的 body
   - `{TIMESTAMP}` → `YYYY-MM-DD HH:MM`
   - `{KIND}` → `rebalance`
5. Write 到 `{output_dir}/portfolio-rebalance-{YYYY-MM-DD-HHMM}.html`
6. 输出末尾追加："📄 HTML 报告：file:///..."

## 异常处理

| 场景 | 处理 |
|------|------|
| `stock_weights` 全空 | 报错提示先 `/portfolio-init` |
| Position 表为空 | 视作纯现金，输出全建仓计划 |
| 实时价个别失败 | 用 UnifiedStockCache 最近行 + ⚠️ 标记 |
| 持仓表中股票不在重点池 | 单独列「重点池外建议清仓」，不计主题 |
| sell shares 超过 current quantity | shares = current quantity（清仓），diff 标"超配 + 清仓" |
| docs/analysis 近 7 天无新增 | 事件清单可空，输出"近 7 天无新分析" |
| `stock_meta_lookup` 三处反查全失败 | 用 code 兜底但记 warning，HTML 仍显示 code 但日志会有提示 |
