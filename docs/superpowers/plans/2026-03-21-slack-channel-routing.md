# Slack 多频道路由推送架构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将所有推送从单一 Webhook 切换到 Bot Token + chat.postMessage，按消息类型路由到 4 个 Slack 频道，并移除多通道抽象层。

**Architecture:** 删除 `app/notifications/` 抽象层，将去重逻辑迁移到 `NotificationService`。`send_slack()` 改用 `chat.postMessage` API + `channel` 参数做路由。各调用方按消息类型指定目标频道。

**Tech Stack:** Flask, Slack Bot Token (chat.postMessage API), urllib + certifi SSL

**Spec:** `docs/superpowers/specs/2026-03-21-slack-channel-routing-design.md`

---

## File Map

| 操作 | 文件 | 职责 |
|------|------|------|
| 重写 | `app/config/notification_config.py` | Bot Token + 频道常量 |
| 修改 | `app/services/notification.py` | send_slack 改造、去重迁移、esports 拆分、send_all 删除、push_daily_report 路由 |
| 修改 | `app/__init__.py` | 事件总线订阅改为 NotificationService.dispatch_signal |
| 修改 | `app/services/esports_monitor_service.py` | 4 处 send_slack 加频道参数 |
| 修改 | `app/templates/base.html` | 前端提示文字更新，移除邮件相关 UI |
| 修改 | `.env.sample` | 环境变量更新 |
| 修改 | `CLAUDE.md` | 配置文档同步，移除 notifications/ 架构引用 |
| 修改 | `README.md` | Slack 设置指南改为 Bot Token 流程 |
| 修改 | `docs/TECHNICAL_DOCUMENTATION.md` | 更新 SLACK_WEBHOOK_URL 引用 |
| 删除 | `app/notifications/` (5 文件) | 移除整个目录 |

---

### Task 1: 配置层改造

**Files:**
- Modify: `app/config/notification_config.py`

- [ ] **Step 1: 重写 notification_config.py**

将 `SLACK_WEBHOOK_URL` 替换为 `SLACK_BOT_TOKEN` + 频道常量：

```python
"""消息推送配置"""
import os

SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN', '')
SLACK_ENABLED = bool(SLACK_BOT_TOKEN)

# 频道常量（不带 # 前缀，chat.postMessage 要求频道名或频道 ID）
CHANNEL_NEWS = 'news'
CHANNEL_AI_TOOL = 'news_ai_tool'
CHANNEL_LOL = 'news_lol'
CHANNEL_NBA = 'news_nba'
```

- [ ] **Step 2: Commit**

```bash
git add app/config/notification_config.py
git commit -m "refactor: 配置层从 Webhook URL 切换到 Bot Token + 频道常量"
```

---

### Task 2: send_slack 改造 + 去重迁移 + 清理

**Files:**
- Modify: `app/services/notification.py`

- [ ] **Step 1: 更新 imports 和模块文档**

文件头部（第 1-14 行）改为：

```python
"""
消息推送服务 - Slack Bot Token (chat.postMessage)
"""
import json
import logging
import ssl
import threading
from datetime import date, datetime, timedelta
from urllib.request import urlopen, Request

import certifi

from app.config.notification_config import (
    SLACK_BOT_TOKEN, SLACK_ENABLED,
    CHANNEL_NEWS, CHANNEL_AI_TOOL, CHANNEL_LOL, CHANNEL_NBA,
)
```

- [ ] **Step 2: 重写 send_slack 方法**

替换现有 `send_slack` 方法（第 29-43 行）：

```python
@staticmethod
def send_slack(message: str, channel: str = CHANNEL_NEWS) -> bool:
    if not SLACK_ENABLED:
        logger.warning('[通知.Slack] Slack 未配置')
        return False

    try:
        payload = json.dumps({'channel': channel, 'text': message}).encode('utf-8')
        req = Request(
            'https://slack.com/api/chat.postMessage',
            data=payload,
            headers={
                'Content-Type': 'application/json; charset=utf-8',
                'Authorization': f'Bearer {SLACK_BOT_TOKEN}',
            },
        )
        ctx = ssl.create_default_context(cafile=certifi.where())
        with urlopen(req, timeout=10, context=ctx) as resp:
            body = json.loads(resp.read().decode('utf-8'))
            if not body.get('ok'):
                logger.error(f'[通知.Slack] API 错误: {body.get("error", "unknown")}')
                return False
            return True
    except Exception as e:
        logger.error(f'[通知.Slack] 推送失败: {e}', exc_info=True)
        return False
```

