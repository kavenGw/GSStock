"""Google Gemini Provider — 用于公司识别，支持多 API Key 轮转"""
import logging
import os
import time
import threading
import httpx
from app.llm.base import LLMProvider

logger = logging.getLogger(__name__)

GEMINI_BASE_URL = 'https://generativelanguage.googleapis.com/v1beta'
LLM_REQUEST_TIMEOUT = int(os.environ.get('LLM_REQUEST_TIMEOUT', '300'))


class _KeyPool:
    """多 API Key 轮转池，429 时自动切换下一个 key"""

    def __init__(self):
        raw = os.environ.get('GEMINI_API_KEY', '')
        self._keys = [k.strip() for k in raw.split(',') if k.strip()]
        self._index = 0
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        return len(self._keys) > 0

    @property
    def size(self) -> int:
        return len(self._keys)

    def next(self) -> str:
        with self._lock:
            if not self._keys:
                raise ValueError('GEMINI_API_KEY 未配置')
            key = self._keys[self._index % len(self._keys)]
            self._index += 1
            return key


_key_pool = _KeyPool()


class GeminiFlashProvider(LLMProvider):
    name = "gemini-flash"
    model = "gemini-2.5-flash-lite"
    cost_per_1k_tokens = 0.0001

    def chat(self, messages: list[dict], temperature: float = 0.3, max_tokens: int = 500) -> str:
        return _call_gemini(self.model, messages, temperature, max_tokens)


def _convert_messages(messages: list[dict]) -> tuple[str | None, list[dict]]:
    """将 OpenAI 格式的 messages 转换为 Gemini 格式"""
    system_instruction = None
    contents = []

    for msg in messages:
        role = msg['role']
        text = msg['content']

        if role == 'system':
            system_instruction = text
        elif role == 'assistant':
            contents.append({'role': 'model', 'parts': [{'text': text}]})
        else:
            contents.append({'role': 'user', 'parts': [{'text': text}]})

    return system_instruction, contents


def _call_gemini(model: str, messages: list[dict], temperature: float, max_tokens: int) -> str:
    """调用 Gemini API，多 key 轮转 + 429 重试"""
    if not _key_pool.available:
        raise ValueError('GEMINI_API_KEY 未配置')

    system_instruction, contents = _convert_messages(messages)

    body = {
        'contents': contents,
        'generationConfig': {
            'temperature': temperature,
            'maxOutputTokens': max_tokens,
        },
    }
    if system_instruction:
        body['systemInstruction'] = {'parts': [{'text': system_instruction}]}

    RETRYABLE_STATUS = {429, 500, 502, 503, 504}

    # 最多尝试所有 key，每个 key 重试一次
    max_attempts = _key_pool.size * 2
    last_error = None
    for attempt in range(max_attempts):
        api_key = _key_pool.next()
        key_hint = api_key[-6:]
        try:
            response = httpx.post(
                f'{GEMINI_BASE_URL}/models/{model}:generateContent',
                params={'key': api_key},
                headers={'Content-Type': 'application/json'},
                json=body,
                timeout=LLM_REQUEST_TIMEOUT,
            )
            if response.status_code in RETRYABLE_STATUS:
                logger.warning(f'[GeminiAPI] key ...{key_hint} {response.status_code}，切换下一个 key ({attempt + 1}/{max_attempts})')
                time.sleep(3 if response.status_code != 429 else 2)
                continue
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            last_error = e
            if e.response.status_code in RETRYABLE_STATUS:
                continue
            raise
        except Exception:
            raise

        data = response.json()
        candidates = data.get('candidates', [])
        if not candidates:
            logger.warning(f'[GeminiAPI] {model} 无候选结果')
            raise ValueError('Gemini API 返回空结果')

        parts = candidates[0].get('content', {}).get('parts', [])
        content = ''.join(p.get('text', '') for p in parts).strip()
        if not content:
            finish_reason = candidates[0].get('finishReason', 'unknown')
            logger.warning(f'[GeminiAPI] {model} 返回空内容, finishReason={finish_reason}')
            raise ValueError('Gemini API 返回空内容')

        return content

    logger.error(f'[GeminiAPI] 所有 key ({_key_pool.size}个) 重试耗尽')
    if last_error:
        raise last_error
    raise ValueError(f'所有 Gemini API key 重试耗尽')
