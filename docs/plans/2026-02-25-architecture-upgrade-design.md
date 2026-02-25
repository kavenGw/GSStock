# 架构升级设计方案

> 参考项目：[moneyclaw-py](https://github.com/Qiyd81/moneyclaw-py.git)
> 日期：2026-02-25

## 概述

在现有 Flask 架构基础上，一次性引入五大模块升级：策略插件系统、通知系统、LLM 智能分析层、调度引擎、UI 暗色主题。

## 1. 策略插件系统

### 目录结构

```
app/strategies/
├── base.py              # Strategy 抽象基类 + Signal 数据类
├── registry.py          # 自动发现 + 注册
├── price_alert/         # 价格预警策略
│   ├── __init__.py
│   └── config.yaml
├── wyckoff_signal/      # 威科夫信号策略
│   ├── __init__.py
│   └── config.yaml
├── change_alert/        # 涨跌幅预警策略
│   ├── __init__.py
│   └── config.yaml
└── daily_briefing/      # 每日简报策略
    ├── __init__.py
    └── config.yaml
```

### 核心抽象

```python
@dataclass
class Signal:
    strategy: str
    priority: Literal["HIGH", "MEDIUM", "LOW"]
    title: str
    detail: str
    data: dict

class Strategy(ABC):
    name: str
    description: str
    schedule: str              # cron 表达式
    needs_llm: bool = False

    async def scan(self) -> list[Signal]: ...
    async def evaluate(self, signal: Signal) -> Action: ...
    def get_config(self) -> dict: ...
```

### 要点
- 启动时自动扫描 `strategies/` 目录注册
- 每个策略独立 `config.yaml` 管理阈值参数
- 现有 `alert.py` 和 `wyckoff.py` 的逻辑迁移到对应策略插件

## 2. 通知系统

### 目录结构

```
app/notifications/
├── base.py              # Notifier 抽象基类
├── manager.py           # 通知管理器
└── channels/
    ├── slack.py          # Slack Webhook
    └── web.py            # Web 端内通知
```

### 核心设计

```python
class Notifier(ABC):
    async def send(self, signal: Signal, formatted: str) -> bool: ...

class NotificationManager:
    channels: list[Notifier]

    async def dispatch(self, signal: Signal):
        # HIGH → Slack + Web
        # MEDIUM → Slack + Web
        # LOW → Web only
```

### Slack 集成
- Slack Incoming Webhook
- Block Kit 格式化消息
- 配置项存环境变量 `SLACK_WEBHOOK_URL`

## 3. LLM 智能分析层

### 目录结构

```
app/llm/
├── base.py              # LLMProvider 抽象基类
├── router.py            # 分层路由器
├── providers/
│   └── zhipu.py         # 智谱 GLM API
└── prompts/
    ├── wyckoff_analysis.py
    └── trade_advice.py
```

### 分层路由

| 层级 | 处理方式 | 场景 |
|------|---------|------|
| L0 | 规则引擎（现有逻辑） | 价格比较、阈值触发 |
| L1 | 智谱 GLM-4-Flash | 简报摘要、情绪分析 |
| L2 | 智谱 GLM-4 | 威科夫深度解读、操作建议 |

### 成本控制
- 日预算上限（可配置）
- 按场景选择模型
- 缓存 LLM 响应

## 4. 调度引擎

### 目录结构

```
app/scheduler/
├── engine.py            # APScheduler 调度引擎
└── event_bus.py         # 事件总线
```

### 数据流

```
Strategy.scan() → Signal → EventBus → NotificationManager → Slack/Web
                                    → LLM (if needs_llm)
```

### 调度示例
- 价格预警：每 5 分钟（交易时段）
- 威科夫扫描：每 30 分钟
- 每日简报：每日 8:30
- 涨跌幅预警：每 10 分钟

## 5. UI 暗色主题

### 设计方向
- 全局暗色背景 (#0d1117)
- Glassmorphism 毛玻璃卡片（backdrop-filter blur）
- 强调色 cyan/teal (#00d4aa)
- 保持 Bootstrap 5，用 CSS 变量覆盖

### 改动范围
- 新建 `static/css/theme-dark.css`
- 卡片组件统一 glassmorphism 风格
- 图表适配暗色背景
- 骨架屏适配暗色主题
- 数据表格暗色 + hover 高亮

### 不做
- 不引入 Three.js 3D
- 不换前端框架

## 技术选型

| 组件 | 选型 |
|------|------|
| 调度 | APScheduler |
| 通知 | Slack Incoming Webhook |
| LLM | 智谱 GLM-4 / GLM-4-Flash |
| UI | Bootstrap 5 + CSS Variables + Glassmorphism |
| 框架 | 保持 Flask |