- [ ] **Step 3: 删除 send_all 方法**

删除 `send_all` 方法（第 45-50 行）：

```python
# 删除整个方法
@staticmethod
def send_all(subject: str, text_content: str) -> dict:
    results = {}
    if SLACK_ENABLED:
        results['slack'] = NotificationService.send_slack(text_content)
    return results
```

- [ ] **Step 4: 新增去重逻辑和 dispatch_signal**

在 `NotificationService` 类中添加（在 `get_status` 方法之后、`send_slack` 方法之前）：

```python
_signal_state = {}  # 类变量，状态机去重

@staticmethod
def _make_signal_key(signal) -> str:
    data = signal.data or {}
    stock_code = data.get('stock_code') or data.get('code', '')
    signal_name = data.get('name', '')
    if stock_code and signal_name:
        return f"{signal.strategy}:{stock_code}:{signal_name}"
    return ''

@staticmethod
def _get_signal_direction(signal) -> str:
    data = signal.data or {}
    direction = data.get('type', '')
    if direction:
        return direction
    change_pct = data.get('change_pct')
    if change_pct is not None:
        return 'up' if change_pct > 0 else 'down'
    return ''

@staticmethod
def _is_duplicate(signal) -> bool:
    key = NotificationService._make_signal_key(signal)
    if not key:
        return False
    direction = NotificationService._get_signal_direction(signal)
    if not direction:
        return False
    last_direction = NotificationService._signal_state.get(key)
    if last_direction == direction:
        logger.debug(f'[通知去重] 跳过重复信号: {key} direction={direction}')
        return True
    NotificationService._signal_state[key] = direction
    return False

@staticmethod
def dispatch_signal(signal):
    """事件总线回调：去重 + 格式化 + 发送到 news 频道"""
    if signal.priority == "LOW":
        return
    if NotificationService._is_duplicate(signal):
        return
    emoji = {"HIGH": "\U0001f534", "MEDIUM": "\U0001f7e1"}.get(signal.priority, "")
    text = f"{emoji} *[{signal.strategy}]* {signal.title}\n{signal.detail}"
    NotificationService.send_slack(text, CHANNEL_NEWS)
```

- [ ] **Step 5: Commit**

```bash
git add app/services/notification.py
git commit -m "refactor: send_slack 切换到 chat.postMessage + 迁移去重逻辑"
```

---

### Task 3: format_esports_summary 拆分 + push_daily_report 路由

**Files:**
- Modify: `app/services/notification.py`

- [ ] **Step 1: 将 format_esports_summary 改为 format_esports_summary_split**

替换 `format_esports_summary` 方法（第 657-707 行）：

```python
@staticmethod
def format_esports_summary_split() -> tuple[str, str]:
    """格式化赛事资讯，分别返回 NBA 和 LoL 文本

    Returns:
        (nba_text, lol_text)，获取失败的部分返回空字符串
    """
    from app.config.esports_config import ESPORTS_ENABLED
    if not ESPORTS_ENABLED:
        return '', ''

    nba_text = ''
    lol_text = ''

    try:
        from app.services.esports_service import EsportsService

        # NBA
        nba = EsportsService.get_nba_schedule()
        if nba is not None:
            nba_text = NotificationService._format_nba_section(nba)

        # LoL
        lol = EsportsService.get_lol_schedule()
        if lol is not None:
            lol_sections = []
            for league_name in ['LPL', 'LCK', '先锋赛', 'Worlds', 'MSI']:
                if league_name not in lol:
                    continue
                league_data = lol[league_name]
                if league_data is None:
                    lol_sections.append(f'🎮 {league_name}\n数据获取失败')
                else:
                    section = NotificationService._format_lol_section(
                        league_name, league_data,
                    )
                    lol_sections.append(section)
            if lol_sections:
                lol_text = '\n\n'.join(lol_sections)
    except Exception as e:
        logger.warning(f'[通知.赛事] 格式化失败: {e}')

    return nba_text, lol_text
```

- [ ] **Step 2: 改造 push_daily_report 的消息组装和发送**

在 `push_daily_report` 方法中做以下修改：

**2a** — 替换赛事获取（约第 817 行）：

```python
# 旧代码:
# esports_text = NotificationService.format_esports_summary()

# 新代码:
nba_text, lol_text = NotificationService.format_esports_summary_split()
```

**2b** — 从 msg3_parts 中移除 release_texts（约第 907-908 行），删除这两行：

```python
# 删除:
# for rt in release_texts:
#     msg3_parts.append(rt)
```

