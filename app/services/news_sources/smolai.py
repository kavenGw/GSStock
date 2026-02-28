"""smol.ai AI新闻源 (RSS)"""
import logging
import hashlib
from datetime import datetime
from time import mktime
import feedparser
from app.services.news_sources.base import NewsSourceBase

logger = logging.getLogger(__name__)

SMOLAI_RSS_URL = 'https://news.smol.ai/rss.xml'


class SmolAISource(NewsSourceBase):
    name = 'smolai'

    def fetch_latest(self) -> list[dict]:
        try:
            feed = feedparser.parse(SMOLAI_RSS_URL)
            if feed.bozo and not feed.entries:
                logger.warning(f'smol.ai RSS解析异常: {feed.bozo_exception}')
                return []
            results = []
            for entry in feed.entries[:20]:
                title = entry.get('title', '')
                summary = entry.get('summary', '')
                content = f"{title}. {summary}" if summary else title
                source_id = entry.get('id') or hashlib.md5(title.encode()).hexdigest()
                published = entry.get('published_parsed')
                ts = mktime(published) if published else datetime.now().timestamp()
                results.append({
                    'content': content,
                    'source_id': str(source_id),
                    'display_time': ts,
                    'source_name': self.name,
                    'score': 1,
                })
            return results
        except Exception as e:
            logger.error(f'smol.ai获取失败: {e}')
            return []
