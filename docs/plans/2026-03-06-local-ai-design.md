# 本地 AI 模型实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 引入本地 LLM（llama-server + Qwen3.5-9B）替代云端 Flash 层，并构建 PyTorch 时序 Transformer 生成交易信号。

**Architecture:** llama-server 作为独立进程提供 OpenAI 兼容 API，新增 `LlamaServerProvider` 接入现有 `LLMRouter`；走势预测模块 `app/ml/` 独立于 LLM 体系，通过 `SignalService` 对外暴露，可接入盯盘助手和策略插件系统。

**Tech Stack:** llama-server (llama.cpp), Qwen3.5-9B-Instruct GGUF (Q4_K_M, ~6.5GB VRAM), PyTorch (CUDA), RTX 4070 Super 12GB

---

## Phase 1：本地 LLM

### Task 1: 创建 LlamaServerProvider

**Files:**
- Create: `app/llm/providers/llamacpp.py`

**Step 1: 创建 provider 文件**

```python
"""llama-server 本地 LLM Provider"""
import logging
import os
import httpx
from app.llm.base import LLMProvider

logger = logging.getLogger(__name__)

LLAMA_SERVER_URL = os.environ.get('LLAMA_SERVER_URL', 'http://127.0.0.1:8080')
LLAMA_SERVER_ENABLED = os.environ.get('LLAMA_SERVER_ENABLED', 'false').lower() == 'true'
LLAMA_REQUEST_TIMEOUT = int(os.environ.get('LLM_REQUEST_TIMEOUT', '120'))


class LlamaServerProvider(LLMProvider):
    name = "llama-server"
    model = "local"
    cost_per_1k_tokens = 0.0

    def chat(self, messages: list[dict], temperature: float = 0.3, max_tokens: int = 500) -> str:
        response = httpx.post(
            f'{LLAMA_SERVER_URL}/v1/chat/completions',
            json={
                'messages': messages,
                'temperature': temperature,
                'max_tokens': max_tokens,
            },
            timeout=LLAMA_REQUEST_TIMEOUT,
        )
        response.raise_for_status()
        data = response.json()
        content = data['choices'][0]['message']['content'].strip()
        if not content:
            logger.warning(f"[llama-server] 返回空内容, finish_reason={data['choices'][0].get('finish_reason')}")
            raise ValueError('llama-server 返回空内容')
        return content


def is_llama_server_available() -> bool:
    """检测 llama-server 是否在线"""
    if not LLAMA_SERVER_ENABLED:
        return False
    try:
        resp = httpx.get(f'{LLAMA_SERVER_URL}/health', timeout=3)
        return resp.status_code == 200
    except Exception:
        return False
```

**Step 2: 验证文件语法**

Run: `python -c "from app.llm.providers.llamacpp import LlamaServerProvider; print('OK')"`
Expected: OK（需 LLAMA_SERVER_ENABLED=false 时不报错）

**Step 3: Commit**

```bash
git add app/llm/providers/llamacpp.py
git commit -m "feat: 新增 LlamaServerProvider 本地 LLM provider"
```

---

### Task 2: 修改 LLMRouter 支持本地优先

**Files:**
- Modify: `app/llm/router.py`

**Step 1: 修改 init_providers 方法**

在 `init_providers` 中优先检测 llama-server，可用则注册为 FLASH 层；不可用时 fallback 到智谱 Flash。

将 `router.py` 的 `init_providers` 方法改为：

```python
def init_providers(self):
    """延迟初始化 providers — 本地优先"""
    if self._providers:
        return

    # 本地 llama-server 优先作为 FLASH 层
    from app.llm.providers.llamacpp import LlamaServerProvider, is_llama_server_available
    if is_llama_server_available():
        self._providers[LLMLayer.FLASH] = LlamaServerProvider()
        logger.info('[LLM路由] llama-server 本地模型已加载 (FLASH)')

    # 智谱 GLM
    from app.llm.providers.zhipu import ZhipuFlashProvider, ZhipuPremiumProvider, ZHIPU_API_KEY
    if ZHIPU_API_KEY:
        if LLMLayer.FLASH not in self._providers:
            self._providers[LLMLayer.FLASH] = ZhipuFlashProvider()
            logger.info('[LLM路由] 智谱 Flash 已加载 (FLASH)')
        self._providers[LLMLayer.PREMIUM] = ZhipuPremiumProvider()
        logger.info('[LLM路由] 智谱 GLM-4 已加载 (PREMIUM)')
```

