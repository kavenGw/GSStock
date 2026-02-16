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


def migrate_daily_snapshot_table():
    """迁移 daily_snapshots 表：添加 daily_fee 列"""
    from sqlalchemy import inspect, text

    private_engine = db.get_engine(bind='private')
    inspector = inspect(private_engine)

    try:
        columns = [col['name'] for col in inspector.get_columns('daily_snapshots')]
    except Exception:
        return

    if 'daily_fee' in columns:
        return

    logging.info("迁移 daily_snapshots 表: 添加 daily_fee 列")
    with private_engine.connect() as conn:
        conn.execute(text('ALTER TABLE daily_snapshots ADD COLUMN daily_fee FLOAT DEFAULT 0'))
        conn.commit()
    logging.info("daily_snapshots 表迁移完成")


def migrate_trades_table():
    """迁移 trades 表：添加 fee 列"""
    from sqlalchemy import inspect, text

    private_engine = db.get_engine(bind='private')
    inspector = inspect(private_engine)

    try:
        columns = [col['name'] for col in inspector.get_columns('trades')]
    except Exception:
        return

    if 'fee' in columns:
        return

    logging.info("迁移 trades 表: 添加 fee 列")
    with private_engine.connect() as conn:
        conn.execute(text('ALTER TABLE trades ADD COLUMN fee FLOAT DEFAULT 0'))
        conn.commit()
    logging.info("trades 表迁移完成")


def migrate_wyckoff_table():
    """迁移 wyckoff_auto_result 表：新增多周期字段"""
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    try:
        columns = [col['name'] for col in inspector.get_columns('wyckoff_auto_result')]
    except Exception:
        return

    if 'timeframe' in columns:
        return

    logging.info("迁移 wyckoff_auto_result: 添加 timeframe/score/confidence/composite_signal")
    with db.engine.connect() as conn:
        conn.execute(text("ALTER TABLE wyckoff_auto_result ADD COLUMN timeframe VARCHAR(10) DEFAULT 'daily'"))
        conn.execute(text("ALTER TABLE wyckoff_auto_result ADD COLUMN score INTEGER"))
        conn.execute(text("ALTER TABLE wyckoff_auto_result ADD COLUMN confidence FLOAT"))
        conn.execute(text("ALTER TABLE wyckoff_auto_result ADD COLUMN composite_signal VARCHAR(20)"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_wyckoff_auto_date_stock_tf ON wyckoff_auto_result(analysis_date, stock_code, timeframe)"))
        conn.commit()
    logging.info("wyckoff_auto_result 迁移完成")


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

    # 只有在使用 SQLite 时才创建数据目录
    db_uri = app.config['SQLALCHEMY_DATABASE_URI']
    if db_uri.startswith('sqlite:///'):
        db_dir = os.path.dirname(db_uri.replace('sqlite:///', ''))
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    setup_logging(app)

    db.init_app(app)

    # CockroachDB: patch Session.execute 自动重试读查询
    from app.utils.db_retry import setup_db_retry
    setup_db_retry(db, app)

    from app.services.migration import check_migration_needed, migrate_to_dual_db, cleanup_legacy_tables, get_db_paths
    if check_migration_needed(app):
        logging.info("检测到需要数据迁移，开始执行...")
        migrate_to_dual_db(app)
        logging.info("数据迁移完成")
    else:
        stock_db_path, _ = get_db_paths(app)
        cleanup_legacy_tables(stock_db_path)

    from app.routes import main_bp, position_bp, advice_bp, category_bp, trade_bp, stock_bp, daily_record_bp, profit_bp, rebalance_bp, heavy_metals_bp, preload_bp, alert_bp, briefing_bp, strategy_bp, stock_detail_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(position_bp)
    app.register_blueprint(advice_bp)
    app.register_blueprint(category_bp)
    app.register_blueprint(trade_bp)
    app.register_blueprint(stock_bp)
    app.register_blueprint(daily_record_bp)
    app.register_blueprint(profit_bp)
    app.register_blueprint(rebalance_bp)
    app.register_blueprint(heavy_metals_bp)
    app.register_blueprint(preload_bp)
    app.register_blueprint(alert_bp)
    app.register_blueprint(briefing_bp)
    app.register_blueprint(strategy_bp)
    app.register_blueprint(stock_detail_bp)

    with app.app_context():
        from app.models import Position, Advice, Category, StockCategory, Trade, Settlement, WyckoffReference, WyckoffAnalysis, Stock, StockAlias, StockWeight, PreloadStatus, DailySnapshot, PositionPlan, SignalCache, UnifiedStockCache, TradingStrategy, StrategyExecution

        # 检查是否需要执行 CockroachDB 迁移
        from app.services.cockroach_migration import check_cockroach_migration_needed, migrate_local_to_cockroach
        cockroach_migration_needed = check_cockroach_migration_needed(app)

        # 创建所有表
        db.create_all()

        # CockroachDB 需要 ALTER 已有列宽度（db.create_all 不会修改已有列）
        if app.config.get('COCKROACH_CONFIGURED'):
            from sqlalchemy import text
            alter_stmts = [
                'ALTER TABLE stock_categories ALTER COLUMN stock_code TYPE VARCHAR(20)',
                'ALTER TABLE wyckoff_auto_result ALTER COLUMN stock_code TYPE VARCHAR(20)',
            ]
            try:
                with db.engine.connect() as conn:
                    for stmt in alter_stmts:
                        try:
                            conn.execute(text(stmt))
                        except Exception:
                            pass
                    conn.commit()
            except Exception:
                pass

        # 如果配置了 CockroachDB 且本地数据库存在，执行迁移
        if cockroach_migration_needed:
            logging.info("检测到 CockroachDB 配置，开始将本地数据迁移到云端...")
            if migrate_local_to_cockroach(app):
                logging.info("本地数据已成功迁移到 CockroachDB")
            else:
                logging.warning("CockroachDB 迁移未完成，请检查日志")

        migrate_position_table()
        migrate_daily_snapshot_table()
        migrate_trades_table()
        migrate_wyckoff_table()

        # 初始化默认交易策略
        from app.services.trading_strategy import TradingStrategyService
        TradingStrategyService.init_default_strategies()

    # 预加载 OCR 模型，避免首次识别时卡顿
    from app.services.ocr import preload_model
    preload_model()

    # 预加载数据（简报优先，走势看板其次）
    if not app.config.get('READONLY_MODE'):
        from app.services.briefing_preload import start_background_preload as start_briefing_preload
        start_briefing_preload(app)

        from app.services.heavy_metals_preload import start_background_preload as start_heavy_metals_preload
        start_heavy_metals_preload(app)

    # 添加只读模式上下文处理器
    @app.context_processor
    def inject_readonly_mode():
        from app.utils.readonly_mode import is_readonly_mode
        return {'readonly_mode': is_readonly_mode()}

    if app.config.get('READONLY_MODE'):
        logging.info("应用运行在只读模式：不从服务器获取数据，stock.db 只读")

    return app
