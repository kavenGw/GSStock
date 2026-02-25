# 架构升级实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 在现有 Flask 架构上引入策略插件系统、通知重构、智谱 LLM 分析、APScheduler 调度引擎、暗色主题 UI。

**Architecture:** 保持 Flask 框架不变，新增 `app/strategies/`（插件系统）、`app/llm/`（LLM 层）、`app/scheduler/`（调度引擎），重构现有 `app/services/notification.py` 为通知管理器，用 CSS 变量实现暗色主题。现有 `AIAnalyzerService` 迁移到 LLM 层并改用智谱 API。

**Tech Stack:** Flask, APScheduler, 智谱 GLM-4/GLM-4-Flash, Bootstrap 5 CSS Variables, PyYAML

---

## Task 1: 策略插件基础框架

**Files:**
- Create: `app/strategies/__init__.py`
- Create: `app/strategies/base.py`
- Create: `app/strategies/registry.py`

**Step 1: 创建 Signal 和 Strategy 基类**

`app/strategies/base.py`:
```python
"""策略插件基础框架"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

@dataclass
class Signal:
    """策略产出的信号"""
    strategy: str
    priority: Literal["HIGH", "MEDIUM", "LOW"]
    title: str
    detail: str
    data: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

class Strategy(ABC):
    """策略抽象基类"""
    name: str = ""
    description: str = ""
    schedule: str = ""          # cron 表达式，如 "*/5 * * * *"
    needs_llm: bool = False
    enabled: bool = True

    def __init__(self):
        self._config = self._load_config()

    def _load_config(self) -> dict:
        """从同目录 config.yaml 加载配置"""
        import yaml
        from pathlib import Path
        config_path = Path(__file__).parent / self.__class__.__module__.split('.')[-2] / 'config.yaml'
        # 子类在自己目录，需要向上找
        module_dir = Path(__import__(self.__class__.__module__, fromlist=['']).__file__).parent
        config_file = module_dir / 'config.yaml'
        if config_file.exists():
            with open(config_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        return {}

    @abstractmethod
    def scan(self) -> list[Signal]:
        """扫描并产出信号"""
        ...

    def get_config(self) -> dict:
        return self._config
```

`app/strategies/__init__.py`:
```python
from app.strategies.base import Signal, Strategy
from app.strategies.registry import StrategyRegistry
```

**Step 2: 创建策略注册中心**

`app/strategies/registry.py`:
```python
"""策略自动发现与注册"""
import importlib
import logging
from pathlib import Path

from app.strategies.base import Strategy

logger = logging.getLogger(__name__)

class StrategyRegistry:
    """策略注册中心 — 自动扫描 strategies/ 子目录"""

    _instance = None
    _strategies: dict[str, Strategy] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._strategies = {}
        return cls._instance

    def discover(self):
        """扫描 app/strategies/ 下所有子包，自动注册"""
        strategies_dir = Path(__file__).parent
        for child in sorted(strategies_dir.iterdir()):
            if not child.is_dir() or child.name.startswith('_'):
                continue
            init_file = child / '__init__.py'
            if not init_file.exists():
                continue
            try:
                module = importlib.import_module(f'app.strategies.{child.name}')
                # 查找 Strategy 子类
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and issubclass(attr, Strategy)
                            and attr is not Strategy):
                        instance = attr()
                        if instance.enabled:
                            self._strategies[instance.name] = instance
                            logger.info(f'[策略注册] {instance.name}: {instance.description}')
            except Exception as e:
                logger.error(f'[策略注册] 加载 {child.name} 失败: {e}')

    @property
    def active(self) -> list[Strategy]:
        return list(self._strategies.values())

    def get(self, name: str) -> Strategy | None:
        return self._strategies.get(name)

registry = StrategyRegistry()
```

**Step 3: Commit**

```bash
git add app/strategies/
git commit -m "feat: 策略插件基础框架 — Signal/Strategy/Registry"
```

---

## Task 2: 四个策略插件实现

**Files:**
- Create: `app/strategies/price_alert/__init__.py`
- Create: `app/strategies/price_alert/config.yaml`
- Create: `app/strategies/wyckoff_signal/__init__.py`
- Create: `app/strategies/wyckoff_signal/config.yaml`
- Create: `app/strategies/change_alert/__init__.py`
- Create: `app/strategies/change_alert/config.yaml`
- Create: `app/strategies/daily_briefing/__init__.py`
- Create: `app/strategies/daily_briefing/config.yaml`
- Refer: `app/services/signal_detector.py`（信号检测逻辑）
- Refer: `app/services/wyckoff_analyzer.py`（威科夫自动分析）
- Refer: `app/services/briefing.py`（简报数据收集）

