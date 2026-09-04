"""同花顺（HiThink Fuyao）金融数据 API 底座

唯一碰 HTTP 的地方。成功判据是 HTTP 200 且信封 code == 0。
未配 HITHINK_FINANCE_API_KEY 时 is_available() 返回 False，上游分支全部跳过。
"""
import logging
import os
import threading

import requests

logger = logging.getLogger(__name__)

BASE_URL = 'https://fuyao.aicubes.cn'
ENV_KEY = 'HITHINK_FINANCE_API_KEY'
TIMEOUT = 15


class HithinkError(Exception):
    def __init__(self, message, code=None, request_id=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.request_id = request_id


def to_thscode(code: str) -> str:
    """任意形态 A 股代码 → thscode（600519.SH）。"""
    c = code.strip()
    up = c.upper()
    if up.endswith('.SH') or up.endswith('.SZ'):
        return up
    if up.endswith('.SS'):
        return f"{up[:-3]}.SH"
    if up.startswith('SH') or up.startswith('SZ'):
        return f"{up[2:]}.{up[:2]}"
    digits = ''.join(ch for ch in up if ch.isdigit())
    suffix = 'SH' if digits[:1] in ('6', '9') else 'SZ'
    return f"{digits}.{suffix}"


def from_thscode(thscode: str) -> str:
    """thscode → 裸 6 位代码。"""
    return thscode.strip().upper().split('.')[0]


class HithinkClient:
    def __init__(self):
        self._session = requests.Session()

    @property
    def api_key(self):
        return os.environ.get(ENV_KEY, '').strip()

    def is_available(self) -> bool:
        return bool(self.api_key)

    def get(self, path: str, params: dict) -> dict:
        if not self.is_available():
            raise HithinkError(f'{ENV_KEY} 未配置')

        url = f"{BASE_URL}{path}"
        resp = self._session.get(
            url, params=params,
            headers={'X-api-key': self.api_key},
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            raise HithinkError(f'HTTP {resp.status_code}', code=resp.status_code)

        payload = resp.json()
        code = payload.get('code')
        if code != 0:
            raise HithinkError(
                payload.get('message', '未知错误'),
                code=code,
                request_id=payload.get('request_id'),
            )
        return payload.get('data') or {}


_client = None
_lock = threading.Lock()


def get_client() -> HithinkClient:
    global _client
    if _client is None:
        with _lock:
            if _client is None:
                _client = HithinkClient()
    return _client
