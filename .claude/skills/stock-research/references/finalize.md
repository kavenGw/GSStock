# 分析档收尾（Phase C）

> 适用：模式 3/4 及 buffett 等写档收尾按需取用（模式 1/2 的 Phase C 已由 `.claude/agents/sr-finalize.md` 内置承载）。执行者通常是控制者派的 sonnet，派发时要求其 **Read 本文件**。
>
> **本文件正文与 `.claude/agents/sr-finalize.md` 同源，改一处必须同步另一处。**

收尾是确定性动作清单，不是分析活：目标是 **双 lint exit 0 + valuations 落库 + 一条只含本任务文件的 commit**。
每一步都有亲验命令，不信任何"已完成"自报。

## 动作清单（按序）

1. `git status` 查遗留改动，确认工作区没有他人在写的文件会被裹挟。
2. **删除旧档**（目标此前已是 `<股票名>/` 文件夹**且**清单内无季报点评/预告 theme → 步骤 2/3 整体跳过，路径稳定无反向链可改）：对控制者传来的待删清单逐个 `git rm -q --ignore-unmatch <path>`。清单只含三类：
   **该股历史 buffett 档**，以及**控制者已 surface 用户确认、被本次新档取代的 `quarterly/**/*季报点评.md` 与单主体业绩预告 theme**（判据见 `mode-deep.md` 步骤 4b/4c）。
   **comps / theme / quarterly 下的专题档与业绩说明会档一律保留**。无清单（首建档）跳过。
3. **反向链收尾**（两类被删档处理方式不同，别混）：

   | 被删档 | 入链处理 |
   |---|---|
   | buffett 旧档 | 全仓扫 `symmetric: true` 指向它的 related_docs 条目（comps/theme/quarterly 里）→ **改指**新档 `<股票名>/index.md`，或删该条目 |
   | 季报点评 | related_docs 条目**整条摘除**（不改指）；某档 `related_docs` 因此摘空则删掉整个 key |
    | 业绩预告 theme（单主体） | 同上**整条摘除**；其对账结论已由新档 `events.md` note 承接，不再改指 |

   **硬闸**：对每个被删档 `grep -rn <被删档文件名> docs/` **必须零命中**才算本步完成 —— refs lint 抓不到正文行内死链，
   而行内链是句子的一部分（"详见 [26Q1 点评](...)"），必须人工改写措辞，不能机械删掉留下病句。
4. 给新档 `related.md` 里 `symmetric: true` 指向的每份外部文档补反向 related_docs 条目（path 按被链档所在目录算相对路径，**指向 `<股票名>/index.md`** —— 阅读入口；refs lint 按文件夹粒度判对称，指 index.md 即可与 related.md 里的正向条目配对）。
5. 重生顶部块 + 双 lint + 孤儿检查：

```bash
python scripts/lint_docs_refs.py --rewrite-blocks   # 别手编块；有 violation 时它提前 return 不重写，故必须排在步骤 3-4 之后 [L18]，且必须排在步骤 2 的旧档物理删除之后——改完反向链而旧档还在磁盘上时，旧档自己的正向 symmetric 条目会变单向悬空、必然报 violation [L20]
python scripts/lint_docs_frontmatter.py             # exit 0
python scripts/lint_docs_refs.py                    # exit 0
python scripts/lint_docs_refs.py --check-orphans    # 新档非孤儿
```

   并行 session 下 refs lint 退出码是全仓状态：只要违规不指向本任务文件即视为通过（见 memory
   `parallel-session-lint-gate`）。
6. **同步 valuations.yaml**（估值数字已在新档 frontmatter `valuation` 块）：

```bash
PYTHONIOENCODING=utf-8 rtk python scripts/sync_valuations.py --stock-code <code>
```

   脚本按 `stock_code` upsert（`market` 按 `stock_code` 推断；无参数则全量扫描）、不删存量条目、保留 `note`/`quality` 手写值。**sync 不覆盖 `note`**：重做档后
   旧 note 停在旧估值口径需手改。
7. **quality 质地星级（仅当与 rating 背离才写）**：渲染层缺省按 rating 现算（core→5 / config→4 / watch→3 /
   exclude→2）。护城河顶级仅因太贵评 watch → 手工在该条目加 `quality: 5`；平庸生意因超跌进 config → `quality: 2`；
   ★1 留给"质地很差"。一致时留空。
8. **矿产/商品标的**：frontmatter 与 valuations.yaml 同步写 `commodity`（枚举 `scripts/_docs_schema.py:COMMODITIES`）
   + `commodity_impact`（positive/negative/neutral，按产业链位置）。
9. 遗留检查：`.omc/artifacts/` 下 evidence/report 未被 `git add`。
    **一次性脚本清理必须用正向白名单，禁止按 `scripts/_*.py` 一把删**（见 lessons [L30][L31]）——
    同仓常有并行 session 在跑别的标的，且其文件名**不一定带你认得出的前缀**。
    只删**你自己本轮创建**的脚本（自己建了哪些自己清楚，按名逐个 `rm`）；`scripts/` 下其余
    `_a1_*`/`_a2_*`/`_a3_*`/`_ctl_*` 等**一律视为他人产物，不得删除**。拿不准的**留着**并在报告里列出交控制者判——
    留下的垃圾下轮可清，删掉的 untracked 文件**永久不可恢复**。删前可跑一次归属检查：
    ```bash
    PYTHONIOENCODING=utf-8 python -c "
    import glob,os,time
    for p in sorted(glob.glob('scripts/_a*_*')):
        print(time.strftime('%m-%d %H:%M:%S',time.localtime(os.path.getmtime(p))), p)"
    ```
    mtime 早于本轮开工、或主题与本轮标的无关者 = 不是你的。
10. **提交**（删增与 commit 必须同一条命令链，防并行 session 抢 index）：

```bash
git rm -q --ignore-unmatch <待删旧档...> && git add <新档文件夹>/ <被改档...> docs/stock-analytics/valuations.yaml && git commit -F .git/MSG-<股票名>-<日期>.txt
```

   message 文件名带任务专属后缀（固定 `.git/MSG.txt` 会被后写者覆盖）；中文多行 message 走文件不走 heredoc。
   **禁止 `git commit -- <pathspec>`**（提交工作区而非暂存区，会裹挟他人在写改动）。
11. **提交后亲验**：`git show --stat HEAD` 只含本任务文件；`git show HEAD:docs/stock-analytics/valuations.yaml`
    复核本股条目真的落库（sync 自报不可信；另一 session 可能抢先提交或用旧工作区覆盖）。
    valuations.yaml 被连带提交了对方条目时**不回退**，commit message 注明非本任务产物即可。

## 汇报

含：双 lint 退出码、valuations 同步状态（以 `git show HEAD:` 为准）、commit SHA、`git show --stat HEAD`
文件清单、遗留检查结论。不主动 push。
