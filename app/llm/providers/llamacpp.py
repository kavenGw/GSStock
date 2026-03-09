"""llama-server (llama.cpp) 本地 Provider"""
import logging
import os
import re
import threading
import time
import httpx
from app.llm.base import LLMProvider

logger = logging.getLogger(__name__)

LLAMA_SERVER_URL = os.environ.get('LLAMA_SERVER_URL', 'http://127.0.0.1:8080')
LLAMA_SERVER_ENABLED = os.environ.get('LLAMA_SERVER_ENABLED', 'false').lower() == 'true'
LLAMA_REQUEST_TIMEOUT = int(os.environ.get('LLM_REQUEST_TIMEOUT', '120'))
LLAMA_MAX_CONTEXT = int(os.environ.get('LLAMA_MAX_CONTEXT', '4096'))

_CONTEXT_RESERVE = 64
_REASONING_MULTIPLIER = 6
_MAX_INPUT_RATIO = 0.4


def _estimate_tokens(text: str) -> int:
    """粗略估算 token 数：中文≈1.5 token/字，ASCII≈0.4 token/字符"""
    cn_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    ascii_chars = len(text) - cn_chars
    return int(cn_chars * 1.5 + ascii_chars * 0.4)


def _extract_from_reasoning(reasoning: str) -> str | None:
    """从 reasoning_content 中提取 </think> 后的实际回答"""
    m = re.search(r'</think>\s*(.+)', reasoning, re.DOTALL)
    if m:
        answer = m.group(1).strip()
        if answer:
            return answer
    return None


class LlamaServerProvider(LLMProvider):
    name = "llama-server"
    model = "local"
    cost_per_1k_tokens = 0.0
    _model_ready = False
    _lock = threading.Lock()

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

        # 硬性输入上限：输入超过上下文的 40% 直接跳过，留足空间给推理+输出
        max_input = int(LLAMA_MAX_CONTEXT * _MAX_INPUT_RATIO)
        if input_tokens > max_input:
            raise ValueError(
                f'输入过大({input_tokens}>{max_input} tokens)，跳过本地'
            )

        # 推理模型需要足够空间（reasoning + content）
        min_required = max_tokens * _REASONING_MULTIPLIER
        if available < min_required:
            raise ValueError(
                f'上下文不足(可用 {available}，需 {min_required})，跳过本地'
            )

        effective_max_tokens = min(max_tokens * _REASONING_MULTIPLIER, available)

        # 串行化请求，避免并发竞争 llama-server 有限的 slot
        with self._lock:
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
            # 推理模型可能把答案混在 reasoning_content 的 </think> 之后
            reasoning = data['choices'][0]['message'].get('reasoning_content', '')
            extracted = _extract_from_reasoning(reasoning)
            if extracted:
                logger.info(f'[llama-server] content 为空，从 reasoning 中提取到 {len(extracted)} 字符')
                return extracted
            finish_reason = data['choices'][0].get('finish_reason')
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
