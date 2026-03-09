# 盯盘走势图优化设计

## 目标

优化盯盘页面走势图的可读性、AI分析展示、操作建议整合。

## 变更清单

### 1. 走势图坐标轴优化

**X轴（时间）**：
- 固定半小时间隔标签（09:30, 10:00, 10:30, ... 15:00）
- `axisLabel.formatter` 过滤：只显示分钟为 `:00` 或 `:30` 的时间点
- 字号 9px，不旋转

**Y轴（价格）**：
- `axisLabel.show: true`，格式化为实际价格
- grid 改为 `containLabel: true` 自适应价格标签宽度
- 保留 `scale: true`

### 2. AI分析自动化与Prompt增强

**触发机制**（现有基本满足）：
- 开盘立即触发 + 每15分钟触发
- 每次结果追加到右侧侧边栏

**Prompt增强**（`watch_analysis.py` 实时分析）：
- 输入增加：60日OHLC（均线计算）、持仓成本（如有）
- 输出扩展：走势解读（80字）+ 操作信号（买入/卖出/观望）+ 关键均线位置 + 建议操作价位区间
- 支撑位/阻力位继续输出（画线用）

### 3. 走势图布局改造

```
┌──────────────────────────────┬────────────┐
│          走势图 (70%)         │  AI分析    │
│  - 价格Y轴 + 时间X轴         │  侧边栏    │
│  - 支撑/压力线               │  (30%)     │
│  - 前日参考线                │            │
│                              │ 09:30 分析 │
│                              │ 09:45 分析 │
│                              │ 10:00 分析 │
└──────────────────────────────┴────────────┘
```

侧边栏：时间戳 + 信号标签（买入绿/卖出红/观望灰）+ 走势解读 + 均线/价位信息，时间倒序，可滚动。

### 4. 移除首页操作建议

删除：
- `app/services/portfolio_advice.py`
- portfolio-advice 相关API端点
- `index.html` 中操作建议渲染模块和JS

### 5. 算法支撑/压力线整合

- 从 `PortfolioAdviceService` 提取支撑/压力计算逻辑到独立工具函数
- 盯盘走势图用算法支撑/压力画 markLine
- AI分析返回的支撑/压力作为补充

## 涉及文件

- `app/static/js/watch.js` — 图表渲染、布局、侧边栏
- `app/templates/watch.html` — 布局结构
- `app/routes/watch.py` — 分析API增强
- `app/llm/prompts/watch_analysis.py` — Prompt重写
- `app/services/watch_service.py` — 分析数据存储扩展
- `app/services/portfolio_advice.py` — 删除
- `app/templates/index.html` — 移除操作建议模块
- `app/utils/support_resistance.py` — 新建，提取支撑/压力算法
