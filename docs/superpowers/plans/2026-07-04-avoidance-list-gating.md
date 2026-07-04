# 低质地非科技标的清理 + 避坑列表 gating 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 删除已建的低质地非科技档及其 valuations 条目,建立机器可读的 `avoidance-list.yaml`,并在建档 skill 中加入「建档前避坑验证硬门」。

**Architecture:** 一次性存量清理(Task 1 采证+人审 → Task 2 执行删除)→ 建避坑列表 YAML(Task 3)→ gating 协议落到规则文档 + 三个 SKILL(Task 4)→ memory 同步(Task 5)。避坑列表与 `valuations.yaml` 并列,不受 docs linter 约束。

**Tech Stack:** Python(akshare 取数)、YAML(避坑列表 + valuations)、Markdown(docs + SKILL)、`scripts/lint_docs_refs.py`(refs 校验闸)。

## Global Constraints

- 所有 git/python/pytest 命令前加 `rtk`,链式 `&&` 中也要。
- Windows 打印含中文/emoji 对象需 `PYTHONIOENCODING=utf-8`;写含中文文件必须显式 `encoding='utf-8'`。
- `stock_code` / `stock_codes` 在 YAML 中必须字符串引号(防前导 0 丢失)。
- 一次性脚本用 `Write → scripts/_xxx.py → python scripts/_xxx.py`,任务结束 `rm`,不入库。`scripts/_xxx.py` 内 `from app import ...` 需在顶部 `sys.path.insert(0, str(Path(__file__).resolve().parent.parent))`。
- `git add` 与 `git commit` 放同一条 Bash 命令链(防并行 session 抢 index);中文多行 message 走文件 `git commit -F`。
- 删除判据(三条全中才删):非科技类 **AND** 质地差(ROE 长期偏低 / 曾巨亏 / 无护城河低质量多元化) **AND** 题材敞口 ≈ 0(纯蹭热度)。
- 科技类(`semiconductor` / `electronics` / `ai-application`)一律不删,即便 exclude。
- lint 收尾真闸:`PYTHONIOENCODING=utf-8 rtk python scripts/lint_docs_refs.py --check-orphans` exit 0。

---

### Task 1: 扫描非科技档 + 质地验证 → 候选删除列表(人审关口)

**Files:**
- Create(临时): `scripts/_scan_lowquality_nontech.py`
- Read: `docs/stock-analytics/sectors/{materials,industrial,media,consumer,energy,financial,healthcare}/**/*.md`
- Produce(临时): `.omc/artifacts/lowquality-nontech-candidates.json`(已 gitignore)

**Interfaces:**
- Produces:候选删除列表,每条 `{stock_code, stock_name, sector, subsector, doc_path, rating, roe_series, worst_loss_year, theme_revenue_pct, verdict, evidence}`。Task 2/3 消费 `doc_path` / `stock_code` / 各硬指标。

- [ ] **Step 1: 收集非科技候选档 + frontmatter**

Write `scripts/_scan_lowquality_nontech.py`:用 Glob 遍历 7 个非科技 sector 目录下所有 `*-buffett分析.md` 与分析档,`yaml.safe_load` 读 frontmatter,提取 `stock_code`/`stock_name`/`rating`/所在 subsector。输出初筛清单(仅 `rating in {exclude, watch}` 的进候选池,`config`/`core` 高信念档跳过)。用 `str(fm.get('conviction_date') or '')` 防 date 比较 TypeError。

```python
import sys, json, yaml, glob
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
NONTECH = ['materials','industrial','media','consumer','energy','financial','healthcare']
rows = []
for sec in NONTECH:
    for p in glob.glob(str(ROOT/f'docs/stock-analytics/sectors/{sec}/**/*.md'), recursive=True):
        txt = Path(p).read_text(encoding='utf-8')
        if not txt.startswith('---'): continue
        fm = yaml.safe_load(txt.split('---',2)[1])
        if not isinstance(fm, dict): continue
        rating = fm.get('rating')
        if rating not in ('exclude','watch'): continue
        rows.append({'doc_path': str(Path(p).relative_to(ROOT)).replace('\\','/'),
                     'stock_code': str(fm.get('stock_code') or fm.get('stock_codes')),
                     'stock_name': fm.get('stock_name'), 'sector': sec, 'rating': rating})
Path(ROOT/'.omc/artifacts').mkdir(parents=True, exist_ok=True)
Path(ROOT/'.omc/artifacts/lowquality-nontech-candidates.json').write_text(
    json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'{len(rows)} candidates')
```

