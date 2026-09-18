"""财联社新闻源

2026-09 起 /nodeapi/telegraphList 下线，改走 /v1/roll/get_roll_list，
请求须带 sign = md5(sha1(按 key 排序的 k=v&k=v，不做 URL 编码))，与前端 _app chunk 一致。
"""
import hashlib
import logging
import requests
from app.services.news_sources.base import NewsSourceBase

logger = logging.getLogger(__name__)

CLS_API = 'https://www.cls.cn/v1/roll/get_roll_list'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Referer': 'https://www.cls.cn/telegraph',
}
PARAMS = {
    'app': 'CailianpressWeb',
    'os': 'web',
    'sv': '8.7.9',
    'refresh_type': '1',
    'rn': '20',
    'last_time': '',
}


def _sign(params: dict) -> str:
    qs = '&'.join(f'{k}={params[k]}' for k in sorted(params))
    return hashlib.md5(hashlib.sha1(qs.encode()).hexdigest().encode()).hexdigest()


class CLSSource(NewsSourceBase):
    name = 'cls'

    def fetch_latest(self) -> list[dict]:
        params = dict(sorted(PARAMS.items()))
        params['sign'] = _sign(params)
        resp = requests.get(CLS_API, params=params, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if str(data.get('errno', 0)) != '0':
            raise ValueError(f'API异常: {data.get("msg")}')
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
