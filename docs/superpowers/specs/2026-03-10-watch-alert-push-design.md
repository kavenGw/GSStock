# 盯盘推送告警设计

## 概述

为盯盘助手新增四类实时推送告警：整数价格穿越、支撑/压力位接近与穿越、九转信号、锚点价格累计波动。通过现有 Strategy → EventBus → NotificationManager → Slack 链路推送。

## 架构

### 数据流

```
APScheduler (interval_minutes:1)
  → WatchAlertStrategy.scan()
    → WatchAlertService.check_alerts()
      ├─ get_realtime_prices() → 整数价格穿越检测
      ├─ WatchAnalysis 表 → 读支撑/压力位 → 接近/穿越检测
      ├─ 分时数据 → TDSequentialService.calculate() → 九转变化检测
      └─ _anchors → 锚点价格累计变动检测
      └─ 冷却过滤（5分钟）
    ← Signal[]
  → EventBus.publish(signal)
    → NotificationManager → SlackNotifier

APScheduler (每日开盘前)
  → WatchAnchorStrategy.scan()
    → LLM 为每只股票计算波动阈值
    → WatchAlertService 设置锚点
```

### 新增文件

| 文件 | 用途 |
|------|------|
| `app/services/watch_alert_service.py` | 四类信号检测 + 冷却 + 状态管理 |
| `app/strategies/watch_alert/__init__.py` | 60秒调度策略 |
| `app/strategies/watch_anchor/__init__.py` | 每日锚点阈值AI计算策略 |
| `app/llm/prompts/watch_anchor.py` | 锚点阈值AI prompt |

### 对现有代码的修改

无。策略自动发现机制会自动注册新策略。

## 四类信号检测逻辑

### 1. 整数价格穿越

根据当前价格确定整数档位：

| 价格范围 | 步长 | 示例 |
|---------|------|------|
| < 10 | 1 | 8→9, 9→10 |
| 10 ~ 100 | 10 | 85→90, 98→100 |
| 100 ~ 1000 | 100 | 480→500, 900→1000 |
| ≥ 1000 | 100 | 1780→1800, 1900→2000 |

检测方式：比较 `prev_price` 和 `curr_price`，判断两者之间是否跨越了某个整数关口。上穿和下穿都触发。

推送示例：
> 贵州茅台(600519) 突破 1800 整数关口 ↑ | 当前 1805.20

### 2. 关键位置（支撑/压力位）

数据来源：从 `WatchAnalysis` 表读取最新的 `support_levels` 和 `resistance_levels`。

两阶段检测：
- **接近预警**：当前价格进入某个位置的 ±0.5% 范围内
- **穿越推送**：`prev_price` 在 level 一侧，`curr_price` 在另一侧（跌破支撑 / 突破压力）

推送示例：
> 贵州茅台(600519) 接近支撑位 1750 | 当前 1755.30（距离 0.3%）
> 贵州茅台(600519) 跌破支撑位 1750 ↓ | 当前 1745.80

### 3. 九转信号

每次用最新分时数据调用 `TDSequentialService.calculate()`，与 `_prev_td_counts` 对比：
- count 从 <7 变为 ≥7 → 预警推送（MEDIUM）
- count 变为 9（completed）→ 确认推送（HIGH）

推送示例：
> 贵州茅台(600519) 九转买入信号 7/9 | 当前 1755.30
> 贵州茅台(600519) 九转买入信号完成 9/9 ✓ | 当前 1748.50

### 4. 锚点价格模式

流程：
1. 每日开盘前，调用AI为每只盯盘股票计算波动阈值（基于近期走势、波动率等）
2. 以当时价格设为锚点
3. 每60秒检查价格相对锚点的累计变动，超过阈值则触发推送
4. 触发后重置锚点为当前价格，阈值沿用当日AI计算值

LLM 输出格式：
```json
{
  "stock_code": "600519",
  "threshold_pct": 2.5,
  "reasoning": "近期日均波幅1.2%，考虑茅台低波动特性，建议2.5%为显著波动阈值"
}
```

推送示例：
> 贵州茅台(600519) 累计上涨 3.2%（超过阈值 2.5%）| 锚点 1750 → 当前 1806.00

## 信号优先级

| 信号类型 | Priority |
|---------|----------|
| 整数价格穿越 | MEDIUM |
| 接近支撑/压力位 | MEDIUM |
| 穿越支撑/压力位 | HIGH |
| 九转 ≥7 预警 | MEDIUM |
| 九转 =9 完成 | HIGH |
| 锚点价格超阈值 | HIGH |

## 状态管理

`WatchAlertService` 实例变量：

```python
_prev_prices = {}      # {code: price} 上一次价格
_prev_td_counts = {}   # {code: {direction, count}} 上一次九转状态
_anchors = {}          # {code: {price: float, threshold_pct: float}} 锚点
_cooldown = {}         # {key: datetime} 冷却时间戳
```

首次运行时没有 `_prev_prices`，不产出信号，只建立基线。

## 冷却机制

同类信号5分钟内不重复推送。冷却 key 按信号类型+股票+具体触发点区分：

```
"integer:600519:1800"          # 整数关口
"approach:600519:support:1750" # 接近支撑位
"cross:600519:support:1750"    # 穿越支撑位
"approach:600519:resist:1900"  # 接近压力位
"cross:600519:resist:1900"     # 穿越压力位
"td:600519:buy:7"              # 九转预警
"td:600519:buy:9"              # 九转完成
"anchor:600519"                # 锚点超阈值
```

接近和穿越使用不同的 key，互不影响。

## 配置

| 环境变量 | 说明 | 默认值 |
|---------|------|-------|
| `WATCH_ALERT_COOLDOWN_SECONDS` | 同类信号冷却时间（秒） | `300` |
| `WATCH_ALERT_APPROACH_PCT` | 接近支撑/压力位阈值（%） | `0.5` |
