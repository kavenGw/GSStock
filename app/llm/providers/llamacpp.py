"""llama-server (llama.cpp) 本地 Provider"""
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
            headers={'Content-Type': 'application/json'},
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
    if not LLAMA_SERVER_ENABLED:
        return False
    try:
        resp = httpx.get(f'{LLAMA_SERVER_URL}/health', timeout=3)
        return resp.status_code == 200
    except Exception:
        return False
