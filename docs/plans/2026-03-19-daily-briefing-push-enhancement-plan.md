# 每日推送增强：简报数据整合 + GLM 总结 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将简报页面全部数据纳入 Slack 每日推送，并通过 GLM-4 生成"今日核心观点"和"操作建议"包裹结构化数据

**Architecture:** 在 `NotificationService` 新增 6 个格式化方法复用 `BriefingService` 数据，新增 GLM prompt 文件，改造 `push_daily_report()` 流程为：收集数据 → GLM 总结 → 组装消息

**Tech Stack:** Flask, 智谱 GLM-4 (PREMIUM), BriefingService, DramPriceService

**Spec:** `docs/plans/2026-03-19-daily-briefing-push-enhancement-design.md`

---

## 文件变更地图

| 文件 | 操作 | 职责 |
|------|------|------|
| `app/llm/prompts/daily_briefing.py` | 新增 | GLM prompt 构建函数 |
| `app/llm/router.py` | 修改(第9-22行) | TASK_LAYER_MAP 新增 daily_briefing |
| `app/services/notification.py` | 修改 | 新增6个格式化方法 + 改造 push_daily_report() |

---

### Task 1: 新增 GLM Prompt 文件

**Files:**
- Create: `app/llm/prompts/daily_briefing.py`

- [ ] **Step 1: 创建 prompt 文件**

```python
"""每日简报 GLM 综合分析 Prompt"""

DAILY_BRIEFING_SYSTEM_PROMPT = (
    "你是专业的投资分析助手。根据以下市场数据和持仓信息，生成投资分析。"
    "用简洁中文回答，数据以JSON格式返回。"
)


def build_daily_briefing_prompt(all_data: dict) -> str:
    """构建每日简报综合分析 prompt

    Args:
        all_data: 包含以下 key 的字典，每个 value 为格式化后的文本字符串：
            - position_summary: 持仓概览
            - alert_signals: 预警信号
            - earnings_alerts: 财报提醒
            - pe_alerts: PE估值预警
            - watch_analysis: 盯盘分析(7d+30d)
            - indices: 指数行情
            - futures: 期货数据
            - etf_premium: ETF溢价
            - sectors: 板块涨跌
            - dram: DRAM价格
            - technical: 技术评分
    """
    sections = []
    label_map = {
        'position_summary': '持仓概览',
        'indices': '指数行情',
        'futures': '期货数据',
        'etf_premium': 'ETF溢价',
        'sectors': '板块涨跌',
        'dram': 'DRAM价格',
        'technical': '技术评分',
        'alert_signals': '预警信号',
        'earnings_alerts': '财报提醒',
        'pe_alerts': 'PE估值预警',
        'watch_analysis': '盯盘分析',
    }

    for key, label in label_map.items():
        text = all_data.get(key, '')
        if text:
            sections.append(f"【{label}】\n{text}")

    data_text = "\n\n".join(sections)

    return f"""以下是今日完整的市场数据和持仓信息：

{data_text}

请综合分析以上所有数据，返回JSON（不要markdown代码块包裹）：
{{
  "core_insights": "今日核心观点（200字以内，涵盖市场环境、持仓关注点、关键变化）",
  "action_suggestions": "操作建议（100字以内，具体的关注/操作方向）"
}}"""
```

- [ ] **Step 2: Commit**

```bash
git add app/llm/prompts/daily_briefing.py
git commit -m "feat: 新增每日简报 GLM 综合分析 prompt"
```

---

### Task 2: LLMRouter 路由注册

**Files:**
- Modify: `app/llm/router.py:9-22`

- [ ] **Step 1: 在 TASK_LAYER_MAP 中新增 daily_briefing**

在 `app/llm/router.py` 的 `TASK_LAYER_MAP` 字典中，在 `'watch_analysis'` 行后新增：

```python
'daily_briefing': LLMLayer.PREMIUM,
```

- [ ] **Step 2: Commit**

```bash
git add app/llm/router.py
git commit -m "feat: LLMRouter 新增 daily_briefing 路由到 PREMIUM"
```

