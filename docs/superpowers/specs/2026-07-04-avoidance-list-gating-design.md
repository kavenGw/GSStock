# 低质地非科技标的清理 + 避坑列表 gating 机制

- **日期**: 2026-07-04
- **状态**: 设计已批准,待写实施计划
- **背景规则**: `.claude/rules/docs-conventions.md`「建档 gating」节 + memory `no-doc-for-lowquality-nontech.md`(露笑 002617 删档案例,2026-07-03)

## 目标

1. **存量清理**:删除已建的「低质地 + 非科技」buffett/分析档及其 `valuations.yaml` 条目。
2. **避坑列表**:建立机器可读的 `avoidance-list.yaml`,记录被避坑标的 + 负面 thesis + 当时硬数据快照。
3. **gating 机制**:未来建档前先查避坑列表;命中则做「避坑原因验证」——理由仍成立即中断建档,仅当理由被真实推翻(基本面改善)才放行,并把该标的移出列表。

## 非目标(YAGNI)

- 不为 `avoidance-list.yaml` 写专用 lint 校验脚本(结构简单,首批手工保证)。
- 不翻查历史上所有已删档补录(仅回填能确证的:露笑 + 本次删除标的)。
- 不删科技类 exclude 档(半导体/电子/ai-application 即便 exclude 也保留作反面对照)。

## 一、存量清理(一次性)

### 扫描范围
非科技 sector 的 buffett/分析档:`materials` / `industrial` / `media` / `consumer` / `energy` / `financial` / `healthcare` / `other`。**排除**科技类:`semiconductor` / `electronics` / `ai-application`。

### 逐档质地验证(akshare)
- ROE 多年序列:`ak.stock_financial_abstract_ths(symbol, indicator="按年度")`
- 是否曾巨亏(最差年份净利)
- 护城河 / 是否无护城河的低质量多元化制造
- 题材敞口:主业与所蹭题材的收入关联度,`ak.stock_zygc_em(symbol='SZ<code>')` 最新报告期「按产品分类」切片

### 删除判据(三条全中才删)
1. 非科技类,**AND**
2. 质地差(ROE 长期偏低 / 曾巨亏 / 无护城河的低质量多元化制造),**AND**
3. 题材敞口 ≈ 0(纯蹭热度)

> 万华化学、中金黄金等高质地非科技龙头**不命中,保留**。

### 产出与确认
候选删除列表,每条带证据(ROE 序列 / 巨亏年份 / 题材收入占比)→ **用户逐个确认后才删**。

### 删除动作(每个确认标的)
- 删 `.md` 档(`git rm`)
- 删 `valuations.yaml` 对应条目
- 清理兄弟档 `related_docs` 反向链
- 同步 supply_chain tag(若该股在 `SUPPLY_CHAIN_GRAPHS` 内)
- 跑 `PYTHONIOENCODING=utf-8 python scripts/lint_docs_refs.py --check-orphans`,exit 0 为真闸

## 二、避坑列表 YAML

**位置**:`docs/stock-analytics/avoidance-list.yaml`(与 `valuations.yaml` 并列,不受 docs linter 约束)。

**Schema**(每条):
```yaml
- stock_code: '002617'          # 带引号防前导 0 丢失(YAML int 化)
  stock_name: 露笑科技
  sector: industrial
  avoid_reason: 多元化工业(漆包线+高空机械+光伏电站),ROE<5%,2022 巨亏,SiC 纯蹭概念收入≈0
  avoid_date: '2026-07-03'
  key_metrics_snapshot:         # 当时硬数据,供未来 gating 验证逐条对照
    roe_recent: 4.2
    worst_loss_year: '2022'
    theme_revenue_pct: 0
  source: 已删 exclude 档(sectors/industrial/.../露笑科技-buffett分析.md)
```

**首批数据** = 一、确认删除的标的 + 露笑 002617(历史案例回填)。按 `stock_code` 唯一去重/覆盖。

## 三、gating 协议(建档前硬门)

**落点**:
- 扩写 `.claude/rules/docs-conventions.md`「建档 gating」节,新增避坑列表验证协议。
- 在 `buffett` / `stock-deep-redo` / `analyze-category` 三个 SKILL 的采证阶段各加一步硬门。

**流程**:建档前 `load avoidance-list.yaml` → 命中 `stock_code`?
- **未命中** → 正常建档流程。
- **命中** → 强制**避坑原因验证**:
  - 用最新单季季报 + akshare 重取 `key_metrics_snapshot` 对应指标。
  - 对照 `avoid_reason` **逐条**判定「仍成立 / 被推翻」,必须列出每条原因 + 当前实测值对照(不接受空口「改善了」)。
  - **判定结果**:
    - **仍成立** → **中断建档**,口头说明「命中避坑列表且理由仍成立,不建档」,停手。不进入写档/estimate/valuations 流程。
    - **被推翻**(基本面真实反转)→ 放行建档;建档完成后从 `avoidance-list.yaml` **移除该条**。

## 四、收尾/校验

- `PYTHONIOENCODING=utf-8 python scripts/lint_docs_refs.py --check-orphans` exit 0。
- `avoidance-list.yaml` 不入 docs frontmatter/refs linter(和 `valuations.yaml` 同待遇)。
- 更新 memory `no-doc-for-lowquality-nontech.md`:关联 `[[avoidance-list]]`,补 gating 验证协议要点。

## 关键设计决策(brainstorm 结论)

| 决策点 | 结论 |
|--------|------|
| 「反转→中断」语义 | 验证后**避坑理由仍成立即中断建档**;仅理由被推翻(基本面改善)才放行 |
| 避坑列表形态 | 独立 YAML(类 `valuations.yaml`),机器可读优先 |
| 删除识别方式 | 扫描非科技 sector + 逐档 akshare 验证质地 → 提候选列表,用户逐个审批 |
| 放行后列表维护 | 从 `avoidance-list.yaml` 移除该条 |
| 首批回填范围 | 仅露笑 + 本次删除标的(能确证的) |
| gating 落点 | 三个 SKILL 各加硬门 + `docs-conventions.md` 扩写 |
