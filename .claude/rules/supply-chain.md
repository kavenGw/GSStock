---
paths:
  - "app/config/supply_chain.py"
  - "app/templates/supply_chain.html"
---
# 产业链图谱与 tag 同步

> **何时读**：改 `SUPPLY_CHAIN_GRAPHS`、调 `/supply-chain` 渲染、回写标的 tag

- 配置 `app/config/supply_chain.py:SUPPLY_CHAIN_GRAPHS`，路由 `/supply-chain/api/<name>` 按 dict 遍历自动注册，新增图谱只加 key，零路由/模板/seed 改动。
- `upstream/midstream/downstream` 均支持 `companies`；公司条目 `tag` 取值 `frontEC` / `don_buy` / `keep_watching` / `not_analyzed`，前端 `TAG_LABELS` 映射文案。主题型图谱 `competitors` 可留 `{}`，`core.code` 用虚拟 slug。跨链复用标的在 `role` 末尾标「（同属 X 产业链）」。
- **tag 与分析档同步**：已建档标的不能停留在 `not_analyzed`。stock-research（模式 1/2）/ analyze-category 收尾时检查该股是否在图谱里、tag 是否需按评级更新。