**Step 2: 验证启动**

Run: `python -c "from app.llm.router import llm_router; print('Router OK')"`

**Step 3: Commit**

```bash
git add app/llm/router.py
git commit -m "feat: LLMRouter 支持本地 llama-server 优先路由"
```

---

### Task 3: 更新配置文件

**Files:**
- Modify: `.env.sample`
- Modify: `CLAUDE.md`
- Modify: `README.md`（如有 LLM 配置段落）

**Step 1: 在 `.env.sample` 的 LLM 配置段落末尾添加**

```
# 本地 LLM（llama-server，替代 Flash 层）
# 需要先启动 llama-server: llama-server -m model.gguf -ngl 99 -c 4096 --port 8080
# LLAMA_SERVER_ENABLED=true
# LLAMA_SERVER_URL=http://127.0.0.1:8080
```

**Step 2: 在 `CLAUDE.md` 的 LLM 配置表格中添加两行**

| `LLAMA_SERVER_ENABLED` | 启用本地 llama-server | `false` |
| `LLAMA_SERVER_URL` | llama-server 地址 | `http://127.0.0.1:8080` |

**Step 3: Commit**

```bash
git add .env.sample CLAUDE.md
git commit -m "docs: 新增本地 LLM 环境变量配置"
```

---

## Phase 2：走势预测基础

### Task 4: 创建 ML 模块结构和特征工程

**Files:**
- Create: `app/ml/__init__.py`
- Create: `app/ml/models/__init__.py`
- Create: `app/ml/features.py`

**Step 1: 创建目录和 __init__.py**

`app/ml/__init__.py` — 空文件
`app/ml/models/__init__.py` — 空文件

**Step 2: 实现特征工程 `app/ml/features.py`**

