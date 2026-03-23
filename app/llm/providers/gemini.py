"""Google Gemini Provider — 用于公司识别"""
import logging
import os
import httpx
from app.llm.base import LLMProvider

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
GEMINI_BASE_URL = 'https://generativelanguage.googleapis.com/v1beta'
LLM_REQUEST_TIMEOUT = int(os.environ.get('LLM_REQUEST_TIMEOUT', '300'))


class GeminiFlashProvider(LLMProvider):
    name = "gemini-flash"
    model = "gemini-2.0-flash"
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
    """调用 Gemini API"""
    if not GEMINI_API_KEY:
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

    response = httpx.post(
        f'{GEMINI_BASE_URL}/models/{model}:generateContent',
        params={'key': GEMINI_API_KEY},
        headers={'Content-Type': 'application/json'},
        json=body,
        timeout=LLM_REQUEST_TIMEOUT,
    )
    response.raise_for_status()
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
