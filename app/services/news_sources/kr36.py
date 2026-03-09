"""36kr新闻源 (RSS)"""
import logging
import hashlib
from datetime import datetime
from time import mktime
import requests
import feedparser
from app.services.news_sources.base import NewsSourceBase

logger = logging.getLogger(__name__)

KR36_RSS_URL = 'https://36kr.com/feed'


class Kr36Source(NewsSourceBase):
    name = '36kr'

    def fetch_latest(self) -> list[dict]:
        resp = requests.get(KR36_RSS_URL, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'application/rss+xml, application/xml, text/xml, */*',
        }, timeout=15)
        feed = feedparser.parse(resp.content)
        if feed.bozo and not feed.entries:
            raise ValueError(f'RSS解析失败: {feed.bozo_exception}')
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
