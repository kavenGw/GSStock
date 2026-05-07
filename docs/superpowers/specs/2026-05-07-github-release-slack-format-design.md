# GitHub Release Slack 推送格式优化

> 日期：2026-05-07
> 范围：`news_ai_tool` 频道下的 GitHub Release 版本更新推送

## 背景与问题

当前 GitHub Release 推送（`format_github_release_updates()` + GLM 摘要）输出形如：

```
🤖 Claude Code 更新
v2.1.132 (2026-05-06)
本次更新新增了 CLAUDE_CODE_SESSION_ID 和 CLAUDE_CODE_DISABLE_ALTERNATE_SCREEN
环境变量，后者允许用户选择不使用全屏渲染器，保留对话在终端滚动区域。同时，
增加了粘贴图片时的"Pasting…"提示。修复了 SIGINT 信号未正确处理、终端关闭或
SSH 断开时的异常、恢复会话时 emoji 截断导致的错误、以及 --permission-mode
标志被忽略等问题。此外，还解决了全屏模式下笔记本休眠/唤醒后屏幕空白、
... [一大段连续中文]

🔗 https://github.com/anthropics/claude-code/releases/tag/v2.1.132
```

痛点：
1. 一段无视觉断点的中文，无法 5 秒抓重点
2. 新功能 / Bug 修复混在一起，看完才知道有什么类型
3. 内联代码标识符与正文挤在一起

## 目标

把单段摘要改造为「分类 bullet」结构，分两段：

- ✨ **新功能**：用户可感知的新功能 / 增强（含破坏性变更，描述里点明）
- 🐛 **修复**：bug 修复，全部列出

文档 / 重构 / CI / 格式化等内部变更不入选。

## 输出格式

```
🤖 *Claude Code v2.1.132* (2026-05-06)

✨ *新功能*
• 新增 `CLAUDE_CODE_SESSION_ID` 环境变量，Bash 子进程可读
• 新增 `CLAUDE_CODE_DISABLE_ALTERNATE_SCREEN`，保留对话在终端滚动区域
• 粘贴图片时显示 "Pasting..." 提示

🐛 *修复*
• SIGINT 信号未正确处理
• 终端关闭 / SSH 断开时的异常
• 全屏模式下笔记本休眠后屏幕空白
• `--permission-mode` 标志被忽略
• MCP 服务器内存泄漏
• ...（全部修复都列）

🔗 https://github.com/anthropics/claude-code/releases/tag/v2.1.132
```

格式约定：

- **标题行**：`{emoji} *{name} {version}* ({date})`，版本号并入标题省一行
- **分段**：仅 ✨新功能 / 🐛修复，对应字段为空时整段跳过（不出现空标题）
- **bullet**：每条 ≤30 字，关键标识符（env var / 命令 / flag / 文件名）保留 `` ` `` 反引号
- **多版本批量**：每个 version 独立 block，version 之间空行分隔；末尾共用一个 🔗（指向最新版本 url）
- **不区分破坏性变更**：并入 features，描述里写明"破坏性"

## 改动范围

### 1. `app/llm/prompts/github_release_update.py` — 改 prompt 输出 JSON

新版 prompt 要求 LLM 返回结构化 JSON：

```jsonc
{
  "versions": [
    {
      "version": "v2.1.132",
      "date": "2026-05-06",
      "features": ["新增 `CLAUDE_CODE_SESSION_ID` 环境变量", "..."],
      "fixes": ["SIGINT 信号未正确处理", "..."]
    }
  ]
}
```

Prompt 关键约束：
- 仅返回 JSON，不带任何 markdown 代码块或前后说明
- features 包含新功能 / 增强 / 破坏性变更（破坏性变更在描述里点明）
- fixes 是 bug 修复，全部列出，不限条数
- 文档 / 重构 / CI / 格式化 / 内部依赖升级不入选
- 每条 ≤30 字
- 关键标识符（env var / 命令 / flag / 文件名）用反引号包裹
- 中文描述

### 2. `app/services/notification.py` — `format_github_release_updates()` 装组逻辑

- 调 LLM 后 `json.loads` 解析；失败 → warning log + 走降级
- 解析成功 → 遍历 `versions`，每个 version 调 `_format_release_block()` 生成文本块
- 多个 block 用 `\n\n` 拼接，末尾追加 `🔗 {url}`

伪代码：

```python
def _format_release_block(name: str, emoji: str, version_data: dict) -> str:
    lines = [f"{emoji} *{name} {version_data['version']}* ({version_data['date']})"]
    if version_data.get('features'):
        lines.append('')
        lines.append('✨ *新功能*')
        lines.extend(f"• {item}" for item in version_data['features'])
    if version_data.get('fixes'):
        lines.append('')
        lines.append('🐛 *修复*')
        lines.extend(f"• {item}" for item in version_data['fixes'])
    return '\n'.join(lines)
```

### 3. 降级路径 — 保持现状

下列情况走原有的纯文本 changelog 截断逻辑（已存在）：
- LLM 调用失败 / 超时
- LLM 返回非 JSON
- JSON 解析后所有 version 的 features 和 fixes 都为空（说明分类失败）

降级时打 `logger.warning('[通知.GitHub Release更新] LLM JSON 失败 / 分类失败，降级')` 便于追踪频率。

## 不改动

- `format_blog_updates()` / `format_github_trending_updates()`（本轮仅 Release）
- `GitHubReleaseStrategy.scan()` 调度逻辑
- `GitHubReleaseService` 数据获取逻辑
- `GITHUB_RELEASE_REPOS` 配置 / 插件动态发现

## 测试

放在 `tests/test_github_release_format.py`：

1. **mock LLM 返回完整 JSON** → 验证文本输出含标题、✨段、🐛段、🔗
2. **mock LLM 返回 features 为空** → 验证仅出 🐛 段
3. **mock LLM 返回 fixes 为空** → 验证仅出 ✨ 段
4. **mock LLM 返回非 JSON** → 验证走降级路径，输出含原 changelog 截断
5. **mock 多 version JSON** → 验证多 block + 单 🔗 拼装

手动验证：本地运行一次真实仓库摘要（可用 `python -c "from app.services.notification import NotificationService; print(NotificationService.format_github_release_updates())"`）看效果，确认对接 Slack 渲染正常后再合并。

## 风险点

| 风险 | 处理 |
|---|---|
| LLM 偶尔不出 JSON | 降级路径已存在；额外 log warning 便于跟踪 |
| 修复条数 20+ 时消息很长 | 用户明确选「全列」，遵从决定；Slack 单消息 40k 字符上限远高于实际长度 |
| 多 release 合并推送（首次以外极少见） | 每个 version 独立 block，链接只放整体末尾，使用最新版本的 url |
| Prompt 输出 30 字超限 | LLM 偶尔超限不影响显示，仅观感；不做硬截断 |

## 验收

- 真实跑一次 `format_github_release_updates()` 输出符合上述格式样例
- 单测全过
- Slack 实际渲染断行 / 反引号 / 加粗符合预期
