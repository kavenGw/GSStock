# 每日推送增强设计：简报数据整合 + GLM 总结

## 概述

将每日简报页面的全部数据纳入 Slack 推送，并通过 GLM-4 生成"今日核心观点"和"操作建议"，夹在结构化数据前后，形成完整的每日投资报告。

## 当前状态

每日 8:30am 推送包含 7 部分：持仓概览、预警信号、财报提醒、PE估值、AI分析摘要（可选）、盯盘7d分析、盯盘30d分析。

简报页面额外展示：指数行情、期货数据、ETF溢价率、板块涨跌、DRAM价格、技术评分 — 这些未包含在推送中。

## 设计方案

### 1. 数据收集层

在 `NotificationService` 中新增 6 个格式化方法，复用 `BriefingService` 获取数据，转为纯文本：

| 方法 | 数据源 | 输出格式 |
|------|-------|---------|
| `format_indices_summary()` | `BriefingService.get_indices_data()` | 按区域分组（A股/海外），每个指数一行：名称 价格 (涨跌%)。数据结构为 `{'regions': [...], 'indices': {region_key: [...]}}` 嵌套，需按 region 遍历 |
| `format_futures_summary()` | `BriefingService.get_futures_data()` | 每个期货一行：名称 价格 (涨跌%) |
| `format_etf_premium_summary()` | `BriefingService.get_etf_premium_data()` | ETF名称 溢价率 |
| `format_sectors_summary()` | `BriefingService.get_cn_sectors_data()` + `BriefingService.get_us_sectors_data()` | 分别调用两个方法，A股Top5 + 美股Top5 板块涨跌（内部已做 Top5 切片，无需再次截断） |
| `format_dram_summary()` | `DramPriceService.get_dram_data()` | 仅消费返回值的 `today` 字段，各型号价格及涨跌。`change_pct` 为 None 时显示 "—" |
| `format_technical_summary()` | `BriefingService.get_stocks_technical_data()` | 股票 评分 MACD信号 |

每个方法数据获取失败时返回空字符串，不阻塞推送。

### 2. GLM Prompt 设计

新增 `app/llm/prompts/daily_briefing.py`：

- System Prompt：专业投资分析助手角色
- User Prompt：拼接全部结构化文本数据，要求返回 JSON：
  ```json
  {
    "core_insights": "今日核心观点（200字以内）",
    "action_suggestions": "操作建议（100字以内）"
  }
  ```
- 调用层级：PREMIUM（GLM-4），通过 `LLMRouter` 路由（路由器自带预算降级机制）
- 容错：GLM 调用失败或超时时跳过两段总结，仅推送结构化数据（超时由 `LLM_REQUEST_TIMEOUT` 控制，默认 300 秒）

### 3. 消息组装

改造 `push_daily_report()` 流程：

```
1. 收集全部结构化数据（任一失败不阻塞）
   ├─ 原有：持仓概览 / 预警信号 / 财报 / PE / 盯盘分析
   └─ 新增：指数 / 期货 / ETF溢价 / 板块 / DRAM / 技术评分

2. 全部文本打包 → build_daily_briefing_prompt() → GLM PREMIUM
   └─ 失败/超时时 core_insights = "", action_suggestions = ""

3. 组装最终消息：
   ├─ 🎯 今日核心观点（GLM）
   ├─ ---
   ├─ 📊 持仓概览
   ├─ 📈 指数行情
   ├─ 📉 期货数据
   ├─ 💰 ETF溢价
   ├─ 🏭 板块涨跌
   ├─ 💾 DRAM价格
   ├─ 🔧 技术评分
   ├─ ⚠️ 预警信号
   ├─ 📅 财报提醒
   ├─ 📊 PE估值
   ├─ 🤖 盯盘分析(7d/30d)
   ├─ ---
   └─ 💡 操作建议（GLM）

4. send_slack(full_text)
```

空数据块整段跳过，GLM 总结与结构化数据用 `---` 分隔。

### 4. LLMRouter 路由

路由映射新增 `'daily_briefing': LLMLayer.PREMIUM`。

## 文件变更清单

| 文件 | 变更类型 | 内容 |
|------|---------|------|
| `app/llm/prompts/daily_briefing.py` | 新增 | `build_daily_briefing_prompt(all_data: dict)` |
| `app/llm/router.py` | 修改 | `TASK_LAYER_MAP` 新增 `'daily_briefing': LLMLayer.PREMIUM` |
| `app/services/notification.py` | 修改 | 新增6个 `format_*_summary()` 方法 + 改造 `push_daily_report()` 流程 |

不涉及变更：BriefingService、前端、模板、策略调度。
