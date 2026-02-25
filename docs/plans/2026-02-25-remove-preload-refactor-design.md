# 移除预加载 + 数据获取重构 实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 移除预加载机制，改为按需获取数据，各页面先返回缓存数据快速渲染，缺失数据后台获取后补全，start.bat 合并为单窗口启动。

**Architecture:** 删除预加载服务/路由/模型/UI，在 UnifiedStockDataService 新增 `get_cached_only()` 和 `refresh_missing_async()` 方法实现"快速缓存返回 + 后台异步刷新"模式。各页面API端点使用此模式，前端收到 partial 响应后延迟重试。

**Tech Stack:** Flask, SQLAlchemy, SQLite, JavaScript (原生)

---

### Task 1: 删除预加载文件

**Files:**
- Delete: `app/services/preload.py`
- Delete: `app/routes/preload.py`
- Delete: `app/models/preload.py`

**Step 1: 删除三个文件**

```bash
rm app/services/preload.py app/routes/preload.py app/models/preload.py
```

**Step 2: 确认无其他文件 import 这些模块**

```bash
grep -r "from app.services.preload" app/ --include="*.py"
grep -r "from app.models.preload" app/ --include="*.py"
grep -r "from app.routes.preload" app/ --include="*.py"
```

Expected: 除了 `__init__.py` 和 `preload.py` 自身外无其他引用。

**Step 3: Commit**

```bash
git add -A && git commit -m "refactor: 删除预加载服务/路由/模型文件"
```

---

### Task 2: 移除 preload_bp 注册和 imports

**Files:**
- Modify: `app/routes/__init__.py`

**Step 1: 修改 `__init__.py`**

删除第13行 `preload_bp = Blueprint('preload', __name__)`

修改第19行 import，移除 `preload`：
```python
from app.routes import main, position, advice, category, trade, stock, daily_record, profit, rebalance, heavy_metals, alert, briefing, strategy, stock_detail
```

**Step 2: 检查 `create_app()` 中是否注册了 preload_bp**

```bash
grep -r "preload_bp" app/
```

如果 `app/__init__.py` 中有 `app.register_blueprint(preload_bp)`，也需要移除。

**Step 3: Commit**

```bash
git add app/routes/__init__.py app/__init__.py && git commit -m "refactor: 移除 preload blueprint 注册"
```

---

### Task 3: 移除 Category 模型的 preload_enabled 字段

**Files:**
- Modify: `app/models/category.py:11` — 删除 `preload_enabled` 字段
- Modify: `app/models/category.py:23` — 从 `to_dict()` 移除

**Step 1: 修改模型**

从 Category 类中删除:
```python
preload_enabled = db.Column(db.Boolean, default=False, nullable=False)
```

从 `to_dict()` 中删除:
```python
'preload_enabled': self.preload_enabled,
```

**Step 2: Commit**

```bash
git add app/models/category.py && git commit -m "refactor: 移除 Category.preload_enabled 字段"
```

---

### Task 4: 移除 category 路由和服务中的 preload 相关代码

**Files:**
- Modify: `app/routes/category.py:86-94` — 删除 `toggle_preload` 路由
- Modify: `app/services/category.py:135-143` — 删除 `toggle_preload` 方法

**Step 1: 删除路由**

从 `app/routes/category.py` 删除:
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

**Step 2: 删除服务方法**

从 `app/services/category.py` 删除:
```python
@staticmethod
def toggle_preload(category_id, enabled):
    """切换板块预加载开关"""
    category = Category.query.get(category_id)
    if not category:
        return None, '板块不存在'
    category.preload_enabled = enabled
    db.session.commit()
    return category, None
```

**Step 3: Commit**

```bash
git add app/routes/category.py app/services/category.py && git commit -m "refactor: 移除 category preload toggle 路由和服务"
```

---

### Task 5: 移除前端预加载 UI

**Files:**
- Modify: `app/templates/category.html:31-36` — 删除 preload toggle 开关
- Modify: `app/templates/category.html:153-167` — 删除 preload toggle JS
- Modify: `app/templates/index.html:444-559` — 删除 PreloadManager 及其调用

**Step 1: 修改 category.html**

删除板块卡片中的预加载开关 HTML（第31-36行）:
```html
<div class="form-check form-switch mb-0" title="预加载开关">
    <input class="form-check-input preload-toggle" type="checkbox"
           data-id="{{ parent.id }}"
           {{ 'checked' if parent.preload_enabled else '' }}>
    <label class="form-check-label small text-muted">预加载</label>
</div>
```

