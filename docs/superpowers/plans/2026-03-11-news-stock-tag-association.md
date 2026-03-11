# 新闻-股票标签关联机制 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为股票添加关键标签（LLM生成+手动编辑），新闻匹配时关联股票，通知中展示关联股票。

**Architecture:** Stock 表新增 `tags` 字段存储逗号分隔标签，NewsItem 表新增 `matched_stocks` 字段存储关联的股票代码。InterestPipeline._match_keywords() 中加入股票标签反向索引匹配。StockService 新增 LLM 标签生成方法。

**Tech Stack:** Flask, SQLAlchemy, 智谱 GLM (Flash), Jinja2, Bootstrap 5

---

## Task 1: 数据模型变更

**Files:**
- Modify: `app/models/stock.py`
- Modify: `app/models/news.py`

- [ ] **Step 1: Stock 模型新增 tags 字段**

在 `app/models/stock.py` 的 `Stock` 类中，`investment_advice` 字段之后新增：

```python
tags = db.Column(db.Text, nullable=True)
```

同时更新 `to_dict()` 方法，加入 `'tags': self.tags`。

- [ ] **Step 2: NewsItem 模型新增 matched_stocks 字段**

在 `app/models/news.py` 的 `NewsItem` 类中，`matched_keywords` 字段之后新增：

```python
matched_stocks = db.Column(db.Text)
```

- [ ] **Step 3: 数据库迁移**

项目使用 SQLite，直接用 ALTER TABLE 添加列：

```bash
cd D:/Git/stock
python -c "
from app import create_app, db
app = create_app()
with app.app_context():
    with db.engine.connect() as conn:
        import sqlalchemy
        try:
            conn.execute(sqlalchemy.text('ALTER TABLE stock ADD COLUMN tags TEXT'))
            conn.commit()
            print('stock.tags added')
        except Exception as e:
            print(f'stock.tags: {e}')
        try:
            conn.execute(sqlalchemy.text('ALTER TABLE news_item ADD COLUMN matched_stocks TEXT'))
            conn.commit()
            print('news_item.matched_stocks added')
        except Exception as e:
            print(f'news_item.matched_stocks: {e}')
"
```

- [ ] **Step 4: Commit**

```bash
git add app/models/stock.py app/models/news.py
git commit -m "feat: Stock 新增 tags 字段, NewsItem 新增 matched_stocks 字段"
```

---

## Task 2: LLM 标签生成 Prompt

**Files:**
- Create: `app/llm/prompts/stock_tags.py`

- [ ] **Step 1: 创建标签生成 prompt 文件**

创建 `app/llm/prompts/stock_tags.py`：

```python
"""股票标签生成 prompts"""

TAGS_SYSTEM_PROMPT = """你是股票分析助手。根据给定的股票代码和名称，生成一组关联关键词标签。
标签应包括：公司全称、简称、核心产品/品牌、所属行业、概念板块、英文名（如有）。
标签用于匹配新闻内容，应尽量覆盖该公司可能出现在新闻中的各种提法。

要求：
- 返回严格的JSON数组，每个元素是一个关键词字符串
- 标签数量5-15个，优先覆盖常见提法
- 不要包含过于宽泛的词（如"科技"、"公司"）
- 只返回JSON数组，不要其他文字"""


def build_tags_prompt(stock_code: str, stock_name: str) -> str:
    return f"请为以下股票生成关联关键词标签：\n股票代码：{stock_code}\n股票名称：{stock_name}"


def build_batch_tags_prompt(stocks: list[dict]) -> str:
    """批量生成标签的prompt，每个stock含code和name"""
    lines = []
    for i, s in enumerate(stocks):
        lines.append(f"[{i}] {s['code']} {s['name']}")
    return (
        f"请为以下{len(stocks)}只股票分别生成关联关键词标签。\n"
        f"返回JSON数组，每个元素格式：{{\"index\": 序号, \"tags\": [\"标签1\", \"标签2\", ...]}}\n\n"
        + "\n".join(lines)
    )
```

