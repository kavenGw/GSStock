"""华尔街见闻新闻源"""
import logging
import requests
from app.config.news_config import WALLSTREETCN_API, WALLSTREETCN_CHANNEL
from app.services.news_sources.base import NewsSourceBase

logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}


class WallstreetcnSource(NewsSourceBase):
    name = 'wallstreetcn'

    def fetch_latest(self) -> list[dict]:
        params = {
            'channel': WALLSTREETCN_CHANNEL,
            'client': 'pc',
            'limit': 20,
        }
        resp = requests.get(WALLSTREETCN_API, params=params, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get('code') != 20000:
            raise ValueError(f'API异常: {data.get("message")}')
        items = data.get('data', {}).get('items', [])
        return [{
            'content': item.get('content_text', ''),
            'source_id': str(item.get('id', '')),
            'display_time': item.get('display_time', 0),
            'source_name': self.name,
            'score': item.get('score', 1),
        } for item in items if item.get('id')]