**Step 1: 价格预警策略**

`app/strategies/price_alert/config.yaml`:
```yaml
# 价格预警阈值
change_threshold: 5.0     # 涨跌幅超过5%触发HIGH
volume_ratio: 2.0          # 成交量倍数超过2倍触发
```

`app/strategies/price_alert/__init__.py`:
将 `SignalDetector` 的4种信号检测逻辑（volume_breakout, new_high, top_volume, ma5_cross）迁移为 `PriceAlertStrategy.scan()`。从 `PositionService` 获取持仓股票列表，获取 OHLC 数据，运行检测。

**Step 2: 威科夫信号策略**

`app/strategies/wyckoff_signal/config.yaml`:
```yaml
timeframes: [daily, weekly, monthly]
min_confidence: 0.6
```

`app/strategies/wyckoff_signal/__init__.py`:
调用 `WyckoffAutoService.analyze_batch()` 获取持仓股票的威科夫分析，过滤出 strong_buy/strong_sell 等强信号，包装为 Signal。

**Step 3: 涨跌幅预警策略**

`app/strategies/change_alert/config.yaml`:
```yaml
high_threshold: 5.0    # 涨幅>5%触发HIGH
low_threshold: -5.0    # 跌幅<-5%触发HIGH
medium_threshold: 3.0  # 涨跌幅>3%触发MEDIUM
```

`app/strategies/change_alert/__init__.py`:
从 `UnifiedStockDataService.get_realtime_prices()` 获取持仓股票实时价格，按阈值生成信号。

**Step 4: 每日简报策略**

`app/strategies/daily_briefing/config.yaml`:
```yaml
schedule: "30 8 * * 1-5"   # 工作日8:30
include_sections:
  - stocks
  - indices
  - futures
  - sectors
  - technical
```

`app/strategies/daily_briefing/__init__.py`:
调用 `BriefingService` 各方法收集数据，组装为一个综合的 Signal。`needs_llm: True` 标记，由 LLM 层生成市场总结。

**Step 5: Commit**

```bash
git add app/strategies/
git commit -m "feat: 实现四个策略插件 — 价格预警/威科夫/涨跌幅/每日简报"
```

---

## Task 3: 通知系统重构

**Files:**
- Create: `app/notifications/__init__.py`
- Create: `app/notifications/base.py`
- Create: `app/notifications/manager.py`
- Create: `app/notifications/channels/__init__.py`
- Create: `app/notifications/channels/slack.py`
- Create: `app/notifications/channels/email.py`
- Modify: `app/services/notification.py` → 改为薄包装调用新通知系统
- Refer: `app/config/notification_config.py`

**Step 1: 通知基类和管理器**

`app/notifications/base.py`:
```python
from abc import ABC, abstractmethod
from app.strategies.base import Signal

class Notifier(ABC):
    name: str = ""
    enabled: bool = False

    @abstractmethod
    def send(self, signal: Signal, formatted: str) -> bool: ...

    @abstractmethod
    def format_signal(self, signal: Signal) -> str: ...
```

`app/notifications/manager.py`:
```python
class NotificationManager:
    def __init__(self):
        self.channels: list[Notifier] = []
        self._discover_channels()

    def dispatch(self, signal: Signal):
        """按优先级分发到对应渠道"""
        for channel in self.channels:
            if not channel.enabled:
                continue
            if signal.priority == "LOW" and channel.name != "web":
                continue
            formatted = channel.format_signal(signal)
            channel.send(signal, formatted)
```

**Step 2: Slack 通知渠道**

`app/notifications/channels/slack.py`:
迁移现有 `NotificationService.send_slack()` 逻辑，增加 Block Kit 格式化（卡片式消息，含标题、详情、优先级颜色标识）。

**Step 3: 邮件通知渠道**

`app/notifications/channels/email.py`:
迁移现有 `NotificationService.send_email()` 逻辑。

**Step 4: 重构旧 NotificationService**

修改 `app/services/notification.py`：保留 `format_briefing_summary()`, `format_alert_signals()`, `push_daily_report()` 等方法，内部改为调用 `NotificationManager`。保持 briefing 路由兼容。

**Step 5: Commit**