```python
"""特征工程 — OHLCV 数据转换为模型输入特征"""
import numpy as np


# 特征维度：OHLCV(5) + MA(4) + RSI(1) + MACD(3) + 布林带(3) + ATR(1) + 量变化率(1) + OBV(1) = 19
FEATURE_DIM = 19
WINDOW_SIZE = 60


def compute_features(ohlcv: list[dict]) -> np.ndarray | None:
    """将 OHLCV 数据列表转换为特征矩阵

    Args:
        ohlcv: OHLCV 数据列表，每项包含 open, high, low, close, volume

    Returns:
        (seq_len, FEATURE_DIM) 的 numpy 数组，MinMax 归一化到 [0,1]
        数据不足时返回 None
    """
    if len(ohlcv) < WINDOW_SIZE:
        return None

    opens = np.array([d['open'] for d in ohlcv], dtype=np.float64)
    highs = np.array([d['high'] for d in ohlcv], dtype=np.float64)
    lows = np.array([d['low'] for d in ohlcv], dtype=np.float64)
    closes = np.array([d['close'] for d in ohlcv], dtype=np.float64)
    volumes = np.array([d['volume'] for d in ohlcv], dtype=np.float64)

    ma5 = _moving_average(closes, 5)
    ma10 = _moving_average(closes, 10)
    ma20 = _moving_average(closes, 20)
    ma60 = _moving_average(closes, 60)

    rsi = _rsi(closes, 14)
    macd_line, signal_line, histogram = _macd(closes)
    upper, middle, lower = _bollinger(closes, 20, 2)
    atr = _atr(highs, lows, closes, 14)
    vol_change = _volume_change_rate(volumes)
    obv = _obv(closes, volumes)

    features = np.column_stack([
        opens, highs, lows, closes, volumes,
        ma5, ma10, ma20, ma60,
        rsi,
        macd_line, signal_line, histogram,
        upper, middle, lower,
        atr,
        vol_change,
        obv,
    ])

    # MinMax 归一化（按列）
    feat_min = features.min(axis=0)
    feat_max = features.max(axis=0)
    feat_range = feat_max - feat_min
    feat_range[feat_range == 0] = 1.0
    features = (features - feat_min) / feat_range

    return features.astype(np.float32)


def _moving_average(data: np.ndarray, window: int) -> np.ndarray:
    result = np.full_like(data, np.nan)
    cumsum = np.cumsum(data)
    result[window - 1:] = (cumsum[window - 1:] - np.concatenate([[0], cumsum[:-window]])) / window
    # 前面填充第一个有效值
    result[:window - 1] = result[window - 1]
    return result


def _rsi(closes: np.ndarray, period: int) -> np.ndarray:
    deltas = np.diff(closes, prepend=closes[0])
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = np.full_like(closes, np.nan)
    avg_loss = np.full_like(closes, np.nan)
    avg_gain[period] = gains[1:period + 1].mean()
    avg_loss[period] = losses[1:period + 1].mean()
    for i in range(period + 1, len(closes)):
        avg_gain[i] = (avg_gain[i - 1] * (period - 1) + gains[i]) / period
        avg_loss[i] = (avg_loss[i - 1] * (period - 1) + losses[i]) / period
    rs = avg_gain / np.where(avg_loss == 0, 1e-10, avg_loss)
    rsi = 100 - 100 / (1 + rs)
    rsi[:period] = 50.0
    return rsi


def _macd(closes: np.ndarray, fast=12, slow=26, signal=9):
    ema_fast = _ema(closes, fast)
    ema_slow = _ema(closes, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def _ema(data: np.ndarray, period: int) -> np.ndarray:
    result = np.empty_like(data)
    multiplier = 2.0 / (period + 1)
    result[0] = data[0]
    for i in range(1, len(data)):
        result[i] = (data[i] - result[i - 1]) * multiplier + result[i - 1]
    return result


def _bollinger(closes: np.ndarray, period: int, num_std: float):
    middle = _moving_average(closes, period)
    rolling_std = np.full_like(closes, np.nan)
    for i in range(period - 1, len(closes)):
        rolling_std[i] = closes[i - period + 1:i + 1].std()
    rolling_std[:period - 1] = rolling_std[period - 1]
    upper = middle + num_std * rolling_std
    lower = middle - num_std * rolling_std
    return upper, middle, lower


def _atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int) -> np.ndarray:
    tr = np.maximum(highs - lows,
                    np.maximum(np.abs(highs - np.roll(closes, 1)),
                               np.abs(lows - np.roll(closes, 1))))
    tr[0] = highs[0] - lows[0]
    atr = np.full_like(tr, np.nan)
    atr[period - 1] = tr[:period].mean()
    for i in range(period, len(tr)):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    atr[:period - 1] = atr[period - 1]
    return atr


def _volume_change_rate(volumes: np.ndarray) -> np.ndarray:
    prev = np.roll(volumes, 1)
    prev[0] = volumes[0]
    rate = (volumes - prev) / np.where(prev == 0, 1, prev)
    return rate


def _obv(closes: np.ndarray, volumes: np.ndarray) -> np.ndarray:
    direction = np.sign(np.diff(closes, prepend=closes[0]))
    obv = np.cumsum(direction * volumes)
    return obv
```

**Step 3: 验证**

Run: `python -c "from app.ml.features import compute_features, FEATURE_DIM; print(f'Features OK, dim={FEATURE_DIM}')"`

**Step 4: Commit**

```bash
git add app/ml/
git commit -m "feat: ML 模块结构和特征工程"
```

---

### Task 5: 实现 Transformer 模型

**Files:**
- Create: `app/ml/models/trend_transformer.py`

**Step 1: 实现模型**

```python
"""时序 Transformer — 交易信号分类模型"""
import math
import torch
import torch.nn as nn


class PositionalEncoding(nn.Module):
    def __init__(self, d_model: int, max_len: int = 200):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer('pe', pe.unsqueeze(0))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.pe[:, :x.size(1)]


class TrendTransformer(nn.Module):
    """轻量时序 Transformer，输出 3 分类信号（买入/卖出/持有）"""

    def __init__(self, input_dim: int = 19, d_model: int = 64,
                 nhead: int = 4, num_layers: int = 4,
                 dim_feedforward: int = 256, dropout: float = 0.1):
        super().__init__()
        self.input_proj = nn.Linear(input_dim, d_model)
        self.pos_encoder = PositionalEncoding(d_model)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout, batch_first=True,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.classifier = nn.Sequential(
            nn.Linear(d_model, d_model),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(d_model, 3),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: (batch, seq_len, input_dim)
        Returns:
            (batch, 3) logits for [buy, sell, hold]
        """
        x = self.input_proj(x)
        x = self.pos_encoder(x)
        x = self.transformer(x)
        x = x.mean(dim=1)  # Global Average Pooling
        return self.classifier(x)
```