**2c** — 删除整个 Message 4 块（约第 910-913 行）：

```python
# 删除:
# msg4_parts = []
# if esports_text:
#     msg4_parts.append(esports_text)
```

**2d** — 修改 messages 组装（约第 915-916 行），移除 msg4_parts：

```python
# 旧代码:
# for parts in (msg1_parts, msg2_parts, msg3_parts, msg4_parts):

# 新代码:
for parts in (msg1_parts, msg2_parts, msg3_parts):
```

**2e** — 修改发送循环（约第 926-931 行），改为指定频道，并在发完主消息后单独发送 release 和 esports：

```python
sent = 0
for msg in messages:
    if NotificationService.send_slack(msg, CHANNEL_NEWS):
        sent += 1

# GitHub Release → news_ai_tool
if release_texts:
    release_msg = '\n\n'.join(release_texts)
    if NotificationService.send_slack(release_msg, CHANNEL_AI_TOOL):
        sent += 1

# 赛事 → 各自频道
if nba_text:
    if NotificationService.send_slack(nba_text, CHANNEL_NBA):
        sent += 1
if lol_text:
    if NotificationService.send_slack(lol_text, CHANNEL_LOL):
        sent += 1

results = {'slack': sent > 0, 'messages_sent': sent, 'messages_total': len(messages)}
results['content_preview'] = messages[0][:500] if messages else ''
return results
```

- [ ] **Step 3: Commit**

```bash
git add app/services/notification.py
git commit -m "refactor: 拆分赛事摘要 + 每日简报多频道路由"
```

---

### Task 4: 事件总线订阅改造

**Files:**
- Modify: `app/__init__.py`

- [ ] **Step 1: 修改 app/__init__.py 第 285-293 行**

```python
# 旧代码（第 288-293 行）:
# from app.scheduler.event_bus import event_bus
# from app.notifications.manager import notification_manager
#
# registry.discover()
# notification_manager.init_channels()
# event_bus.subscribe(notification_manager.dispatch)

# 新代码:
from app.scheduler.event_bus import event_bus
from app.services.notification import NotificationService

registry.discover()
event_bus.subscribe(NotificationService.dispatch_signal)
```

- [ ] **Step 2: Commit**

```bash
git add app/__init__.py
git commit -m "refactor: 事件总线直接订阅 NotificationService.dispatch_signal"
```

---

### Task 5: 调用方频道路由

**Files:**
- Modify: `app/services/esports_monitor_service.py`

- [ ] **Step 1: esports_monitor_service.py — 4 处 send_slack 加频道参数**

在 `_poll_match` 方法体内的 lazy import 块中（第 168 行 `from app.services.notification import NotificationService` 之后），添加一行：

```python
from app.config.notification_config import CHANNEL_NBA, CHANNEL_LOL
```

将第 182 行和第 191 行的 NBA 推送改为：
```python
NotificationService.send_slack(msg, CHANNEL_NBA)
```

将第 205 行和第 214 行的 LoL 推送改为：
```python
NotificationService.send_slack(msg, CHANNEL_LOL)
```

注意：`interest_pipeline.py`、`company_news_service.py`、`notification.py:push_realtime_analysis` 的 `send_slack(msg)` 调用无需修改，因为 `CHANNEL_NEWS` 已是 `send_slack` 的默认参数。

- [ ] **Step 2: Commit**

```bash
git add app/services/esports_monitor_service.py
git commit -m "refactor: 赛事监控推送添加频道路由参数"
```

---

### Task 6: 删除 notifications 目录

**Files:**
- Delete: `app/notifications/__init__.py`
- Delete: `app/notifications/base.py`
- Delete: `app/notifications/manager.py`
- Delete: `app/notifications/channels/__init__.py`
- Delete: `app/notifications/channels/slack.py`

- [ ] **Step 1: 删除整个 app/notifications 目录**

```bash
rm -rf app/notifications
```

- [ ] **Step 2: 确认无其他文件引用 notifications 模块**

```bash
grep -r "app\.notifications\|from notifications\|import notifications" app/ --include="*.py"
```

预期：无输出（app/__init__.py 已在 Task 4 中修改）。

- [ ] **Step 3: Commit**

```bash
git add -A app/notifications
git commit -m "refactor: 删除 notifications 多通道抽象层"
```

---

### Task 7: 前端 + 配置文档同步

**Files:**
- Modify: `app/templates/base.html`
- Modify: `.env.sample`
- Modify: `CLAUDE.md`
- Modify: `README.md`
- Modify: `docs/TECHNICAL_DOCUMENTATION.md`

