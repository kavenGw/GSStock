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

## 技术栈

- **后端** — Flask + SQLAlchemy + SQLite
- **前端** — Bootstrap 5 + 原生 JavaScript
- **数据源** — akshare (A股) + yfinance (美股/港股/期货)
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
