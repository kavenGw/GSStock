# stock-research 模式 1/2 派发手册（控制者读；subagent 不读）

每个 subagent 都要拿到**完整自包含上下文**：标的 + 代码 + 市场 + 今天日期 + 知识截止须联网 + 本节列出的
必内联内容 + §0 汇报协议。它自行加载的只有：evidence 片段、旧档、`Skill buffett`、`Skill buffett-doc-spec`
（写手/审查员）、`Skill stock-doc-finalize`（Phase C）。

## 0. 两条通用协议

### 0.1 汇报文件协议（所有 subagent，硬约定）

subagent 完成后多数只发 idle 不回正文，prompt 里写"最终回复必须含正文"已被证明无效，必须改机制。
每份派发 prompt 末尾**一字不省**地加：

> 汇报**必须**用 Write 写到 `.omc/artifacts/<股票名>-<日期>-<阶段标识>-report.md`，写完才结束。
> 文件头两行固定为耗时戳（开工/收工各跑一次 `date "+%Y-%m-%d %H:%M:%S"`）：
> ```
> start: YYYY-MM-DD HH:MM:SS
> end: YYYY-MM-DD HH:MM:SS
> ```
> 其后是汇报正文。消息回传是可选冗余通道，不是交付方式。

阶段标识六种：`phaseA1` / `phaseA2` / `phaseA3` / `phaseB` / `review` / `phaseC`；追派复核写 `review-2`、
Phase B 返修写 `phaseB-2`。控制者不等消息、不追要，subagent 结束后直接 Read 文件。
自报时间戳只作交叉参考，耗时账以控制者自记派发/收回时刻为准，两者相差超 2 倍时在耗时账注明该棒自报失真 [L3]；
异常轮次并入对应段落并注明轮次（例：`审查 5.5 + 复核 2.0`）。

### 0.2 内联铁律：控制者摘原文，不给路径让 subagent 自读

让 subagent 自读整份参考文件既费墙钟又会挑错节（实测兄弟档 791 行只有 3-5 条有用、sector-lenses 261 行
只命中约 70 行）。下列内容**必须摘原文内联**，不许写"去读 sector-lenses.md / 参考兄弟档 xxx.md"：

| 内容 | 内联到 |
|---|---|
| 命中 lens 的【必查清单】 | A3 + 审查 |
| 命中 lens 的【撰写落点】【双面必答】【监控指标模板】 | Phase B |
| 兄弟档口径要点（3-5 行） | Phase B |
| 控制者前置观察，写成「我的推断是 X，请核实 X 是否成立」 | A1/A2/A3 三路都给 [L5] |

## 1. Phase A — 采证三路（并行，均 opus）

三份 prompt 共有：证据分级【硬/软/缺】+ 不造数 + 英文中文交叉验证 + 区分官方/媒体/分析师 + 找不到写
"未找到公开证据" + 每个关键数字挂 URL + 日期；各自深度上限一条（A1 跑完必查清单即收 / A2 每论点取到能定性即止
/ A3 逐条回应即可）；「A1 是所有硬数字唯一权威源，A2/A3 以定性为主，冲突以 A1 为准」[L15]。
evidence 文件 `.omc/artifacts/<股票名>-<日期>-evidence-A{1,2,3}-<后缀>.md`。

**A1 数据锚**（`-evidence-A1-数据锚.md`）：实时行情双源交叉 + 市值自洽校验、最新财报、逐月交付/出货、
可比公司估值表。取数脚本内联给它：

```python
import urllib.request
raw = urllib.request.urlopen('http://qt.gtimg.cn/q=sh603986', timeout=10).read().decode('gbk')
f = raw.split('"')[1].split('~')
print(f[1], f[3], f[39], f[45], f[46])  # name, price, PE_TTM, 市值(亿), PB —— A 股索引
```

A 股前缀 6→`sh`、0/3→`sz`；直连失败用 `UnifiedStockDataService.get_realtime_prices([code], force_refresh=True)`
兜底。**港股 `q=hk01810` 字段索引异于 A 股**，须 dump 全串自辨 + 市值=现价×总股本自洽校验（曾靠此兜住索引误读）；
港/美股市值/PE/PB/52 周优先 WebFetch `stockanalysis.com/quote/hkg|nasdaq/<code>/statistics/` 或 Yahoo，**双源交叉**。
亏损标的 PE=N/A 改看 PS/PB/Forward PE。多年财务 `ak.stock_financial_abstract_ths(symbol, indicator="按年度")`；
PE/PB 5 年分位 `ak.stock_zh_valuation_baidu(symbol, indicator=..., period="近5年")`；主营构成 `ak.stock_zygc_em(symbol='SZ300757')`。
消费/材料/能源/工业/金融标的须查最新年度分红（东财/同花顺/公司公告）。
akshare 限流/失效、新浪 IR PDF 无法解析、腾讯港股字段等取数坑见 `.claude/rules/data-fetch-conventions.md`；缓存见 `stock-data-cache.md`。A+H 新上市股腾讯市值/PB 失真见 memory `ah-newly-listed-quote-distortion`。
一次性脚本 `scripts/_xxx.py` 跑完即删（`PYTHONIOENCODING=utf-8`、写文件显式 utf-8、别用 heredoc、管道可能吞 stdout
→ 验证脚本改写文件再 Read；详见 `.claude/rules/dev-environment.md`）。