删除底部 JS 中的 preload toggle 事件监听（第153-167行）。

**Step 2: 修改 index.html**

删除整个 `PreloadManager` 对象定义（第444-542行）。

删除 DOMContentLoaded 中的调用（第557-558行）:
```javascript
// 检查并启动预加载
PreloadManager.checkAndStart();
```

同时检查是否有 preload 相关的 CSS（如 `.preload-overlay`, `.preload-modal` 等），在 `app/static/css/` 中搜索并删除。

**Step 3: Commit**

```bash
git add app/templates/ app/static/ && git commit -m "refactor: 移除前端预加载 UI 和 JS"
```

---

### Task 6: 数据库迁移 — 删除 preload_status 表和 preload_enabled 列

**Files:**
- 直接操作 SQLite 数据库 `data/stock.db`

**Step 1: 写迁移脚本或手动执行**

由于使用 SQLAlchemy + SQLite 且无 Alembic，直接在 `create_app()` 中用 `db.create_all()` 管理表结构。删除模型后表不会自动删除，需要手动处理：

在项目根目录创建一次性迁移脚本 `migrate_remove_preload.py`：

```python
"""一次性迁移：删除预加载相关表和字段"""
import sqlite3
import os

db_path = os.path.join(os.path.dirname(__file__), 'data', 'stock.db')
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 1. 删除 preload_status 表
cursor.execute("DROP TABLE IF EXISTS preload_status")
print("已删除 preload_status 表")

# 2. 从 categories 表移除 preload_enabled 列
# SQLite 不支持 DROP COLUMN (3.35.0之前)，需要重建表
cursor.execute("PRAGMA table_info(categories)")
columns = cursor.fetchall()
has_preload = any(col[1] == 'preload_enabled' for col in columns)

if has_preload:
    keep_cols = [col[1] for col in columns if col[1] != 'preload_enabled']
    cols_str = ', '.join(keep_cols)
    cursor.execute(f"CREATE TABLE categories_new AS SELECT {cols_str} FROM categories")
    cursor.execute("DROP TABLE categories")
    cursor.execute("ALTER TABLE categories_new RENAME TO categories")
    print("已从 categories 表移除 preload_enabled 列")
else:
    print("categories 表无 preload_enabled 列，跳过")

conn.commit()
conn.close()
print("迁移完成")
```

**Step 2: 运行迁移**

```bash
python migrate_remove_preload.py
```

**Step 3: 验证后删除迁移脚本**

```bash
python -c "import sqlite3; c=sqlite3.connect('data/stock.db'); print(c.execute('SELECT name FROM sqlite_master WHERE type=\"table\"').fetchall())"
```

确认 `preload_status` 已不存在。然后删除迁移脚本。

**Step 4: Commit**

```bash
git add -A && git commit -m "refactor: 数据库迁移 — 删除 preload_status 表和 preload_enabled 列"
```

---

### Task 7: UnifiedStockDataService 新增 get_cached_only 方法

**Files:**
- Modify: `app/services/unified_stock_data.py`

**Step 1: 添加 get_prices_cached_only 方法**

在 `UnifiedStockDataService` 类中新增：

```python
def get_prices_cached_only(self, stock_codes: list) -> tuple:
    """只返回已缓存的实时价格，不触发API

    Returns:
        (cached_result: dict, missing_codes: list)
    """
    if not stock_codes:
        return {}, []

    cache_type = 'price'
    result = {}
    remaining = list(stock_codes)

    # 内存缓存
    memory_cached = memory_cache.get_batch(remaining, cache_type)
    result.update(memory_cached)
    remaining = [c for c in remaining if c not in memory_cached]

    if not remaining:
        return result, []

    # DB缓存
    effective_dates = self._get_effective_cache_dates(remaining)
    date_groups = {}
    for code in remaining:
        d = effective_dates[code]
        date_groups.setdefault(d, []).append(code)

    for cache_date, codes in date_groups.items():
        cached_data = UnifiedStockCache.get_cache_with_status(codes, cache_type, cache_date)
        for code, cache_info in cached_data.items():
            if cache_info and cache_info.get('data'):
                result[code] = cache_info['data']
                memory_cache.set(code, cache_type, cache_info['data'], stable=True)

    missing = [c for c in stock_codes if c not in result]
    return result, missing
```

**Step 2: 添加 get_trend_cached_only 方法**

