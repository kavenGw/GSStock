# 股票信息批量预加载重构 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 重构预加载系统，支持板块级 Toggle 控制 + 按市场分组批量获取，减少 API 调用次数

**Architecture:** Category 表增加 `preload_enabled` 字段控制预加载。PreloadService 重构为按市场分组（A股/美股/港股），美股/港股使用 `yf.download()` 真批量接口，A股保持 ThreadPool 并发。管理界面每个一级板块加 Toggle 开关。

**Tech Stack:** Flask + SQLAlchemy + SQLite, akshare, yfinance, Bootstrap 5

---

### Task 1: Category 模型增加 preload_enabled 字段

**Files:**
- Modify: `app/models/category.py:7` (Category 类字段定义)

**Step 1: 添加字段**

在 `app/models/category.py` 的 Category 类中，`description` 字段后面加：

```python
preload_enabled = db.Column(db.Boolean, default=False, nullable=False)
```

**Step 2: 更新 to_dict()**

在 `to_dict()` 返回值中增加 `preload_enabled` 字段：

```python
def to_dict(self):
    return {
        'id': self.id,
        'name': self.name,
        'description': self.description,
        'parent_id': self.parent_id,
        'preload_enabled': self.preload_enabled,
        'full_name': f"{self.parent.name} - {self.name}" if self.parent else self.name
    }
```

**Step 3: 验证**

启动应用 `python run.py`，SQLAlchemy `create_all()` 会自动添加新列（SQLite）。如果已有数据库，需确认 SQLite 的 `create_all()` 行为 — SQLite 不会 ALTER 已有表，需手动处理。

**注意**: SQLite 的 `create_all()` 不会给已有表加列。需要在 `__init__.py` 的迁移区域加一段：

```python
# 在 migrate_wyckoff_table() 之后
def migrate_category_table():
    """为 Category 表添加 preload_enabled 列"""
    from sqlalchemy import text, inspect
    inspector = inspect(db.engine)
    columns = [c['name'] for c in inspector.get_columns('categories')]
    if 'preload_enabled' not in columns:
        with db.engine.connect() as conn:
            conn.execute(text("ALTER TABLE categories ADD COLUMN preload_enabled BOOLEAN DEFAULT 0 NOT NULL"))
            conn.commit()
        logging.info("已添加 categories.preload_enabled 列")
```

在 `app/__init__.py:241` 的 `migrate_wyckoff_table()` 后调用 `migrate_category_table()`。

**Step 4: Commit**

```
feat: Category 表增加 preload_enabled 字段
```

---

### Task 2: CategoryService 增加 toggle_preload 方法

**Files:**
- Modify: `app/services/category.py` (增加方法)

**Step 1: 添加方法**

在 `CategoryService` 类末尾（`update_description` 之后）添加：

```python
@staticmethod
def toggle_preload(category_id, enabled):
    """切换板块预加载开关，返回 (category, error)"""
    category = Category.query.get(category_id)
    if not category:
        return None, '板块不存在'

    category.preload_enabled = enabled
    db.session.commit()
    return category, None
```

**Step 2: Commit**

```
feat: CategoryService 增加 toggle_preload 方法
```

---

### Task 3: 添加 Toggle API 路由

**Files:**
- Modify: `app/routes/category.py` (增加路由)

**Step 1: 添加路由**

在 `update_description` 路由之后添加：

```python
@category_bp.route('/<int:category_id>/preload', methods=['PUT'])
def toggle_preload(category_id):
    """切换板块预加载开关"""
    data = request.get_json()
    enabled = data.get('enabled', False) if data else False
    category, error = CategoryService.toggle_preload(category_id, enabled)
    if error:
        return jsonify({'error': error}), 404
    return jsonify({'success': True, 'preload_enabled': category.preload_enabled})
```

**Step 2: 验证**

启动应用后用 curl 或浏览器 DevTools 测试：
```bash
curl -X PUT http://127.0.0.1:5000/categories/1/preload \
  -H "Content-Type: application/json" \
  -d '{"enabled": true}'
```

