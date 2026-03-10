# 盯盘助手 — 显示最新数据时间

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在盯盘页面显示价格数据的最后刷新时间，让用户知道数据新鲜度。

**Architecture:** 前端 Watch 对象记录每次价格刷新成功的时间戳，显示在页面标题下方的状态栏中，与股票数量并列展示。时间戳纳入 sessionStorage 缓存，页面刷新后可恢复。

**Tech Stack:** 原生 JavaScript, HTML

---

## 文件变更

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/static/js/watch.js` | 修改 | 添加 lastRefreshTime 属性、更新时机、状态显示 |
| `app/templates/watch.html` | 修改 | 状态栏增加刷新时间显示元素 |

---

### Task 1: 前端 — 记录并显示刷新时间

**Files:**
- Modify: `app/static/js/watch.js` — Watch 对象
- Modify: `app/templates/watch.html` — 状态栏

- [ ] **Step 1: watch.html — 状态栏增加时间元素**

在 `#watchStatus` 旁增加刷新时间显示：

```html
<!-- 原来 -->
<small class="text-muted" id="watchStatus">加载中...</small>

<!-- 改为 -->
<small class="text-muted">
    <span id="watchStatus">加载中...</span>
    <span id="lastRefreshTime" class="ms-2" style="display:none;"></span>
</small>
```

- [ ] **Step 2: watch.js — Watch 对象添加 lastRefreshTime 属性**

在 Watch 对象属性区域（约行 80 附近）添加：

```javascript
lastRefreshTime: null,
```

- [ ] **Step 3: watch.js — refreshIncrementalData 成功后记录时间**

在 `refreshIncrementalData()` 方法中，`priceData.success` 分支内追加：

```javascript
this.lastRefreshTime = new Date().toLocaleTimeString('zh-CN', {hour: '2-digit', minute: '2-digit', second: '2-digit'});
this.showRefreshTime();
```

- [ ] **Step 4: watch.js — 初始数据加载成功后也记录时间**

在 `init()` 方法中首次加载价格成功后，同样设置 lastRefreshTime（与 step 3 逻辑一致）。

- [ ] **Step 5: watch.js — 添加 showRefreshTime 方法**

在 `updateStatus` 方法附近添加：

```javascript
showRefreshTime() {
    const el = document.getElementById('lastRefreshTime');
    if (el && this.lastRefreshTime) {
        el.textContent = `· 最后刷新 ${this.lastRefreshTime}`;
        el.style.display = '';
    }
},
```

- [ ] **Step 6: watch.js — 缓存 snapshot/restore 纳入 lastRefreshTime**

`WatchCache.snapshot()` 添加 `lastRefreshTime: watch.lastRefreshTime`

`WatchCache.restore()` 添加 `watch.lastRefreshTime = cache.lastRefreshTime || null`

在 restore 后调用 `watch.showRefreshTime()` 恢复显示。

- [ ] **Step 7: 验证**

启动应用，打开盯盘页面：
- 初始加载完成后，状态栏应显示 "X 只股票 · 最后刷新 HH:MM:SS"
- 每 60 秒自动刷新后，时间应更新
- 页面 F5 刷新后，从缓存恢复时间戳仍显示
- 非交易时段（无活跃市场）最后刷新时间保持不变

- [ ] **Step 8: Commit**

```bash
git add app/static/js/watch.js app/templates/watch.html
git commit -m "feat: 盯盘助手显示最新数据刷新时间"
```
