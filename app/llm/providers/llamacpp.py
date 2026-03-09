"""llama-server (llama.cpp) 本地 Provider"""
import logging
import os
import time
import httpx
from app.llm.base import LLMProvider

logger = logging.getLogger(__name__)

LLAMA_SERVER_URL = os.environ.get('LLAMA_SERVER_URL', 'http://127.0.0.1:8080')
LLAMA_SERVER_ENABLED = os.environ.get('LLAMA_SERVER_ENABLED', 'false').lower() == 'true'
LLAMA_REQUEST_TIMEOUT = int(os.environ.get('LLM_REQUEST_TIMEOUT', '120'))
LLAMA_MAX_CONTEXT = int(os.environ.get('LLAMA_MAX_CONTEXT', '4096'))

_CONTEXT_RESERVE = 64
_REASONING_MULTIPLIER = 4


def _estimate_tokens(text: str) -> int:
    """粗略估算 token 数：中文≈1.5 token/字，ASCII≈0.4 token/字符"""
    cn_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    ascii_chars = len(text) - cn_chars
    return int(cn_chars * 1.5 + ascii_chars * 0.4)


class LlamaServerProvider(LLMProvider):
    name = "llama-server"
    model = "local"
    cost_per_1k_tokens = 0.0
    _model_ready = False

    def _wait_for_ready(self):
        """等待 llama-server 模型加载完成（首次调用时）"""
        if self._model_ready:
            return
        for i in range(60):
            try:
                resp = httpx.get(f'{LLAMA_SERVER_URL}/health', timeout=3)
                if resp.status_code == 200:
                    self._model_ready = True
                    logger.info('[llama-server] 模型已就绪')
                    return
                logger.info(f'[llama-server] 模型加载中... ({i+1}/60)')
            except Exception:
                logger.info(f'[llama-server] 等待连接... ({i+1}/60)')
            time.sleep(2)
        raise ConnectionError('llama-server 未能在 120 秒内就绪')

    def chat(self, messages: list[dict], temperature: float = 0.3, max_tokens: int = 500) -> str:
        self._wait_for_ready()
        input_tokens = sum(_estimate_tokens(m.get('content', '')) for m in messages)
        available = LLAMA_MAX_CONTEXT - input_tokens - _CONTEXT_RESERVE

        # 预检：推理模型需要足够空间（reasoning + content），不足则跳过让 FallbackProvider 走云端
        min_required = max_tokens * _REASONING_MULTIPLIER
        if available < min_required:
            raise ValueError(
                f'上下文不足(可用 {available}，需 {min_required})，跳过本地'
            )

        if available < max_tokens:
            if available > 100:
                logger.warning(f'[llama-server] 输入约 {input_tokens} tokens，max_tokens {max_tokens}→{available}')
                max_tokens = available
            else:
                last_user = next((m for m in reversed(messages) if m['role'] == 'user'), None)
                if last_user:
                    original_len = len(last_user['content'])
                    target_input = LLAMA_MAX_CONTEXT - max_tokens - _CONTEXT_RESERVE
                    other_tokens = input_tokens - _estimate_tokens(last_user['content'])
                    user_budget = max(200, target_input - other_tokens)
                    char_limit = int(user_budget / 1.0)
                    if char_limit < original_len:
                        last_user['content'] = last_user['content'][:char_limit] + '\n...(已截断)'
                        logger.warning(f'[llama-server] 输入过长，截断 user message {original_len}→{char_limit} 字符')

        effective_max_tokens = min(max_tokens * _REASONING_MULTIPLIER, available) if available > max_tokens else available

        try:
            response = httpx.post(
                f'{LLAMA_SERVER_URL}/v1/chat/completions',
                headers={'Content-Type': 'application/json'},
                json={
                    'messages': messages,
                    'temperature': temperature,
                    'max_tokens': effective_max_tokens,
                },
                timeout=LLAMA_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        except (httpx.ConnectError, httpx.RemoteProtocolError):
            self._model_ready = False
            logger.warning('[llama-server] 连接失败，等待重启...')
            self._wait_for_ready()
            response = httpx.post(
                f'{LLAMA_SERVER_URL}/v1/chat/completions',
                headers={'Content-Type': 'application/json'},
                json={
                    'messages': messages,
                    'temperature': temperature,
                    'max_tokens': effective_max_tokens,
                },
                timeout=LLAMA_REQUEST_TIMEOUT,
            )
            response.raise_for_status()
        data = response.json()
        content = data['choices'][0]['message']['content'].strip()
        if not content:
            finish_reason = data['choices'][0].get('finish_reason')
            reasoning = data['choices'][0]['message'].get('reasoning_content', '')
            logger.warning(f"[llama-server] 返回空内容, finish_reason={finish_reason}, reasoning={len(reasoning)}字符")
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