---

### Task 3: NotificationService 新增 6 个格式化方法

**Files:**
- Modify: `app/services/notification.py`

在 `format_watch_analysis()` 方法之后、`push_daily_report()` 方法之前插入以下 6 个静态方法：

- [ ] **Step 1: 新增 format_indices_summary()**

```python
@staticmethod
def format_indices_summary() -> str:
    """格式化指数行情用于推送"""
    try:
        from app.services.briefing import BriefingService
        data = BriefingService.get_indices_data()
        regions = data.get('regions', [])
        indices = data.get('indices', {})
        if not regions:
            return ''

        lines = ['指数行情']
        for region in regions:
            key = region['key']
            region_indices = indices.get(key, [])
            if not region_indices:
                continue
            lines.append(f"\n  [{region['name']}]")
            for idx in region_indices:
                if idx.get('close') is None:
                    continue
                pct = idx.get('change_percent')
                pct_str = f"{pct:+.2f}%" if pct is not None else "—"
                lines.append(f"  {idx['name']}: {idx['close']:,.2f} ({pct_str})")

        return '\n'.join(lines) + '\n' if len(lines) > 1 else ''
    except Exception as e:
        logger.warning(f'[通知.指数] 格式化失败: {e}')
        return ''
```

- [ ] **Step 2: 新增 format_futures_summary()**

```python
@staticmethod
def format_futures_summary() -> str:
    """格式化期货数据用于推送"""
    try:
        from app.services.briefing import BriefingService
        data = BriefingService.get_futures_data()
        futures = data.get('futures', [])
        if not futures:
            return ''

        lines = ['期货数据']
        for f in futures:
            if f.get('close') is None:
                continue
            pct = f.get('change_percent')
            pct_str = f"{pct:+.2f}%" if pct is not None else "—"
            lines.append(f"  {f['name']}: {f['close']:,.2f} ({pct_str})")

        return '\n'.join(lines) + '\n' if len(lines) > 1 else ''
    except Exception as e:
        logger.warning(f'[通知.期货] 格式化失败: {e}')
        return ''
```

- [ ] **Step 3: 新增 format_etf_premium_summary()**

```python
@staticmethod
def format_etf_premium_summary() -> str:
    """格式化ETF溢价率用于推送"""
    try:
        from app.services.briefing import BriefingService
        data = BriefingService.get_etf_premium_data()
        etfs = data.get('etfs', [])
        if not etfs:
            return ''

        signal_map = {'buy': '适合买入', 'sell': '溢价过高', 'normal': '正常'}
        lines = ['ETF溢价']
        for etf in etfs:
            if etf.get('premium_rate') is None:
                continue
            signal = signal_map.get(etf.get('signal', ''), '')
            signal_str = f" {signal}" if signal else ''
            lines.append(f"  {etf['name']}({etf['code']}): 溢价 {etf['premium_rate']:+.2f}%{signal_str}")

        return '\n'.join(lines) + '\n' if len(lines) > 1 else ''
    except Exception as e:
        logger.warning(f'[通知.ETF溢价] 格式化失败: {e}')
        return ''
```

- [ ] **Step 4: 新增 format_sectors_summary()**

```python
@staticmethod
def format_sectors_summary() -> str:
    """格式化板块涨跌用于推送"""
    try:
        from app.services.briefing import BriefingService

        lines = ['板块涨跌']

        cn_sectors = BriefingService.get_cn_sectors_data()
        if cn_sectors:
            lines.append('\n  [A股行业Top5]')
            for s in cn_sectors:
                leader = f" 领涨: {s['leader']}" if s.get('leader') else ''
                lines.append(f"  {s['name']}: {s['change_percent']:+.2f}%{leader}")

        us_sectors = BriefingService.get_us_sectors_data()
        if us_sectors:
            lines.append('\n  [美股行业Top5]')
            for s in us_sectors:
                lines.append(f"  {s['name']}: {s['change_percent']:+.2f}%")

        return '\n'.join(lines) + '\n' if len(lines) > 1 else ''
    except Exception as e:
        logger.warning(f'[通知.板块] 格式化失败: {e}')
        return ''
```

