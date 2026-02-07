import os
import secrets

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(32)
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'data', 'stock.db')
    SQLALCHEMY_BINDS = {
        'private': os.environ.get('PRIVATE_DATABASE_URL') or \
            'sqlite:///' + os.path.join(basedir, 'data', 'private.db')
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB
    LOG_DIR = os.path.join(basedir, 'logs')

    # OCR 配置
    OCR_MAX_SIZE = 2048          # 图片最大边长（像素）
    OCR_TIMEOUT = 60             # 识别超时（秒）
    OCR_USE_GPU = True           # 是否启用 GPU
    OCR_GPU_BACKEND = 'auto'     # 'auto', 'cuda', 'directml', 'cpu'