- [ ] **Step 2: 运行初筛,确认产出清单非空**

Run: `PYTHONIOENCODING=utf-8 rtk python scripts/_scan_lowquality_nontech.py`
Expected: 打印 `N candidates`(N≥1),`.omc/artifacts/lowquality-nontech-candidates.json` 生成。用 Read 工具查看清单。

- [ ] **Step 3: 逐档 akshare 质地验证**

对 Step 2 每个候选(A 股)批量取数,不在循环里逐 code:
- ROE 多年序列:`ak.stock_financial_abstract_ths(symbol, indicator="按年度")`(取 ROE 行,判长期是否偏低 <8%)
- 最差年份净利(判是否曾巨亏)
- 题材敞口:`ak.stock_zygc_em(symbol='SZ<code>')` 最新报告期「按产品分类」切片,估算所蹭题材收入占比

把结果并回 JSON,每条加 `roe_series`/`worst_loss_year`/`theme_revenue_pct`/`verdict`(三条全中=`DELETE`,否则 `KEEP`)/`evidence`(一句话理由)。港股/非 A 股候选标 `verdict=MANUAL`(akshare 财务接口不覆盖,人工判)。

> 复用 Step 1 脚本追加取数逻辑;akshare 接口坑见 `.claude/rules/data-fetch-conventions.md`。

- [ ] **Step 4: 呈现候选删除列表,等待用户逐个确认**

把 `verdict==DELETE` 的标的整理成表格(stock_name / sector / ROE序列 / 巨亏年份 / 题材占比 / evidence)呈现给用户。**这是人审硬关口**——用户逐个确认哪些真删。把用户批准的最终删除集写入 `.omc/artifacts/lowquality-nontech-candidates.json` 的 `approved: true` 字段。

Expected:用户明确回复批准删除集(可能为空——若为空则跳过 Task 2,仅回填露笑到 Task 3)。

- [ ] **Step 5: 删临时脚本**

```bash
rm scripts/_scan_lowquality_nontech.py
```

> 无 commit——本任务仅产出待审清单(artifacts 已 gitignore),不改仓库跟踪文件。

---

### Task 2: 执行删除(仅对已批准标的)

**Files:**
- Delete: 每个批准标的的 `docs/stock-analytics/sectors/<sec>/<sub>/<date>-<name>-buffett分析.md`
- Modify: `docs/stock-analytics/valuations.yaml`(删对应条目)
- Modify: 引用被删档的兄弟档 `related_docs` 块
- Modify(如命中): `app/config/supply_chain.py`(tag 同步)

**Interfaces:**
- Consumes:Task 1 的 `approved: true` 标的(`doc_path` / `stock_code` / `stock_name`)。

> 若 Task 1 批准集为空,跳过整个 Task 2。

- [ ] **Step 1: 记录删前 refs lint 基线**

Run: `PYTHONIOENCODING=utf-8 rtk python scripts/lint_docs_refs.py --check-orphans; echo "exit=$?"`
Expected:记录当前 exit(理想 0)。若非 0,先确认违例是否本任务无关(并行 session 在写档),无关则继续。

- [ ] **Step 2: 逐标的删档 + 删 valuations 条目 + 清反向链**