- [ ] **Step 2: 在 LLM 路由中注册任务类型**

在 `app/llm/router.py` 的 `TASK_LAYER_MAP` 字典中添加：

```python
'stock_tags': LLMLayer.FLASH,
```

- [ ] **Step 3: Commit**

```bash
git add app/llm/prompts/stock_tags.py app/llm/router.py
git commit -m "feat: 添加股票标签生成 prompt 和 LLM 路由注册"
```

---

## Task 3: StockService 标签生成方法

**Files:**
- Modify: `app/services/stock.py`

- [ ] **Step 1: 添加 generate_tags 方法**

在 `app/services/stock.py` 的 `StockService` 类末尾新增：

```python
@staticmethod
def generate_tags(stock_code, stock_name=None):
    """调用 LLM 为单个股票生成标签，返回 (tags_str, error)"""
    import json
    import re

    stock = Stock.query.get(stock_code)
    if not stock:
        return None, '股票代码不存在'

    name = stock_name or stock.stock_name

    from app.llm.router import llm_router
    from app.llm.prompts.stock_tags import TAGS_SYSTEM_PROMPT, build_tags_prompt

    provider = llm_router.route('stock_tags')
    if not provider:
        return None, 'LLM 不可用'

    try:
        response = provider.chat([
            {'role': 'system', 'content': TAGS_SYSTEM_PROMPT},
            {'role': 'user', 'content': build_tags_prompt(stock_code, name)},
        ], temperature=0.3, max_tokens=500)

        text = response.strip()
        m = re.search(r'```(?:json)?\s*([\s\S]*?)```', text)
        if m:
            text = m.group(1).strip()

        tags_list = json.loads(text)
        if not isinstance(tags_list, list):
            return None, 'LLM 返回格式错误'

        tags_str = ','.join(str(t) for t in tags_list if t)
        stock.tags = tags_str
        db.session.commit()
        return tags_str, None
    except Exception as e:
        return None, f'标签生成失败: {e}'

@staticmethod
def batch_generate_tags(overwrite=False):
    """批量为股票生成标签，返回 {code: tags_str} 或 {code: error}"""
    import logging
    logger = logging.getLogger(__name__)

    stocks = Stock.query.all()
    results = {}

    for stock in stocks:
        if not overwrite and stock.tags:
            results[stock.stock_code] = stock.tags
            continue

        tags_str, error = StockService.generate_tags(stock.stock_code)
        if error:
            logger.warning(f'[标签生成] {stock.stock_code} 失败: {error}')
            results[stock.stock_code] = f'ERROR: {error}'
        else:
            results[stock.stock_code] = tags_str
            logger.info(f'[标签生成] {stock.stock_code}: {tags_str}')

    return results

@staticmethod
def update_tags(code, tags):
    """手动更新股票标签，返回 (stock, error)"""
    stock = Stock.query.get(code)
    if not stock:
        return None, '股票代码不存在'

    stock.tags = tags.strip() if tags else None
    db.session.commit()
    return stock, None
```

- [ ] **Step 2: Commit**

```bash
git add app/services/stock.py
git commit -m "feat: StockService 添加标签生成和更新方法"
```

---

## Task 4: 标签生成 API 路由

**Files:**
- Modify: `app/routes/stock.py`

- [ ] **Step 1: 添加标签相关 API**

在 `app/routes/stock.py` 末尾添加三个端点：

