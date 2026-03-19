"""LLM 分层路由器"""
import logging
import os
from datetime import date
from app.llm.base import LLMProvider, LLMLayer

logger = logging.getLogger(__name__)

TASK_LAYER_MAP = {
    'summary': LLMLayer.FLASH,
    'sentiment': LLMLayer.FLASH,
    'analysis': LLMLayer.PREMIUM,
    'advice': LLMLayer.PREMIUM,
    'watch_analysis': LLMLayer.PREMIUM,
    'daily_briefing': LLMLayer.PREMIUM,
    'news_briefing': LLMLayer.FLASH,
    'news_classify': LLMLayer.FLASH,
    'news_derivation': LLMLayer.FLASH,
    'news_derivation_deep': LLMLayer.PREMIUM,
    'news_recommend': LLMLayer.FLASH,
    'earnings_compare': LLMLayer.FLASH,
    'stock_tags': LLMLayer.FLASH,
}


class FallbackProvider(LLMProvider):
    """主 Provider 失败时自动降级到备用 Provider"""

    def __init__(self, primary: LLMProvider, fallback: LLMProvider):
        self.primary = primary
        self.fallback = fallback
        self.name = primary.name
        self.model = primary.model
        self.cost_per_1k_tokens = primary.cost_per_1k_tokens

    def chat(self, messages: list[dict], temperature: float = 0.3, max_tokens: int = 500) -> str:
        try:
            return self.primary.chat(messages, temperature, max_tokens)
        except ValueError as e:
            logger.info(f'[{self.primary.name}] {e}，转 {self.fallback.name}')
            return self.fallback.chat(messages, temperature, max_tokens)
        except Exception as e:
            logger.warning(f'[{self.primary.name}] 异常，降级到 {self.fallback.name}: {e}')
            return self.fallback.chat(messages, temperature, max_tokens)


class LLMRouter:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._providers = {}
            cls._instance._daily_cost = 0.0
            cls._instance._cost_date = None
            _raw = os.environ.get('LLM_DAILY_BUDGET')
            cls._instance._daily_budget = float(_raw) if _raw else None
        return cls._instance

    def init_providers(self):
        """延迟初始化 providers — 本地优先，云端兜底"""
        if self._providers:
            return

        from app.llm.providers.llamacpp import LlamaServerProvider, LLAMA_SERVER_ENABLED

        from app.llm.providers.zhipu import ZhipuFlashProvider, ZhipuPremiumProvider, ZHIPU_API_KEY
        if ZHIPU_API_KEY:
            zhipu_flash = ZhipuFlashProvider()
            if LLAMA_SERVER_ENABLED:
                self._providers[LLMLayer.FLASH] = FallbackProvider(LlamaServerProvider(), zhipu_flash)
                logger.info('[LLM路由] FLASH = llama-server → 智谱 Flash (降级)')
            else:
                self._providers[LLMLayer.FLASH] = zhipu_flash
                logger.info('[LLM路由] FLASH = 智谱 Flash')
            self._providers[LLMLayer.PREMIUM] = ZhipuPremiumProvider()
            logger.info('[LLM路由] PREMIUM = 智谱 GLM-4')
        elif LLAMA_SERVER_ENABLED:
            self._providers[LLMLayer.FLASH] = LlamaServerProvider()
            logger.info('[LLM路由] FLASH = llama-server (无云端兜底)')

    def route(self, task_type: str) -> LLMProvider | None:
        """按任务类型路由到合适的 LLM"""
        self.init_providers()
        if not self._providers:
            return None

        today = date.today()
        if self._cost_date != today:
            self._daily_cost = 0.0
            self._cost_date = today

        target_layer = TASK_LAYER_MAP.get(task_type, LLMLayer.FLASH)

        if self._daily_budget is not None:
            if self._daily_cost >= self._daily_budget:
                logger.warning(f'[LLM路由] 日预算已用尽 ({self._daily_cost:.2f}/{self._daily_budget:.2f})')
                if LLMLayer.FLASH in self._providers:
                    return self._providers[LLMLayer.FLASH]
                return None

            if self._daily_cost >= self._daily_budget * 0.8 and target_layer == LLMLayer.PREMIUM:
                logger.info('[LLM路由] 预算紧张，降级到 Flash')
                target_layer = LLMLayer.FLASH

        return self._providers.get(target_layer)

    def record_cost(self, tokens: int, provider: LLMProvider):
        """记录消耗"""
        cost = tokens / 1000 * provider.cost_per_1k_tokens
        self._daily_cost += cost

    @property
    def is_available(self) -> bool:
        self.init_providers()
        return bool(self._providers)

    @property
    def daily_cost(self) -> float:
        return self._daily_cost

    @property
    def daily_budget(self) -> float | None:
        return self._daily_budget


llm_router = LLMRouter()