对每个批准标的:
1. 删 `.md`:`git rm -q --ignore-unmatch <doc_path>`
2. 删 valuations 条目:编辑 `valuations.yaml`,移除 `source_doc` 等于该 `doc_path`(或 `stock_code` 匹配)的整条 dict。A+H 标的 valuations code 可能是港股形态,按 `source_doc` 匹配更稳。
3. 清兄弟档反向链:`grep -rn "<被删档名>" docs/stock-analytics/**/*.md` 找出所有 `related_docs` 指向它的兄弟档,删掉对应条目(仅删 frontmatter `related_docs` 列表项,`<!-- BEGIN/END related_docs -->` 块由 lint 重生,不手编)。

- [ ] **Step 3: 同步 supply_chain tag**

Run: `grep -n "<stock_code>\|<stock_name>" app/config/supply_chain.py`
若命中,该股所在图谱条目若还挂 `not_analyzed` 或指向已删档,改为反映"已避坑/已删档"态(至少去掉悬空引用)。未命中则跳过。

- [ ] **Step 4: 重生本任务档的 refs 块 + 跑 lint**

只渲染本任务改动档的块(避免裹挟并行 session 在写档):

```bash
PYTHONIOENCODING=utf-8 rtk python -c "from pathlib import Path; import scripts.lint_docs_refs as L; docs=L._load_all(Path('.')); mine=[<本任务改动的兄弟档相对路径列表>]; sub={(Path('.')/p).resolve():docs[(Path('.')/p).resolve()] for p in mine}; L._rewrite_blocks(sub)"
```

> 若 `_load_all`/`_rewrite_blocks` 实际函数名不同,先 `grep -n "def " scripts/lint_docs_refs.py` 核对。

Run: `PYTHONIOENCODING=utf-8 rtk python scripts/lint_docs_refs.py --check-orphans; echo "exit=$?"`
Expected: exit=0(或仅剩与本任务无关的并行 session 违例)。

- [ ] **Step 5: Commit**

只精确 add 本任务文件,勿 `git add -A`(防裹挟他人半成品):

```bash
printf '%s\n' 'docs(cleanup): 删除低质地非科技档 + valuations 条目 + 清反向链' '' 'Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>' > .git/COMMIT_MSG.txt && rtk git add docs/stock-analytics/valuations.yaml <被删档路径> <改动的兄弟档路径...> app/config/supply_chain.py && rtk git commit -F .git/COMMIT_MSG.txt && rtk git show --stat HEAD | head -20
```

Expected:`git show --stat` 只含本任务文件,未裹挟他人在写档。

---

### Task 3: 建 avoidance-list.yaml(首批数据)

**Files:**
- Create: `docs/stock-analytics/avoidance-list.yaml`

**Interfaces:**
- Consumes:Task 1 批准删除标的的硬指标(`roe_series`/`worst_loss_year`/`theme_revenue_pct`)+ 露笑 002617 历史数据。
- Produces:`avoidance-list.yaml` 供 Task 4 的 gating 协议 load。

- [ ] **Step 1: 写 avoidance-list.yaml(露笑 + 本次删除标的)**

首条固定回填露笑,其余按 Task 2 已删标的补齐。`key_metrics_snapshot` 取 Task 1 采证的实测值。

```yaml
# 避坑列表 — 低质地非科技/已判掉标的登记表(不受 docs linter 约束,类 valuations.yaml)
# gating:建档前 skill 按 stock_code 查此表命中即做「避坑原因验证」,详见 .claude/rules/docs-conventions.md
- stock_code: '002617'
  stock_name: 露笑科技
  sector: industrial
  avoid_reason: 多元化工业(漆包线+高空机械+光伏电站),ROE<5%,2022 巨亏,SiC 纯蹭概念收入≈0
  avoid_date: '2026-07-03'
  key_metrics_snapshot:
    roe_recent: 4.2
    worst_loss_year: '2022'
    theme_revenue_pct: 0
  source: 已删 exclude 档(sectors/industrial/.../露笑科技-buffett分析.md)
# 以下按 Task 2 批准删除标的逐条补齐(字段同上)
```

- [ ] **Step 2: 验证 YAML 可解析且 stock_code 为字符串**