**Step 2: 验证模型可实例化**

Run: `python -c "from app.ml.models.trend_transformer import TrendTransformer; import torch; m = TrendTransformer(); print(f'Params: {sum(p.numel() for p in m.parameters()):,}'); y = m(torch.randn(2, 60, 19)); print(f'Output: {y.shape}')"`
Expected: 参数约 500K, Output: torch.Size([2, 3])

**Step 3: Commit**

```bash
git add app/ml/models/trend_transformer.py
git commit -m "feat: TrendTransformer 时序模型定义"
```

---

### Task 6: 实现数据集构建和标签生成

**Files:**
- Create: `app/ml/dataset.py`

**Step 1: 实现 dataset**

```python
"""数据集构建 — OHLCV 数据转换为训练样本"""
import numpy as np
import torch
from torch.utils.data import Dataset
from app.ml.features import compute_features, WINDOW_SIZE


# 标签定义
LABEL_BUY = 0
LABEL_SELL = 1
LABEL_HOLD = 2
SIGNAL_NAMES = {LABEL_BUY: 'buy', LABEL_SELL: 'sell', LABEL_HOLD: 'hold'}

# 默认参数
DEFAULT_FUTURE_DAYS = 5
DEFAULT_THRESHOLD = 0.02


def generate_labels(closes: list[float], future_days: int = DEFAULT_FUTURE_DAYS,
                    threshold: float = DEFAULT_THRESHOLD) -> np.ndarray:
    """基于未来 N 日收益率生成标签

    Returns:
        标签数组，长度 = len(closes) - future_days
    """
    closes = np.array(closes, dtype=np.float64)
    labels = []
    for i in range(len(closes) - future_days):
        future_return = (closes[i + future_days] - closes[i]) / closes[i]
        if future_return > threshold:
            labels.append(LABEL_BUY)
        elif future_return < -threshold:
            labels.append(LABEL_SELL)
        else:
            labels.append(LABEL_HOLD)
    return np.array(labels)


class TrendDataset(Dataset):
    """滑动窗口数据集"""

    def __init__(self, ohlcv: list[dict], future_days: int = DEFAULT_FUTURE_DAYS,
                 threshold: float = DEFAULT_THRESHOLD):
        features = compute_features(ohlcv)
        if features is None:
            self.samples = []
            return

        closes = [d['close'] for d in ohlcv]
        labels = generate_labels(closes, future_days, threshold)

        # 滑动窗口：每个样本取 WINDOW_SIZE 行特征，对应 1 个标签
        self.samples = []
        max_start = min(len(features) - WINDOW_SIZE, len(labels) - 1)
        for i in range(max_start + 1):
            window = features[i:i + WINDOW_SIZE]
            label_idx = i + WINDOW_SIZE - 1
            if label_idx < len(labels):
                self.samples.append((
                    torch.tensor(window, dtype=torch.float32),
                    torch.tensor(labels[label_idx], dtype=torch.long),
                ))

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        return self.samples[idx]
```

**Step 2: 验证**

Run: `python -c "from app.ml.dataset import TrendDataset; print('Dataset OK')"`

**Step 3: Commit**

```bash
git add app/ml/dataset.py
git commit -m "feat: TrendDataset 数据集和标签生成"
```

---

### Task 7: 实现训练流程

**Files:**
- Create: `app/ml/trainer.py`

**Step 1: 实现 trainer**

