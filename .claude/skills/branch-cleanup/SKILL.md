---
name: branch-cleanup
description: >-
  批量收口仓库里堆积的分支：盘点所有远程/本地分支，按"是否已合并到 main"二分——
  已合并的删掉，未合并的逐个 merge 进 main（解冲突 → 改 docs 跑 lint → push），最后删除全部已并入分支。
  当用户要求"处理所有分支""没合并的合并、已合并的删除""清理一堆 slack-session 分支""把这些分支收尾掉"
  "批量 merge 未合并分支并删除已合并的"时，务必触发本 skill——即使用户只是甩一张分支列表截图说"处理一下"也要触发。
  典型触发语："处理这些分支""没 merge 的 merge 已经 merge 的删除""清理分支""把分支都收掉""branch cleanup"。
  不要用于：单个 PR 的常规 review/merge（直接 gh pr merge）、单分支内部冲突的逐步调试（用 systematic-debugging）、
  新建/切分支、git 历史改写（rebase/reset）。
---

# 分支批量收口（branch-cleanup）

一堆分支堆在仓库里（典型是自动会话分支 `claude/slack-session-*`、`feat/*`），需要一次性收口。
逻辑只有一句：**按"是否已合并到 main"二分——已合并的删掉，未合并的合进 main 再删掉。**

这个 skill 的价值不在"会敲 git merge"，而在**纪律与安全**：

- **先盘点再动手**：push main 和删除远程分支都不可逆，分类清楚、把冲突风险摆出来、让用户确认范围，再开始。
- **冲突按语义解**，不是粗暴 `--theirs`/`--ours`——本仓最常见的 `related_docs` 对称冲突是"双方各加一条反向链"，正解是两条都留。
- **改了 docs 必须过 lint 才 push**，否则会把 frontmatter/反向链破损推上 main。

## 何时用 / 何时不用

**用**：用户给一批分支（截图、口头"这些"、或泛指"所有分支"），要求"未合并的合并、已合并的删除"这类批量收尾。

**不用**：
- 单个 PR 的常规合并 → 直接 `gh pr merge` 或走 code-review
- 单分支里一处复杂冲突要逐步定位 → systematic-debugging
- 新建分支 / rebase / reset 历史改写

## 前提与默认

- 目标分支默认 `main`（用户另指则用其指定的）。
- 合并方式默认**本地 merge 后 push**（最快）；用户要求留 review 痕迹时改走 PR（`gh pr create` 后 `gh pr merge`）。
- 所有 git 命令前加 `rtk`（链式 `&&` 中也要）。**例外**：解冲突时看 `git diff` 要用 plain `git` 看清 `<<<<<<<` marker，rtk 会压缩。
- Windows：跑 lint / 含中文输出的 python 前加 `PYTHONIOENCODING=utf-8`。

## 工作流

### 阶段 0 · 盘点

```bash
git fetch --prune origin
git branch -a --format="%(refname:short) | %(committerdate:relative) | %(subject)"
```

二分分类（去掉 `origin/main` 自身）：

```bash
git branch -r --merged origin/main | grep -v "origin/main$"   # 已合并 → 待删
git branch -r --no-merged origin/main                          # 未合并 → 待 merge
```

对每个未合并分支看改动范围，**预判冲突**——重点找多个分支共同改的文件（本仓最常见是 `docs/stock-analytics/valuations.yaml` 和 comps 的 `related_docs`）：

```bash
git diff --stat origin/main...origin/<branch>
```

### 阶段 1 · 确认范围（不可逆操作前的铁律）

用户给的截图/"这些"经常无法精确对应到分支名。把盘点结果整理成两组摆给用户，**用 AskUserQuestion 确认**后再动手：

- **已合并 → 删除**：列分支名 + 一句话内容
- **未合并 → 合并**：列分支名 + 内容 + **冲突风险标注**（哪些分支改了同一文件）
- **疑似不在范围**：老分支（如几个月前的 `feat/*`）、纯本地分支——明确点出来问要不要动，默认不动
- 顺带确认**合并方式**（本地 push / PR）

宁可多问一句，不要默认把用户没指的老分支也合了。

