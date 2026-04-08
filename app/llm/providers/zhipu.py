"""智谱 GLM Provider"""
import logging
import os
import time
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


_MAX_RETRIES = 3
_BACKOFF_BASE = 2  # 2s, 4s, 8s


def _call_zhipu(model: str, messages: list[dict], temperature: float, max_tokens: int) -> str:
    """调用智谱 API（带限流 + 429 重试）"""
    if not ZHIPU_API_KEY:
        raise ValueError('ZHIPU_API_KEY 未配置')

    from app.llm.rate_limiter import rate_limiter

    payload = {
        'model': model,
        'messages': messages,
        'temperature': temperature,
        'max_tokens': max_tokens,
    }
    headers = {
        'Authorization': f'Bearer {ZHIPU_API_KEY}',
        'Content-Type': 'application/json',
    }

    for attempt in range(1, _MAX_RETRIES + 1):
        rate_limiter.acquire()

        response = httpx.post(
            f'{ZHIPU_BASE_URL}/chat/completions',
            headers=headers,
            json=payload,
            timeout=LLM_REQUEST_TIMEOUT,
        )

        if response.status_code == 429:
            body_text = response.text[:300] if response.text else ''
            try:
                err_data = response.json().get('error', {})
                err_code = err_data.get('code', '')
            except Exception:
                err_code = ''

            if err_code == '1113':
                raise RuntimeError(f'[智谱API] 余额不足，请充值 | {body_text}')

            delay = _BACKOFF_BASE ** attempt
            retry_after = response.headers.get('Retry-After', '')
            logger.warning(
                f'[智谱API] {model} 429 限流，{delay}s 后重试 ({attempt}/{_MAX_RETRIES})'
                f' | Retry-After={retry_after} | body={body_text}'
            )
            if retry_after and retry_after.isdigit():
                delay = max(delay, int(retry_after))
            time.sleep(delay)
            continue

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

    raise RuntimeError(f'[智谱API] {model} 连续 {_MAX_RETRIES} 次 429 限流，放弃请求')
