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
    "volume_baseline": 1500000,
    "volume_anomaly_ratio": 2.0
  }
}
```

- `target_prices`：AI 根据技术形态设定的目标价和方向
- `change_threshold_pct`：AI 根据近期波动率计算的涨跌幅阈值
- `volume_baseline` + `volume_anomaly_ratio`：近期平均成交量 + 异动倍率

修改文件：`app/llm/prompts/watch_analysis.py` 中 `build_7d_analysis_prompt`

### 2. 七种检测器

| 检测器 | 输入数据 | 触发条件 | 去重 key |
|--------|---------|---------|----------|
| `check_target_price` | AI target_prices + 实时价格 | 价格穿越目标价（方向匹配） | `target:{code}:{price}` |
| `check_price_change` | AI change_threshold_pct + 实时涨跌幅 | 涨跌幅超阈值 | `change:{code}:{direction}` |
| `check_support_resistance` | AI support/resistance + 实时价格 | 价格触及（±0.5%范围内） | `sr:{code}:{level}` |
| `check_ma_crossover` | AI ma_levels + 实时价格 | 价格穿越均线（上穿/下穿） | `ma:{code}:{ma_type}:{direction}` |
| `check_volume_anomaly` | AI volume_baseline/ratio + 实时成交量 | 当前量 ≥ baseline × ratio | `volume:{code}` |
| `check_td_sequential` | TDSequentialService 计算结果 | count ≥ 7 | `td:{code}:{count}` |
| `check_intraday_extreme` | 实时价格 + 日内极值追踪 | 突破前高/跌破前低 | `extreme:{code}:{level}` |

7 个 checker 作为 `WatchAlertService` 的方法，每个 20-30 行。

### 3. 去重机制

```python
_fired: dict[str, set[str]]  # {date_str: {fired_key, ...}}
```

- 日切清空整个 `_fired`
- 触发前检查 key 是否在当日集合中
- 不同 level 生成不同 key，突破多个支撑位分别告警
- 移除 10 分钟确认延迟和 300 秒冷却

### 4. 数据流

```
8:30 DailyBriefingStrategy
  └─ WatchAnalysisService.analyze_stocks('7d')
     └─ LLM 输出扩展 JSON（含 alert_params）
     └─ 存入 WatchAnalysis.analysis_detail

全天每分钟 WatchAlertStrategy.scan()
  ├─ 从 DB 读取当日 7d 分析结果（含 alert_params）→ 内存缓存
  ├─ 获取实时价格
  ├─ 每15分钟：获取趋势数据 → TDSequentialService.calculate()
  └─ 依次执行 7 个 checker → 产出 Signal[]
```

### 5. 改动范围

| 文件 | 改动 |
|------|------|
| `app/llm/prompts/watch_analysis.py` | 7d prompt 扩展，要求输出 `alert_params` |
| `app/services/watch_analysis_service.py` | 解析并存储 `alert_params` 到 analysis_detail |
| `app/services/watch_alert_service.py` | 重写：移除确认/冷却，改为 7 个 checker + fired 去重 |
| `app/strategies/watch_alert/__init__.py` | 扩展：加载 AI 参数、TD 定时计算 |

不需要新增文件，不改动前端、数据模型、通知推送链路。
