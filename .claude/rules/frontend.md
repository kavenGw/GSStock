---
paths:
  - "app/templates/**"
  - "app/static/**"
---
# 前端通用约定

> **何时读**：新增或改动任何页面的数据表格、写 Jinja 模板 / 静态 JS

## 表格排序

- **新增/改动任何数据表格都必须支持点击表头排序**，不允许只留一个写死的默认排序。参考实现：`value_dip.js` 的 `compare()` / `updateHeadIndicator()` + `watch.html` 的 `th.sortable[data-sort]`。
- 三条硬要求：① N/A / null **恒沉底**，不随升降序翻转（否则升序时满屏空值）② 表头带箭头指示当前排序列与方向（未排序列 ↕）③ 中文列用 `localeCompare(..., 'zh-CN')`，不要按码点排。
- 列 key 随状态变化时（如价值洼地的「高点回退」列随 7d/30d/90d 切换 `pullback_*`），`sortKey` 存**逻辑名**（`pullback`），渲染时再映射到实际字段，否则切周期后排序静默失效。
