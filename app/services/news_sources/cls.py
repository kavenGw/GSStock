"""财联社新闻源"""
import logging
import requests
from app.services.news_sources.base import NewsSourceBase

logger = logging.getLogger(__name__)

CLS_API = 'https://www.cls.cn/nodeapi/telegraphList'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.cls.cn/telegraph',
}
PARAMS = {
    'app': 'CailianpressWeb',
    'os': 'web',
    'sv': '8.4.6',
    'refresh_type': '1',
    'rn': '20',
}


class CLSSource(NewsSourceBase):
    name = 'cls'

    def fetch_latest(self) -> list[dict]:
        resp = requests.get(CLS_API, params=PARAMS, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        items = data.get('data', {}).get('roll_data', [])
        results = []
        for item in items[:20]:
            content = item.get('content', '') or item.get('title', '')
            if not content:
                continue
            results.append({
                'content': content,
                'source_id': str(item.get('id', '')),
                'display_time': item.get('ctime', 0),
                'source_name': self.name,
                'score': 2 if item.get('level') == 'B' else 1,
            })
        return results