```python
@stock_bp.route('/<code>/tags', methods=['PUT'])
def update_tags(code):
    """手动更新股票标签"""
    data = request.get_json() or {}
    tags = data.get('tags', '')

    stock, error = StockService.update_tags(code, tags)
    if error:
        status = 404 if '不存在' in error else 400
        return jsonify({'error': error}), status
    return jsonify(stock.to_dict())


@stock_bp.route('/<code>/generate-tags', methods=['POST'])
def generate_tags(code):
    """为单个股票生成标签"""
    tags_str, error = StockService.generate_tags(code)
    if error:
        status = 404 if '不存在' in error else 500
        return jsonify({'error': error}), status
    return jsonify({'tags': tags_str})


@stock_bp.route('/batch-generate-tags', methods=['POST'])
def batch_generate_tags():
    """批量生成所有股票标签"""
    data = request.get_json() or {}
    overwrite = data.get('overwrite', False)
    results = StockService.batch_generate_tags(overwrite=overwrite)
    return jsonify({'results': results})
```

- [ ] **Step 2: 创建股票时异步生成标签**

修改 `app/routes/stock.py` 中的 `create()` 函数，在 `StockMetaService.bump_version()` 之后添加异步标签生成：

```python
@stock_bp.route('', methods=['POST'])
def create():
    """创建股票"""
    data = request.get_json()
    code = data.get('stock_code', '') if data else ''
    name = data.get('stock_name', '') if data else ''
    stock, error = StockService.create_stock(code, name)
    if error:
        return jsonify({'error': error}), 400
    StockMetaService.bump_version()

    # 异步生成标签
    import threading
    def _gen_tags(app, stock_code):
        with app.app_context():
            StockService.generate_tags(stock_code)
    from flask import current_app
    threading.Thread(
        target=_gen_tags,
        args=(current_app._get_current_object(), code),
        daemon=True
    ).start()

    return jsonify(stock.to_dict()), 201
```

- [ ] **Step 3: Commit**

```bash
git add app/routes/stock.py
git commit -m "feat: 添加标签生成/更新 API，创建股票时异步生成标签"
```

---

## Task 5: InterestPipeline 股票标签匹配

**Files:**
- Modify: `app/services/interest_pipeline.py`

- [ ] **Step 1: 在 _match_keywords 中加入股票标签匹配**

修改 `app/services/interest_pipeline.py` 的 `_match_keywords` 方法。在现有关键词匹配之后，增加股票标签匹配逻辑：

```python
@staticmethod
def _match_keywords(items: list[NewsItem], classified: list[dict]):
    """将 GLM 提取的关键词与用户兴趣关键词+公司名匹配，同时做股票标签匹配"""
    user_keywords = InterestKeyword.query.filter_by(is_active=True).all()
    company_keywords = CompanyKeyword.query.filter_by(is_active=True).all()

    kw_set = {kw.keyword.lower() for kw in user_keywords}
    kw_set.update(c.name.lower() for c in company_keywords)

    # 构建股票标签反向索引 {tag_lower: [stock_code, ...]}
    from app.models.stock import Stock
    stock_tag_index = {}
    all_stocks = Stock.query.filter(Stock.tags.isnot(None), Stock.tags != '').all()
    stock_name_map = {}
    for stock in all_stocks:
        stock_name_map[stock.stock_code] = stock.stock_name
        for tag in stock.tags.split(','):
            tag = tag.strip().lower()
            if tag and len(tag) >= 2:
                if tag not in stock_tag_index:
                    stock_tag_index[tag] = []
                stock_tag_index[tag].append(stock.stock_code)

    for r in classified:
        idx = r.get('index', -1)
        if idx < 0 or idx >= len(items):
            continue
        item = items[idx]
        extracted = r.get('keywords', [])

        # 现有兴趣关键词匹配（保持不变）
        matched = []
        if kw_set:
            for ext_kw in extracted:
                ext_lower = ext_kw.lower()
                for user_kw in kw_set:
                    if user_kw in ext_lower or ext_lower in user_kw:
                        matched.append(user_kw)
                        break

            if not matched:
                content_lower = item.content.lower()
                for user_kw in kw_set:
                    if user_kw in content_lower:
                        matched.append(user_kw)

        if matched:
            item.is_interest = True
            item.matched_keywords = ','.join(set(matched))

        # 股票标签匹配
        if stock_tag_index:
            content_lower = item.content.lower()
            matched_codes = set()
            for tag, codes in stock_tag_index.items():
                if tag in content_lower:
                    matched_codes.update(codes)
            if matched_codes:
                item.matched_stocks = ','.join(sorted(matched_codes))
```