```bash
git add app/notifications/ app/services/notification.py
git commit -m "refactor: 通知系统重构为插件化架构 — Slack/Email 渠道"
```

---

## Task 4: LLM 智能分析层（智谱）

**Files:**
- Create: `app/llm/__init__.py`
- Create: `app/llm/base.py`
- Create: `app/llm/router.py`
- Create: `app/llm/providers/__init__.py`
- Create: `app/llm/providers/zhipu.py`
- Create: `app/llm/prompts/__init__.py`
- Create: `app/llm/prompts/wyckoff_analysis.py`
- Create: `app/llm/prompts/trade_advice.py`
- Create: `app/llm/prompts/market_summary.py`
- Modify: `app/services/ai_analyzer.py` → 改为调用 LLM 层

**Step 1: LLM 基类和路由器**

`app/llm/base.py`:
```python
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    name: str = ""
    model: str = ""
    cost_per_1k_tokens: float = 0.0

    @abstractmethod
    def chat(self, messages: list[dict], temperature: float = 0.3, max_tokens: int = 500) -> str: ...

class LLMLayer:
    RULE = 0      # 规则引擎，$0
    FLASH = 1     # 智谱 GLM-4-Flash，便宜
    PREMIUM = 2   # 智谱 GLM-4，强
```

`app/llm/router.py`:
```python
class LLMRouter:
    """分层路由器 — 按任务复杂度选择模型"""

    def __init__(self):
        self.providers = {}
        self._daily_cost = 0.0
        self._daily_budget = float(os.environ.get('LLM_DAILY_BUDGET', '5.0'))

    def route(self, task_type: str) -> LLMProvider | None:
        """
        task_type 映射:
        - 'summary' → FLASH
        - 'analysis' → PREMIUM
        - 'advice' → PREMIUM
        预算超限 → 自动降级
        """
```

**Step 2: 智谱 Provider**

`app/llm/providers/zhipu.py`:
使用 httpx 调用智谱 API（`https://open.bigmodel.cn/api/paas/v4/chat/completions`）。环境变量 `ZHIPU_API_KEY`。支持 GLM-4-Flash 和 GLM-4 两个模型。

**Step 3: Prompt 模板**

`app/llm/prompts/wyckoff_analysis.py`:
复用现有 `_build_prompt()` 中的技术分析 prompt 结构，增加威科夫深度解读部分。

`app/llm/prompts/trade_advice.py`:
复用现有 prompt 的 JSON 输出格式，增加仓位管理建议。

`app/llm/prompts/market_summary.py`:
新增 — 为每日简报生成市场总结，输入指数/期货/板块数据，输出 2-3 句市场概况。

**Step 4: 重构 AIAnalyzerService**

修改 `app/services/ai_analyzer.py`：
- `_call_llm()` 改为调用 `LLMRouter.route('analysis').chat()`
- 删除旧的 OpenAI 兼容调用代码
- 环境变量从 `AI_API_KEY/AI_BASE_URL/AI_MODEL` 迁移到 `ZHIPU_API_KEY`

**Step 5: Commit**

```bash
git add app/llm/ app/services/ai_analyzer.py
git commit -m "feat: LLM 智能分析层 — 智谱 GLM-4 + 分层路由 + 成本控制"
```

---

## Task 5: APScheduler 调度引擎 + 事件总线

**Files:**
- Create: `app/scheduler/__init__.py`
- Create: `app/scheduler/engine.py`
- Create: `app/scheduler/event_bus.py`
- Modify: `app/__init__.py:148-260` → 在 `create_app()` 中初始化调度引擎
- Modify: `requirements.txt` → 添加 `apscheduler>=3.10.0` 和 `pyyaml>=6.0`

**Step 1: 事件总线**

`app/scheduler/event_bus.py`:
```python
import logging
from typing import Callable
from app.strategies.base import Signal

logger = logging.getLogger(__name__)

class EventBus:
    """简单的同步事件总线"""
    _instance = None
    _handlers: list[Callable] = []

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._handlers = []
        return cls._instance

    def subscribe(self, handler: Callable[[Signal], None]):
        self._handlers.append(handler)

    def publish(self, signal: Signal):
        for handler in self._handlers:
            try:
                handler(signal)
            except Exception as e:
                logger.error(f'[事件总线] handler 失败: {e}')

event_bus = EventBus()
```

**Step 2: 调度引擎**