```python
"""模型训练流程"""
import json
import logging
import os
from datetime import datetime
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, random_split

from app.ml.dataset import TrendDataset, SIGNAL_NAMES
from app.ml.features import FEATURE_DIM
from app.ml.models.trend_transformer import TrendTransformer

logger = logging.getLogger(__name__)

MODEL_DIR = 'data/models'
DEFAULT_EPOCHS = 50
DEFAULT_BATCH_SIZE = 32
DEFAULT_LR = 1e-3


class TrendTrainer:
    """单只股票的训练器"""

    def __init__(self, stock_code: str):
        self.stock_code = stock_code
        self.model_dir = Path(MODEL_DIR) / stock_code
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    def train(self, ohlcv: list[dict], epochs: int = DEFAULT_EPOCHS,
              batch_size: int = DEFAULT_BATCH_SIZE, lr: float = DEFAULT_LR) -> dict:
        """训练模型

        Args:
            ohlcv: 完整历史 OHLCV 数据（越长越好，建议 1 年以上）

        Returns:
            训练结果 dict
        """
        dataset = TrendDataset(ohlcv)
        if len(dataset) < 100:
            return {'error': f'数据不足: {len(dataset)} 样本（需要至少 100）'}

        # 80/20 划分
        train_size = int(len(dataset) * 0.8)
        val_size = len(dataset) - train_size
        train_set, val_set = random_split(dataset, [train_size, val_size])

        train_loader = DataLoader(train_set, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_set, batch_size=batch_size)

        # 类别权重（处理不平衡）
        all_labels = [s[1].item() for s in dataset.samples]
        class_counts = np.bincount(all_labels, minlength=3).astype(np.float32)
        class_counts[class_counts == 0] = 1
        weights = torch.tensor(1.0 / class_counts, device=self.device)
        weights = weights / weights.sum()

        model = TrendTransformer(input_dim=FEATURE_DIM).to(self.device)
        criterion = nn.CrossEntropyLoss(weight=weights)
        optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
        scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

        best_val_acc = 0.0
        history = []

        for epoch in range(epochs):
            # 训练
            model.train()
            train_loss = 0.0
            for X, y in train_loader:
                X, y = X.to(self.device), y.to(self.device)
                optimizer.zero_grad()
                out = model(X)
                loss = criterion(out, y)
                loss.backward()
                optimizer.step()
                train_loss += loss.item()
            scheduler.step()

            # 验证
            model.eval()
            correct = total = 0
            with torch.no_grad():
                for X, y in val_loader:
                    X, y = X.to(self.device), y.to(self.device)
                    preds = model(X).argmax(dim=1)
                    correct += (preds == y).sum().item()
                    total += y.size(0)
            val_acc = correct / total if total > 0 else 0

            history.append({
                'epoch': epoch + 1,
                'train_loss': round(train_loss / len(train_loader), 4),
                'val_acc': round(val_acc, 4),
            })

            if val_acc > best_val_acc:
                best_val_acc = val_acc
                self._save_model(model)

        # 标签分布
        label_dist = {SIGNAL_NAMES[i]: int(c) for i, c in enumerate(class_counts)}

        result = {
            'stock_code': self.stock_code,
            'samples': len(dataset),
            'train_size': train_size,
            'val_size': val_size,
            'best_val_acc': round(best_val_acc, 4),
            'epochs': epochs,
            'label_distribution': label_dist,
            'device': str(self.device),
            'trained_at': datetime.now().isoformat(),
        }
        self._save_log(result, history)
        logger.info(f'[训练] {self.stock_code} 完成, val_acc={best_val_acc:.2%}, samples={len(dataset)}')
        return result

    def _save_model(self, model: nn.Module):
        self.model_dir.mkdir(parents=True, exist_ok=True)
        torch.save(model.state_dict(), self.model_dir / 'model.pt')

    def _save_log(self, result: dict, history: list):
        self.model_dir.mkdir(parents=True, exist_ok=True)
        with open(self.model_dir / 'train_log.json', 'w', encoding='utf-8') as f:
            json.dump({'result': result, 'history': history}, f, ensure_ascii=False, indent=2)
```

**Step 2: 验证导入**

Run: `python -c "from app.ml.trainer import TrendTrainer; print('Trainer OK')"`

**Step 3: Commit**

```bash
git add app/ml/trainer.py
git commit -m "feat: TrendTrainer 模型训练流程"
```

---

## Phase 3：信号集成

### Task 8: 实现推理服务

**Files:**
- Create: `app/ml/predictor.py`

**Step 1: 实现 predictor**