- [ ] **Step 2: 修改 _notify_interest_slack 追加关联股票信息**

修改 `app/services/interest_pipeline.py` 中的 `_notify_interest_slack` 方法：

```python
@staticmethod
def _notify_interest_slack(items: list[NewsItem]):
    from app.services.notification import NotificationService
    try:
        # 预加载关联股票名称
        all_codes = set()
        for n in items:
            if n.matched_stocks:
                all_codes.update(n.matched_stocks.split(','))

        stock_name_map = {}
        if all_codes:
            from app.models.stock import Stock
            stocks = Stock.query.filter(Stock.stock_code.in_(all_codes)).all()
            stock_name_map = {s.stock_code: s.stock_name for s in stocks}

        for n in items:
            tag = f" [{n.matched_keywords}]" if n.matched_keywords else ""
            msg = f"📰{tag} {n.content}"

            if n.matched_stocks:
                codes = n.matched_stocks.split(',')
                stock_labels = []
                for code in codes:
                    name = stock_name_map.get(code, '')
                    stock_labels.append(f"{code}{name}")
                msg += f"\n→ 关联: {', '.join(stock_labels)}"

            NotificationService.send_slack(msg)
    except Exception as e:
        logger.error(f'[兴趣] Slack通知失败: {e}')
```

- [ ] **Step 3: 同时对未经 GLM 分类的新闻也做标签匹配**

在 `process_new_items` 方法中，GLM 分类可能只覆盖部分新闻。需要确保所有新闻都做股票标签匹配。当前 `_match_keywords` 只处理 `classified` 列表中有的条目。

在 `_match_keywords` 末尾增加对未分类新闻的标签匹配：

```python
        # 对未被 classified 覆盖的新闻也做标签匹配
        if stock_tag_index:
            classified_indices = {r.get('index', -1) for r in classified}
            for i, item in enumerate(items):
                if i in classified_indices:
                    continue
                content_lower = item.content.lower()
                matched_codes = set()
                for tag, codes in stock_tag_index.items():
                    if tag in content_lower:
                        matched_codes.update(codes)
                if matched_codes:
                    item.matched_stocks = ','.join(sorted(matched_codes))
```

- [ ] **Step 4: Commit**

```bash
git add app/services/interest_pipeline.py
git commit -m "feat: InterestPipeline 集成股票标签匹配和通知关联展示"
```

---

## Task 6: UI — 股票代码管理页面

**Files:**
- Modify: `app/templates/partials/stock_row.html`
- Modify: `app/templates/stock_manage.html`

- [ ] **Step 1: stock_row.html 新增标签列**

在 `app/templates/partials/stock_row.html` 中，别名列（`alias-cell`）之后、投资建议列（`advice-cell`）之前，插入标签列：

```html
<td class="editable tags-cell" data-field="tags">{{ stock.tags or '' }}</td>
```

- [ ] **Step 2: stock_manage.html 表头新增标签列**

在 `app/templates/stock_manage.html` 中，所有 `<thead>` 里别名列 `<th class="col-alias">别名</th>` 之后，投资建议 `<th>投资建议</th>` 之前，插入：

```html
<th class="col-tags">标签</th>
```

共有3处 `<thead>`（一级分类、二级分类、未分类），都需要添加。

- [ ] **Step 3: CSS 新增标签列样式**

在 `app/templates/stock_manage.html` 的 `<style>` 中添加：

```css
#stockList th.col-tags { width: 20%; }
#stockList .tags-cell { word-break: break-all; font-size: 0.85em; color: #666; }
```

- [ ] **Step 4: 页面顶部添加"批量生成标签"按钮**