- [ ] **Step 5: 新增 format_dram_summary()**

```python
@staticmethod
def format_dram_summary() -> str:
    """格式化DRAM价格用于推送"""
    try:
        from app.services.dram_price import DramPriceService
        data = DramPriceService.get_dram_data()
        today_data = data.get('today', [])
        if not today_data:
            return ''

        lines = ['DRAM价格']
        for item in today_data:
            if item.get('avg_price') is None:
                continue
            pct = item.get('change_pct')
            pct_str = f" ({pct:+.2f}%)" if pct is not None else ''
            lines.append(f"  {item['label']}: ${item['avg_price']:.2f}{pct_str}")

        return '\n'.join(lines) + '\n' if len(lines) > 1 else ''
    except Exception as e:
        logger.warning(f'[通知.DRAM] 格式化失败: {e}')
        return ''
```

- [ ] **Step 6: 新增 format_technical_summary()**

```python
@staticmethod
def format_technical_summary() -> str:
    """格式化技术评分用于推送"""
    try:
        from app.services.briefing import BriefingService, BRIEFING_STOCKS
        data = BriefingService.get_stocks_technical_data()
        if not data:
            return ''

        name_map = {s['code']: s['name'] for s in BRIEFING_STOCKS}
        lines = ['技术评分']
        for code, info in data.items():
            name = name_map.get(code, code)
            score = info.get('score', 0)
            signal_text = info.get('signal_text', '')
            macd = info.get('macd_signal', '')
            lines.append(f"  {name}({code}): {score}分 {signal_text} MACD:{macd}")

        return '\n'.join(lines) + '\n' if len(lines) > 1 else ''
    except Exception as e:
        logger.warning(f'[通知.技术评分] 格式化失败: {e}')
        return ''
```

- [ ] **Step 7: Commit**

```bash
git add app/services/notification.py
git commit -m "feat: NotificationService 新增6个简报数据格式化方法"
```

---

### Task 4: 改造 push_daily_report()

**Files:**
- Modify: `app/services/notification.py` — `push_daily_report()` 方法（当前第366-431行）

- [ ] **Step 1: 替换 push_daily_report() 方法**

将现有 `push_daily_report()` 方法替换为以下实现：