Run:
```bash
PYTHONIOENCODING=utf-8 rtk python -c "import yaml; d=yaml.safe_load(open('docs/stock-analytics/avoidance-list.yaml',encoding='utf-8')); assert all(isinstance(e['stock_code'],str) for e in d), 'stock_code 必须字符串'; assert len({e['stock_code'] for e in d})==len(d),'stock_code 有重复'; print(f'{len(d)} entries OK')"
```
Expected: `N entries OK`,无 AssertionError。

- [ ] **Step 3: 确认 valuations 无 orphan 引用(避坑标的应已无 valuations 条目)**

Run:
```bash
PYTHONIOENCODING=utf-8 rtk python -c "import yaml; av={e['stock_code'] for e in yaml.safe_load(open('docs/stock-analytics/avoidance-list.yaml',encoding='utf-8'))}; val=yaml.safe_load(open('docs/stock-analytics/valuations.yaml',encoding='utf-8')); dup=[v['stock_code'] for v in val if str(v.get('stock_code')) in av]; print('冲突:',dup or '无')"
```
Expected: `冲突: 无`(避坑标的不应还在 valuations)。

- [ ] **Step 4: Commit**

```bash
printf '%s\n' 'docs(avoidance): 新建 avoidance-list.yaml 避坑列表(首批:露笑+本次删除标的)' '' 'Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>' > .git/COMMIT_MSG.txt && rtk git add docs/stock-analytics/avoidance-list.yaml && rtk git commit -F .git/COMMIT_MSG.txt && rtk git show --stat HEAD | head -5
```

---

### Task 4: gating 协议落地(规则文档 + 三个 SKILL)

**Files:**
- Modify: `.claude/rules/docs-conventions.md`(「建档 gating」节扩写)
- Modify: `.claude/skills/buffett/SKILL.md`(或对应路径)采证阶段加硬门
- Modify: `.claude/skills/stock-deep-redo/SKILL.md` 同上
- Modify: `.claude/skills/analyze-category/SKILL.md` 同上

**Interfaces:**
- Consumes:`docs/stock-analytics/avoidance-list.yaml`(Task 3)。

- [ ] **Step 1: 定位三个 SKILL 的采证/gating 段落**

Run: `grep -rln "低质地\|建档 gating\|不建档\|采证" .claude/skills/ .claude/rules/docs-conventions.md`
用 Read 查看各 SKILL 现有采证阶段与 docs-conventions.md 现有 gating 节,确认插入点。

- [ ] **Step 2: 扩写 docs-conventions.md 建档 gating 节**

在现有「建档 gating:低质地非科技标的不建档」节后追加避坑验证协议:

```markdown
## 建档前避坑列表验证(硬门)

建档 skill(buffett / stock-deep-redo / analyze-category)采证阶段**第一步**先 load `docs/stock-analytics/avoidance-list.yaml`,按 `stock_code` 查命中:
- **未命中** → 正常流程。
- **命中** → 强制「避坑原因验证」:用最新单季季报 + akshare 重取 `key_metrics_snapshot` 对应指标,对照 `avoid_reason` **逐条**判「仍成立 / 被推翻」,**必须列出每条原因 + 当前实测值对照**,不接受空口「改善了」。
  - **仍成立** → **中断建档**,口头说明「命中避坑列表且理由仍成立,不建档」,停手,不进入写档/estimate/valuations 流程。
  - **被推翻**(基本面真实反转) → 放行建档;建档完成后从 `avoidance-list.yaml` **移除该条**并 commit。
```

- [ ] **Step 3: 三个 SKILL 采证阶段各加硬门指引**

在 `buffett` / `stock-deep-redo` / `analyze-category` 三个 SKILL 的采证/第一阶段各插入一行(措辞按各 SKILL 语境微调):

```markdown
**建档前避坑门(强制)**:采证第一步先查 `docs/stock-analytics/avoidance-list.yaml`——命中 `stock_code` 则按 `.claude/rules/docs-conventions.md`「建档前避坑列表验证」做原因验证;理由仍成立即中断建档,被推翻才放行并移除列表条目。
```

- [ ] **Step 4: 验证三处引用一致 + 文件可读**