在 `app/templates/stock_manage.html` 中，新增股票表单的 `<div class="col-md-8">` 之后，添加按钮区域：

```html
<div class="col-md-4 d-flex align-items-end">
    <button class="btn btn-outline-success" id="batchGenerateTags" title="为没有标签的股票自动生成">
        批量生成标签
    </button>
</div>
```

- [ ] **Step 5: JavaScript — 标签编辑和批量生成**

在 `app/templates/stock_manage.html` 的 `<script>` 中，双击编辑的 `saveEdit` 函数里，在 `} else if (field === 'alias') {` 分支之前，添加 `tags` 字段的保存逻辑：

```javascript
if (field === 'tags') {
    const res = await fetch(`/stocks/${code}/tags`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({tags: newValue || null})
    });
    const data = await res.json();
    if (data.error) {
        alert(data.error);
        cell.textContent = oldValue;
        return;
    }
    cell.textContent = data.tags || '';
    return;
}
```

同时更新 `input.maxLength` 逻辑，在 `field === 'advice' ? 500` 之前添加 `field === 'tags' ? 500 :`。

在 `<script>` 末尾（`</script>` 之前）添加批量生成按钮事件：

```javascript
// 批量生成标签
document.getElementById('batchGenerateTags').addEventListener('click', async () => {
    if (!confirm('将为所有没有标签的股票自动生成标签（需要 LLM），确定继续？')) return;

    const btn = document.getElementById('batchGenerateTags');
    btn.disabled = true;
    btn.textContent = '生成中...';

    try {
        const res = await fetch('/stocks/batch-generate-tags', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({overwrite: false})
        });
        const data = await res.json();

        if (data.error) {
            alert(data.error);
        } else {
            const results = data.results || {};
            const total = Object.keys(results).length;
            const errors = Object.values(results).filter(v => v.startsWith('ERROR:')).length;
            alert(`完成！共处理 ${total} 只股票，${errors} 个失败`);
            location.reload();
        }
    } catch (e) {
        alert('请求失败: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '批量生成标签';
    }
});
```

- [ ] **Step 6: 允许 tags 字段清空（双击编辑 saveEdit 守卫更新）**

在 `saveEdit` 函数中，将现有的空值检查从：
```javascript
if (field !== 'alias' && field !== 'advice' && !newValue) {
```
改为：
```javascript
if (field !== 'alias' && field !== 'advice' && field !== 'tags' && !newValue) {
```

- [ ] **Step 7: Commit**

```bash
git add app/templates/partials/stock_row.html app/templates/stock_manage.html
git commit -m "feat: 股票代码管理页面新增标签列和批量生成按钮"
```

---

## Task 7: 端到端验证

- [ ] **Step 1: 启动应用验证数据库迁移**

```bash
python run.py
```

访问 http://127.0.0.1:5000/stocks/manage ，确认页面正常加载，表格新增标签列。

- [ ] **Step 2: 验证手动编辑标签**

在页面上双击某只股票的标签列，输入 `测试,标签`，回车保存。刷新页面确认持久化。

- [ ] **Step 3: 验证单个标签生成**

```bash
curl -X POST http://127.0.0.1:5000/stocks/600519/generate-tags
```

确认返回 `{"tags": "贵州茅台,茅台,..."}` 格式。

- [ ] **Step 4: 验证批量标签生成**

点击页面上的"批量生成标签"按钮，确认弹出确认框，执行后刷新页面显示标签。

- [ ] **Step 5: 验证新闻匹配**

检查新闻轮询日志，确认新闻处理时股票标签匹配正常运行，`matched_stocks` 字段有写入。

- [ ] **Step 6: 验证 Slack 通知格式**

确认兴趣新闻推送时，若有关联股票，消息末尾包含 `→ 关联: 600519贵州茅台` 格式。

- [ ] **Step 7: 最终 Commit**

确认所有功能正常后，如有修正一并提交。