**Step 3: Commit**

```
feat: 添加板块预加载 Toggle API
```

---

### Task 4: 板块管理界面添加 Toggle 开关

**Files:**
- Modify: `app/templates/category.html` (UI + JS)

**Step 1: 在每个一级板块 card-header 中添加 Toggle**

修改 `category.html:28-34`，在板块名称和按钮组之间插入 Toggle 开关。只在一级板块（parent）上显示，子板块继承父板块的设置。

```html
<div class="card-header d-flex justify-content-between align-items-center">
    <span class="category-name fw-bold">{{ parent.name }}</span>
    <div class="d-flex align-items-center gap-2">
        <div class="form-check form-switch mb-0" title="预加载开关">
            <input class="form-check-input preload-toggle" type="checkbox"
                   data-id="{{ parent.id }}"
                   {{ 'checked' if parent.preload_enabled else '' }}>
            <label class="form-check-label small text-muted">预加载</label>
        </div>
        <div class="btn-group btn-group-sm">
            <button class="btn btn-outline-success add-child-btn" title="添加子板块">+ 子板块</button>
            <button class="btn btn-outline-primary edit-btn" title="编辑">编辑</button>
            <button class="btn btn-outline-danger delete-btn" title="删除">删除</button>
        </div>
    </div>
</div>
```

**Step 2: 添加 Toggle 事件处理 JS**

在 `<script>` 块末尾（`categoryTree` 事件监听之后）添加：

```javascript
document.querySelectorAll('.preload-toggle').forEach(toggle => {
    toggle.addEventListener('change', async (e) => {
        const id = e.target.dataset.id;
        const enabled = e.target.checked;
        const res = await fetch(`/categories/${id}/preload`, {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({enabled})
        });
        if (!res.ok) {
            e.target.checked = !enabled;
            alert('操作失败');
        }
    });
});
```

**Step 3: 验证**

打开 `/categories/manage`，确认每个一级板块有 Toggle 开关，点击后 AJAX 保存，无需刷新页面。

**Step 4: Commit**

```
feat: 板块管理界面添加预加载 Toggle 开关
```

---

### Task 5: 重构 get_all_stock_codes → 基于 Toggle 的股票收集

**Files:**
- Modify: `app/services/preload.py:422-442` (重写 `get_all_stock_codes`)

**Step 1: 重写方法**

将 `get_all_stock_codes()` 改为只从 `preload_enabled=True` 的板块收集股票：

```python
@staticmethod
def get_all_stock_codes() -> list:
    """获取所有需要预加载的股票代码（仅 preload_enabled=True 的板块）"""
    from app.models.category import Category

    enabled_categories = Category.query.filter_by(preload_enabled=True).all()
    if not enabled_categories:
        return []

    # 收集所有启用板块的 ID（含子板块）
    category_ids = set()
    for cat in enabled_categories:
        category_ids.add(cat.id)
        for child in cat.children:
            category_ids.add(child.id)

    # 查询这些板块下的所有股票
    stock_cats = StockCategory.query.filter(
        StockCategory.category_id.in_(category_ids)
    ).all()

    stock_map = {}
    for sc in stock_cats:
        if sc.stock_code and sc.stock_code not in stock_map:
            stock = Stock.query.filter_by(stock_code=sc.stock_code).first()
            stock_map[sc.stock_code] = stock.stock_name if stock else sc.stock_code

    return [{'code': code, 'name': name} for code, name in stock_map.items()]
```

**关键变更**：
- 删除从 Position 表获取股票的逻辑
- 删除 `re.match(r'^[0-9]{6}$')` 过滤 — 不再限制只有A股，支持美股/港股
- 一级板块 `preload_enabled=True` 时，自动包含其所有子板块的股票

**Step 2: 验证**

手动开启某个板块的 Toggle，调用预加载，确认只处理该板块的股票。

**Step 3: Commit**

```
refactor: get_all_stock_codes 改为基于板块 Toggle 收集股票
```

---

### Task 6: 重构预加载流程 — 按市场分组 + yfinance 批量

