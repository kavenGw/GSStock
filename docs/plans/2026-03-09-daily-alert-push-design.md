# 每日预警推送优化 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将预警中心的完整信息（全分类信号+财报提醒+PE预警）整合到每日简报推送，并增加启动补发机制。

**Architecture:** 增强 `NotificationService.push_daily_report()` 作为统一推送入口。策略定时触发和引擎启动补发都调用同一逻辑。推送成功后写本地标记文件防止重复推送。

**Tech Stack:** Flask, SQLAlchemy, APScheduler, Slack Webhook

---

### Task 1: NotificationService — 收集所有关注股票代码

**Files:**
- Modify: `app/services/notification.py`

**Step 1: 新增 `_get_all_watched_codes()` 方法**

在 `NotificationService` 中新增静态方法，收集持仓股 + 所有分类下的A股代码及名称映射：

```python
@staticmethod
def _get_all_watched_codes() -> tuple[list[str], dict[str, str]]:
    """收集所有关注的股票代码（持仓+分类），返回 (codes, name_map)"""
    from app.services.position import PositionService
    from app.models.stock import Stock
    from app.models.category import Category, StockCategory
    from app.utils.market_identifier import MarketIdentifier

    name_map = {}
    code_set = set()

    # 持仓股
    latest_date = PositionService.get_latest_date()
    if latest_date:
        positions = PositionService.get_snapshot(latest_date)
        for p in positions:
            code_set.add(p.stock_code)
            name_map[p.stock_code] = p.stock_name

    # 分类股
    all_sc = StockCategory.query.all()
    sc_codes = [sc.stock_code for sc in all_sc if sc.stock_code not in code_set]
    if sc_codes:
        stocks = Stock.query.filter(Stock.stock_code.in_(sc_codes)).all()
        for s in stocks:
            code_set.add(s.stock_code)
            name_map[s.stock_code] = s.stock_name

    codes = list(code_set)
    return codes, name_map
```

**Step 2: 验证**

启动应用，在 Flask shell 中调用确认能获取到股票列表。

**Step 3: Commit**

```bash
git add app/services/notification.py
git commit -m "feat: NotificationService 新增 _get_all_watched_codes 收集全部关注股票"
```

---

### Task 2: 扩展 format_alert_signals() 覆盖所有分类

**Files:**
- Modify: `app/services/notification.py`

**Step 1: 修改 `format_alert_signals()`**

将现有的"只查持仓A股"逻辑替换为调用 `_get_all_watched_codes()`，覆盖所有分类：

```python
@staticmethod
def format_alert_signals() -> dict:
    """生成预警信号摘要（所有关注股票）"""
    from app.services.signal_cache import SignalCacheService
    from app.utils.market_identifier import MarketIdentifier

    codes, name_map = NotificationService._get_all_watched_codes()
    a_share_codes = [c for c in codes if MarketIdentifier.is_a_share(c)]

    if not a_share_codes:
        return {'text': ''}

    signals = SignalCacheService.get_cached_signals_with_names(a_share_codes, name_map)

    buy_signals = signals.get('buy_signals', [])
    sell_signals = signals.get('sell_signals', [])

    if not buy_signals and not sell_signals:
        return {'text': ''}

    text = "预警信号\n"

    if sell_signals:
        text += "\n卖出信号:\n"
        for sig in sell_signals[:10]:
            text += f"  {sig.get('stock_name', '')}({sig.get('stock_code', '')}) - {sig.get('name', '')}\n"

    if buy_signals:
        text += "\n买入信号:\n"
        for sig in buy_signals[:10]:
            text += f"  {sig.get('stock_name', '')}({sig.get('stock_code', '')}) - {sig.get('name', '')}\n"

    return {'text': text}
```

**Step 2: Commit**

```bash
git add app/services/notification.py
git commit -m "feat: format_alert_signals 覆盖所有分类股票"
```

---

### Task 3: 新增 format_earnings_alerts()

**Files:**
- Modify: `app/services/notification.py`

**Step 1: 新增方法**

调用 `EarningsService.get_upcoming_earnings()` 获取未来7天有财报的股票：

```python
@staticmethod
def format_earnings_alerts() -> dict:
    """生成财报日期提醒（未来7天）"""
    from app.services.earnings import EarningsService
    from app.utils.market_identifier import MarketIdentifier

    codes, name_map = NotificationService._get_all_watched_codes()
    # 财报日期仅针对美股/港股
    non_a_codes = [c for c in codes if not MarketIdentifier.is_a_share(c)]

    if not non_a_codes:
        return {'text': ''}

    upcoming = EarningsService.get_upcoming_earnings(non_a_codes, days=7)
    if not upcoming:
        return {'text': ''}

    text = "财报提醒（未来7天）\n"
    for item in upcoming:
        name = name_map.get(item['code'], item['code'])
        if item['is_today']:
            text += f"  {name}({item['code']}) - 今天发布财报\n"
        else:
            text += f"  {name}({item['code']}) - {item['days_until']}天后({item['earnings_date']})\n"

    return {'text': text}
```

