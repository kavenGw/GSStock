"""新闻源基类"""
from abc import ABC, abstractmethod


class NewsSourceBase(ABC):
    name: str = ''

    @abstractmethod
    def fetch_latest(self) -> list[dict]:
        """获取最新新闻，返回统一格式:
        [{
            'content': str,
            'source_id': str,
            'display_time': float,
            'source_name': str,
            'score': int,
        }]
        """
        ...