**Files:**
- Modify: `app/services/preload.py:114-195` (重写 `start_preload`)
- Modify: `app/services/unified_stock_data.py:1759-1848` (新增 `_fetch_trend_batch_yfinance`)

**Step 1: 在 UnifiedStockDataService 中新增批量走势方法**

在 `app/services/unified_stock_data.py` 的 `_fetch_trend_from_yfinance` 方法之后，添加批量版本：

```python
def _fetch_trend_batch_yfinance(self, stock_codes: list, days: int,
                                 stock_name_map: dict, stock_categories: dict) -> list:
    """使用 yf.download() 批量获取多只股票走势数据"""
    import yfinance as yf

    if not stock_codes:
        return []

    yf_codes = [self._get_yfinance_symbol(c) for c in stock_codes]
    code_map = dict(zip(yf_codes, stock_codes))  # yf_code -> original_code

    logger.info(f"[数据服务.走势] yf.download 批量获取 {len(yf_codes)} 只...")

    try:
        df = yf.download(
            tickers=yf_codes,
            period=f"{days + 10}d",
            group_by='ticker',
            threads=True,
            progress=False
        )
    except Exception as e:
        logger.error(f"[数据服务.走势] yf.download 批量失败: {e}")
        return self._fetch_trend_from_yfinance(
            stock_codes, days,
            date.today() - timedelta(days=days + 10), date.today(),
            stock_name_map, stock_categories, f'ohlc_{days}'
        )

    results = []
    # 单只股票时 yf.download 返回单层 DataFrame，需要特殊处理
    if len(yf_codes) == 1:
        yf_code = yf_codes[0]
        original_code = code_map[yf_code]
        result = self._parse_yf_dataframe(df, original_code, days, stock_name_map, stock_categories)
        if result:
            results.append(result)
    else:
        for yf_code in yf_codes:
            original_code = code_map[yf_code]
            try:
                ticker_df = df[yf_code] if yf_code in df.columns.get_level_values(0) else None
                if ticker_df is None or ticker_df.empty:
                    continue
                result = self._parse_yf_dataframe(ticker_df, original_code, days, stock_name_map, stock_categories)
                if result:
                    results.append(result)
            except Exception as e:
                logger.debug(f"[数据服务.走势] {original_code} 批量解析失败: {e}")

    if results:
        names = ', '.join(f"{r['stock_name']}({len(r['data'])}天)" for r in results)
        logger.info(f"[数据服务.走势] yf.download 批量完成 → {names} ({len(results)}只)")
    return results

def _parse_yf_dataframe(self, df, stock_code: str, days: int,
                         stock_name_map: dict, stock_categories: dict) -> dict | None:
    """解析 yfinance DataFrame 为统一格式"""
    df = df.dropna(subset=['Close']).tail(days)
    if len(df) < 2:
        return None

    base_price = float(df['Close'].iloc[0])
    data_points = []
    for idx, row in df.iterrows():
        open_p = row.get('Open')
        high_p = row.get('High')
        low_p = row.get('Low')
        close_p = row.get('Close')
        volume = row.get('Volume', 0)

        if pd.isna(close_p):
            continue

        change_pct = (float(close_p) - base_price) / base_price * 100
        trade_date = idx.strftime('%Y-%m-%d') if hasattr(idx, 'strftime') else str(idx)[:10]
        data_points.append({
            'date': trade_date,
            'open': round(float(open_p), 2) if not pd.isna(open_p) else 0,
            'high': round(float(high_p), 2) if not pd.isna(high_p) else 0,
            'low': round(float(low_p), 2) if not pd.isna(low_p) else 0,
            'close': round(float(close_p), 2),
            'change_pct': round(change_pct, 2),
            'volume': int(volume) if not pd.isna(volume) else 0
        })

    if len(data_points) < 2:
        return None

    sc = stock_categories.get(stock_code, {})
    return {
        'stock_code': stock_code,
        'stock_name': stock_name_map.get(stock_code, stock_code),
        'category_id': sc.get('category_id'),
        'data': data_points
    }
```

