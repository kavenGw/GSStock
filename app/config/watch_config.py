"""盯盘助手配置"""
import os

WATCH_INTERVAL_MINUTES = int(os.environ.get('WATCH_INTERVAL_MINUTES', '1'))
