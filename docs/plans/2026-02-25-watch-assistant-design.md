# 盯盘助手设计文档

日期：2026-02-25

## 概述

盯盘助手是一个实时监控关注股票价格波动的功能模块。基于策略插件系统实现，支持 A股/美股/港股三个市场，通过 AI 个性化计算每只股票的关键价位和波动阈值，超过阈值时通过 Slack 推送通知。

## 需求

1. 本地保存盯盘股票列表，可从 Stock 表中选择添加
2. 可配置的分钟级价格刷新频率（`.env`）
3. 多市场交易时间管理（含午休时间），非交易时段不监控
4. 每日首次进入页面时 AI 计算支撑位/阻力位/波动阈值
5. 价格变动超过阈值时 Slack 通知
6. 独立 `/watch` 前端页面

## 数据模型

### WatchList

```python
class WatchList(db.Model):
    __tablename__ = 'watch_list'
    id = db.Column(db.Integer, primary_key=True)
    stock_code = db.Column(db.String(20), nullable=False, unique=True)
    stock_name = db.Column(db.String(50))
    market = db.Column(db.String(10))           # 'A', 'US', 'HK'
    added_at = db.Column(db.DateTime, default=datetime.utcnow)
```

### WatchAnalysis

```python
class WatchAnalysis(db.Model):
    __tablename__ = 'watch_analysis'
    id = db.Column(db.Integer, primary_key=True)
    stock_code = db.Column(db.String(20), nullable=False)
    analysis_date = db.Column(db.Date, nullable=False)
    support_levels = db.Column(db.Text)         # JSON: [1780, 1750]
    resistance_levels = db.Column(db.Text)      # JSON: [1820, 1850]
    volatility_threshold = db.Column(db.Float)  # 如 0.01 表示 1%
    analysis_summary = db.Column(db.Text)
    created_at = db.Column(db.DateTime)
    # 唯一约束: (stock_code, analysis_date)
```

## 后台监控 — 策略插件

### 文件结构

```
app/strategies/watch_assistant/
├── __init__.py      # WatchAssistantStrategy
├── config.yaml      # 默认配置
└── prompts.py       # AI prompt 模板
```

### WatchAssistantStrategy

- 继承 `Strategy` 基类
- `schedule = ""` — 不用 cron，使用 `IntervalTrigger(minutes=N)`
- `.env` 配置 `WATCH_INTERVAL_MINUTES`（默认 1）

### scan() 核心逻辑

1. 获取盯盘列表，按市场分组
2. 过滤仅当前交易时段的市场
3. 调用 `unified_stock_data_service.get_realtime_prices()`
4. 与内存中 `_last_prices` 对比，计算变化幅度
5. 超过 `volatility_threshold` → 生成 Signal → EventBus 发布

### 多市场交易时间

```python
MARKET_SESSIONS = {
    'A':  [(time(9,30), time(11,30)), (time(13,0), time(15,0))],
    'US': [(time(9,30), time(16,0))],  # 美东时间
    'HK': [(time(9,30), time(12,0)), (time(13,0), time(16,0))],
}
```

复用 `SmartCacheStrategy` 中现有的市场时间逻辑。

### 价格对比

- `_last_prices: dict[str, float]` 内存字典
- 变化幅度 = `abs(new - last) / last`
- 超过 `volatility_threshold` 触发通知，更新 `_last_prices`

## AI 分析

### 触发时机

- 每天第一次进入 `/watch` 页面时自动触发
- 检查 `WatchAnalysis` 是否有当日记录，有则返回缓存
- 页面提供手动重新分析按钮

### 分析输入

- 近 30 天 OHLC 数据（`get_trend_data`）
- 当前实时价格

### Prompt

请求 LLM 返回 JSON：
- `support_levels`: 2-3 个支撑位
- `resistance_levels`: 2-3 个阻力位
- `volatility_threshold`: 基于近期波动率的监控阈值
- `summary`: 一句话分析

使用 `llm_router.route('analysis')` → glm-4 Premium

### Slack 通知格式

```
🔔 盯盘提醒 | 贵州茅台(600519)
当前价: ¥1815.00 | 变动: +1.2%
距支撑位 ¥1780: +1.97%
距阻力位 ¥1850: -1.89%
AI 分析: 价格突破短期均线，关注1820阻力位
```

## 前端页面 `/watch`

### 布局

**顶部操作栏**：
- "+" 按钮 → Modal 搜索选择股票
- "AI 分析" 按钮 → 手动触发分析

**主体 — 盯盘卡片列表**：
- 股票名称/代码 + 市场标签
- 实时价格 + 涨跌幅
- AI 分析结果（支撑位/阻力位/阈值/摘要）
- 删除按钮
- 市场状态指示（交易中/午休/已收盘）

### 实时刷新

- `setInterval` 轮询 `GET /watch/prices`
- 间隔与后台一致（配置读取）
- 非交易时段停止轮询

### 技术

- Bootstrap 5 + 原生 JS
- 骨架屏加载状态
- 暗色主题兼容

## 环境变量

```
WATCH_INTERVAL_MINUTES=1    # 盯盘刷新间隔（分钟）
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /watch | 盯盘助手页面 |
| GET | /watch/list | 获取盯盘列表 |
| POST | /watch/add | 添加股票到盯盘列表 |
| DELETE | /watch/remove/<code> | 移除股票 |
| GET | /watch/prices | 获取实时价格 |
| POST | /watch/analyze | 触发 AI 分析 |
| GET | /watch/analysis | 获取 AI 分析结果 |

## 复用现有组件

- `Strategy` 基类 + `StrategyRegistry` 自动发现
- `SchedulerEngine` 调度（IntervalTrigger）
- `EventBus` + `NotificationManager` 通知管道
- `UnifiedStockDataService` 数据获取
- `SmartCacheStrategy` 市场时间判断
- `LLMRouter` + `ZhipuProvider` AI 分析
- `MarketIdentifier` 市场识别
