"""36kr新闻源 (RSS)"""
import logging
import hashlib
from datetime import datetime
from time import mktime
import feedparser
from app.services.news_sources.base import NewsSourceBase

logger = logging.getLogger(__name__)

KR36_RSS_URL = 'https://36kr.com/feed'


class Kr36Source(NewsSourceBase):
    name = '36kr'

    def fetch_latest(self) -> list[dict]:
        try:
            feed = feedparser.parse(KR36_RSS_URL)
            if feed.bozo and not feed.entries:
                logger.error(f'36kr RSS解析失败: {feed.bozo_exception}')
                return []
            results = []
            for entry in feed.entries[:20]:
                title = entry.get('title', '')
                source_id = entry.get('id') or hashlib.md5(title.encode()).hexdigest()
                published = entry.get('published_parsed')
                ts = mktime(published) if published else datetime.now().timestamp()
                results.append({
                    'content': title,
                    'source_id': str(source_id),
                    'display_time': ts,
                    'source_name': self.name,
                    'score': 1,
                })
            return results
        except Exception as e:
            logger.error(f'36kr获取失败: {e}')
            return []
