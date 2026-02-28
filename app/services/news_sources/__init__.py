"""新闻源注册"""
from app.services.news_sources.wallstreetcn import WallstreetcnSource
from app.services.news_sources.smolai import SmolAISource
from app.services.news_sources.cls import CLSSource
from app.services.news_sources.kr36 import Kr36Source

ALL_SOURCES = [
    WallstreetcnSource(),
    SmolAISource(),
    CLSSource(),
    Kr36Source(),
]