```python
"""推理服务 — 加载训练好的模型生成交易信号"""
import logging
from pathlib import Path

import numpy as np
import torch

from app.ml.dataset import SIGNAL_NAMES
from app.ml.features import compute_features, FEATURE_DIM, WINDOW_SIZE
from app.ml.models.trend_transformer import TrendTransformer

logger = logging.getLogger(__name__)

MODEL_DIR = 'data/models'


class TrendPredictor:
    """缓存已加载模型，按 stock_code 推理"""
    _models: dict = {}

    def predict(self, stock_code: str, ohlcv: list[dict]) -> dict | None:
        """对单只股票生成交易信号

        Args:
            stock_code: 股票代码
            ohlcv: 最近至少 WINDOW_SIZE 天的 OHLCV 数据

        Returns:
            {'signal': 'buy/sell/hold', 'confidence': 0.82, 'probabilities': {...}, 'model_date': '...'}
            模型不存在或数据不足时返回 None
        """
        model = self._load_model(stock_code)
        if model is None:
            return None

        features = compute_features(ohlcv)
        if features is None or len(features) < WINDOW_SIZE:
            return None

        # 取最后 WINDOW_SIZE 行
        window = features[-WINDOW_SIZE:]
        x = torch.tensor(window, dtype=torch.float32).unsqueeze(0)

        device = next(model.parameters()).device
        x = x.to(device)

        model.eval()
        with torch.no_grad():
            logits = model(x)
            probs = torch.softmax(logits, dim=1).cpu().numpy()[0]

        pred_idx = int(np.argmax(probs))
        model_path = Path(MODEL_DIR) / stock_code / 'model.pt'

        return {
            'signal': SIGNAL_NAMES[pred_idx],
            'confidence': round(float(probs[pred_idx]), 4),
            'probabilities': {SIGNAL_NAMES[i]: round(float(p), 4) for i, p in enumerate(probs)},
            'model_date': _get_model_date(model_path),
        }

    def _load_model(self, stock_code: str) -> TrendTransformer | None:
        if stock_code in self._models:
            return self._models[stock_code]

        model_path = Path(MODEL_DIR) / stock_code / 'model.pt'
        if not model_path.exists():
            return None

        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        model = TrendTransformer(input_dim=FEATURE_DIM).to(device)
        model.load_state_dict(torch.load(model_path, map_location=device, weights_only=True))
        self._models[stock_code] = model
        logger.info(f'[推理] 加载模型 {stock_code}')
        return model

    def clear_cache(self, stock_code: str = None):
        if stock_code:
            self._models.pop(stock_code, None)
        else:
            self._models.clear()


def _get_model_date(model_path: Path) -> str:
    import json
    log_path = model_path.parent / 'train_log.json'
    if log_path.exists():
        with open(log_path, 'r') as f:
            data = json.load(f)
            return data.get('result', {}).get('trained_at', '')[:10]
    return ''
```

**Step 2: 验证**

Run: `python -c "from app.ml.predictor import TrendPredictor; print('Predictor OK')"`

**Step 3: Commit**

```bash
git add app/ml/predictor.py
git commit -m "feat: TrendPredictor 推理服务"
```

---

### Task 9: 实现 SignalService

**Files:**
- Create: `app/services/signal_service.py`

**Step 1: 实现 signal service**

```python
"""交易信号服务 — 对外统一接口"""
import logging

from app.ml.predictor import TrendPredictor

logger = logging.getLogger(__name__)

_predictor = TrendPredictor()


class SignalService:

    @staticmethod
    def get_signal(stock_code: str, ohlcv: list[dict]) -> dict | None:
        """获取单只股票的 AI 交易信号

        Args:
            stock_code: 股票代码
            ohlcv: OHLCV 数据（需要至少 60 天）

        Returns:
            信号 dict 或 None（无模型时）
        """
        return _predictor.predict(stock_code, ohlcv)

    @staticmethod
    def get_batch_signals(stock_data: dict[str, list[dict]]) -> dict[str, dict]:
        """批量获取交易信号

        Args:
            stock_data: {stock_code: ohlcv_data}

        Returns:
            {stock_code: signal_dict}，无模型的股票不包含在结果中
        """
        results = {}
        for code, ohlcv in stock_data.items():
            signal = _predictor.predict(code, ohlcv)
            if signal:
                results[code] = signal
        return results

    @staticmethod
    def has_model(stock_code: str) -> bool:
        from pathlib import Path
        return (Path('data/models') / stock_code / 'model.pt').exists()

    @staticmethod
    def clear_model_cache(stock_code: str = None):
        _predictor.clear_cache(stock_code)
```

**Step 2: 验证**

Run: `python -c "from app.services.signal_service import SignalService; print('SignalService OK')"`

**Step 3: Commit**

```bash
git add app/services/signal_service.py
git commit -m "feat: SignalService 交易信号服务"
```

