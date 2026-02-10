# 股票分析系统增强设计

> 参考项目：[daily_stock_analysis](https://github.com/ZhuLinsen/daily_stock_analysis)
> 日期：2026-02-09

## 一、技术指标增强

### 目标
在现有威科夫分析体系上增加经典技术指标，融入现有页面展示。

### 新增服务：`app/services/technical_indicators.py`

```python
class TechnicalIndicatorService:
    """技术指标计算服务，基于OHLCV数据计算"""

    def calculate_all(self, ohlcv_data) -> dict:
        """一次性计算所有指标，返回综合结果"""

    def calculate_macd(self, closes) -> dict:
        """MACD(12,26,9)
        返回: DIF, DEA, 柱状值, 信号(金叉/死叉/零轴上金叉)"""

    def calculate_rsi(self, closes) -> dict:
        """RSI(6,12,24)
        返回: 各周期值, 状态(超买>70/超卖<30/中性)"""

    def calculate_bias(self, closes) -> dict:
        """乖离率(MA5/MA20)
        返回: 各周期乖离率, 是否追高警告(>5%)"""

    def calculate_score(self, indicators) -> dict:
        """综合评分(100分制)
        权重: 趋势30% + 乖离20% + MACD15% + 量能15% + RSI10% + 支撑10%"""
```

### 数据来源
复用 `UnifiedStockDataService.get_trend_data()` 获取OHLCV数据，零额外API调用。

### 前端融入

| 页面 | 融入内容 |
|------|---------|
| 每日简报 | 股票卡片增加综合评分徽章(0-100) + MACD信号标签 |
| 走势看板 | K线图下方增加MACD/RSI副图 |
| 预警系统 | 增加"RSI超买/超卖"和"乖离率过大"预警类型 |

### 评分体系

| 评分区间 | 信号 | 含义 |
|---------|------|------|
| 80-100 | STRONG_BUY | 强烈买入 |
| 60-79 | BUY | 买入 |
| 40-59 | HOLD | 观望 |
| 20-39 | SELL | 卖出 |
| 0-19 | STRONG_SELL | 强烈卖出 |

---

## 二、AI大模型分析

### 目标
接入OpenAI兼容API，整合技术面数据为每只股票生成结构化决策建议。手动触发。

### 新增服务：`app/services/ai_analyzer.py`

```python
class AIAnalyzerService:
    """AI股票分析服务，OpenAI兼容API"""

    def __init__(self):
        # 从config读取 api_key, base_url, model

    def analyze_stock(self, stock_code) -> dict:
        """单只股票AI分析
        1. 收集数据：价格+技术指标+威科夫阶段+PE
        2. 构建prompt（技术面+持仓信息）
        3. 调用LLM，要求JSON格式输出
        4. 解析返回结构化结果"""

    def analyze_batch(self, stock_codes) -> list:
        """批量分析（持仓股）"""

    def _build_prompt(self, stock_data) -> str:
        """构建分析prompt（决策仪表盘模板）"""
```

### 新增配置：`app/config/ai_config.py`

```python
AI_API_KEY = ""        # 环境变量 AI_API_KEY
AI_BASE_URL = ""       # OpenAI兼容端点
AI_MODEL = ""          # 模型名（如 deepseek-chat）
```

### AI输出结构

```json
{
  "conclusion": "一句话结论",
  "signal": "STRONG_BUY/BUY/HOLD/SELL/STRONG_SELL",
  "score": 75,
  "confidence": "high/medium/low",
  "analysis": {
    "trend": "多头排列分析...",
    "volume": "量能分析...",
    "risk": "风险因素..."
  },
  "action_plan": {
    "buy_price": 1750,
    "stop_loss": 1700,
    "target_price": 1850,
    "position_advice": "轻仓试探"
  }
}
```

### Prompt模板（参考决策仪表盘v2.0）

输入给AI的数据：
- 股票基础信息（代码、名称、市场）
- 今日行情（开收高低、涨跌幅、成交量）
- 均线系统（MA5/MA20/MA60排列状态）
- 技术指标（MACD信号、RSI值、乖离率）
- 威科夫阶段（当前阶段、事件、评分）
- PE估值（当前PE、估值状态）
- 持仓信息（持仓数量、成本价、浮盈）

要求AI遵循的核心纪律：
- 乖离率>5%不追高
- 多头排列是做多前提
- 精确标注买入价/止损价/目标价
- 给出仓位建议

### 前端融入

| 页面 | 融入方式 |
|------|---------|
| 每日简报 | 股票卡片增加"AI分析"按钮，点击展开分析结果 |
| 每日简报顶部 | "批量AI分析"按钮，一键分析所有持仓股 |

### 缓存策略
分析结果存入 `UnifiedStockCache`（cache_type=`ai_analysis`），每日有效，避免重复调API。

---

## 三、回测验证系统

### 目标
验证威科夫阶段判断和买卖信号的历史准确率，建立分析可信度。

### 新增服务：`app/services/backtest.py`

```python
class BacktestService:
    """回测验证服务"""

    def backtest_wyckoff(self, stock_code, lookback_days=180) -> dict:
        """回测威科夫阶段判断
        1. 获取历史自动分析记录（WyckoffAutoAnalysis表）
        2. 获取对应时段的实际走势
        3. 验证阶段判断后N天的走势是否符合预期
           - 吸筹→后续是否上涨？
           - 派发→后续是否下跌？
        4. 输出：方向准确率、平均收益率"""

    def backtest_signals(self, stock_code, lookback_days=365) -> dict:
        """回测买卖信号
        1. 获取历史信号记录（SignalCache表）
        2. 验证信号触发后5/10/20天的实际走势
           - 买入信号→后续N天是否上涨？
           - 卖出信号→后续N天是否下跌？
        3. 输出：信号胜率、平均收益、最大回撤"""

    def backtest_batch(self, stock_codes) -> dict:
        """批量回测所有持仓股"""

    def get_summary(self) -> dict:
        """汇总统计：整体胜率、最佳/最差信号类型"""
```

### 核心指标

| 指标 | 说明 |
|------|------|
| 方向准确率 | 预测方向与实际走势匹配度 |
| 信号胜率 | 触发后N天收益>0的比例 |
| 平均收益率 | 信号触发后的平均涨跌幅 |
| 触发延迟 | 信号到达目标/止损的平均天数 |

### 数据来源（全部复用现有数据）
- 威科夫记录 → `WyckoffAutoAnalysis` 表
- 信号记录 → `SignalCache` 表
- 走势数据 → `UnifiedStockDataService.get_trend_data()`

### 前端融入

| 页面 | 融入方式 |
|------|---------|
| 预警系统 | 每种信号类型旁显示历史胜率徽章 |
| 威科夫自动分析 | 增加"回测验证"按钮，展示准确率报告 |

---

## 四、消息推送（Slack + 邮箱）

### 目标
手动推送分析结果到 Slack 和邮箱。

### 新增服务：`app/services/notification.py`

```python
class NotificationService:
    """消息推送服务"""

    def send_slack(self, message, channel=None) -> bool:
        """推送到Slack（Incoming Webhook）"""

    def send_email(self, subject, html_body, to=None) -> bool:
        """推送邮件（SMTP/SSL）"""

    def send_all(self, subject, content) -> dict:
        """同时推送到所有已配置渠道"""

    def format_briefing_summary(self) -> str:
        """生成每日简报摘要（持仓/收益/异常）"""

    def format_alert_signals(self) -> str:
        """生成预警信号摘要"""

    def format_ai_report(self, analyses) -> str:
        """格式化AI分析报告"""

    def push_daily_report(self) -> dict:
        """一键推送每日报告（简报+预警+AI分析）"""
```

### 新增配置：`app/config/notification_config.py`

```python
SLACK_WEBHOOK_URL = ""     # Slack Incoming Webhook URL
SMTP_HOST = ""             # 邮件服务器
SMTP_PORT = 465            # SSL端口
SMTP_USER = ""             # 发件邮箱
SMTP_PASSWORD = ""         # 邮箱密码/授权码
NOTIFY_EMAIL_TO = ""       # 收件邮箱
```

### 推送内容格式

```markdown
📊 每日股票分析报告 - 2026-02-09

## 持仓概览
- 总市值: ¥xxx | 日收益: +¥xxx (+x.x%)
- 持仓: 12只 | 上涨: 8 | 下跌: 4

## 预警信号
🔴 600519 贵州茅台 - RSI超买(78) + 乖离率5.2%
🟢 000858 五粮液 - 缩量突破信号 | 威科夫:吸筹阶段

## AI分析摘要
- 600519: HOLD(65分) - 高位震荡，建议持有观察
- 000858: BUY(78分) - 吸筹末期，关注突破
```

### 前端融入

| 页面 | 融入方式 |
|------|---------|
| 每日简报 | 顶部增加"推送报告"按钮 |
| 设置（我的菜单） | 推送配置页（Slack Webhook、邮箱设置、推送内容选择） |

### 触发方式
仅手动触发（页面按钮）。如需定时可后续用系统定时任务。

---

## 五、实施优先级

建议按以下顺序实施（后续模块依赖前置模块）：

| 优先级 | 模块 | 依赖关系 | 预估新增文件 |
|--------|------|---------|------------|
| P1 | 技术指标增强 | 无 | 1个service + 前端修改 |
| P2 | AI大模型分析 | 依赖P1的技术指标数据 | 1个service + 1个config + 1个route + 前端修改 |
| P3 | 回测验证系统 | 依赖现有数据，可独立 | 1个service + 1个route + 前端修改 |
| P4 | 消息推送 | 依赖P1-P3的输出内容 | 1个service + 1个config + 1个route + 前端修改 |

## 六、新增依赖

```
openai          # OpenAI兼容API客户端（AI分析）
```

其余功能（MACD/RSI计算、邮件发送、Slack推送）均使用Python标准库或现有依赖实现。

## 七、不做的事情

- 不集成新闻/舆情搜索（避免额外API依赖）
- 不做定时调度（保持本地工具简洁性）
- 不新建独立页面（全部融入现有页面）
- 不引入TA-Lib等第三方技术分析库（纯Python实现）
