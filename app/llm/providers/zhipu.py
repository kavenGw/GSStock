"""智谱 GLM Provider"""
import logging
import os
import httpx
from app.llm.base import LLMProvider

logger = logging.getLogger(__name__)

ZHIPU_API_KEY = os.environ.get('ZHIPU_API_KEY', '')
ZHIPU_BASE_URL = 'https://open.bigmodel.cn/api/paas/v4'
LLM_REQUEST_TIMEOUT = int(os.environ.get('LLM_REQUEST_TIMEOUT', '300'))


class ZhipuLiteProvider(LLMProvider):
    name = "zhipu-lite"
    model = "glm-4-flash"
    cost_per_1k_tokens = 0.0

    def chat(self, messages: list[dict], temperature: float = 0.3, max_tokens: int = 500) -> str:
        return _call_zhipu(self.model, messages, temperature, max_tokens)


class ZhipuFlashProvider(LLMProvider):
    name = "zhipu-flash"
    model = "glm-5-turbo"
    cost_per_1k_tokens = 0.0001

    def chat(self, messages: list[dict], temperature: float = 0.3, max_tokens: int = 500) -> str:
        return _call_zhipu(self.model, messages, temperature, max_tokens)


class ZhipuPremiumProvider(LLMProvider):
    name = "zhipu-premium"
    model = "glm-5"
    cost_per_1k_tokens = 0.01

    def chat(self, messages: list[dict], temperature: float = 0.3, max_tokens: int = 500) -> str:
        return _call_zhipu(self.model, messages, temperature, max_tokens)


REASONING_MODELS = {'glm-5', 'glm-5-turbo', 'glm-5.1'}
REASONING_MIN_TOKENS = 2000


def _call_zhipu(model: str, messages: list[dict], temperature: float, max_tokens: int) -> str:
    """调用智谱 API"""
    if not ZHIPU_API_KEY:
        raise ValueError('ZHIPU_API_KEY 未配置')

    actual_max_tokens = max(max_tokens, REASONING_MIN_TOKENS) if model in REASONING_MODELS else max_tokens

    response = httpx.post(
        f'{ZHIPU_BASE_URL}/chat/completions',
        headers={
            'Authorization': f'Bearer {ZHIPU_API_KEY}',
            'Content-Type': 'application/json',
        },
        json={
            'model': model,
            'messages': messages,
            'temperature': temperature,
            'max_tokens': actual_max_tokens,
        },
        timeout=LLM_REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    choice = data['choices'][0]
    msg = choice['message']
    finish_reason = choice.get('finish_reason')
    usage = data.get('usage', {})
    content = (msg.get('content') or '').strip()
    if not content:
        logger.warning(
            f"[智谱API] {model} 返回空内容, finish_reason={finish_reason}, "
            f"usage={usage}, response={data}"
        )
        raise ValueError(f'智谱API返回空内容 (finish_reason={finish_reason})')
    return content
