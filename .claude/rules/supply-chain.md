# 产业链图谱与 tag 同步

> **何时读**：改 app/config/supply_chain.py、新增/修改 `SUPPLY_CHAIN_GRAPHS` 图谱、调 `/supply-chain` 渲染、回写标的 tag 反映分析结论
> **不必读**：数据获取 / 缓存 / 通知格式 / 盯盘 / 纯前端

## 产业链图谱约定

配置在 `app/config/supply_chain.py` 的 `SUPPLY_CHAIN_GRAPHS` 字典，渲染路由 `/supply-chain/api/<name>`。`upstream/midstream/downstream` 三层均支持 `companies` 字段；公司条目可带 `tag` 承载非产业链语义，约定取值 `frontEC` / `don_buy` / `keep_watching` / `not_analyzed`，前端 `supply_chain.html` 的 `TAG_LABELS` 映射显示文案。主题型图谱（如赛事）的 `competitors` 可留 `{}`，`core.code` 用虚拟 slug（如 `WC2026`）。新增图谱只需在 `SUPPLY_CHAIN_GRAPHS` 加 dict key 即自动注册（路由按 dict 遍历），零路由/模板/seed 改动；跨链复用标的在 `role` 末尾标注「（同属 X 产业链）」与既有图谱保持一致。

## tag 与分析档同步

标的在 supply_chain 标 `not_analyzed` 且已建 buffett/分析档时，回写 `tag` 反映结论（至少从 `not_analyzed` 改为已分析态），避免图谱与 docs/stock-analytics 评级长期脱节。stock-deep-redo / analyze-category 收尾时一并检查该股是否在 `SUPPLY_CHAIN_GRAPHS` 里、tag 是否需更新。

> 关联：tag 与 docs/stock-analytics 评级的同步细节见 `docs-conventions.md`。
