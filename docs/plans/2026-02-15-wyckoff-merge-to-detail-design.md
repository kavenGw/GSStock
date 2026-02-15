# 威科夫分析合并到股票详情页

## 目标

移除威科夫独立页面，将所有威科夫功能整合到股票详情抽屉中，支持单股实时分析。

## 移除清单

### 删除文件
- `app/templates/wyckoff_auto.html`
- `app/templates/wyckoff_reference.html`
- `app/templates/wyckoff_analysis.html`
- `app/static/js/wyckoff.js`
- `app/static/css/wyckoff.css`
- `app/routes/wyckoff.py`

### 修改文件
- `app/templates/base.html` — 导航栏移除"威科夫分析"链接
- `app/__init__.py` — 移除 wyckoff blueprint 注册

### 保留不动
- `app/services/wyckoff.py` — 分析服务
- `app/services/wyckoff_analyzer.py` — 核心算法
- `app/services/wyckoff_score.py` — 评分（走势看板使用）
- `app/services/backtest.py` — 回测服务
- `app/models/wyckoff.py` — 数据模型

## 新增 API（stock_detail.py）

### POST `/api/stock-detail/<code>/wyckoff/analyze`
触发单股威科夫分析，调用 `WyckoffAutoService.analyze_single()`，返回完整分析结果。

### POST `/api/stock-detail/<code>/wyckoff/backtest`
单股回测验证，调用 `BacktestService`，返回阶段准确率和信号胜率。

### GET `/api/stock-detail/<code>/wyckoff/reference/<phase>`
查询指定阶段的参考图，从 `WyckoffReference` 表读取。

### GET `/api/stock-detail/<code>/wyckoff/history`
查询该股票的历史分析记录（自动分析 + 手动分析），按时间倒序。

## 详情抽屉 UI 设计

### 位置
技术分析区下方，AI 分析区上方。

### 结构

```
┌─────────────────────────────────┐
│ 威科夫量价分析    [分析] [回测]  │
├─────────────────────────────────┤
│ 阶段: [吸筹] 📷   建议: [买入]  │
│ 事件: [spring] [shakeout]       │
│ 支撑: 45.20    阻力: 52.80     │
│ 分析时间: 2026-02-15 14:30     │
├─────────────────────────────────┤
│ ▶ 回测结果（折叠）              │
│   阶段准确率: 72%               │
│   信号胜率: 65%                 │
├─────────────────────────────────┤
│ ▶ 历史记录（折叠）              │
│   2026-02-15  吸筹  买入        │
│   2026-02-14  吸筹  观望        │
│   2026-02-13  下跌  观望        │
└─────────────────────────────────┘
```

### 交互逻辑

1. **打开抽屉时**：现有 `loadData()` 已获取 wyckoff 数据（最近一次分析结果），自动渲染
2. **点击"分析"**：POST 触发实时分析，loading 状态，完成后刷新结果区
3. **点击"回测"**：POST 触发回测，结果在折叠区展示
4. **阶段参考图**：阶段徽章旁图标，点击 GET 参考图，模态框展示
5. **历史记录**：折叠列表，展开显示该股票近期分析记录，点击条目展开详情

### 阶段颜色
- 吸筹 accumulation → 绿色
- 上涨 markup → 蓝色
- 派发 distribution → 橙色
- 下跌 markdown → 红色

### 建议颜色
- 买入 buy → 绿色
- 持有 hold → 蓝色
- 卖出 sell → 红色
- 观望 watch → 灰色