**Step 2: 重构 start_preload 按市场分组**

重写 `app/services/preload.py` 的 `start_preload()` 方法：

```python
@staticmethod
def start_preload(target_date: date) -> dict:
    """启动预加载流程 — 按市场分组批量获取"""
    from flask import current_app
    from app.services.unified_stock_data import unified_stock_data_service
    from app.utils.market_identifier import MarketIdentifier

    existing = PreloadStatus.query.filter_by(preload_date=target_date).first()
    if existing and existing.status == 'running':
        return {'success': False, 'message': '预加载正在进行中', 'total': existing.total_count}

    stock_list = PreloadService.get_all_stock_codes()
    if not stock_list:
        return {'success': False, 'message': '无有效股票代码（请在板块管理中开启预加载）', 'total': 0}

    total_count = len(stock_list)

    # 创建/更新预加载状态
    if existing:
        existing.status = 'running'
        existing.total_count = total_count
        existing.success_count = 0
        existing.failed_count = 0
        existing.current_stock = None
        existing.started_at = datetime.now()
        existing.completed_at = None
    else:
        record = PreloadStatus(
            preload_date=target_date, status='running',
            total_count=total_count, success_count=0, failed_count=0,
            started_at=datetime.now(),
        )
        db.session.add(record)
    db.session.commit()

    logger.info(f"[预加载.持仓] 启动: stocks={total_count}")

    # 按市场分组
    a_shares = []
    other_stocks = []
    for item in stock_list:
        market = MarketIdentifier.identify(item['code'])
        if market == 'A':
            a_shares.append(item)
        else:
            other_stocks.append(item)

    logger.info(f"[预加载.持仓] 分组: A股={len(a_shares)}, 其他={len(other_stocks)}")

    success_count = 0
    failed_count = 0

    # 阶段1: 批量获取走势数据（缓存预热）
    all_codes = [item['code'] for item in stock_list]
    PreloadService._update_current_stock(target_date, '批量获取走势数据...')
    try:
        unified_stock_data_service.get_trend_data(all_codes, 60, force_refresh=True)
    except Exception as e:
        logger.error(f"[预加载.持仓] 走势数据批量获取失败: {e}")

    # 阶段2: 批量获取实时价格
    PreloadService._update_current_stock(target_date, '批量获取实时价格...')
    try:
        unified_stock_data_service.get_realtime_prices(all_codes, force_refresh=True)
    except Exception as e:
        logger.error(f"[预加载.持仓] 实时价格批量获取失败: {e}")

    # 阶段3: 威科夫分析（数据已在缓存，直接分析）
    app = current_app._get_current_object()
    with ThreadPoolExecutor(max_workers=15) as executor:
        futures = {
            executor.submit(WyckoffAutoService.analyze_single, item['code'], item['name'], app): item
            for item in stock_list
        }
        for future in as_completed(futures):
            item = futures[future]
            PreloadService._update_current_stock(target_date, f"{item['name']}({item['code']})")
            try:
                result = future.result()
                if result.get('status') == 'success':
                    success_count += 1
                else:
                    failed_count += 1
            except Exception:
                failed_count += 1
            PreloadService._update_progress(target_date, success_count, failed_count)

    PreloadService._mark_completed(target_date, 'completed')
    logger.info(f"[预加载.持仓] 完成: success={success_count}, failed={failed_count}")

    return {
        'success': True,
        'message': f'预加载完成，成功 {success_count} 只，失败 {failed_count} 只',
        'total': total_count,
        'success_count': success_count,
        'failed_count': failed_count,
    }
```

**Step 3: 同步更新 start_preload_extended**

`start_preload_extended()` 同样使用 `get_all_stock_codes()`（已在 Task 5 中改为 Toggle 模式），此方法逻辑无需大改，只需确认 `get_all_stock_codes()` 调用正常。

**Step 4: 验证**

开启某个板块的 Toggle，手动触发预加载，观察日志确认：
1. 走势数据按市场分组获取
2. 美股/港股走的是批量接口
3. 威科夫分析使用缓存数据

