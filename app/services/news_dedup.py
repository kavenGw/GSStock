"""新闻推送去重：跨源文本相似度 + 特征指纹双通道过滤"""
import logging
import os
import re
import threading
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from typing import NamedTuple


class PushedRecord(NamedTuple):
    timestamp: datetime
    content: str
    fingerprint: frozenset

logger = logging.getLogger(__name__)

DEDUP_WINDOW_MINUTES = int(os.getenv('NEWS_DEDUP_WINDOW_MINUTES', '1440'))
SIMILARITY_THRESHOLD = 0.4


class NewsDeduplicator:
    _instance = None
    _init_guard = False

    _PREFIX_PATTERNS = [
        re.compile(r'^(财联社|每经|证券时报|新华社|央视)\d{1,2}月\d{1,2}日(电|讯|消息)[，,\s]*'),
        re.compile(r'^据.{2,10}(报道|消息|透露)[，,\s]*'),
        re.compile(r'^【[^】]+】\s*'),
    ]

    _AMOUNT_RE = re.compile(r'\d+\.?\d*\s*[百千万亿]+[美韩日欧]?[元圆币]|\$[\d.]+[BMK]?')
    _DATE_RE = re.compile(r'\d{4}年|[一二三四1-4]季[度报]|Q[1-4]|[上下]半年|半年报|年报')

    _ENTITY_TTL = timedelta(hours=1)

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._init_guard:
            return
        self._init_guard = True
        self._pushed_buffer: list[PushedRecord] = []
        self._lock = threading.Lock()
        self._entity_re: re.Pattern | None = None
        self._entity_cache_time: datetime | None = None

    @staticmethod
    def _normalize(text: str) -> str:
        return re.sub(r'[\s\W]+', '', text)

    @classmethod
    def _strip_prefix(cls, text: str) -> str:
        for pat in cls._PREFIX_PATTERNS:
            text = pat.sub('', text)
        return text

    def _get_entity_re(self) -> re.Pattern | None:
        now = datetime.now()
        if self._entity_re is not None and self._entity_cache_time and now - self._entity_cache_time < self._ENTITY_TTL:
            return self._entity_re
        try:
            from app.models.news import CompanyKeyword
            from app.models.stock import Stock
            names = set()
            for c in CompanyKeyword.query.filter_by(is_active=True).all():
                if len(c.name) >= 2:
                    names.add(c.name)
            for s in Stock.query.all():
                if len(s.stock_name) >= 2:
                    names.add(s.stock_name)
            if names:
                pattern = '|'.join(re.escape(n) for n in sorted(names, key=len, reverse=True))
                self._entity_re = re.compile(pattern)
            else:
                self._entity_re = None
            self._entity_cache_time = now
        except Exception:
            logger.debug('[去重] 实体名加载失败，跳过实体匹配')
            self._entity_re = None
        return self._entity_re

    def _extract_fingerprint(self, text: str) -> frozenset:
        cleaned = self._strip_prefix(text)
        features = set()
        entity_re = self._get_entity_re()
        if entity_re:
            features.update(entity_re.findall(cleaned))
        features.update(self._AMOUNT_RE.findall(cleaned))
        features.update(self._DATE_RE.findall(cleaned))
        return frozenset(features)

    def _is_fingerprint_match(self, fp_a: frozenset, fp_b: frozenset) -> bool:
        if len(fp_a) < 2 or len(fp_b) < 2:
            return False
        intersection = fp_a & fp_b
        union = fp_a | fp_b
        if len(union) < 3 or len(intersection) < 2:
            return False
        jaccard = len(intersection) / len(union)
        return jaccard >= 0.5

    def _is_text_similar(self, text_a: str, text_b: str) -> bool:
        a = self._normalize(text_a)
        b = self._normalize(text_b)
        if not a or not b:
            return False
        return SequenceMatcher(None, a, b).ratio() >= SIMILARITY_THRESHOLD

    def _is_duplicate(self, text_a: str, fp_a: frozenset,
                      text_b: str, fp_b: frozenset) -> tuple[bool, str]:
        """返回 (是否重复, 匹配方式: 'text'|'fingerprint'|'')"""
        if self._is_text_similar(text_a, text_b):
            return True, 'text'
        if self._is_fingerprint_match(fp_a, fp_b):
            return True, 'fingerprint'
        return False, ''

    def filter_duplicates(self, items: list, content_key) -> list:
        with self._lock:
            now = datetime.now()
            cutoff = now - timedelta(minutes=DEDUP_WINDOW_MINUTES)
            self._pushed_buffer = [r for r in self._pushed_buffer if r.timestamp > cutoff]

            item_data = []
            for item in items:
                content = content_key(item)
                fp = self._extract_fingerprint(content)
                item_data.append((item, content, fp))

            # 批内分组去重
            groups: list[list[tuple]] = []
            for entry in item_data:
                _, content, fp = entry
                merged = False
                for group in groups:
                    _, rep_content, rep_fp = group[0]
                    is_dup, _ = self._is_duplicate(content, fp, rep_content, rep_fp)
                    if is_dup:
                        group.append(entry)
                        merged = True
                        break
                if not merged:
                    groups.append([entry])

            deduplicated = []
            for group in groups:
                best = max(group, key=lambda e: len(e[1]))
                deduplicated.append(best)

            # 跨历史去重
            result = []
            text_filtered = 0
            fp_filtered = 0
            for item, content, fp in deduplicated:
                is_dup = False
                for r in self._pushed_buffer:
                    dup, method = self._is_duplicate(content, fp, r.content, r.fingerprint)
                    if dup:
                        is_dup = True
                        if method == 'text':
                            text_filtered += 1
                        else:
                            fp_filtered += 1
                        logger.debug(f'[去重] {method}命中: {fp} ↔ {r.fingerprint}')
                        break
                if not is_dup:
                    result.append(item)
                    self._pushed_buffer.append(PushedRecord(now, content, fp))

            batch_filtered = len(items) - len(deduplicated)
            total_filtered = len(items) - len(result)
            if total_filtered > 0:
                logger.info(
                    f'[去重] 输入 {len(items)} 条，过滤 {total_filtered} 条'
                    f'（批内合并{batch_filtered}，文本相似{text_filtered}，指纹匹配{fp_filtered}），'
                    f'推送 {len(result)} 条'
                )

            return result


news_deduplicator = NewsDeduplicator()