### 阶段 2 · 同步 main

```bash
git checkout main && git pull --ff-only origin main && git status --short
```

working tree 必须干净再开始 merge。

### 阶段 3 · 逐个 merge 未合并分支

**顺序**：先合不碰公共文件的（纯代码/skill 改动常能 fast-forward），再合 docs 分支——把容易冲突的留后面，前面的先干净落地。

```bash
git merge origin/<branch> --no-edit
```

**冲突处理**：

1. **`related_docs` 对称冲突（本仓最常见）**
   两个分支各自往同一 comps/doc 追加了一条反向链，冲突同时出现在两处：
   - frontmatter 的 `related_docs:` 块
   - 文件底部 `<!-- BEGIN related_docs -->` … `<!-- END related_docs -->` 的 markdown 块

   **正解：两条都保留**（不是二选一）。注意 frontmatter 里冲突块尾部那行共享的 `symmetric: true`——保留双方时要让**每条 entry 各自带一行** `symmetric: true`，别漏。markdown 块同理两行都留。

2. **`valuations.yaml`**：多数情况下 ort 策略能自动合并（各加各的 key）。若真冲突，按股票 key 合并、去重，别整段取一边。

3. **解完验证无残留再提交**：
   ```bash
   git grep -n -e "^<<<<<<<" -e "^=======" -e "^>>>>>>>" -- docs/
   git add "<精确路径1>" "<精确路径2>" && git commit --no-edit
   ```
   中文路径加引号。`git add` 与 `commit` **放同一条命令链**——并行 session 会在两次调用间抢 index 把你 staged 的清空。

### 阶段 4 · 改了 docs 就跑 lint（过了才 push）

任何 `docs/stock-analytics/**` 被合进来后，推之前必须过两个 lint：

```bash
PYTHONIOENCODING=utf-8 python scripts/lint_docs_frontmatter.py
PYTHONIOENCODING=utf-8 python scripts/lint_docs_refs.py
```

两个都 exit 0（"OK: N file(s)"）才进下一步。非 0 列出的违例要先修——通常是反向链没对称或 frontmatter 字段缺失，回阶段 3 补。

> `--check-orphans` 若因中文路径 print 撞 cp950 报 UnicodeEncodeError，加 `PYTHONIOENCODING=utf-8` 才是真 exit 码，别误判 lint 失败。

### 阶段 5 · 推 main

```bash
git log --oneline origin/main..main   # 复核待推 commits 都是本任务的
git push origin main
```

### 阶段 6 · 删除分支

删前**再确认一次**全部目标分支（含刚 merge 的 + 阶段 0 里本来就已合并的）都已并入最新 main：

```bash
git fetch origin
git branch -r --merged origin/main | grep "<分支前缀>"
```

确认无误后一条命令删全部（已合并的 + 刚合并的一起删）：

```bash
git push origin --delete <branch1> <branch2> <branch3> ...
```

收尾确认：

```bash
git fetch --prune origin && git branch -r
```

剩下的应只有 `main` 和用户明确说要保留的分支。

## 收尾汇报

给用户一份清晰小结：

- **已合并 → 删除**：哪几个
- **未合并 → 合并后删除**：哪几个，各是 fast-forward / 自动合并 / 有冲突已解
- **冲突明细**：哪个文件、什么冲突、怎么解的（如"related_docs 对称冲突，两条反向链都保留"）
- **验证**：lint 结果（N 文件全过）、push 的 commit 范围
- **未动的分支**：哪些按确认保留了

## 坑点速查

- **并行 session 抢 git index**：`git add` 与 `commit` 必须同一条命令链；提交后 `git show --stat <sha>` 确认只含本任务文件。
- **中文多行 commit message**：走文件 `git commit -F .git/MSG.txt`，别用 heredoc（Windows bash 易 EOF 失配）。
- **删本地分支**：若也要清本地，`git branch -d <name>`（已合并）/ 谨慎 `-D`；远程删除用 `git push origin --delete`。
- **fetch --prune 后**本地仍残留对已删远程的跟踪引用时，`git fetch --prune` 即可清理。