**Step 5: Commit**

```
refactor: 预加载按市场分组 + yfinance 批量获取
```

---

### Task 7: 清理 start_preload_extended

**Files:**
- Modify: `app/services/preload.py:444-549`

**Step 1: 更新 start_preload_extended**

`start_preload_extended` 同样改为先批量获取走势+价格数据，再并发分析：

```python
@staticmethod
def start_preload_extended(target_date: date, max_workers: int = 15) -> dict:
    """扩展版预加载（先批量缓存，再并发分析）"""
    from flask import current_app
    from app.services.unified_stock_data import unified_stock_data_service

    existing = PreloadStatus.query.filter_by(preload_date=target_date).first()
    if existing and existing.status == 'running':
        return {'success': False, 'message': '预加载正在进行中', 'total': existing.total_count}

    stock_list = PreloadService.get_all_stock_codes()
    if not stock_list:
        return {'success': False, 'message': '无股票需要预加载（请在板块管理中开启预加载）', 'total': 0}

    total_count = len(stock_list)

    if existing:
        existing.status = 'running'
        existing.total_count = total_count
        existing.success_count = 0
        existing.failed_count = 0
        existing.current_stock = None
        existing.started_at = datetime.now()
        existing.completed_at = None
    else:
        record = PreloadStatus(
            preload_date=target_date, status='running',
            total_count=total_count, success_count=0, failed_count=0,
            started_at=datetime.now(),
        )
        db.session.add(record)
    db.session.commit()

    logger.info(f"[预加载.扩展] 启动: date={target_date}, stocks={total_count}, workers={max_workers}")

    # 批量预热缓存
    all_codes = [item['code'] for item in stock_list]
    try:
        unified_stock_data_service.get_trend_data(all_codes, 60, force_refresh=True)
    except Exception as e:
        logger.error(f"[预加载.扩展] 走势数据批量获取失败: {e}")
    try:
        unified_stock_data_service.get_realtime_prices(all_codes, force_refresh=True)
    except Exception as e:
        logger.error(f"[预加载.扩展] 实时价格批量获取失败: {e}")

    # 并发分析
    success_count = 0
    failed_count = 0
    failed_stocks = []
    app = current_app._get_current_object()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(WyckoffAutoService.analyze_single, item['code'], item.get('name', ''), app): item
            for item in stock_list
        }
        for future in as_completed(futures):
            item = futures[future]
            try:
                result = future.result()
                if result.get('status') == 'success':
                    success_count += 1
                else:
                    failed_count += 1
                    failed_stocks.append({
                        'code': item['code'], 'name': item.get('name', ''),
                        'error': result.get('error_msg', '未知错误'),
                    })
            except Exception as e:
                failed_count += 1
                failed_stocks.append({
                    'code': item['code'], 'name': item.get('name', ''),
                    'error': str(e),
                })
            PreloadService._update_progress(target_date, success_count, failed_count)

    PreloadService._mark_completed(target_date, 'completed')
    logger.info(f"[预加载.扩展] 完成: date={target_date}, success={success_count}, failed={failed_count}")

    return {
        'success': True,
        'message': f'预加载完成，成功 {success_count} 只，失败 {failed_count} 只',
        'total': total_count,
        'success_count': success_count,
        'failed_count': failed_count,
        'failed_stocks': failed_stocks,
    }
```

**Step 2: Commit**

```
refactor: start_preload_extended 同步改为批量预热 + 并发分析
```

---

### Task 8: 端到端验证

**Step 1:** 启动应用 `python run.py`，确认无报错

**Step 2:** 访问 `/categories/manage`，确认一级板块有 Toggle 开关

**Step 3:** 开启某个板块的 Toggle，触发预加载，观察日志：
- 确认只获取了该板块的股票
- 确认走势数据批量获取日志
- 确认威科夫分析正常完成

**Step 4:** 关闭所有板块 Toggle，触发预加载，确认提示"无有效股票代码"

**Step 5: Commit**

```
chore: 批量预加载重构验证通过
```