**Step 2: Commit**

```bash
git add app/services/notification.py
git commit -m "feat: 新增 format_earnings_alerts 财报日期提醒"
```

---

### Task 4: 新增 format_pe_alerts()

**Files:**
- Modify: `app/services/notification.py`

**Step 1: 新增方法**

获取美股/港股PE数据，筛选 high/very_high/low 状态：

```python
@staticmethod
def format_pe_alerts() -> dict:
    """生成PE估值预警（偏高/偏低）"""
    from app.services.earnings import EarningsService
    from app.utils.market_identifier import MarketIdentifier

    codes, name_map = NotificationService._get_all_watched_codes()
    non_a_codes = [c for c in codes if not MarketIdentifier.is_a_share(c)]

    if not non_a_codes:
        return {'text': ''}

    pe_data = EarningsService.get_pe_ratios(non_a_codes)

    alerts = []
    for code, data in pe_data.items():
        status = data.get('pe_status', 'na')
        if status in ('high', 'very_high', 'low'):
            name = name_map.get(code, code)
            pe_display = data.get('pe_display', '?')
            label = {'high': '偏高', 'very_high': '极高', 'low': '偏低'}[status]
            alerts.append(f"  {name}({code}) PE={pe_display} {label}")

    if not alerts:
        return {'text': ''}

    text = "PE估值预警\n" + "\n".join(alerts) + "\n"
    return {'text': text}
```

**Step 2: Commit**

```bash
git add app/services/notification.py
git commit -m "feat: 新增 format_pe_alerts PE估值预警"
```

---

### Task 5: 修改 push_daily_report() 整合全部内容 + 标记文件

**Files:**
- Modify: `app/services/notification.py`

**Step 1: 修改 `push_daily_report()`**

整合全部板块，推送成功后写标记文件：

```python
@staticmethod
def push_daily_report(include_ai: bool = False) -> dict:
    """一键推送每日报告（简报+预警信号+财报提醒+PE预警+AI分析）"""
    import os

    today = date.today()
    subject = f'每日股票分析报告 - {today}'

    briefing = NotificationService.format_briefing_summary()
    alerts = NotificationService.format_alert_signals()
    earnings = NotificationService.format_earnings_alerts()
    pe = NotificationService.format_pe_alerts()

    text_parts = [briefing['text']]

    if alerts.get('text'):
        text_parts.append(alerts['text'])
    if earnings.get('text'):
        text_parts.append(earnings['text'])
    if pe.get('text'):
        text_parts.append(pe['text'])

    if include_ai:
        try:
            from app.services.ai_analyzer import AIAnalyzerService, AI_ENABLED
            if AI_ENABLED:
                ai_service = AIAnalyzerService()
                from app.services.position import PositionService
                latest_date = PositionService.get_latest_date()
                if latest_date:
                    positions = PositionService.get_snapshot(latest_date)
                    stock_list = [{'code': p.stock_code, 'name': p.stock_name} for p in positions]
                    analyses = ai_service.analyze_batch(stock_list)
                    ai_report = NotificationService.format_ai_report(analyses)
                    if ai_report['text']:
                        text_parts.append(ai_report['text'])
        except Exception as e:
            logger.warning(f'[通知.AI报告] 生成失败: {e}')

    full_text = '\n---\n'.join(text_parts)

    results = NotificationService.send_all(subject, full_text)
    results['content_preview'] = full_text[:500]

    # 推送成功后写标记文件
    if results.get('slack'):
        NotificationService._mark_daily_push(today)

    return results

@staticmethod
def _mark_daily_push(push_date: date) -> None:
    """写入每日推送标记文件"""
    import os
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
    os.makedirs(data_dir, exist_ok=True)
    flag_path = os.path.join(data_dir, f'daily_push_{push_date.isoformat()}.flag')
    with open(flag_path, 'w') as f:
        f.write('')

@staticmethod
def has_daily_push(push_date: date) -> bool:
    """检查当天是否已推送"""
    import os
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
    flag_path = os.path.join(data_dir, f'daily_push_{push_date.isoformat()}.flag')
    return os.path.exists(flag_path)

@staticmethod
def cleanup_old_flags(keep_days: int = 7) -> None:
    """清理旧的推送标记文件"""
    import os
    import glob
    data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data')
    cutoff = date.today() - timedelta(days=keep_days)
    pattern = os.path.join(data_dir, 'daily_push_*.flag')
    for f in glob.glob(pattern):
        basename = os.path.basename(f)
        try:
            date_str = basename.replace('daily_push_', '').replace('.flag', '')
            flag_date = date.fromisoformat(date_str)
            if flag_date < cutoff:
                os.remove(f)
        except (ValueError, OSError):
            pass
```

