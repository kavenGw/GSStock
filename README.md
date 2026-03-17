# GSStock

个人股票管理工具，支持 A股/美股/港股 多账户持仓管理。

## 功能

- **持仓管理** — 上传持仓截图 OCR 自动识别，多账户合并（数量相加、成本加权平均）
- **实时行情** — A股(akshare) + 美股/港股(yfinance)，统一数据接口，多源负载均衡
- **威科夫分析** — 自动识别市场阶段，多周期信号检测
- **操作建议** — 记录支撑位、压力位、交易策略
- **每日记录** — 持仓快照、盈亏统计、资产走势
- **每日简报** — 市场概况、持仓分析、预警汇总
- **板块管理** — 股票分类、板块评级
- **预警系统** — 涨跌幅预警、价格突破预警、威科夫信号
- **期货/贵金属** — 指数、期货、贵金属走势追踪
- **新闻看板** — 财经快讯、兴趣关键词过滤、公司新闻聚合、财报对比分析、AI 摘要
- **盯盘助手** — 实时分时走势、日K+布林带、支撑阻力位标注、三维度 AI 分析、预置商品/指数监控
- **交易策略** — 策略记录与管理
- **再平衡** — 持仓配置建议
- **利润统计** — 交易利润分析
- **策略插件** — 自动发现注册，Cron 定时执行，内置六种策略（涨跌预警/价格预警/每日简报/威科夫信号/AI走势信号/盯盘助手）
- **通知推送** — Slack 推送，与策略引擎集成
- **AI 分析** — 智谱 GLM 分层路由（Flash/Premium），支持本地 LLM（llama-server）替代 Flash 层
- **AI 走势预测** — PyTorch 时序 Transformer，基于 OHLCV + 技术指标生成买/卖/持有信号（GPU 训练推理）

## 环境要求

- Python 3.10+
- 支持 Windows / Debian (Linux)

## 安装步骤（Windows）

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

编辑 `.env` 文件，完整配置项见 `.env.sample` 注释。核心配置：

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `READONLY_MODE` | 只读模式，不从服务器获取数据 | `false` |
| `SECRET_KEY` | Flask 密钥，留空则自动生成 | 自动生成 |
| `DATABASE_URL` | 公共数据库路径 | `sqlite:///data/stock.db` |
| `PRIVATE_DATABASE_URL` | 私有数据库路径 | `sqlite:///data/private.db` |
| `TWELVE_DATA_API_KEY` | Twelve Data 密钥（可选，美股/港股） | 空 |
| `POLYGON_API_KEY` | Polygon.io 密钥（可选，仅美股） | 空 |
| `ZHIPU_API_KEY` | 智谱 GLM 密钥（可选，AI 分析） | 空 |
| `LLM_DAILY_BUDGET` | LLM 日预算上限（美元） | 无上限 |
| `LLM_REQUEST_TIMEOUT` | LLM API 请求超时（秒） | `300` |
| `LLAMA_SERVER_ENABLED` | 启用本地 llama-server（可选） | `false` |
| `LLAMA_SERVER_URL` | llama-server 地址 | `http://127.0.0.1:8080` |
| `SLACK_WEBHOOK_URL` | Slack 推送（可选） | 空 |
| `WATCH_INTERVAL_MINUTES` | 盯盘刷新间隔（分钟） | `1` |
| `NEWS_INTERVAL_MINUTES` | 新闻后台轮询间隔（分钟） | `10` |
| `NEWS_DERIVATION_ENABLED` | 启用衍生搜索（crawl4ai 爬取+AI 摘要） | `false` |
| `COMPANY_NEWS_MAX_COMPANIES` | 每次轮询最多处理的公司数 | `3` |
| `COMPANY_NEWS_MAX_ARTICLES` | 每个公司最多爬取文章数 | `5` |
| `COMPANY_NEWS_INTERVAL_MINUTES` | 公司新闻获取间隔（分钟） | `30` |
| `NEWS_FETCH_TIMEOUT` | 新闻源获取超时（秒） | `15` |

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

启动时会自动加载策略插件、初始化通知渠道、启动调度引擎。

Windows 用户可双击 `start.bat` 一键启动并打开浏览器。

## 部署步骤（Debian / Ubuntu）

### 1. 安装系统依赖

```bash
sudo apt update
sudo apt install -y python3 python3-pip git
```

### 2. 拉取代码

```bash
cd /home/kaven
git clone <your-repo-url> stock
cd stock
pip install -r requirements.txt
```

如需新闻爬取功能（crawl4ai），还需安装 Playwright 浏览器：

```bash
sudo apt install -y libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
  libcups2 libdrm2 libdbus-1-3 libxcomposite1 libxdamage1 libxrandr2 \
  libgbm1 libpango-1.0-0 libcairo2 libasound2 libxshmfence1
playwright install chromium
```

### 3. 环境配置

```bash
cp .env.sample .env
nano .env
```

### 4. 安装 systemd 服务

```bash
sudo ln -s /home/kaven/stock/gsstock.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable gsstock
sudo systemctl start gsstock
```

### 5. 日常更新

```bash
cd /home/kaven/stock
git pull
pip install -r requirements.txt
sudo systemctl restart gsstock
```

### 6. 管理服务

```bash
sudo systemctl status gsstock    # 查看状态
sudo systemctl restart gsstock   # 重启
sudo journalctl -u gsstock -f    # 查看日志
```

