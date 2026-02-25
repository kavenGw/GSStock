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
    FLASH = 1      # 便宜快速模型
    PREMIUM = 2    # 强力模型
