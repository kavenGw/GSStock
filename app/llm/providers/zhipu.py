"""智谱 GLM Provider"""
import logging
import os
import httpx
from app.llm.base import LLMProvider

logger = logging.getLogger(__name__)

ZHIPU_API_KEY = os.environ.get('ZHIPU_API_KEY', '')
ZHIPU_BASE_URL = 'https://open.bigmodel.cn/api/paas/v4'
LLM_REQUEST_TIMEOUT = int(os.environ.get('LLM_REQUEST_TIMEOUT', '300'))


class ZhipuFlashProvider(LLMProvider):
    name = "zhipu-flash"
    model = "glm-4-flash"
    cost_per_1k_tokens = 0.0001

    def chat(self, messages: list[dict], temperature: float = 0.3, max_tokens: int = 500) -> str:
        return _call_zhipu(self.model, messages, temperature, max_tokens)


class ZhipuPremiumProvider(LLMProvider):
    name = "zhipu-premium"
    model = "glm-4"
    cost_per_1k_tokens = 0.01

    def chat(self, messages: list[dict], temperature: float = 0.3, max_tokens: int = 500) -> str:
        return _call_zhipu(self.model, messages, temperature, max_tokens)


def _call_zhipu(model: str, messages: list[dict], temperature: float, max_tokens: int) -> str:
    """调用智谱 API"""
    if not ZHIPU_API_KEY:
        raise ValueError('ZHIPU_API_KEY 未配置')

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
            'max_tokens': max_tokens,
        },
        timeout=LLM_REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    data = response.json()
    content = data['choices'][0]['message']['content'].strip()
    if not content:
        logger.warning(f"[智谱API] {model} 返回空内容, finish_reason={data['choices'][0].get('finish_reason')}")
        raise ValueError('智谱API返回空内容')
    return content
