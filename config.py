import os
import secrets
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))

# 加载 .env 文件
load_dotenv(os.path.join(basedir, '.env'))


def get_database_uri():
    """获取数据库连接URI

    优先级：
    1. 如果配置了 COCKROACH_URL，使用 CockroachDB 云数据库
    2. 否则使用本地 SQLite 数据库
    """
    cockroach_url = os.environ.get('COCKROACH_URL')
    if cockroach_url:
        return cockroach_url
    return 'sqlite:///' + os.path.join(basedir, 'data', 'stock.db')


def is_cockroach_configured():
    """检查是否配置了 CockroachDB"""
    return bool(os.environ.get('COCKROACH_URL'))


def get_local_stock_db_path():
    """获取本地 stock.db 路径"""
    return os.path.join(basedir, 'data', 'stock.db')


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or get_database_uri()
    SQLALCHEMY_BINDS = {
        'private': os.environ.get('PRIVATE_DATABASE_URL') or \
            'sqlite:///' + os.path.join(basedir, 'data', 'private.db')
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # CockroachDB 配置
    COCKROACH_CONFIGURED = is_cockroach_configured()
    LOCAL_STOCK_DB_PATH = get_local_stock_db_path()

    # 只读模式：不从服务器获取数据，不修改 stock.db，但可以修改 private.db
    READONLY_MODE = os.environ.get('READONLY_MODE', '').lower() in ('1', 'true', 'yes')
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB
    LOG_DIR = os.path.join(basedir, 'logs')

    # OCR 配置
    OCR_MAX_SIZE = 2048          # 图片最大边长（像素）
    OCR_TIMEOUT = 60             # 识别超时（秒）
    OCR_USE_GPU = True           # 是否启用 GPU
    OCR_GPU_BACKEND = 'auto'     # 'auto', 'cuda', 'directml', 'cpu'