`app/scheduler/engine.py`:
```python
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.strategies.registry import registry
from app.scheduler.event_bus import event_bus

class SchedulerEngine:
    def __init__(self, app=None):
        self.scheduler = BackgroundScheduler()
        self.app = app

    def init_app(self, app):
        self.app = app
        # 注册所有策略的定时任务
        for strategy in registry.active:
            if strategy.schedule:
                trigger = CronTrigger.from_crontab(strategy.schedule)
                self.scheduler.add_job(
                    self._run_strategy,
                    trigger=trigger,
                    args=[strategy.name],
                    id=f'strategy_{strategy.name}',
                    replace_existing=True,
                )
        self.scheduler.start()

    def _run_strategy(self, strategy_name: str):
        """在 app context 内执行策略扫描"""
        with self.app.app_context():
            strategy = registry.get(strategy_name)
            if not strategy:
                return
            signals = strategy.scan()
            for signal in signals:
                event_bus.publish(signal)
```

**Step 3: 集成到 Flask app**

修改 `app/__init__.py`：
- 在 `create_app()` 末尾添加策略发现和调度器初始化
- 事件总线订阅 NotificationManager.dispatch

```python
# create_app() 末尾添加
from app.strategies.registry import registry
from app.scheduler.engine import SchedulerEngine
from app.scheduler.event_bus import event_bus
from app.notifications.manager import notification_manager

registry.discover()
event_bus.subscribe(notification_manager.dispatch)

scheduler = SchedulerEngine()
scheduler.init_app(app)
```

**Step 4: 更新 requirements.txt**

添加:
```
apscheduler>=3.10.0
pyyaml>=6.0
```

**Step 5: Commit**

```bash
git add app/scheduler/ app/__init__.py requirements.txt
git commit -m "feat: APScheduler 调度引擎 + 事件总线 — 策略自动定时执行"
```

---

## Task 6: UI 暗色主题 — CSS 变量体系

**Files:**
- Create: `app/static/css/theme-dark.css`
- Modify: `app/static/css/style.css:1-8` → 添加 CSS 变量
- Modify: `app/static/css/skeleton.css` → 适配暗色
- Modify: `app/templates/base.html:7-13` → 引入暗色主题 CSS

**Step 1: 创建暗色主题 CSS 变量文件**

`app/static/css/theme-dark.css`:
```css
:root {
    --bg-primary: #0d1117;
    --bg-secondary: #161b22;
    --bg-card: rgba(22, 27, 34, 0.8);
    --bg-card-hover: rgba(30, 37, 46, 0.9);
    --border-color: rgba(48, 54, 61, 0.6);
    --text-primary: #e6edf3;
    --text-secondary: #8b949e;
    --text-muted: #6e7681;
    --accent: #00d4aa;
    --accent-light: rgba(0, 212, 170, 0.15);
    --profit: #3fb950;
    --loss: #f85149;
    --warning: #d29922;

    /* glassmorphism */
    --glass-bg: rgba(22, 27, 34, 0.6);
    --glass-border: rgba(255, 255, 255, 0.08);
    --glass-blur: 12px;
}

body {
    background-color: var(--bg-primary) !important;
    color: var(--text-primary) !important;
}

/* Glassmorphism 卡片 */
.module-card, .card {
    background: var(--glass-bg) !important;
    border: 1px solid var(--glass-border) !important;
    backdrop-filter: blur(var(--glass-blur));
    -webkit-backdrop-filter: blur(var(--glass-blur));
    border-radius: 12px !important;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

/* 导航栏 */
.navbar {
    background: rgba(13, 17, 23, 0.95) !important;
    border-bottom: 1px solid var(--border-color);
    backdrop-filter: blur(10px);
}

/* 表格 */
.table {
    color: var(--text-primary) !important;
    --bs-table-bg: transparent;
    --bs-table-hover-bg: var(--bg-card-hover);
    --bs-table-border-color: var(--border-color);
}

/* 表单控件 */
.form-control, .form-select {
    background-color: var(--bg-secondary) !important;
    border-color: var(--border-color) !important;
    color: var(--text-primary) !important;
}

/* 模态框 */
.modal-content {
    background: var(--bg-secondary) !important;
    border: 1px solid var(--glass-border) !important;
    color: var(--text-primary) !important;
}

/* 下拉菜单 */
.dropdown-menu {
    background: var(--bg-secondary) !important;
    border: 1px solid var(--border-color) !important;
}
.dropdown-item {
    color: var(--text-primary) !important;
}
.dropdown-item:hover {
    background: var(--bg-card-hover) !important;
}

/* 盈亏颜色 */
.text-success, .profit { color: var(--profit) !important; }
.text-danger, .loss { color: var(--loss) !important; }

/* 强调色 */
.text-accent { color: var(--accent) !important; }
.bg-accent { background-color: var(--accent-light) !important; }

/* 骨架屏暗色适配 */
.skeleton-line, .skeleton-card {
    background: linear-gradient(90deg,
        var(--bg-secondary) 25%,
        rgba(48, 54, 61, 0.5) 50%,
        var(--bg-secondary) 75%) !important;
}
```

