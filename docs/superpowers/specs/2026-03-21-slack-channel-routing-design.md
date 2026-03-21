# Slack 多频道路由推送架构设计

## 背景

当前所有推送通过单一 `SLACK_WEBHOOK_URL` 发到同一个 Slack 频道。随着推送类型增多（股票、新闻、赛事、AI 工具），消息混杂难以管理。需要拆分到多个频道，并简化只保留 Slack 通道。

## 目标

1. 只保留 Slack 推送，移除多通道抽象层
2. 从 Webhook 切换到 Bot Token + `chat.postMessage` API
3. 消息按类型路由到 4 个频道

## 频道路由规则

| 频道 | 内容 |
|------|------|
| `#news` | 每日简报、盯盘分析、盯盘告警、价格/涨跌幅预警、公司新闻、兴趣新闻 |
| `#news_ai_tool` | GitHub Release 更新（Claude Code、Superpowers） |
| `#news_lol` | LoL 赛事实时比分 |
| `#news_nba` | NBA 赛事实时比分 |

## 设计

### 1. Slack 发送层改造

`NotificationService.send_slack()` 新增 `channel` 参数，从 Webhook 切换到 Bot Token API。

**配置 (`app/config/notification_config.py`)**：

```python
SLACK_BOT_TOKEN = os.environ.get('SLACK_BOT_TOKEN', '')
SLACK_ENABLED = bool(SLACK_BOT_TOKEN)
SLACK_DEFAULT_CHANNEL = os.environ.get('SLACK_DEFAULT_CHANNEL', '#news')

# 频道常量
CHANNEL_NEWS = '#news'
CHANNEL_AI_TOOL = '#news_ai_tool'
CHANNEL_LOL = '#news_lol'
CHANNEL_NBA = '#news_nba'
```

**发送方法**：

```python
@staticmethod
def send_slack(message: str, channel: str = CHANNEL_NEWS) -> bool:
    # POST https://slack.com/api/chat.postMessage
    # Headers: Authorization: Bearer {SLACK_BOT_TOKEN}
    # Body: {"channel": channel, "text": message}
```

**环境变量变更**：
- 移除 `SLACK_WEBHOOK_URL`
- 新增 `SLACK_BOT_TOKEN`
- 新增 `SLACK_DEFAULT_CHANNEL`（可选，默认 `#news`）

### 2. 删除多通道抽象层

删除 `app/notifications/` 整个目录（5 个文件）：
- `base.py` — Notifier 抽象基类
- `manager.py` — NotificationManager 单例
- `channels/slack.py` — SlackNotifier
- `channels/__init__.py`
- `__init__.py`

**去重逻辑迁移**：NotificationManager 中的状态机去重（`_is_duplicate`、`_signal_state`）迁移到 NotificationService。

**事件总线订阅改造**：

```python
# app/__init__.py
# 移除 notification_manager 相关代码
# 改为：
event_bus.subscribe(NotificationService.dispatch_signal)
```

NotificationService 新增 `dispatch_signal` 静态方法：

```python
_signal_state = {}

@staticmethod
def dispatch_signal(signal):
    """事件总线回调：去重 + 格式化 + 发送到 #news"""
    if signal.priority == "LOW":
        return
    if NotificationService._is_duplicate(signal):
        return
    emoji = {"HIGH": "🔴", "MEDIUM": "🟡"}.get(signal.priority, "")
    text = f"{emoji} *[{signal.strategy}]* {signal.title}\n{signal.detail}"
    NotificationService.send_slack(text, CHANNEL_NEWS)
```

### 3. 各推送路径频道路由

**每日简报 `push_daily_report()`**：
- Message 1（核心观点+持仓+信号）→ `#news`
- Message 2（盯盘分析）→ `#news`
- Message 3（市场数据）→ `#news`，GitHub Release 部分剥离 → `#news_ai_tool`
- Message 4（赛事）→ 删除，赛事摘要拆分发到 `#news_nba` / `#news_lol`

**赛事监控 `esports_monitor_service.py`**：
- NBA 的 `send_slack(msg)` → `send_slack(msg, CHANNEL_NBA)`
- LoL 的 `send_slack(msg)` → `send_slack(msg, CHANNEL_LOL)`

**兴趣新闻 `interest_pipeline.py`**：
- `send_slack(msg)` → `send_slack(msg, CHANNEL_NEWS)`

**公司新闻 `company_news_service.py`**：
- `send_slack(msg)` → `send_slack(msg, CHANNEL_NEWS)`

**策略信号**（price_alert / change_alert / watch_alert / watch_realtime）：
- 全部走 `dispatch_signal()` → `#news`

**盯盘实时分析 `push_realtime_analysis()`**：
- `send_slack(message)` → `send_slack(message, CHANNEL_NEWS)`

### 4. `format_esports_summary` 拆分

当前返回合并字符串，改为返回元组：

```python
@staticmethod
def format_esports_summary_split() -> tuple[str, str]:
    """返回 (nba_text, lol_text)"""
    nba_text = ...  # 🏀 NBA 部分
    lol_text = ...  # 🎮 LoL 部分
    return nba_text, lol_text
```

原 `format_esports_summary()` 删除。

### 5. 清理

- 删除 `send_all()` 方法
- `get_status()` 保持不变，返回 `{'slack': SLACK_ENABLED}`

## 改动范围

| 改动 | 文件 |
|------|------|
| 删除整个目录 | `app/notifications/` (5 个文件) |
| 重写发送层 + 新增去重 | `app/services/notification.py` |
| 配置改造 | `app/config/notification_config.py` |
| 事件总线订阅 | `app/__init__.py` |
| 赛事频道路由 | `app/services/esports_monitor_service.py` |
| 兴趣新闻频道 | `app/services/interest_pipeline.py` |
| 公司新闻频道 | `app/services/company_news_service.py` |
| 配置文档同步 | `.env.sample` / `CLAUDE.md` / `README.md` |
