# GSStock

个人股票管理工具，支持 A股/美股/港股 多账户持仓管理。

## 功能

- **持仓管理** — 上传持仓截图 OCR 自动识别，多账户合并（数量相加、成本加权平均）
- **实时行情** — A股(akshare) + 美股/港股(yfinance)，统一数据接口，8小时缓存
- **威科夫分析** — 自动识别市场阶段，生成交易信号
- **操作建议** — 记录支撑位、压力位、交易策略
- **每日记录** — 持仓快照、盈亏统计、资产走势
- **板块管理** — 股票分类、板块评级
- **预警系统** — 信号检测与提醒
- **期货/贵金属** — 指数、期货、贵金属走势追踪

## 环境要求

- Python 3.10+
- Windows 系统（OCR 功能依赖 DirectML/CUDA，其他功能跨平台可用）

## 安装步骤

### 1. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

首次运行会自动下载 RapidOCR 中文模型。

### 2. 环境配置

复制环境配置示例文件：

```bash
cp .env.sample .env
```

编辑 `.env` 文件配置选项：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `READONLY_MODE` | 只读模式，不从服务器获取数据，不修改 stock.db | `false` |
| `SECRET_KEY` | Flask 密钥，留空则自动生成 | 自动生成 |
| `DATABASE_URL` | 公共数据库路径 | `sqlite:///data/stock.db` |
| `PRIVATE_DATABASE_URL` | 私有数据库路径 | `sqlite:///data/private.db` |
| `TWELVE_DATA_API_KEY` | Twelve Data 密钥（可选，美股/港股） | 空 |
| `POLYGON_API_KEY` | Polygon.io 密钥（可选，仅美股） | 空 |
| `AI_API_KEY` | AI 分析 API 密钥（可选） | 空 |
| `AI_BASE_URL` | AI API 地址（可选） | `https://api.openai.com/v1` |
| `AI_MODEL` | AI 模型名称（可选） | `gpt-4o-mini` |

**只读模式**适用于：
- 无网络环境
- 仅查看历史数据
- 共享 stock.db 给其他用户使用

### 3. GPU 加速（可选）

OCR 识别支持 GPU 加速，根据硬件选择安装一个：

```bash
# NVIDIA 显卡（CUDA）
pip install onnxruntime-gpu>=1.19.0

# Windows DirectML（Intel/AMD/NVIDIA 通用）
pip install onnxruntime-directml>=1.19.0
```

注意：`onnxruntime-gpu` 和 `onnxruntime-directml` 互斥，只能安装其中一个。不安装则使用 CPU。

### 4. 启动应用

```bash
python run.py
```

访问 http://127.0.0.1:5000

启动时会显示 OCR 后端类型（CUDA/DIRECTML/CPU）。

Windows 用户可双击 `start.bat` 一键启动并打开浏览器。

## 功能说明

| 功能 | 说明 |
|------|------|
| 上传持仓 | 上传截图自动识别或手动输入 |
| 持仓列表 | 查看当日持仓及盈亏 |
| 操作建议 | 记录支撑位、压力位、策略 |
| 历史查询 | 切换日期查看历史数据 |

## 数据存储

| 文件 | 说明 |
|------|------|
| `data/stock.db` | 公共数据（股票列表、缓存、分类） |
| `data/private.db` | 私有数据（持仓、交易、配置），自动生成，不提交到 Git |

首次运行时，如果 `stock.db` 中包含私有表，会自动迁移到 `private.db`。

## 数据源

系统通过负载均衡器自动分配数据源，支持熔断和故障转移。未配置 API 密钥的数据源会自动跳过。

### A股

无需配置，开箱即用。

| 数据源 | 说明 | 密钥 |
|--------|------|------|
| 新浪财经 | 实时行情，权重 40% | 无需 |
| 腾讯财经 | 实时行情，批量获取效率高，权重 35% | 无需 |
| 东方财富 | 实时行情 + 历史K线，权重 25% | 无需 |
| yfinance | 兜底数据源 | 无需 |

### 美股

默认使用 yfinance（无需密钥）。配置额外密钥可启用多数据源负载均衡，提升稳定性。

| 数据源 | 免费额度 | 环境变量 | 支持功能 |
|--------|---------|---------|---------|
| Yahoo Finance | 无限制 | 无需 | 实时 + 历史 + 信息 |
| Twelve Data | 8请求/分钟, 800请求/天 | `TWELVE_DATA_API_KEY` | 实时 + 历史 |
| Polygon.io | 5请求/分钟 | `POLYGON_API_KEY` | 实时 + 历史 |

### 港股

| 数据源 | 环境变量 |
|--------|---------|
| Yahoo Finance | 无需 |
| Twelve Data | `TWELVE_DATA_API_KEY` |

### 韩股 / 台股

仅支持 yfinance，无需配置。

### 数据源配置

在 `.env` 中添加对应的 API 密钥即可启用（详见 `.env.sample`）：

```env
TWELVE_DATA_API_KEY=your_key_here
POLYGON_API_KEY=your_key_here
```

数据源配置文件：`app/config/data_sources.py`（权重、优先级、市场映射）

### AI 分析（可选）

支持 OpenAI 兼容 API（OpenAI、DeepSeek、本地模型等），为持仓股票生成结构化分析建议。

在 `.env` 中配置：

```env
AI_API_KEY=sk-xxx
AI_BASE_URL=https://api.openai.com/v1   # 可选，默认 OpenAI
AI_MODEL=gpt-4o-mini                     # 可选，默认 gpt-4o-mini
```

配置 `AI_API_KEY` 后自动启用 AI 分析功能。

## 技术栈

- **后端** — Flask + SQLAlchemy + SQLite
- **前端** — Bootstrap 5 + 原生 JavaScript
- **数据源** — akshare + yfinance + Twelve Data + Polygon（多源负载均衡）
- **OCR** — RapidOCR (ONNX Runtime)

## 项目结构

```
app/
├── config/       # 股票代码、期货指数配置
├── models/       # SQLAlchemy 数据模型
├── routes/       # Flask Blueprint 路由
├── services/     # 业务逻辑（OCR、行情、分析）
├── templates/    # Jinja2 页面模板
└── static/       # CSS/JS 静态资源
```
