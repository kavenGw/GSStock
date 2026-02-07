# 技术栈

## 项目类型
Flask Web 应用，本地运行

## 核心技术

### 后端
- **Python 3.10+**
- **Flask 3.0+**: Web 框架
- **Flask-SQLAlchemy 3.1+**: ORM
- **SQLite**: 数据存储
- **RapidOCR**: 图片文字识别（支持 GPU 加速）
- **Pillow**: 图片预处理
- **yfinance**: 股票/期货数据 API

### 前端
- **Bootstrap 5.3**: UI 框架
- **Chart.js 4.4**: 图表绘制
- **Jinja2**: 模板引擎
- **原生 JavaScript**: 交互逻辑

## 架构模式

### 分层架构
```
Routes (路由层) → Services (业务层) → Models (数据层)
```

- **Routes**: 处理 HTTP 请求，调用 Service
- **Services**: 业务逻辑，数据处理
- **Models**: SQLAlchemy 模型定义

### 数据流
```
前端请求 → Blueprint 路由 → Service 方法 → Model 操作 → SQLite
```

## 数据存储

### 数据库
- **位置**: `data/stock.db`
- **类型**: SQLite
- **特点**: 按日期保存持仓快照，支持历史对比

### 文件存储
- **uploads/**: 临时上传文件
- **data/wyckoff/**: 威科夫图片
- **data/logs/**: 应用日志

## 外部集成

### yfinance API
- 获取期货价格（黄金、白银、铜、铝）
- 获取指数走势（恒生科技、纳指100、上证50）
- 获取股票实时行情

### 缓存策略
- MetalTrendCache: 期货数据缓存
- IndexTrendCache: 指数数据缓存
- 支持强制刷新

## 开发环境

### 依赖管理
```bash
pip install -r requirements.txt
```

### 启动命令
```bash
python run.py          # 启动应用
start.bat              # Windows 一键启动
```

### OCR GPU 加速
- **CUDA**: NVIDIA 显卡
- **DirectML**: Windows 通用 GPU
- **CPU**: 默认回退

## 配置

### Flask 配置 (config.py)
```python
SQLALCHEMY_DATABASE_URI = 'sqlite:///data/stock.db'
MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB
OCR_MAX_SIZE = 2048
OCR_TIMEOUT = 60
```

### 应用配置 (Config 表)
- `total_capital`: 总资金配置

## 技术决策

### 选择 SQLite
- 个人工具无需复杂数据库
- 单文件便于备份和迁移
- 无需额外数据库服务

### 选择 RapidOCR
- 支持中文识别
- 支持 GPU 加速
- 开源免费

### 按日期保存快照
- 支持历史对比分析
- 便于追踪持仓变化
- 简化数据模型

## 已知限制
- 单用户本地使用
- OCR 识别准确率依赖截图质量
- yfinance 数据存在延迟