```python
@staticmethod
def push_daily_report(include_ai: bool = False) -> dict:
    """一键推送每日报告（持仓+简报数据+GLM总结+预警+盯盘分析）"""
    with NotificationService._daily_push_lock:
        today = date.today()

        if NotificationService.has_daily_push(today):
            logger.info('[通知] 今日已推送，跳过')
            return {'skipped': True}

        NotificationService._mark_daily_push(today)

    subject = f'每日股票分析报告 - {today}'

    codes, name_map = NotificationService._get_all_watched_codes()

    # 收集所有结构化数据
    briefing = NotificationService.format_briefing_summary()
    alerts = NotificationService.format_alert_signals(codes, name_map)
    earnings = NotificationService.format_earnings_alerts(codes, name_map)
    pe = NotificationService.format_pe_alerts(codes, name_map)

    indices_text = NotificationService.format_indices_summary()
    futures_text = NotificationService.format_futures_summary()
    etf_text = NotificationService.format_etf_premium_summary()
    sectors_text = NotificationService.format_sectors_summary()
    dram_text = NotificationService.format_dram_summary()
    technical_text = NotificationService.format_technical_summary()

    ai_text = ''
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
                    ai_text = ai_report.get('text', '')
        except Exception as e:
            logger.warning(f'[通知.AI报告] 生成失败: {e}')

    # 盯盘分析（7d + 30d）
    watch_text = ''
    try:
        from app.services.watch_analysis_service import WatchAnalysisService
        WatchAnalysisService.analyze_stocks('7d')
        WatchAnalysisService.analyze_stocks('30d')
        from app.services.watch_service import WatchService
        watch_analyses = WatchService.get_all_today_analyses()
        watch_report = NotificationService.format_watch_analysis(watch_analyses)
        watch_text = watch_report.get('text', '')
    except Exception as e:
        logger.warning(f'[通知.盯盘分析] 生成失败: {e}')

    # GLM 综合分析
    core_insights = ''
    action_suggestions = ''
    try:
        from app.llm.router import llm_router
        from app.llm.prompts.daily_briefing import (
            DAILY_BRIEFING_SYSTEM_PROMPT, build_daily_briefing_prompt,
        )
        import json as _json

        provider = llm_router.route('daily_briefing')
        if provider:
            all_data = {
                'position_summary': briefing.get('text', ''),
                'indices': indices_text,
                'futures': futures_text,
                'etf_premium': etf_text,
                'sectors': sectors_text,
                'dram': dram_text,
                'technical': technical_text,
                'alert_signals': alerts.get('text', ''),
                'earnings_alerts': earnings.get('text', ''),
                'pe_alerts': pe.get('text', ''),
                'watch_analysis': watch_text,
            }
            prompt = build_daily_briefing_prompt(all_data)
            response = provider.chat(
                [
                    {'role': 'system', 'content': DAILY_BRIEFING_SYSTEM_PROMPT},
                    {'role': 'user', 'content': prompt},
                ],
                temperature=0.3,
                max_tokens=1000,
            )
            cleaned = response.strip()
            if cleaned.startswith('```'):
                cleaned = cleaned.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
            parsed = _json.loads(cleaned)
            core_insights = parsed.get('core_insights', '')
            action_suggestions = parsed.get('action_suggestions', '')
    except Exception as e:
        logger.warning(f'[通知.GLM总结] 生成失败: {e}')

    # 组装最终消息
    text_parts = []

    if core_insights:
        text_parts.append(f"🎯 今日核心观点\n{core_insights}")

    text_parts.append(briefing['text'])

    if indices_text:
        text_parts.append(indices_text)
    if futures_text:
        text_parts.append(futures_text)
    if etf_text:
        text_parts.append(etf_text)
    if sectors_text:
        text_parts.append(sectors_text)
    if dram_text:
        text_parts.append(dram_text)
    if technical_text:
        text_parts.append(technical_text)
    if alerts.get('text'):
        text_parts.append(alerts['text'])
    if earnings.get('text'):
        text_parts.append(earnings['text'])
    if pe.get('text'):
        text_parts.append(pe['text'])
    if ai_text:
        text_parts.append(ai_text)
    if watch_text:
        text_parts.append(watch_text)

    if action_suggestions:
        text_parts.append(f"💡 操作建议\n{action_suggestions}")

    full_text = '\n---\n'.join(text_parts)

    results = NotificationService.send_all(subject, full_text)
    results['content_preview'] = full_text[:500]
    return results
```

- [ ] **Step 2: Commit**

```bash
git add app/services/notification.py
git commit -m "feat: push_daily_report 整合简报数据 + GLM综合分析"
```

---

### Task 5: 验证

- [ ] **Step 1: 启动应用检查无导入错误**

```bash
cd D:/Git/stock && python -c "from app.services.notification import NotificationService; print('OK')"
```

Expected: `OK`

- [ ] **Step 2: 验证 prompt 构建**

```bash
python -c "
from app.llm.prompts.daily_briefing import build_daily_briefing_prompt
result = build_daily_briefing_prompt({'position_summary': '测试持仓', 'indices': '纳指100: 18500 (+1.2%)'})
print(result[:200])
print('OK')
"
```

Expected: 包含"今日完整的市场数据"文本，结尾 OK

- [ ] **Step 3: 验证路由注册**

```bash
python -c "
from app.llm.router import TASK_LAYER_MAP
from app.llm.base import LLMLayer
assert TASK_LAYER_MAP.get('daily_briefing') == LLMLayer.PREMIUM
print('OK')
"
```

Expected: `OK`