---

### Task 10: 注册为策略插件

**Files:**
- Create: `app/strategies/trend_signal/__init__.py`
- Create: `app/strategies/trend_signal/config.yaml`

**Step 1: 创建策略插件**

`app/strategies/trend_signal/config.yaml`:

```yaml
future_days: 5
threshold: 0.02
```

`app/strategies/trend_signal/__init__.py`:

```python
"""AI 走势信号策略 — 基于 Transformer 模型的交易信号"""
import logging
from app.strategies.base import Strategy, Signal

logger = logging.getLogger(__name__)


class TrendSignalStrategy(Strategy):
    name = "trend_signal"
    description = "AI 走势信号 — Transformer 模型交易信号"
    schedule = "interval_minutes:30"
    enabled = True

    def scan(self) -> list[Signal]:
        from app.models.stock import Stock
        from app.services.signal_service import SignalService
        from app.services.unified_stock_data import UnifiedStockDataService

        stocks = Stock.query.all()
        if not stocks:
            return []

        data_svc = UnifiedStockDataService()
        codes = [s.code for s in stocks if SignalService.has_model(s.code)]
        if not codes:
            return []

        signals = []
        trend_data = data_svc.get_trend_data(codes, days=120)

        for code in codes:
            stock_trend = trend_data.get(code)
            if not stock_trend or not stock_trend.get('data'):
                continue

            result = SignalService.get_signal(code, stock_trend['data'])
            if not result or result['signal'] == 'hold':
                continue
            if result['confidence'] < 0.6:
                continue

            stock = next((s for s in stocks if s.code == code), None)
            name = stock.name if stock else code
            action = '买入' if result['signal'] == 'buy' else '卖出'
            probs = result['probabilities']

            signals.append(Signal(
                strategy=self.name,
                priority='HIGH' if result['confidence'] >= 0.8 else 'MEDIUM',
                title=f'{name}({code}) AI {action}信号',
                detail=f"置信度 {result['confidence']:.0%} | 买入:{probs['buy']:.0%} 卖出:{probs['sell']:.0%} 持有:{probs['hold']:.0%}",
                data={'stock_code': code, **result},
            ))

        logger.info(f'[AI信号] 扫描 {len(codes)} 只, 产出 {len(signals)} 个信号')
        return signals
```

**Step 2: 验证**

Run: `python -c "from app.strategies.trend_signal import TrendSignalStrategy; s = TrendSignalStrategy(); print(f'{s.name}: {s.description}')"`

**Step 3: Commit**

```bash
git add app/strategies/trend_signal/
git commit -m "feat: AI 走势信号策略插件"
```

---

### Task 11: 添加 PyTorch 依赖

**Files:**
- Modify: `requirements.txt`

**Step 1: 在 requirements.txt 末尾添加**

```
# AI 走势预测（需要 CUDA 版本: pip install torch --index-url https://download.pytorch.org/whl/cu124）
# torch>=2.0.0
```

注意：torch 注释掉，因为 CUDA 版本需要通过 `--index-url` 安装，直接 pip install -r 会装 CPU 版。

**Step 2: Commit**

```bash
git add requirements.txt
git commit -m "docs: requirements.txt 添加 PyTorch 依赖说明"
```

---

## 任务总览

| Task | Phase | 描述 | 新增/修改文件 |
|------|-------|------|--------------|
| 1 | 1 | LlamaServerProvider | `app/llm/providers/llamacpp.py` |
| 2 | 1 | LLMRouter 本地优先 | `app/llm/router.py` |
| 3 | 1 | 环境变量配置 | `.env.sample`, `CLAUDE.md` |
| 4 | 2 | ML 模块 + 特征工程 | `app/ml/__init__.py`, `app/ml/features.py` |
| 5 | 2 | Transformer 模型 | `app/ml/models/trend_transformer.py` |
| 6 | 2 | 数据集和标签 | `app/ml/dataset.py` |
| 7 | 2 | 训练流程 | `app/ml/trainer.py` |
| 8 | 3 | 推理服务 | `app/ml/predictor.py` |
| 9 | 3 | SignalService | `app/services/signal_service.py` |
| 10 | 3 | 策略插件 | `app/strategies/trend_signal/` |
| 11 | 3 | PyTorch 依赖 | `requirements.txt` |