```python
def get_trend_cached_only(self, stock_codes: list, days: int = 60) -> tuple:
    """只返回已缓存的走势数据，不触发API

    Returns:
        (cached_stocks: list, missing_codes: list)
    """
    if not stock_codes:
        return [], []

    cache_type = f'ohlc_{days}'
    cached_stocks = []
    remaining = list(stock_codes)

    # 内存缓存
    memory_cached = memory_cache.get_batch(remaining, cache_type)
    for code, data in memory_cached.items():
        cached_stocks.append(data)
    remaining = [c for c in remaining if c not in memory_cached]

    if not remaining:
        return cached_stocks, []

    # DB缓存
    effective_dates = self._get_effective_cache_dates(remaining)
    date_groups = {}
    for code in remaining:
        d = effective_dates[code]
        date_groups.setdefault(d, []).append(code)

    for cache_date, codes in date_groups.items():
        cached_data = UnifiedStockCache.get_cache_with_status(codes, cache_type, cache_date)
        for code, cache_info in cached_data.items():
            if cache_info and cache_info.get('data'):
                cached_stocks.append(cache_info['data'])
                memory_cache.set(code, cache_type, cache_info['data'], stable=True)

    cached_codes = set()
    for s in cached_stocks:
        if isinstance(s, dict) and 'stock_code' in s:
            cached_codes.add(s['stock_code'])
        elif isinstance(s, dict) and 'code' in s:
            cached_codes.add(s['code'])

    missing = [c for c in stock_codes if c not in cached_codes]
    return cached_stocks, missing
```

**Step 3: 添加 refresh_async 方法**

```python
def refresh_async(self, stock_codes: list, data_type: str = 'price', days: int = 60):
    """后台线程获取数据并写入缓存

    Args:
        stock_codes: 需要获取的股票代码
        data_type: 'price' 或 'trend'
        days: 走势天数（仅 data_type='trend' 时使用）
    """
    if not stock_codes:
        return

    def _do_refresh():
        try:
            from flask import current_app
            with current_app.app_context():
                if data_type == 'price':
                    self.get_realtime_prices(stock_codes, force_refresh=True)
                elif data_type == 'trend':
                    self.get_trend_data(stock_codes, days, force_refresh=True)
        except Exception as e:
            logger.error(f"[数据服务.异步刷新] 失败: {data_type}, codes={stock_codes[:3]}..., error={e}")

    thread = threading.Thread(target=_do_refresh, daemon=True)
    thread.start()
```

注意：`refresh_async` 需要 Flask app context。在路由中调用时，需要传入 app 对象或用 `current_app._get_current_object()` 获取。可能需要调整为接收 app 参数：

```python
def refresh_async(self, stock_codes: list, data_type: str = 'price', days: int = 60, app=None):
    if not stock_codes:
        return

    def _do_refresh():
        try:
            ctx = app.app_context() if app else None
            if ctx:
                ctx.push()
            try:
                if data_type == 'price':
                    self.get_realtime_prices(stock_codes, force_refresh=True)
                elif data_type == 'trend':
                    self.get_trend_data(stock_codes, days, force_refresh=True)
            finally:
                if ctx:
                    ctx.pop()
        except Exception as e:
            logger.error(f"[数据服务.异步刷新] 失败: {e}")

    thread = threading.Thread(target=_do_refresh, daemon=True)
    thread.start()
```

**Step 4: Commit**

```bash
git add app/services/unified_stock_data.py && git commit -m "feat: 新增 cached_only 和 refresh_async 方法支持渐进式数据加载"
```

---

### Task 8: 重构 Briefing API 端点支持 partial 返回

**Files:**
- Modify: `app/routes/briefing.py` — 各API端点增加 partial 逻辑
- Modify: `app/static/js/briefing.js` — 前端处理 partial 响应

**Step 1: 修改 `/briefing/api/stocks` 端点**

在路由中，先尝试 cached_only，有 missing 时启动异步刷新并标记 partial：

```python
@briefing_bp.route('/api/stocks')
def api_stocks():
    force = request.args.get('force', '').lower() == 'true'
    # ... 收集 stock_codes ...

    if not force:
        cached_prices, missing = unified_stock_data_service.get_prices_cached_only(stock_codes)
        if missing:
            app = current_app._get_current_object()
            unified_stock_data_service.refresh_async(missing, 'price', app=app)
        # 用 cached_prices 构建结果
        result = build_stock_result(cached_prices)
        return jsonify({'stocks': result, 'partial': len(missing) > 0, 'missing_count': len(missing)})
    else:
        # force 模式走原来的完整获取
        # ... 原有逻辑 ...
```