**A2 论点验证**（`-evidence-A2-论点.md`）：给旧档核心多空论点清单 + 本次重审触发的新变量；逐条联网核实，
每条给证据分级 + URL + 日期 + **反驳点**；供给侧论点逐家拆退出/扩产/政策的范围+时间表+动机；报价/需求数据
注明机构间分歧；标的最新动向（季报/路线图）。目标已是文件夹档时，内联 `events.md` 里的未消化事件
（theme `date` > 旧 index `conviction_date` 的条目：note/impact/magnitude）作为必核新变量，逐条判强化/动摇/推翻是否成立。

**A3 lens 专项**（`-evidence-A3-lens.md`）：内联命中 lens 的【必查清单】原文，逐条核实，查不到明写不许跳过；
概念维度线索标【实证/概念】。

**不派合并 agent**；"相对旧档变化清单"移交 Phase B（需全局视野）。附件型（.docx/.pdf）二值事实缺口由控制者
亲自补证 [L12]。

**返回后控制者亲验**（自报不可信）：`ls scripts/` 确认采证脚本真删；逐个 Read 三份 evidence 确认真实落盘、
来源可靠；跨路校准消息必须收到「已闭合」回复才算闭合 [L2]。

## 2. Phase B — 撰写（1 个 opus，不拆）

要求先 `Skill buffett` 再 `Skill buffett-doc-spec`（frontmatter/13 节/估值机制/红线/变化清单均在该规格里，
不必再由控制者内联）。给：三份 evidence 路径 + 旧档路径（平铺档或旧 index.md）+ 新档目标文件夹
`sectors/<sector>/<subsector>/<股票名>/`。产出 6 文件（index/business/thesis/valuation/sources/events，节落点见规格）；
**events.md 已存在则不碰**，不存在才新建 `related_docs: []`；index.md ≤12KB，§0/§10/§11 引其他文件用相对链接不复制正文。

必内联：
- 命中 lens 的【撰写落点】【双面必答】【监控指标模板】原文——命中 lens 的每个必查项正文都要有回应
- 兄弟档口径要点 3-5 行（不给全文）
- A1 关键事实锚（实时市值/PB/PS/股本/汇率）+ 需纠正的旧档错误假设
- A+H 口径选定结果（取估值更低一侧，`stock_code`/`currency` 随之）

交办：写"相对旧档变化清单"（valuation.md 末尾）；标注 A2/A3 与 A1 的数字冲突（取 A1 并显式标注）；
只跑 `python scripts/lint_docs_frontmatter.py`，**不跑 refs、不 git add/commit**。
抗中断：先落主体、市值分母等待锚处留 `【待锚】` 再填 [L14]；财报盘后披露 + 次日盘前采证时开盘后补锚 [L10]。
汇报含评级 + 期望内在价值 + 安全边际 + 最脆弱论点自评。

**派发坑**：写 300+ 行可能报 `Stream idle timeout`、文件 0 落盘。先 `ls <文件夹>`/逐文件行数确认哪些未生成，再用
`SendMessage` 按原 agentId 续跑（"只 Write 缺的文件、勿再读文件/联网、勿分段"），**别重派**。六文件天然分段，
落盘顺序建议 index → valuation → thesis → business → sources → events，先保结论与估值。

## 3. 合并审查（1 个 read-only sonnet；异常升 opus）

给：新档文件夹路径（6 文件全读）+ 三份 evidence 路径；要求 `Skill buffett-doc-spec`（审查输出格式与红线在其 §4-§5）。
必内联：命中 lens 的【必查清单】【双面必答】原文；「所有含数字的 frontmatter 字段都要与正文 §0/§9 逐个比对」。
两段正文全文写进 report 文件——审查是"只回 idle 不给正文"的重灾区。

升级：`CHANGES-REQUESTED` 或规格段 Critical → 追派 opus 只读审查员复核（`review-2`），同一上下文复审直到过；
Minor nits 可修后控制者直接核验。

## 4. Phase C — 收尾（1 个 sonnet）

要求 `Skill stock-doc-finalize`（动作清单全在其中）。给：新档文件夹路径、待删旧档清单（仅平铺历史档，控制者已 Read 确认；目标此前已是文件夹则为空）、
`stock_code`、需补反向条目的被链档路径 + 控制者备好的反向 YAML 条目（path/note/symmetric）、commit message 文件名 `.git/MSG-<股票名>-<日期>.txt`。
汇报含双 lint 退出码 + valuations 同步状态 + SHA + `git show --stat HEAD` 文件清单 + 遗留检查结论。
