"""新闻推送去重：跨源文本相似度过滤"""
import logging
import re
import threading
from datetime import datetime, timedelta
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

DEDUP_WINDOW_MINUTES = 30
SIMILARITY_THRESHOLD = 0.4


class NewsDeduplicator:
    _instance = None
    _init_guard = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._init_guard:
            return
        self._init_guard = True
        self._pushed_buffer: list[tuple[datetime, str]] = []
        self._lock = threading.Lock()

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r'[\s\W]+', '', text)

    def _is_similar(self, text_a: str, text_b: str) -> bool:
        a = self._normalize(text_a)
        b = self._normalize(text_b)
        if not a or not b:
            return False
        return SequenceMatcher(None, a, b).ratio() >= SIMILARITY_THRESHOLD

    def filter_duplicates(self, items: list, content_key) -> list:
        with self._lock:
            now = datetime.now()
            cutoff = now - timedelta(minutes=DEDUP_WINDOW_MINUTES)
            self._pushed_buffer = [(t, c) for t, c in self._pushed_buffer if t > cutoff]

            groups: list[list] = []
            for item in items:
                content = content_key(item)
                merged = False
                for group in groups:
                    representative = content_key(group[0])
                    if self._is_similar(content, representative):
                        group.append(item)
                        merged = True
                        break
                if not merged:
                    groups.append([item])

            deduplicated = []
            for group in groups:
                best = max(group, key=lambda x: len(content_key(x)))
                deduplicated.append(best)

            result = []
            for item in deduplicated:
                content = content_key(item)
                is_dup = any(self._is_similar(content, pushed_content)
                            for _, pushed_content in self._pushed_buffer)
                if not is_dup:
                    result.append(item)
                    self._pushed_buffer.append((now, content))

            filtered_count = len(items) - len(result)
            if filtered_count > 0:
                logger.info(f'[去重] 输入 {len(items)} 条，过滤 {filtered_count} 条重复，推送 {len(result)} 条')

            return result


news_deduplicator = NewsDeduplicator()