Run: `grep -rn "avoidance-list.yaml" .claude/rules/docs-conventions.md .claude/skills/`
Expected:docs-conventions.md 1+ 处 + 三个 SKILL 各 1 处,共 ≥4 处命中,路径一致。

- [ ] **Step 5: Commit**

```bash
printf '%s\n' 'docs(gating): 建档前避坑列表验证硬门——docs-conventions + buffett/stock-deep-redo/analyze-category 三 SKILL' '' 'Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>' > .git/COMMIT_MSG.txt && rtk git add .claude/rules/docs-conventions.md .claude/skills/buffett/SKILL.md .claude/skills/stock-deep-redo/SKILL.md .claude/skills/analyze-category/SKILL.md && rtk git commit -F .git/COMMIT_MSG.txt && rtk git show --stat HEAD | head -10
```

> SKILL 实际路径若不在 `.claude/skills/<name>/SKILL.md`,Step 1 的 grep 会给出真实路径,按实调整 add 列表。

---

### Task 5: memory 同步

**Files:**
- Modify: `C:\Users\kaven\.claude\projects\D--Git-stock\memory\no-doc-for-lowquality-nontech.md`
- Modify: `C:\Users\kaven\.claude\projects\D--Git-stock\memory\MEMORY.md`(加指针)
- Create: `C:\Users\kaven\.claude\projects\D--Git-stock\memory\avoidance-list.md`

**Interfaces:**
- Consumes:Task 3/4 成果(avoidance-list.yaml + gating 协议)。

- [ ] **Step 1: 更新 no-doc-for-lowquality-nontech.md**

在 `How to apply` 末尾补一句:命中避坑标的时先查 `[[avoidance-list]]` 做原因验证,理由仍成立即中断建档。用 Write 覆写(显式 `encoding='utf-8'` 由 Write 工具保证)。

- [ ] **Step 2: 新建 avoidance-list.md memory**

```markdown
---
name: avoidance-list
description: 避坑列表 avoidance-list.yaml + 建档前验证硬门机制
metadata:
  type: project
---

`docs/stock-analytics/avoidance-list.yaml`(类 valuations.yaml,不受 docs linter 约束)登记低质地/已判掉标的:`stock_code`(引号)/`avoid_reason`/`avoid_date`/`key_metrics_snapshot`。

建档 skill(buffett/stock-deep-redo/analyze-category)采证第一步查此表,命中则做「避坑原因验证」:逐条对照 avoid_reason 判仍成立/被推翻——**仍成立中断建档,被推翻才放行并移除该条**。协议见 `.claude/rules/docs-conventions.md`。关联 [[no-doc-for-lowquality-nontech]] [[valuations-yaml-partial-sync]]。
```

- [ ] **Step 3: MEMORY.md 加指针**

在「工作流约定」节加一行:
```markdown
- [避坑列表 gating](avoidance-list.md) — avoidance-list.yaml 登记低质地标的,建档前查表验证,理由仍成立中断建档、被推翻放行并移除
```

- [ ] **Step 4: 验证 memory 文件完整**

Run: `ls "C:/Users/kaven/.claude/projects/D--Git-stock/memory/avoidance-list.md" && grep -c "avoidance-list" "C:/Users/kaven/.claude/projects/D--Git-stock/memory/MEMORY.md"`
Expected:文件存在,MEMORY.md 命中 ≥1。

> memory 在 `~/.claude` 下,不进本仓 git,无 commit 步骤。

---

## 收尾校验(全任务完成后)

- [ ] `PYTHONIOENCODING=utf-8 rtk python scripts/lint_docs_refs.py --check-orphans; echo "exit=$?"` → exit=0(或仅剩无关并行违例)
- [ ] `git log --oneline -4` 确认 3 个 commit(Task 2/3/4)在链上;并行环境用 `git merge-base --is-ancestor <sha> HEAD` 核对
- [ ] avoidance-list.yaml 与 valuations.yaml 无 stock_code 冲突(Task 3 Step 3 已验)
- [ ] 无残留临时脚本:`ls scripts/_*.py 2>/dev/null` 为空
