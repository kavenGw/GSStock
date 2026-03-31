"""LLM 提供商抽象"""
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    name: str = ""
    model: str = ""
    cost_per_1k_tokens: float = 0.0

    @abstractmethod
    def chat(self, messages: list[dict], temperature: float = 0.3, max_tokens: int = 500) -> str:
        """调用 LLM 返回文本响应"""
        ...


class LLMLayer:
    RULE = 0       # 规则引擎，$0
    LITE = 1       # 最便宜模型（glm-4-flash）
    FLASH = 2      # 便宜快速模型
    PREMIUM = 3    # 强力模型
