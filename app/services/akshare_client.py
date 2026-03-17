import logging
import os
from functools import wraps

import akshare as _ak

logger = logging.getLogger(__name__)

_last_proxy_fingerprint = None


def _get_proxy_env() -> dict:
    return {
        "http_proxy": os.getenv("http_proxy", ""),
        "https_proxy": os.getenv("https_proxy", ""),
        "HTTP_PROXY": os.getenv("HTTP_PROXY", ""),
        "HTTPS_PROXY": os.getenv("HTTPS_PROXY", ""),
        "no_proxy": os.getenv("no_proxy", ""),
        "NO_PROXY": os.getenv("NO_PROXY", ""),
    }


def _proxy_fingerprint(env: dict) -> tuple:
    return tuple(sorted(env.items()))


def log_proxy_context(api_name: str | None = None) -> None:
    global _last_proxy_fingerprint

    env = _get_proxy_env()
    fingerprint = _proxy_fingerprint(env)

    if fingerprint != _last_proxy_fingerprint:
        _last_proxy_fingerprint = fingerprint
        logger.info(
            "[数据服务.AKShare] proxy env | api=%s | http_proxy=%s | https_proxy=%s | HTTP_PROXY=%s | HTTPS_PROXY=%s | no_proxy=%s | NO_PROXY=%s",
            api_name or "-",
            env["http_proxy"],
            env["https_proxy"],
            env["HTTP_PROXY"],
            env["HTTPS_PROXY"],
            env["no_proxy"],
            env["NO_PROXY"],
        )

    logger.debug(
        "[数据服务.AKShare] proxy preflight | api=%s",
        api_name or "-",
    )


class _AkshareProxy:
    def __getattr__(self, name):
        attr = getattr(_ak, name)
        if callable(attr):
            @wraps(attr)
            def wrapper(*args, **kwargs):
                log_proxy_context(api_name=name)
                return attr(*args, **kwargs)

            return wrapper
        return attr


ak = _AkshareProxy()
