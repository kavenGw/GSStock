# 公司新闻表格格式化 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将资金流向日报和机构调研名单的纯文本表格数据格式化为 Slack 可读的等宽对齐表格

**Architecture:** 在 `company_news_service.py` 新增模块级格式化函数，推送前检测内容类型并格式化，不匹配则原样返回

**Tech Stack:** Python re（正则），Slack mrkdwn 代码块

**Spec:** `docs/plans/2026-03-19-company-news-table-format-design.md`

---

### Task 1: 新增格式化函数

**Files:**
- Modify: `app/services/company_news_service.py`

- [ ] **Step 1: 在文件顶部（class 定义之前）添加三个模块级函数**

```python
def _format_capital_flow(content: str) -> str:
    """资金流向日报格式化"""
    # 提取标题：取"主力资金"之前的部分
    title_match = re.match(r'(.+?资金流向[^：]*日报)[：:](.*?)(\d{6})', content)
    if not title_match:
        return content
    title = title_match.group(1)
    subtitle = title_match.group(2).strip()

    # 提取每行数据：代码 + 名称 + 涨跌% + 换手% + 净流入
    rows = re.findall(r'(\d{6})\s+(\S+)\s+(-?\d+\.?\d*)\s+(-?\d+\.?\d*)\s+(-?\d+\.?\d*)', content)
    if not rows:
        return content

    lines = [title]
    if subtitle:
        lines.append(subtitle)
    lines.append('')

    # 计算列宽
    name_width = max(len(r[1]) for r in rows)
    name_width = max(name_width, 2)  # 最小宽度

    header = f"{'代码':<8}{'名称':<{name_width + 2}}{'涨跌%':>8}{'换手%':>8}{'主力净流入':>12}"
    lines.append(header)

    for code, name, chg, turnover, net_flow in rows:
        net_val = int(float(net_flow))
        net_str = f"{net_val:,}"
        line = f"{code:<8}{name:<{name_width + 2}}{chg:>8}{turnover:>8}{net_str:>12}"
        lines.append(line)

    return '\n'.join(lines)


def _format_institution_research(content: str) -> str:
    """机构调研名单格式化"""
    # 提取标题：取第一个6位数字之前的描述文本，去掉表头字段名
    title_match = re.match(r'(.+?调研[^：]*名单)[：:]', content)
    title = title_match.group(1) if title_match else '机构调研名单'

    # 去掉表头字段名后匹配数据
    rows = re.findall(r'(\d{6})\s+(\S+)\s+(\d+)\s+(\d+\.?\d*)\s+(-?\d+\.?\d*)\s+(\S+)', content)
    if not rows:
        return content

    lines = [title, '']

    name_width = max(len(r[1]) for r in rows)
    name_width = max(name_width, 2)
    industry_width = max(len(r[5]) for r in rows)
    industry_width = max(industry_width, 2)

    header = f"{'代码':<8}{'名称':<{name_width + 2}}{'机构数':>6}{'收盘价':>8}{'涨跌%':>8}  {'行业'}"
    lines.append(header)

    for code, name, count, price, chg, industry in rows:
        line = f"{code:<8}{name:<{name_width + 2}}{count:>6}{price:>8}{chg:>8}  {industry}"
        lines.append(line)

    return '\n'.join(lines)


def _format_table_content(content: str) -> str:
    """检测并格式化表格类新闻内容，不匹配则原样返回"""
    if '资金流向' in content:
        return _format_capital_flow(content)
    if '调研' in content:
        return _format_institution_research(content)
    return content
```

- [ ] **Step 2: 修改 `_notify_company_slack` 调用格式化函数**

将第 271-272 行：
```python
            for company, content in items:
                NotificationService.send_slack(f"🏢 [{company}] {content}")
```

改为：
```python
            for company, content in items:
                formatted = _format_table_content(content)
                # 表格内容用代码块包裹确保等宽对齐
                if formatted != content:
                    msg = f"🏢 [{company}] {formatted.split(chr(10), 1)[0]}\n```\n{chr(10).join(formatted.split(chr(10))[1:])}\n```"
                else:
                    msg = f"🏢 [{company}] {content}"
                NotificationService.send_slack(msg)
```

- [ ] **Step 3: 验证**

手动构造测试数据在 Python REPL 中验证格式化输出：
```bash
python -c "
from app.services.company_news_service import _format_table_content
test1 = '电子行业3月19日资金流向日报：主力资金流量（万元）300476 胜宏科技 -4.27 3.81 -140622.36 002463 沪电股份 -5.13 5.63 -116310.93'
print(_format_table_content(test1))
print('---')
test2 = '近日海外机构调研股名单：近10日海外机构调研股 证券代码 证券简称 海外机构家数 最新收盘价（元） 其间涨跌幅（%） 行业 301265 华新环保 1 21.61 30.97 环保 002382 蓝帆医疗 9 7.89 21.38 医药生物'
print(_format_table_content(test2))
"
```

- [ ] **Step 4: Commit**

```bash
git add app/services/company_news_service.py
git commit -m "feat: 公司新闻推送表格内容格式化（资金流向、机构调研）"
```
