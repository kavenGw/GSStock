# 立讯精密（002475）buffett 重做 —— 设计 spec

> 日期：2026-05-31 ｜ 框架：brainstorming → 单文档六维深度重写（双轨结论）
> 目标：把 5-30 偏空的 buffett 档，沿 Rubin/AI/iPhone 新周期上行催化做深，收敛为六维深度重写 + 双轨估值。

## 背景

现有 `sectors/electronics/ems/2026-05-30-立讯精密-buffett分析.md`（143 行）结论 = **不买/分批减仓**，纪律轨论据扎实（毛利率 23.3%→11.9% 十年腰斩、近 5 年 FCF/净利 43%、2025 capex 179 亿致 FCF 转负、31x 已计入 AI 互联完美兑现）。但上行催化只有定性提及、无量化：

- Rubin/AI 高速铜连接：仅"224G/448G 线缆与背板连接器"一句，无单柜价值量·份额·三情景
- iPhone 新周期：未覆盖 FY26 出货弹性，**折叠屏 iPhone 完全缺失**
- 市场规模 / 全球竞争力：仅"全球互联龙头是 Amphenol/TE，立讯是追赶者"一句，无 TAM 拆分与对标体量

## 决策（已与用户确认）

1. **产出形态**：重做现有 buffett 档，`git mv` 5-30 → 5-31 原地升级（保留 git 历史），不新建文档
2. **结论立场**：双轨结论（同沃尔 house style）—— buffett 纪律轨（可能仍偏空）+ 成长/动量轨（Rubin·AI·iPhone 三情景量化的上行期望）并列，读者自取
3. **研究深度**：联网深研（WebSearch 取证），交叉 2-3 家锁数字后再建情景
4. **§2 现金流硬证据不软化**：毛利率腰斩 + FCF/净利 43% 是纪律轨锚点，保持
5. **成长轨年限**：FY27 + FY28 两年（Rubin 2026-27 爬坡、折叠屏约 2026-27 上市，单年看不全弹性）

## 交付物 —— 六维深度重写（git mv 后路径）

`sectors/electronics/ems/2026-05-31-立讯精密-buffett分析.md`

### frontmatter
- `doc_type: buffett` 不变；`conviction_date: 2026-05-31`；`stock_code: '002475'`（字符串引号）
- 现价 / 总市值 / PE_TTM / PB 联网刷新（基准日 2026-05-31）
- `rating: watch` 维持（双轨制下主评级以纪律轨为准）
- `watch_reason` 改写：纪律轨偏空 + 成长轨上行已量化，二者并列，避免与正文双轨矛盾
- `themes` 保留并补：消费电子 / ai_compute / 汽车线束（按需加 iPhone 折叠屏相关标签）
- `related_docs` 三篇保留（歌尔对比 / 汽车线束专题 / 工业富联），lint 重生块

### 六节结构与量化

| 节 | 收敛自 | 量化动作 |
|---|---|---|
| §1 市场规模与全球竞争格局 | 市场规模 + 全球竞争力 | 三块 TAM 拆分（消费电子代工 / AI 高速铜连接 / 汽车线束）各给规模与立讯份额；横向对标 Amphenol·TE·富士康·比亚迪电子互联/代工体量，落"高速互联追赶者非定义者"定位 |
| §2 盈利能力与现金流真相 | 盈利能力 | 沿用硬证据（毛利率十年腰斩、净利率 5.47%、近 5 年 FCF/净利 43%、2025 capex 179 亿 FCF 转负）+ 近 5 年 FCF 表，**不软化**，纪律轨锚 |
| §3 核心优势/护城河 | 核心优势 | 垂直整合 + 精密制造 + 王来春执行力 + 连接器切换成本雏形 vs commodity 本质张力；管理层资本配置（莱尼整合）评估 |
| §4 Rubin/AI 三情景量化 | Rubin 潜力 + AI 潜力 | GB300/Rubin 单柜高速铜连接（224G/448G 线缆+背板连接器）价值量 × 出货 × 立讯份额 → 熊/基/牛三情景 AI 连接收入与毛利贡献表 |
| §5 iPhone 新周期 | iPhone 销量增加 + iPhone 折叠屏 | ①FY26 iPhone 出货回升对立讯组装+AirPods/Watch 弹性（份额×ASP）；②折叠屏 iPhone 铰链/精密结构件/连接器 BOM 单机价值量增量 × 立讯卡位 × 渗透节奏 |
| §6 双轨估值与结论 | 结论 | 纪律轨（真实股东盈余多倍数法→内在价值区间→安全边际/买点）+ 成长轨（§4+§5 三情景加权 FY27/FY28 盈利→期望市值区间，标注"为成长付溢价=博弈非投资"前提）并列；Sell Criteria 复核 + Monitoring Indicators |

约束：保留 buffett doc_type 字段集；§2 不软化；双轨结论不互相覆盖。

## 研究计划（WebSearch 取证，交叉 2-3 家，标注来源与年度）

1. 立讯当前价 / 市值 / PE_TTM / PB（刷新基准；A 股实时价优先 `get_realtime_prices` 批量，估值分位走 web）
2. Rubin/GB300 高速铜连接单柜价值量 + 立讯在 NVIDIA 链份额（传闻口径需标注）
3. iPhone 折叠屏上市时点 / BOM 增量 / 立讯铰链·结构件卡位
4. FY26 iPhone 出货预估（多家投行口径交叉）
5. Amphenol(APH) / TE(TEL) 互联收入体量（全球竞争对标）

数据来源：复用现档 FY2025 财务 + 5 年 FCF 表；akshare 补采按需（`stock_financial_abstract_ths` / `stock_zygc_em`）；一次性脚本走 `scripts/_xxx.py`（顶部加 sys.path），产物存 `.omc/artifacts/`，结束 `rm`，不入库。

## 收尾

- `python scripts/lint_docs_frontmatter.py`
- `python scripts/lint_docs_refs.py --rewrite-blocks`
- 退出码 0 后 commit（rtk 前缀）；commit message 记录 git mv + 六维重写 + 双轨

## 验收标准

- 文档 git mv 5-30→5-31，六节齐备，§4 含 Rubin 三情景表、§5 含折叠屏 BOM 量化、§1 含 TAM 拆分与对标
- §2 现金流硬证据保留未软化；§6 双轨结论并列、各自前提清晰
- 联网数字均标注来源与年度，传闻口径显式标注
- frontmatter 过 `lint_docs_frontmatter`；related_docs 反向对称，`lint_docs_refs` 退出码 0
