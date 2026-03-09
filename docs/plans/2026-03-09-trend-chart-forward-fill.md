# 走势看板 Forward-Fill 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复走势看板中不同市场股票因休市日不同导致的数据线断裂问题

**Architecture:** 在 `FuturesService` 聚合层新增 `_forward_fill_missing_dates()` 方法，对所有股票的数据按日期并集做 forward-fill，确保每只股票在完整日期轴上都有数据点

**Tech Stack:** Python, Flask

---

### Task 1: 实现 `_forward_fill_missing_dates` 方法

**Files:**
- Modify: `app/services/futures.py`

**Step 1: 在 `FuturesService` 类中添加静态方法**

在 `_save_index_to_cache` 方法之后、`_fetch_from_api` 方法之前，添加：

```python
@staticmethod
def _forward_fill_missing_dates(results: list[dict]) -> list[dict]:
    """对多股票数据做 forward-fill，填充因市场休市导致的缺失日期

    算法：
    1. 收集所有股票的日期并集
    2. 逐股票遍历，缺失日期用最近交易日数据填充
       - price: 复制上一交易日的 price
       - change_pct: 保持上一交易日的累计涨跌幅
       - volume: 设为 0（休市日无成交）
    3. 股票在日期轴最前面缺数据时不填充
    """
    if len(results) <= 1:
        return results

    # 收集所有日期并集
    all_dates = set()
    for stock in results:
        for dp in stock.get('data', []):
            all_dates.add(dp['date'])

    if not all_dates:
        return results

    sorted_dates = sorted(all_dates)

    for stock in results:
        data = stock.get('data', [])
        if not data:
            continue

        # 构建日期→数据映射
        date_map = {dp['date']: dp for dp in data}

        # 该股票最早有数据的日期
        first_date = data[0]['date']

        filled_data = []
        last_known = None

        for d in sorted_dates:
            if d in date_map:
                last_known = date_map[d]
                filled_data.append(last_known)
            elif last_known is not None and d >= first_date:
                # forward-fill: 用上一个已知数据填充
                filled_data.append({
                    'date': d,
                    'price': last_known['price'],
                    'change_pct': last_known['change_pct'],
                    'volume': 0
                })

        stock['data'] = filled_data

    return results
```

---

### Task 2: 在 `get_trend_data()` 返回前调用 forward-fill

**Files:**
- Modify: `app/services/futures.py:416`

**Step 1: 在构建返回值前调用**

在 `get_trend_data()` 方法中，`# 获取日期范围` 注释之前（约 line 404），插入：

```python
results = FuturesService._forward_fill_missing_dates(results)
```

---

### Task 3: 在 `get_custom_trend_data()` 返回前调用 forward-fill

**Files:**
- Modify: `app/services/futures.py:605`

**Step 1: 在构建返回值前调用**

在 `get_custom_trend_data()` 方法中，`sorted_dates = sorted(all_dates)` 之前（约 line 605），插入：

```python
results = FuturesService._forward_fill_missing_dates(results)

# 重新计算日期集合（forward-fill 后日期可能增加）
all_dates = set()
for r in results:
    for dp in r['data']:
        all_dates.add(dp['date'])
```

并删除原来的 `sorted_dates = sorted(all_dates)` 之前已有的 `all_dates` 相关代码（因为 forward-fill 后需要重新收集）。

---

### Task 4: 手动验证

**Step 1: 启动应用并验证**

```bash
python run.py
```

打开走势看板，选择包含不同市场股票的分类（如"存储"），确认：
- 所有股票线条连续，无断裂
- 休市日股价保持水平（与上一交易日一致）
- Volume 柱状图在休市日显示为 0
- Tooltip 在休市日正确显示数据

**Step 2: Commit**

```bash
git add app/services/futures.py
git commit -m "fix: 走势看板 forward-fill — 修复不同市场休市日导致的数据线断裂"
```
