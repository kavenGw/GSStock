# 安装指南

## 环境要求

- Python 3.10+
- Windows 系统

## 安装步骤

### 1. 安装 Python 依赖

```bash
cd D:\Git\stock
pip install -r requirements.txt
```

首次运行会自动下载 RapidOCR 中文模型。

### 2. GPU 加速（可选）

根据硬件选择安装一个 GPU 加速包：

**NVIDIA 显卡（CUDA）**
```powershell
pip install onnxruntime-gpu>=1.19.0
```

**Windows DirectML（Intel/AMD/NVIDIA 通用）**
```powershell
pip install onnxruntime-directml>=1.19.0
```

注意：`onnxruntime-gpu` 和 `onnxruntime-directml` 互斥，只能安装其中一个。

### 3. 启动应用

```bash
python run.py
```

访问 http://127.0.0.1:5000

启动时会显示 OCR 后端类型（CUDA/DIRECTML/CPU）。

## 功能说明

| 功能 | 说明 |
|------|------|
| 上传持仓 | 上传截图自动识别或手动输入 |
| 持仓列表 | 查看当日持仓及盈亏 |
| 操作建议 | 记录支撑位、压力位、策略 |
| 历史查询 | 切换日期查看历史数据 |

## 数据存储

- 数据库：`data/stock.db`
- 上传图片：`uploads/`
