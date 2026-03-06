"""模型训练流程"""
import json
import logging
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

        train_size = int(len(dataset) * 0.8)
        val_size = len(dataset) - train_size
        train_set, val_set = random_split(dataset, [train_size, val_size])

        train_loader = DataLoader(train_set, batch_size=batch_size, shuffle=True)
        val_loader = DataLoader(val_set, batch_size=batch_size)

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