对其他端点（indices, futures, etf, sectors 等）做类似改造。

**Step 2: 修改 briefing.js 处理 partial**

每个 load 函数收到 `partial: true` 时，先渲染已有数据，然后 3 秒后自动重试一次：

```javascript
async loadStocks() {
    const data = await this.fetchAPI('/briefing/api/stocks');
    this.renderStocks(data.stocks);

    if (data.partial) {
        setTimeout(async () => {
            const fullData = await this.fetchAPI('/briefing/api/stocks');
            this.renderStocks(fullData.stocks);
        }, 3000);
    }
}
```

**Step 3: Commit**

```bash
git add app/routes/briefing.py app/static/js/briefing.js && git commit -m "feat: Briefing 页面支持渐进式数据加载（partial 模式）"
```

---

### Task 9: 重构 Heavy Metals API 端点支持 partial 返回

**Files:**
- Modify: `app/routes/heavy_metals.py` — category-data 等端点
- Modify: `app/templates/heavy_metals.html` 或相关 JS

**Step 1: 修改 `/heavy-metals/api/category-data` 端点**

当前该端点调用 `FuturesService.get_category_trend_data()` → `UnifiedStockDataService.get_trend_data()`。

改为：先用 `get_trend_cached_only()` 返回已有数据，missing 部分异步获取。

```python
# 在 category_data 路由中
cached_stocks, missing = unified_stock_data_service.get_trend_cached_only(codes, days)
if missing:
    app = current_app._get_current_object()
    unified_stock_data_service.refresh_async(missing, 'trend', days=days, app=app)

# 用 cached_stocks 构建响应
result = build_category_result(cached_stocks)
return jsonify({**result, 'partial': len(missing) > 0, 'missing_count': len(missing)})
```

**Step 2: 前端处理 partial**

Heavy Metals 的 JS 收到 partial 响应后，渲染已有数据，3秒后重试一次。

**Step 3: Commit**

```bash
git add app/routes/heavy_metals.py app/templates/heavy_metals.html && git commit -m "feat: Heavy Metals 支持渐进式数据加载"
```

---

### Task 10: start.bat 改造 — 单窗口启动

**Files:**
- Modify: `start.bat`
- Modify: `run.py`

**Step 1: 修改 start.bat**

```bat
@echo off
chcp 65001 >nul
cd /d "%~dp0"
title GSStock Server
echo 正在启动股票管理工具...
python run.py
```

**Step 2: 修改 run.py**

```python
import sys
import os
import webbrowser
import threading
import traceback
from app import create_app


def open_browser():
    """延迟打开浏览器"""
    webbrowser.open('http://127.0.0.1:5000')


def main():
    """启动应用"""
    try:
        app = create_app()
        # 仅在非 reloader 子进程时打开浏览器
        if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
            threading.Timer(1.5, open_browser).start()
        app.run(debug=True)
    except Exception as e:
        print("\n" + "=" * 60)
        print("启动失败！错误信息如下：")
        print("=" * 60)
        traceback.print_exc()
        print("=" * 60)
        print("\n按回车键退出...")
        input()
        sys.exit(1)


app = None
try:
    app = create_app()
except Exception as e:
    print(f"应用创建失败: {e}")
    traceback.print_exc()

if __name__ == '__main__':
    main()
```

**Step 3: 测试启动**

```bash
python run.py
```

确认：只有一个窗口，浏览器自动打开。

**Step 4: Commit**

```bash
git add start.bat run.py && git commit -m "refactor: start.bat 单窗口启动 + 自动打开浏览器"
```

---

### Task 11: 清理和验证

**Step 1: 全局搜索残留引用**

```bash
grep -r "preload" app/ --include="*.py" --include="*.html" --include="*.js" -l
grep -r "PreloadService\|PreloadStatus\|preload_bp\|PreloadManager\|preload_enabled" app/ -l
```

清理所有残留。

**Step 2: 启动应用验证**

```bash
python run.py
```

访问以下页面确认功能正常：
- 首页 `/` — 无预加载进度条
- 板块管理 `/categories` — 无预加载开关
- 每日简报 `/briefing/` — 数据渐进加载
- 走势看板 `/heavy-metals/` — 数据渐进加载
- 预警 `/alert/` — 功能不变

**Step 3: Commit**

```bash
git add -A && git commit -m "refactor: 清理预加载残留引用，完成重构验证"
```