- [ ] **Step 1: 更新 base.html**

**1a** — 第 79-83 行，将推送配置提示改为（删除邮件配置行）：

```html
推送配置通过环境变量管理：
<ul class="mt-1 mb-0">
    <li>Slack: <code>SLACK_BOT_TOKEN</code></li>
</ul>
```

**1b** — 第 88 行，删除邮件测试按钮：

```html
<!-- 删除这行 -->
<button type="button" class="btn btn-outline-primary btn-sm" onclick="NotifySettings.test('email')">测试邮件</button>
```

**1c** — 第 110 行，从 `loadStatus` 的 JS 中删除邮件状态显示。将 `el.innerHTML` 模板改为：

```javascript
el.innerHTML = `
    <div class="d-flex gap-3">
        <span>Slack: ${data.slack ? '<span class="text-success fw-bold">已配置</span>' : '<span class="text-muted">未配置</span>'}</span>
    </div>`;
```

- [ ] **Step 2: 更新 .env.sample**

将第 54-55 行：

```
# Slack 推送
# SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx
```

替换为：

```
# Slack 推送（Bot Token + 多频道路由）
# SLACK_BOT_TOKEN=xoxb-your-bot-token
```

- [ ] **Step 3: 更新 CLAUDE.md**

**3a** — 架构树中移除第 37 行 `├── notifications/     # 通知系统（Slack）`

**3b** — 通知配置表中，将 `SLACK_WEBHOOK_URL` 行替换为：

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `SLACK_BOT_TOKEN` | Slack Bot Token | 空 |

并添加频道路由说明：

| 频道 | 内容 |
|------|------|
| `news` | 每日简报、盯盘、预警、公司新闻、兴趣新闻 |
| `news_ai_tool` | GitHub Release 更新 |
| `news_lol` | LoL 赛事 |
| `news_nba` | NBA 赛事 |

- [ ] **Step 4: 更新 README.md**

**4a** — 环境变量表中第 64 行，将 `SLACK_WEBHOOK_URL` 替换为 `SLACK_BOT_TOKEN`

**4b** — 替换 Slack 设置指南（第 277-289 行）为 Bot Token 流程：

```markdown
### Slack

1. 打开 [Slack API: Applications](https://api.slack.com/apps)，点击 **Create New App** → **From scratch**
2. 输入应用名称（如 `Stock Alert`），选择目标 Workspace，点击 **Create App**
3. 左侧菜单 **OAuth & Permissions**，在 **Bot Token Scopes** 添加 `chat:write`
4. 页面顶部点击 **Install to Workspace**，点击 **Allow**
5. 复制 **Bot User OAuth Token**（`xoxb-...`），填入 `.env`：

\```env
SLACK_BOT_TOKEN=xoxb-your-bot-token
\```

6. 在 Slack 中将 Bot 邀请到目标频道（`/invite @Stock Alert`）

配置后自动启用，消息按类型路由到 `news`、`news_ai_tool`、`news_lol`、`news_nba` 频道。
```

- [ ] **Step 5: 更新 docs/TECHNICAL_DOCUMENTATION.md**

第 820-821 行，将 `SLACK_WEBHOOK_URL=<Slack Webhook>` 替换为 `SLACK_BOT_TOKEN=<Slack Bot Token>`，删除相邻的 SMTP 相关配置行（如有）。

- [ ] **Step 6: Commit**

```bash
git add app/templates/base.html .env.sample CLAUDE.md README.md docs/TECHNICAL_DOCUMENTATION.md
git commit -m "docs: 同步 Slack Bot Token 配置到文档和前端"
```

---

### Task 8: 冒烟验证

- [ ] **Step 1: 启动应用验证无 import 错误**

```bash
python -c "from app import create_app; app = create_app(); print('OK')"
```

预期：输出 `OK`，无 ImportError。

- [ ] **Step 2: 验证无残余引用 notifications 模块**

```bash
grep -r "app\.notifications\|from notifications\|import notifications" app/ --include="*.py"
```

预期：无输出。

- [ ] **Step 3: 验证无残余引用 SLACK_WEBHOOK_URL**

```bash
grep -r "SLACK_WEBHOOK_URL" app/ --include="*.py"
grep -r "SLACK_WEBHOOK_URL" app/templates/ --include="*.html"
```

预期：无输出。

- [ ] **Step 4: Commit（如有修复）**

如果冒烟测试发现问题，修复后提交。
