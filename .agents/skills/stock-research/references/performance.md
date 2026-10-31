# 正式财报 → 业绩页

模式 1/2 核实正式财报时加载本文件。A1 采数，写手落盘，独立审查对账，C 校验后随研究档提交。
预告、快报、卖方预测、新闻和会议纪要不覆盖正式业绩。页面 `/performance/` 每次读取研究目录中的
`performance.yaml`，无需数据库任务；七份 Markdown 的结构保持原约定。
招股书中已实现、经审阅的历史季度财务数据可作比较基数，须注明审阅状态，不能取同书中的业绩预计。

## 数据口径

- 公司身份沿用本公司 `index.md` 的 `stock_code`/`stock_name`；A+H 不拆成两份同公司财报。
- `revenue` = 合并单季度营业收入；`adjusted_profit` = 单季度扣非归母净利润；`inventory` = 合并季末存货账面净额。
- 金额单位 `CNY_100M`（亿元人民币），沿用原表精度；万元÷10000、元÷100000000。
  不把估值主体的港币币种当作人民币财报币种。非人民币报表不作无汇率的强行换算，明确报告尚未接入。
- Q2=H1−Q1；Q3=前三季度−H1；Q4=全年−前三季度。须取同主体/同口径累计原数，保留算式及来源。
  库存是时点余额，不做累计差分；不得从已舍入环比反推比较基数。
- 至少采本季度和上一季度的三项原数；Q1 的上一季度是上年 Q4。已有其他季度可同时补入。
  无法取得的字段写 `null` 并在 `missing_reasons` 说明，不补零，不用归母或全部净利润冒充扣非。
- 每个季度保留正式财报 URL、标题、页码/科目定位；差分须有两个累计来源。
- 不存手写环比。页面从相邻季度原数算 `(本季/上季−1)×100`；缺数不计算。
  扣非亏损或零基数以扭亏/转亏/减亏/增亏/持平/上季为零标注。

## A1 交付

在既有 A1.md 中附**唯一一个**标记为 `performance` 的代码块，内容为以下 YAML。
它是同一份报告中的结构化事实，不另写报告。下方是格式示例，真实交付须替换全部示例内容，
按上述规则补比较季度，数值与明细及研究正文一致。

````text
```performance
schema_version: 1
stock_code: '公司代码'
stock_name: 公司名称
unit: CNY_100M
periods:
  - period: 2026Q3
    report_type: formal
    updated_at: '2026-10-31'
    revenue: 1.0
    adjusted_profit: 0.1
    inventory: null
    missing_reasons:
      inventory: 实际未取得原因
    sources:
      - title: 公司2026年第三季度报告
        url: https://example.com/official-report.pdf
        locator: 实际交付填写真实官方URL、页码及科目；差分列原数与算式
    notes: 可选，说明重述、并表或数据精度限制
```
````

## 写手、审查与收尾

写手按 A1 输入执行，合并到本公司 `performance.yaml`，保留未更新季度：

```bash
python scripts/sync_performance.py --input .omc/artifacts/<股票名>-<日期>-A1.md --doc docs/stock-analytics/sectors/<sector>/<subsector>/<股票名>
```

再次研究同季度以新正式证据修正该季度；不能因为旧期本轮未披露就清空原记录。
审查读取完整 `git diff <公司目录>`，核对字段、单位、单季差分、期末存货、来源和与正文镜像；
基数缺失须明确记录，不能用“较年初”或同比代替环比。

```bash
python scripts/sync_performance.py --check
```

校验须 exit 0；它检查身份、季度唯一性、数值、缺失原因和来源结构，不替代对原文的事实审查。
C 的提交清单包含本股 `performance.yaml`；不写 SQLite。
