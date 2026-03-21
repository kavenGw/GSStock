# 价值洼地分析页面设计

## 概述

新增独立的"价值洼地"页面，对比半导体产业链 5 个板块的涨幅表现，找出涨幅最少的板块作为"价值洼地"。同时在每日推送中加入洼地提醒。

## 板块配置

硬编码在 `app/config/stock_codes.py`，新增 `VALUE_DIP_SECTORS` 字典：

| 板块 key | 名称 | 股票 |
|---------|------|------|
| `korea_storage` | 韩国存储 | 005930.KS 三星电子, 000660.KS SK海力士 |
| `a_storage_controller` | A股存储主控 | 300671 德明利, 603005 江波龙, 688525 佰维存储 |
| `a_storage` | A股存储 | 300223 北京君正, 603986 兆易创新 |
| `a_pcb` | A股PCB | 002463 沪电股份, 300476 胜宏科技 |
| `a_ccl` | A股CCL | 600183 生益科技, 688519 南亚新材 |

## 核心逻辑

### 涨幅计算

- 调用 `UnifiedStockDataService.get_trend_data(codes, days=90)` 获取 90 天走势
- 从 90 天数据中截取 7d/30d 子集计算各周期涨幅
- 单只股票涨幅 = (最新收盘价 - N天前收盘价) / N天前收盘价 × 100
- 板块涨幅 = 板块内各股票涨幅的等权平均

### 洼地判断

- 计算所有板块在某周期的平均涨幅 `avg`
- 若某板块涨幅 `< avg - |avg| × 0.5`，标记为洼地
  - 正涨幅例：avg=10%，阈值=10%-5%=5%，低于 5% 的为洼地
  - 负涨幅例：avg=-10%，阈值=-10%-5%=-15%，低于 -15% 的为洼地
- 三个周期（7d/30d/90d）独立判断

## 服务层

新建 `app/services/value_dip.py`：

```python
class ValueDipService:
    def get_sector_performance() -> dict:
        """获取所有板块的 7d/30d/90d 涨幅及个股明细"""
        # 1. 收集所有股票代码
        # 2. 批量调用 UnifiedStockDataService.get_trend_data(codes, 90)
        # 3. 按板块分组，计算各周期涨幅
        # 4. 等权平均算板块涨幅
        # 5. 判断洼地标记

    def detect_value_dips() -> list:
        """检测当前洼地板块，用于推送"""
        # 调用 get_sector_performance()
        # 筛选 is_dip=True 的板块及对应周期
```

## 路由与API

新建 `app/routes/value_dip.py`，Blueprint 前缀 `/value-dip`：

- `GET /value-dip` — 渲染页面模板
- `GET /value-dip/api/sectors` — 返回所有板块涨幅数据

返回格式：
```json
{
  "sectors": [
    {
      "key": "korea_storage",
      "name": "韩国存储",
      "change_7d": 3.2,
      "change_30d": 8.5,
      "change_90d": 15.1,
      "is_dip_7d": false,
      "is_dip_30d": false,
      "is_dip_90d": false,
      "stocks": [
        {
          "code": "005930.KS",
          "name": "三星电子",
          "price": 65000,
          "change_7d": 2.1,
          "change_30d": 7.8,
          "change_90d": 14.2,
          "trend_data": [{"date": "2024-01-01", "close": 62000}, ...]
        }
      ]
    }
  ],
  "averages": {"avg_7d": 5.1, "avg_30d": 10.2, "avg_90d": 18.3},
  "dip_threshold": 0.5
}
```

走势数据已包含在 sectors 响应的 `trend_data` 字段中，无需单独的走势端点。

## 前端界面

独立页面，导航栏新增"价值洼地"入口。

### 布局：卡片 + 展开走势

**板块卡片区域（顶部横排）**：
- 5 个板块横排卡片
- 每个卡片显示：板块名、默认 30d 涨幅（大字）、7d/90d 涨幅（小字）
- 洼地板块：红色边框 + ⚠ 标记
- 支持切换周期（7d/30d/90d），切换后排序和洼地判断跟着变

**展开走势区域（卡片下方）**：
- 点击板块卡片 → 下方展开该板块所有股票的 90 天走势图
- 每只股票一个 ECharts 小图，横排排列（2-3 只一行）
- 走势图样式复用走势看板（分时线 + 成交量）
- 再次点击同一卡片收起，点击另一卡片切换

### 技术选型
- ECharts 走势图
- Bootstrap 5 布局
- 原生 JS，与项目风格一致

## 每日推送集成

### 推送调用链

在 `DailyBriefingStrategy.scan()` 中，`push_daily_report()` 完成后，单独调用洼地检测并推送：

```python
# DailyBriefingStrategy.scan() 末尾追加
dips = ValueDipService.detect_value_dips()
if dips:
    message = format_value_dip_message(dips)  # 策略层格式化
    NotificationService.send_slack(message, 'news')  # 独立消息推送
```

`ValueDipService` 只负责数据计算，不涉及推送。消息格式化在策略层完成，作为独立 Slack 消息发送（不嵌入每日简报正文）。

### 触发条件

对 7d/30d/90d 三个周期分别检查，任一周期出现洼地板块就推送。

### 推送格式

```
⚠ 价值洼地提醒

30d维度：A股PCB（+2.1%）显著落后板块均值（+10.2%）
  · 沪电股份 +1.8%  · 胜宏科技 +2.4%

7d维度：A股存储（+0.5%）显著落后板块均值（+3.1%）
  · 北京君正 +0.3%  · 兆易创新 +0.7%
```

### 推送频道

`news` 频道（与每日简报同频道）。

### 冷却机制

同一板块同一周期 24 小时内不重复推送。由于仅在每日简报时段（8:30am）触发，天然满足冷却要求，无需额外冷却逻辑。

## 文件清单

| 文件 | 类型 | 说明 |
|------|------|------|
| `app/config/stock_codes.py` | 修改 | 新增 VALUE_DIP_SECTORS |
| `app/services/value_dip.py` | 新建 | 板块涨幅计算 + 洼地检测 |
| `app/routes/value_dip.py` | 新建 | 路由 + API |
| `app/templates/value_dip.html` | 新建 | 页面模板 |
| `app/static/js/value_dip.js` | 新建 | 前端交互 + ECharts |
| `app/strategies/daily_briefing/__init__.py` | 修改 | 添加洼地检测 + 格式化 + 推送 |
| `app/__init__.py` | 修改 | 注册 Blueprint |
| `app/templates/base.html` 或导航模板 | 修改 | 导航栏新增入口 |
