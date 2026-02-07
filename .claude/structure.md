# 项目结构

## 目录组织

```
stock/
├── run.py                    # 应用入口
├── config.py                 # Flask 配置
├── requirements.txt          # Python 依赖
├── start.bat                 # Windows 启动脚本
├── CLAUDE.md                 # Claude Code 指引
├── INSTALL.md                # 安装文档
│
├── app/                      # 应用主包
│   ├── __init__.py          # Flask 工厂函数
│   ├── models/              # 数据模型
│   ├── routes/              # 路由 Blueprint
│   ├── services/            # 业务逻辑
│   ├── templates/           # Jinja2 模板
│   └── static/              # 静态资源
│
├── data/                     # 数据目录（运行时创建）
│   ├── stock.db             # SQLite 数据库
│   ├── logs/                # 应用日志
│   ├── uploads/             # 临时上传文件
│   └── wyckoff/             # 威科夫图片
│
└── .claude/                  # Claude Code 配置
    ├── specs/               # 功能规格文档
    └── templates/           # 文档模板
```

## 模块说明

### Models (数据模型)
| 文件 | 模型 | 用途 |
|------|------|------|
| position.py | Position | 持仓快照 |
| trade.py | Trade | 交易记录 |
| settlement.py | Settlement | 结算统计 |
| advice.py | Advice | 操作建议 |
| category.py | Category, StockCategory | 板块分类 |
| stock.py | Stock | 股票代码映射 |
| stock_weight.py | StockWeight | 股票权重 |
| wyckoff.py | WyckoffReference, WyckoffAnalysis | 威科夫分析 |
| config.py | Config | 应用配置 |
| metal_trend_cache.py | MetalTrendCache | 期货缓存 |
| index_trend_cache.py | IndexTrendCache | 指数缓存 |

### Routes (路由)
| 文件 | 前缀 | 功能 |
|------|------|------|
| main.py | / | 首页和持仓展示 |
| position.py | /positions | 持仓管理 API |
| trade.py | /trades | 交易管理 |
| daily_record.py | /daily-record | 每日记录上传 |
| advice.py | /advices | 操作建议 |
| category.py | /categories | 板块管理 |
| stock.py | /stocks | 股票代码管理 |
| profit.py | /profit | 收益统计 |
| wyckoff.py | /wyckoff | 威科夫分析 |
| rebalance.py | /rebalance | 仓位配平 |
| heavy_metals.py | /heavy-metals | 期货指数走势 |
| ticker.py | /ticker | 实时行情窗口 |

### Services (业务逻辑)
| 文件 | 类 | 职责 |
|------|-----|------|
| position.py | PositionService | 持仓合并、快照保存、统计计算 |
| trade.py | TradeService | 交易处理、结算计算 |
| daily_record.py | DailyRecordService | 每日收益计算 |
| ocr.py | OcrService | 图片识别、数据提取 |
| stock.py | StockService | 股票代码管理、冲突检测 |
| category.py | CategoryService | 板块树形管理 |
| wyckoff.py | WyckoffService | 威科夫图片和分析管理 |
| rebalance.py | RebalanceService | 仓位配平计算 |
| futures.py | FuturesService | 期货指数数据获取 |
| ticker.py | TickerService | 实时行情获取 |

### Templates (模板)
| 文件 | 页面 |
|------|------|
| base.html | 基础布局（导航栏） |
| index.html | 首页（持仓列表和统计） |
| daily_record.html | 每日记录上传 |
| daily_stats.html | 每日统计详情 |
| trade_list.html | 交易列表 |
| trade_stats.html | 交易统计 |
| daily_profit.html | 每日收益分析 |
| overall_profit.html | 整体收益分析 |
| category.html | 板块管理 |
| stock_manage.html | 股票代码管理 |
| wyckoff_reference.html | 威科夫参考图 |
| wyckoff_analysis.html | 威科夫分析记录 |
| rebalance.html | 仓位配平 |
| heavy_metals.html | 期货指数走势 |
| ticker_widget.html | 行情小窗口 |

### Static (静态资源)
```
static/
├── css/
│   ├── style.css        # 主样式
│   └── wyckoff.css      # 威科夫样式
└── js/
    ├── main.js          # 首页交互
    ├── charts.js        # 图表绑定
    ├── profit_charts.js # 收益图表
    ├── daily_record.js  # 每日记录
    ├── trade_list.js    # 交易列表
    ├── trade_stats.js   # 交易统计
    ├── rebalance.js     # 仓位配平
    └── wyckoff.js       # 威科夫交互
```

## 命名规范

### 文件命名
- **Python**: snake_case（如 `daily_record.py`）
- **模板**: snake_case（如 `trade_list.html`）
- **CSS/JS**: snake_case（如 `profit_charts.js`）

### 代码命名
- **类**: PascalCase（如 `PositionService`）
- **函数**: snake_case（如 `get_latest_date`）
- **常量**: UPPER_SNAKE_CASE（如 `MAX_CONTENT_LENGTH`）
- **变量**: snake_case（如 `stock_code`）

## 导入顺序
```python
# 1. 标准库
from datetime import datetime

# 2. 第三方库
from flask import Blueprint, jsonify
from sqlalchemy import func

# 3. 项目模块
from app import db
from app.models import Position
from app.services.position import PositionService
```

## 代码组织原则

### Route 层
- 只处理请求/响应
- 调用 Service 完成业务
- 不直接操作数据库

### Service 层
- 封装业务逻辑
- 调用 Model 操作数据
- 可被多个 Route 复用

### Model 层
- 定义数据结构
- 简单的数据验证
- 不包含业务逻辑