**Step 2: Commit**

```bash
git add app/services/notification.py
git commit -m "feat: push_daily_report 整合财报+PE预警，增加推送标记文件"
```

---

### Task 6: 简化 DailyBriefingStrategy

**Files:**
- Modify: `app/strategies/daily_briefing/__init__.py`

**Step 1: 修改 `scan()`**

直接调用 `push_daily_report()`，返回空信号列表避免重复推送：

```python
"""每日简报策略 — 汇总市场数据生成日报"""
import logging
from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)


class DailyBriefingStrategy(Strategy):
    name = "daily_briefing"
    description = "每日简报（市场概况+持仓+预警）"
    schedule = "30 8 * * 1-5"
    needs_llm = True

    def scan(self) -> list[Signal]:
        from app.services.notification import NotificationService

        try:
            results = NotificationService.push_daily_report()
            if results.get('slack'):
                logger.info('[每日简报] 推送成功')
            else:
                logger.warning('[每日简报] 推送失败或未配置')
        except Exception as e:
            logger.error(f'[每日简报] 推送失败: {e}')

        return []
```

**Step 2: Commit**

```bash
git add app/strategies/daily_briefing/__init__.py
git commit -m "refactor: DailyBriefingStrategy 简化为调用 push_daily_report"
```

---

### Task 7: SchedulerEngine 启动补发机制

**Files:**
- Modify: `app/scheduler/engine.py`

**Step 1: 在 `init_app()` 末尾增加补发检查**

在 `self.scheduler.start()` 之后、`logger.info` 之前，增加补发逻辑：

```python
# 在 init_app() 末尾，self.scheduler.start() 之后添加：

# 启动补发检查
self._check_daily_push_catchup(app)
```

**Step 2: 新增 `_check_daily_push_catchup()` 方法**

```python
def _check_daily_push_catchup(self, app):
    """检查是否需要补发每日推送"""
    from datetime import date, time

    now = datetime.now()
    today = date.today()

    # 仅工作日 + 8:30之后
    if today.weekday() >= 5:
        return
    if now.time() < time(8, 30):
        return

    from app.services.notification import NotificationService
    if NotificationService.has_daily_push(today):
        logger.info('[调度器] 今日已推送，跳过补发')
        return

    # 清理旧标记文件
    NotificationService.cleanup_old_flags()

    # 延迟30秒执行补发
    from apscheduler.triggers.date import DateTrigger
    run_time = datetime.now() + timedelta(seconds=30)

    self.scheduler.add_job(
        self._run_daily_push_catchup,
        trigger=DateTrigger(run_date=run_time),
        id='daily_push_catchup',
        replace_existing=True,
    )
    logger.info(f'[调度器] 今日未推送，将在30秒后补发')

def _run_daily_push_catchup(self):
    """执行补发"""
    if not self.app:
        return
    with self.app.app_context():
        try:
            from app.services.notification import NotificationService
            results = NotificationService.push_daily_report()
            if results.get('slack'):
                logger.info('[调度器] 每日推送补发成功')
            else:
                logger.warning('[调度器] 每日推送补发失败或未配置')
        except Exception as e:
            logger.error(f'[调度器] 每日推送补发失败: {e}')
```

注意 `engine.py` 顶部需导入 `timedelta`：

```python
from datetime import datetime, timedelta
```

**Step 3: Commit**

```bash
git add app/scheduler/engine.py
git commit -m "feat: SchedulerEngine 启动时检查补发每日推送"
```

---

### Task 8: 端到端验证

**Step 1: 启动应用验证**

```bash
python run.py
```

观察日志：
- 若当前时间 > 8:30 且为工作日，应看到 `[调度器] 今日未推送，将在30秒后补发`
- 30秒后应看到 `[调度器] 每日推送补发成功`（需配置 Slack）
- `data/` 目录下应生成 `daily_push_YYYY-MM-DD.flag` 文件

**Step 2: 再次启动验证不重复推送**

重启应用，应看到 `[调度器] 今日已推送，跳过补发`

**Step 3: Commit（如有修正）**

```bash
git add -u
git commit -m "fix: 每日预警推送端到端修正"
```