**Step 2: 修改 base.html 引入暗色主题**

在 `app/templates/base.html` 第11行后添加:
```html
<link rel="stylesheet" href="{{ url_for('static', filename='css/theme-dark.css') }}">
```

**Step 3: 修改 style.css 使用 CSS 变量**

将 `style.css` 中硬编码的颜色值替换为 CSS 变量引用。如：
- `background-color: #fff` → `background-color: var(--bg-card, #fff)`
- `color: #333` → `color: var(--text-primary, #333)`
- `border: 1px solid #dee2e6` → `border: 1px solid var(--border-color, #dee2e6)`

**Step 4: 图表暗色适配**

修改 `app/static/js/charts.js` 和 `app/static/js/profit_charts.js`：
- Chart.js 全局默认颜色改为暗色系
- ECharts 主题切换为 dark

在 `app/static/js/main.js` 中添加全局 Chart.js 暗色默认配置:
```javascript
if (typeof Chart !== 'undefined') {
    Chart.defaults.color = '#8b949e';
    Chart.defaults.borderColor = 'rgba(48, 54, 61, 0.6)';
    Chart.defaults.backgroundColor = 'rgba(0, 212, 170, 0.15)';
}
```

**Step 5: 各页面微调**

逐一检查所有模板，确保无硬编码的白色背景或深色文字。重点关注：
- `briefing.html` — 各数据卡片
- `alert.html` — 信号列表
- `heavy_metals.html` — 走势图容器
- `index.html` — 持仓表格

**Step 6: Commit**

```bash
git add app/static/css/ app/static/js/ app/templates/
git commit -m "feat: UI 暗色主题 — glassmorphism + CSS 变量体系"
```

---

## Task 7: 集成验证 + 清理

**Files:**
- Modify: `app/__init__.py` → 确保启动顺序正确
- Delete: `app/services/preload.py` 的 `__pycache__` 残留（可选）
- Modify: `app/routes/alert.py` → 可选：从策略系统读取信号
- Modify: `app/routes/briefing.py` → 可选：从策略系统触发推送

**Step 1: 启动顺序验证**

确保 `create_app()` 中初始化顺序：
1. DB 初始化
2. Blueprint 注册
3. 策略发现 (`registry.discover()`)
4. 通知管理器初始化
5. 事件总线绑定
6. 调度器启动

**Step 2: 端到端验证**

启动应用 `python run.py`，确认：
- 无启动错误
- 策略自动发现并注册（日志中可见）
- 调度器按 cron 调度（日志中可见 job 注册）
- 页面暗色主题正常渲染
- Slack 通知可测试发送（推送设置）
- AI 分析走智谱 API（需配置 ZHIPU_API_KEY）

**Step 3: 环境变量汇总**

更新 `.env.example`（如果存在）或在 CLAUDE.md 中记录：
```
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
ZHIPU_API_KEY=your-zhipu-api-key
LLM_DAILY_BUDGET=5.0
```

**Step 4: Commit**

```bash
git add -A
git commit -m "feat: 架构升级集成 — 策略插件/通知/LLM/调度/暗色主题"
```

---

## 依赖关系

```
Task 1 (策略基础) ← Task 2 (策略实现)
Task 1 (策略基础) ← Task 3 (通知重构)
Task 1 (策略基础) ← Task 5 (调度引擎)
Task 4 (LLM层) ← Task 2 (daily_briefing 需要 LLM)
Task 6 (UI) — 独立，可并行
Task 7 (集成) ← 所有其他 Task
```

**推荐执行顺序**: Task 1 → Task 3 → Task 4 → Task 2 → Task 5 → Task 6 → Task 7

可并行组合:
- Task 6 (UI) 可以和 Task 1-5 中的任何一个并行
- Task 3 (通知) 和 Task 4 (LLM) 可以并行
