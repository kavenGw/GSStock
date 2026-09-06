---
paths:
  - "app/services/notification.py"
  - "app/services/watch_alert_service.py"
  - "app/services/esports*"
  - "app/strategies/**"
---
# Slack 推送、告警格式与推送语义

> **何时读**：改 notification.py、新增推送策略、改告警格式/排版、调频道路由、改 `_fetch_*` 失败语义或新闻去重

## 频道路由（`SLACK_BOT_TOKEN`，常量在 `app/config/notification_config.py`）

| 频道 | 内容 |
|------|------|
| `news` | 每日简报、预警、公司新闻、兴趣新闻 |
| `news_watch` | 盯盘实时分析、简报盯盘部分 |
| `news_daily` | 每日核心观点 |
| `news_operation` | 清仓策略、操作计划 |
| `news_research` | 投行观点 / 野村研报 |
| `news_ai_tool` | GitHub Release / Trending / 博客 |
| `news_nba` / `news_lol` / `news_worldcup` | 赛事 |

## 盯盘告警格式

title 一行核心信息，detail 补上下文。支撑/阻力用描述性标签（跌破/突破/测试/触及），其余用 `>` `<`：

| 类型 | 示例 |
|------|------|
| 盘中极值 / 目标价 | `当前 26.00 > 前高 25.50` / `当前 26.00 > 目标 25.50` |
| 支撑阻力 | `跌破支撑 25.00 \| 当前 24.95` + detail `下方支撑 24.00(-3.8%)` |
| 均线穿越 | `上穿 当前 21.00 > MA5 20.50` |
| 成交量异动 | `成交量 100 > 日均 50 (2.0x)` |
| TD九转 | `TD九转买入信号 \| 当前 26.00` |

- 检测器在 `watch_alert_service.py`（8 种：极值/目标价/支撑阻力/均线/成交量/TD九转/动量）；`notification.py` 的 `dispatch_signal()` 按 direction 路由 emoji（🔴=up/buy/resistance_break，🟢=down/sell/support_break）。
- **合并推送**：`watch_alert` 经 `WatchSignalPipeline` 按股合并 → `push_watch_alerts()` 一股一条。首行 `emoji *名称(代码)* 股价 涨幅 [优先级]`，主信号行 + 次信号 `  · ` + 上下文行（量比/区间位置）。A 类（支撑阻力/TD/动量）信号行尾 ` | 当前 X` 由 `_strip_current` 剥离，B 类（极值/目标价/均线）保留作比较主语。HIGH/MID 推送，LOW 只 debug log。
- 取价 `cache_only=True` + `price_freshness` 闸门（见 watch.md），无新鲜价整块不推，不降级推旧价。

## Slack 排版规范（所有 `format_*`，mrkdwn）

- 标题 `emoji + *粗体*`；多条目列表用 `'─' * 30` 分隔、条目名粗体、正文前空行、链接放末行；紧凑列表用 `  · ` 前缀、同类数据 ` | ` 一行。
- 大数千分位 `{:,}`，百分比带正负号。
- **涨跌着色**统一走 `NotificationService.fmt_pct(pct, digits=2, code=False, none='—')`：全局红涨绿跌不分市场（🔴/🟢/⚪平/`—` 无数据），色块紧贴百分比；Block Kit 传 `code=True`。**不着色**：ETF 溢价、ADR 溢价折价、距支撑/阻力距离、成交量倍数。一条目只出现一个色块。`📈` 仅作节标题；`📉` `▲` `▼` 已废弃。
- 避免同一信息重复出现、同一 emoji 表达不同含义。

## 失败语义与去重

- **`_fetch_*` 返回 None = 异常/重试耗尽，空 dict = API 成功但无数据**，上层据此区分「获取失败」vs「今日无内容」。异常分支必须 `logger.warning(..., exc_info=True)` 并含 `type(e).__name__` + 关键上下文（league_id / HTTP status / 响应片段）。
- **新闻多分支去重**：`InterestPipeline.process_new_items` 的 AI 公司识别与兴趣关键词两条 Slack 分支可同时命中同一 NewsItem，按 `NewsItem.id` 集合去重；新增推送路径并入该去重链。
