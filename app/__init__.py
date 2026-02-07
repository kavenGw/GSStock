import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def migrate_position_table():
    """迁移 positions 表：cost_price -> total_amount"""
    from sqlalchemy import inspect, text

    private_engine = db.get_engine(bind='private')
    inspector = inspect(private_engine)

    try:
        columns = [col['name'] for col in inspector.get_columns('positions')]
    except Exception:
        return

    if 'total_amount' in columns:
        return

    if 'cost_price' in columns:
        logging.info("迁移 positions 表: cost_price -> total_amount")
        with private_engine.connect() as conn:
            conn.execute(text('ALTER TABLE positions ADD COLUMN total_amount FLOAT'))
            conn.execute(text('UPDATE positions SET total_amount = cost_price * quantity'))
            conn.commit()
        logging.info("positions 表迁移完成")


def setup_logging(app):
    """配置应用日志系统"""
    log_dir = app.config.get('LOG_DIR', 'data/logs')
    os.makedirs(log_dir, exist_ok=True)

    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # app.log - 所有日志
    file_handler = logging.FileHandler(
        os.path.join(log_dir, 'app.log'),
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # error.log - 仅错误
    error_handler = logging.FileHandler(
        os.path.join(log_dir, 'error.log'),
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    # 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # 配置根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_handler)
    root_logger.addHandler(console_handler)

    # 抑制 yfinance 关于退市股票的错误日志
    logging.getLogger('yfinance').setLevel(logging.CRITICAL)


def create_app(config_class=None):
    app = Flask(__name__)

    if config_class is None:
        from config import Config
        config_class = Config

    app.config.from_object(config_class)

    # 确保必要目录存在
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.dirname(app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')), exist_ok=True)

    setup_logging(app)

    db.init_app(app)

    from app.services.migration import check_migration_needed, migrate_to_dual_db, cleanup_legacy_tables, get_db_paths
    if check_migration_needed(app):
        logging.info("检测到需要数据迁移，开始执行...")
        migrate_to_dual_db(app)
        logging.info("数据迁移完成")
    else:
        stock_db_path, _ = get_db_paths(app)
        cleanup_legacy_tables(stock_db_path)

    from app.routes import main_bp, position_bp, advice_bp, category_bp, trade_bp, wyckoff_bp, stock_bp, daily_record_bp, profit_bp, rebalance_bp, heavy_metals_bp, preload_bp, alert_bp, briefing_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(position_bp)
    app.register_blueprint(advice_bp)
    app.register_blueprint(category_bp)
    app.register_blueprint(trade_bp)
    app.register_blueprint(wyckoff_bp)
    app.register_blueprint(stock_bp)
    app.register_blueprint(daily_record_bp)
    app.register_blueprint(profit_bp)
    app.register_blueprint(rebalance_bp)
    app.register_blueprint(heavy_metals_bp)
    app.register_blueprint(preload_bp)
    app.register_blueprint(alert_bp)
    app.register_blueprint(briefing_bp)

    with app.app_context():
        from app.models import Position, Advice, Category, StockCategory, Trade, Settlement, WyckoffReference, WyckoffAnalysis, Stock, StockAlias, StockWeight, PreloadStatus, DailySnapshot, PositionPlan, SignalCache, UnifiedStockCache
        db.create_all()
        migrate_position_table()

    # 预加载 OCR 模型，避免首次识别时卡顿
    from app.services.ocr import preload_model
    preload_model()

    return app
