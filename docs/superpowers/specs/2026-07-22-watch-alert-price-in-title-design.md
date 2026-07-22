# watch_alert 标题行前置股价（名(代码) → 股价 → 涨幅）

## 背景与问题

`news_watch` 频道的盯盘合并告警（`NotificationService.push_watch_alerts`，一股一条）标题行现为 `emoji + 涨幅 + 名(代码) + [优先级]`（涨幅前置见 `2026-07-21-watch-alert-change-pct-in-title-design.md`），股价仍埋在第二行 `当前 X` 里：

```
🔴 +5.56% SK海力士(000660.KS)  [MID]
突破阻力 1936000.0 | 当前 1938000.00
量比 0.7x | 距下方支撑 1839000.0(-5.1%)
```

扫一眼只得"色 + 幅度"，要读到具体股价还得往下看第二行。

## 目标

标题行改为 **`emoji *名(代码)* 股价 涨幅 [优先级]`**，一眼读到"名称 + 现价 + 涨幅"；股价从第二行提到标题并去重（遵循 `notifications.md`「同一信息避免重复出现」）。

## 最终格式

```
🔴 *SK海力士(000660.KS)* 1,938,000 +5.56%  [MID]
突破阻力 1936000.0
量比 0.7x | 距下方支撑 1839000.0(-5.1%)
```

emoji 保留最前作颜色标记（🔴涨/🟢跌/⚪平/⚠️缺失，四态判定不变），其后按用户要求的顺序 名(代码) → 股价 → 涨幅。

## 去重的关键取舍：只删 A 类尾部 `| 当前 X`

`当前 X` 由 `watch_alert_service.py` 的检测器拼进 title，但**不同告警类型里"当前"语法角色不同**，不能无脑删：

**A 类 —— `当前` 是尾部独立段（`… | 当前 X`），删掉干净：**

| 检测器 | title 格式（`watch_alert_service.py`） |
|--------|--------|
| 支撑阻力（跌破/突破/测试） | `{label} {level} \| 当前 {curr:.2f}`（L192/L210） |
| TD九转 | `TD九转{label}信号 \| 当前 {curr:.2f}`（L385） |
| 急拉急跌动量 | `{label} {change_pct:+.1f}% \| 当前 {curr:.2f}`（L365） |

**B 类 —— `当前` 是比较句主语（load-bearing，删了拆坏句子），保留：**

| 检测器 | title 格式 |
|--------|--------|
| 盘中极值 | `当前 {curr:.2f} > 前高 {level:.2f}` / `< 前低`（L127/L139） |
| 目标价 | `当前 {curr:.2f} > 目标 {price}` / `< 目标`（L160/L166） |
| 均线穿越 | `{label} 当前 {curr:.2f} {cmp} {MA} {ma_val:.2f}`（L273） |

**决策**：去重只删 A 类的尾部 ` | 当前 X` 段（正则 `r' \| 当前 [\d.]+$'`）。B 类无 ` | 当前` 尾段，天然不受影响，其中 `当前 X` 作为比较主语保留——代价是 B 类告警标题现价与信号行 `当前 X` 各出现一次，但语义不同（标题=现价本身，信号行=现价 vs 参照的比较），可接受。

## 改动点

### 1. `app/services/watch_signal_pipeline.py`

**`ConsolidatedAlert` 加字段**（与现有 `change_percent` 对称）：

```python
current_price: Optional[float] = None
```

**`process()` 填充**（现 L109 `change_percent=...` 旁）：

```python
current_price=prices.get(code, {}).get('current_price'),
```

**新增 helper 剥离 A 类尾部 `| 当前 X`**，对 `primary_line` 与每条 `secondary_lines` 应用（在现有 `_strip_prefix` 之后）：

```python
@staticmethod
def _strip_current(line: str) -> str:
    return re.sub(r' \| 当前 [\d.]+$', '', line)
```

- `primary_line = _strip_current(_strip_prefix(primary.title, name, code))`
- 每条 secondary 同样先 `_strip_prefix` 再 `_strip_current`。

### 2. `app/services/notification.py:push_watch_alerts`

标题行拼装（现 L112-L113）。emoji 四态判定不动。新增股价与涨幅独立可选拼接：

```python
def _fmt_price(p):
    return f'{p:,.2f}'.rstrip('0').rstrip('.')

parts = [emoji, f'*{a.name}({a.code})*']
if a.current_price is not None:
    parts.append(_fmt_price(a.current_price))
if chg is not None:
    parts.append(f'{chg:+.2f}%')
parts.append(f'[{a.priority}]')
lines = [' '.join(parts), a.primary_line]
```

- 价格格式 `f'{p:,.2f}'.rstrip('0').rstrip('.')`：千分位 + 去无意义尾零，不丢有效精度。示例：`1938000.00→1,938,000`、`26.00→26`、`150.25→150.25`、`30.05→30.05`。
- 缺失兜底：价格、涨幅各自独立。二者皆缺 → `⚠️ *名(代码)* [MID]`；仅价格在 → `⚠️ *名(代码)* 1,938,000 [MID]`；仅涨幅在（罕见）→ `🔴 *名(代码)* +5.56% [MID]`。

### 3. `tests/test_watch_signal_pipeline.py`

- 更新现有 `test_push_skips_low_and_formats_high`：断言标题行为 `*名(代码)* {价} {±X.XX%}` 顺序，含千分位；A 类 context/primary 不再含 ` | 当前 X`。
- 价格格式用例：`1938000.00→1,938,000`、`26.00→26`、`150.25→150.25`。
- 去重用例：A 类（支撑阻力）primary/secondary 去掉 ` | 当前 X`；B 类（盘中极值 `当前 X > 前高`、目标价、均线穿越）`当前 X` **保留**。
- 缺失用例：`current_price=None` → 标题不拼价格；`change_percent=None` → emoji=⚠️ 且不拼涨幅。

### 4. `.claude/rules/notifications.md`

更新「合并推送（信号管线）」段（现 L53）的标题格式描述与示例，改为 `emoji *名(代码)* 股价 涨幅 [优先级]`，并注明去重只删 A 类尾部 `| 当前 X`。

## 明确不改的范围

- emoji 四态上色（🔴/🟢/⚪/⚠️）、优先级过滤（LOW 静默）、次信号 `· ` bullet、第三行量比 / 区间位置格式。
- B 类检测器 title 中的 `当前 X`（比较主语，保留）。
- `NotificationService.push_realtime_analysis`（AI 买卖建议语义，非价格颜色）。
- `ConsolidatedAlert` 其余字段（`change_percent`/`direction` 均保留）。

## 验收标准

1. 有价有涨幅的告警标题行为 `{emoji} *名(代码)* {千分位股价} {±X.XX%}  [优先级]`，emoji 涨🔴/跌🟢/平⚪。
2. 股价千分位、去无意义尾零：`1938000.00→1,938,000`、`26.00→26`、`150.25→150.25`。
3. A 类告警（支撑阻力/TD九转/动量）primary/secondary 不再出现 ` | 当前 X`；B 类（盘中极值/目标价/均线）`当前 X` 保留。
4. `current_price` 缺失时标题不拼价格；`change_percent` 缺失时 emoji=⚠️ 且标题不含涨幅数字；二者皆缺 → `⚠️ *名(代码)* [优先级]`。
5. `tests/test_watch_signal_pipeline.py` 全绿，含格式 / 去重 / 缺失各态用例。
