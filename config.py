import os
import secrets
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))

# 加载 .env 文件
load_dotenv(os.path.join(basedir, '.env'))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'data', 'stock.db')
    SQLALCHEMY_BINDS = {
        'private': os.environ.get('PRIVATE_DATABASE_URL') or \
            'sqlite:///' + os.path.join(basedir, 'data', 'private.db')
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False

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
