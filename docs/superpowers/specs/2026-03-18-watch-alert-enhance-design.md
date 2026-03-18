# 盯盘告警系统增强设计

## 目标

将告警系统从单一的"日内突破前高/前低"扩展为 7 种告警类型，移除确认延迟和冷却机制，复用现有 AI 分析输出驱动告警参数。

## 现状

- `WatchAlertService` 仅检测日内突破前高/前低
- 10 分钟确认延迟 + 300 秒冷却期
- 与 AI 分析结果完全脱节

## 设计

### 1. AI 分析输出扩展

扩展 7d 分析 prompt，在现有输出基础上新增 `alert_params` 字段：

```json
{
  "support_levels": [1800, 1750],
  "resistance_levels": [1850, 1900],
  "ma_levels": {"ma5": 1825, "ma20": 1810, "ma60": 1790},
  "signal": "hold",
  "summary": "...",
  "alert_params": {
    "target_prices": [
      {"price": 1900, "direction": "above", "reason": "突破前高压力位"},
      {"price": 1720, "direction": "below", "reason": "跌破关键支撑"}
    ],
    "change_threshold_pct": 3.5,
    "volume_anomaly_ratio": 2.0
  }
}
```

- `target_prices`：AI 根据技术形态设定的目标价和方向。prompt 中明确指示 **不要与 support_levels/resistance_levels 重复**，仅包含超出常规支撑阻力的关键突破位
- `change_threshold_pct`：AI 根据近期波动率计算的涨跌幅阈值，代码 clamp 到 1%-10% 防止异常值
- `volume_anomaly_ratio`：AI 判断的异动倍率（如 2.0 表示 2 倍于均量视为异动）
- `volume_baseline` 不由 AI 输出，改为代码直接从 7 日 K 线计算日均成交量（简单算术平均，避免 LLM 计算误差）

修改文件：`app/llm/prompts/watch_analysis.py` 中 `build_7d_analysis_prompt`

存储：`watch_analysis_service.py` 构造 `detail` dict 时，显式加入 `parsed.get('alert_params', {})`，同时在代码中计算 `volume_baseline` 并补入 `alert_params`

### 2. 七种检测器

| 检测器 | 输入数据 | 触发条件 | 去重 key |
|--------|---------|---------|----------|
| `check_target_price` | AI target_prices + 实时价格 | 价格穿越目标价（方向匹配） | `target:{code}:{price}` |
| `check_price_change` | AI change_threshold_pct + `prices[code]['change_percent']` | 涨跌幅超阈值 | `change:{code}:{direction}` |
| `check_support_resistance` | AI support/resistance + 实时价格 | 价格触及（±0.5%范围内） | `sr:{code}:{level}` |
| `check_ma_crossover` | AI ma_levels + 实时价格 + `_prev_ma_side` 状态 | 价格从一侧穿越到另一侧 | `ma:{code}:{ma_type}:{direction}` |
| `check_volume_anomaly` | volume_baseline(代码计算) + ratio(AI) + 时间归一化后的实时成交量 | 归一化量 ≥ baseline × ratio | `volume:{code}` |
| `check_td_sequential` | TDSequentialService 计算结果 | count = 9（九转完成） | `td:{code}:{direction}` |
| `check_intraday_extreme` | 实时价格 + 日内极值追踪 | 突破前高/跌破前低 | `extreme:{code}:{level}` |

7 个 checker 作为 `WatchAlertService` 的方法，每个 20-30 行。

#### 检测器细节

**check_ma_crossover 穿越检测**：维护 `_prev_ma_side: dict[str, dict[str, str]]`（`{code: {ma5: 'above'|'below', ...}}`）。只有当前侧与上次不同时才视为穿越。服务重启后首次检测仅记录位置不触发告警，避免误报。

**check_volume_anomaly 时间归一化**：当日累计成交量需按已过交易时间比例归一化后再与日均量比较。公式：`normalized = current_volume / (elapsed_trading_minutes / total_trading_minutes)`。依赖 `TradingCalendarService` 获取交易时段信息。

**check_td_sequential**：仅在 count=9（九转完成信号）时触发，避免 count=7/8/9 连续 3 次推送。

### 3. 去重机制

```python
_fired: dict[str, set[str]]  # {date_str: {fired_key, ...}}
```

- 日切清空整个 `_fired`
- 触发前检查 key 是否在当日集合中
- 不同 level 生成不同 key，突破多个支撑位分别告警
- 移除 10 分钟确认延迟和 300 秒冷却
- `_fired` 是唯一去重层，Signal.data 中不需要适配 NotificationManager 的去重协议

### 4. 数据流

```
8:30 DailyBriefingStrategy
  └─ WatchAnalysisService.analyze_stocks('7d')
     └─ LLM 输出扩展 JSON（含 alert_params）
     └─ 代码计算 volume_baseline 补入 alert_params
     └─ 存入 WatchAnalysis.analysis_detail

全天每分钟 WatchAlertStrategy.scan()
  ├─ 从 DB 读取当日 7d 分析结果（含 alert_params）→ 内存缓存
  ├─ 获取实时价格
  ├─ 每15分钟：获取趋势数据 → TDSequentialService.calculate()（用 _last_td_calc 时间戳节流）
  └─ 依次执行 7 个 checker → 产出 Signal[]
```

#### 降级策略

当某只股票缺少当日 7d 分析（LLM 不可用、服务重启后新加入等）时：
- 仅执行不依赖 AI 参数的检测器：`check_intraday_extreme`、`check_td_sequential`
- 依赖 AI 参数的 5 个检测器跳过该股票，不报错

### 5. 改动范围

| 文件 | 改动 |
|------|------|
| `app/llm/prompts/watch_analysis.py` | 7d prompt 扩展，要求输出 `alert_params`（target_prices 不与支撑阻力重复） |
| `app/services/watch_analysis_service.py` | detail dict 中加入 `alert_params`，代码计算 `volume_baseline` |
| `app/services/watch_alert_service.py` | 重写：移除确认/冷却，改为 7 个 checker + fired 去重 + _prev_ma_side 状态 |
| `app/strategies/watch_alert/__init__.py` | 扩展：加载 AI 参数、TD 定时计算（15分钟节流） |

不需要新增文件，不改动前端、数据模型、通知推送链路。