访问 http://<server-ip>:5000

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
| 新浪财经 | 实时行情 | 无需 |
| 腾讯财经 | 实时行情，批量获取 | 无需 |
| 东方财富 | 实时行情 + 历史K线 | 无需 |
| yfinance | 兜底数据源 | 无需 |

### 美股

默认使用 yfinance（无需密钥）。配置额外密钥可启用多数据源负载均衡。

| 数据源 | 免费额度 | 环境变量 |
|--------|---------|---------|
| Yahoo Finance | 无限制 | 无需 |
| Twelve Data | 8请求/分钟, 800请求/天 | `TWELVE_DATA_API_KEY` |
| Polygon.io | 5请求/分钟 | `POLYGON_API_KEY` |

### 港股

| 数据源 | 环境变量 |
|--------|---------|
| Yahoo Finance | 无需 |
| Twelve Data | `TWELVE_DATA_API_KEY` |

### 韩股 / 台股

仅支持 yfinance，无需配置。

### 数据源配置

在 `.env` 中添加对应的 API 密钥即可启用。数据源配置文件：`app/config/data_sources.py`

## AI 分析（可选）

集成智谱 GLM 大模型，为持仓股票生成结构化分析建议。支持本地 LLM 替代云端 Flash 层。

- **Flash 层** — 本地 llama-server（优先）或 智谱 glm-4-flash，处理快速任务：每日简报、新闻分类、情绪分析
- **Premium 层** (glm-4) — 高质量分析：深度分析、操作建议

### 云端 AI（智谱 GLM）

```env
ZHIPU_API_KEY=your_key_here
LLM_DAILY_BUDGET=5.0      # 日预算上限（美元），默认 5.0
LLM_REQUEST_TIMEOUT=300    # API 请求超时（秒），默认 300
```

配置 `ZHIPU_API_KEY` 后自动启用 AI 分析功能。预算用尽时自动降级到 Flash 层。

### 本地 LLM（llama-server）

用本地模型替代云端 Flash 层，零 API 费用，无网络依赖。推荐 Qwen3.5-9B（Q4_K_M 量化，约 6.5GB VRAM）。

1. 安装 llama.cpp（Windows 可通过 `winget install ggml.llamacpp`）
2. 下载 GGUF 模型（约 5.9GB）：

```bash
curl.exe -L -C - -o "D:/Models/Qwen_Qwen3.5-9B-Q4_K_M.gguf" "https://huggingface.co/bartowski/Qwen_Qwen3.5-9B-GGUF/resolve/main/Qwen_Qwen3.5-9B-Q4_K_M.gguf"
```

`-C -` 支持断点续传，中断后重新运行即可继续。Windows PowerShell 用户需使用 `curl.exe` 替代 `curl`。

3. 在 `.env` 中启用：

```env
LLAMA_SERVER_ENABLED=true
LLAMA_SERVER_URL=http://127.0.0.1:8080
```

本地可用时自动作为 Flash 层；不可用时 fallback 到智谱 Flash（如已配置）。

> **注意**：winget 安装的 llama.cpp 默认使用 Vulkan 后端。如需 CUDA 后端（性能更好），需从源码编译或下载 CUDA 版本的 release。

## AI 走势预测（可选）

基于 PyTorch 时序 Transformer 模型，利用历史 OHLCV + 技术指标（MA/RSI/MACD/布林带等 19 维特征）训练交易信号模型，输出买入/卖出/持有信号及置信度。

- 需要 NVIDIA GPU（推荐 RTX 4070 级别以上）
- 模型存储在 `data/models/{stock_code}/`
- 作为策略插件自动注册，定时扫描并推送信号

安装 PyTorch（CUDA 版本）：

```bash
pip install torch --index-url https://download.pytorch.org/whl/cu124
```

## 通知系统（可选）

策略引擎检测到信号后，通过事件总线推送到已配置的通知渠道。

### Slack

1. 打开 [Slack API: Applications](https://api.slack.com/apps)，点击 **Create New App** → **From scratch**
2. 输入应用名称（如 `Stock Alert`），选择目标 Workspace，点击 **Create App**
3. 左侧菜单选择 **Incoming Webhooks**，开启 **Activate Incoming Webhooks**
4. 页面底部点击 **Add New Webhook to Workspace**，选择接收通知的频道，点击 **Allow**
5. 复制生成的 Webhook URL，填入 `.env`：

```env
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/xxx
```

配置后自动启用。

## 技术栈

- **后端** — Flask + SQLAlchemy + SQLite
- **前端** — Bootstrap 5 + 原生 JavaScript
- **数据源** — akshare + yfinance + Twelve Data + Polygon（多源负载均衡）
- **OCR** — RapidOCR (ONNX Runtime)
- **AI** — 智谱 GLM（Flash/Premium 分层路由） + 本地 LLM（llama-server）
- **走势预测** — PyTorch 时序 Transformer（GPU 训练推理）
- **调度** — APScheduler（Cron 策略执行）

## 项目结构

```
app/
├── config/           # 配置（股票代码、数据源、通知）
├── models/           # SQLAlchemy 数据模型
├── routes/           # Flask Blueprint 路由
├── services/         # 业务逻辑服务
├── templates/        # Jinja2 页面模板
├── static/           # CSS/JS 静态资源
├── llm/              # LLM 路由和提供者（智谱 GLM / 本地 llama-server）
├── ml/               # 走势预测（Transformer 模型、特征工程、训练推理）
├── notifications/    # 多渠道通知系统
├── strategies/       # 策略插件系统
├── scheduler/        # APScheduler 后台调度
├── middleware/       # Flask 中间件
└── utils/            # 工具函数
```
