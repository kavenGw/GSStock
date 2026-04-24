import os
import sys
import logging
from logging.handlers import RotatingFileHandler as _RotatingFileHandler
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


class SafeRotatingFileHandler(_RotatingFileHandler):
    """Windows 安全的 RotatingFileHandler，轮转失败时跳过而非崩溃"""

    def doRollover(self):
        try:
            super().doRollover()
        except PermissionError:
            pass


def setup_logging(app):
    """配置应用日志系统（幂等，重复调用不会叠加 handler）"""
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    log_dir = app.config.get('LOG_DIR', 'data/logs')
    os.makedirs(log_dir, exist_ok=True)

    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # app.log - 所有日志（5MB轮转，保留3份）
    file_handler = SafeRotatingFileHandler(
        os.path.join(log_dir, 'app.log'),
        maxBytes=5*1024*1024, backupCount=3,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # error.log - 仅错误（2MB轮转，保留3份）
    error_handler = SafeRotatingFileHandler(
        os.path.join(log_dir, 'error.log'),
        maxBytes=2*1024*1024, backupCount=3,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    # 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_handler)
    root_logger.addHandler(console_handler)

    # match.log - 赛事监控专用（2MB轮转，保留5份），便于排查 NBA/LoL 推送问题
    match_handler = SafeRotatingFileHandler(
        os.path.join(log_dir, 'match.log'),
        maxBytes=2*1024*1024, backupCount=5,
        encoding='utf-8'
    )
    match_handler.setLevel(logging.DEBUG)
    match_handler.setFormatter(formatter)
    for name in ('app.services.esports_service', 'app.services.esports_monitor_service'):
        lg = logging.getLogger(name)
        lg.setLevel(logging.DEBUG)
        lg.addHandler(match_handler)

    # 抑制第三方库噪音
    logging.getLogger('yfinance').setLevel(logging.CRITICAL)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('apscheduler').setLevel(logging.WARNING)


def check_playwright():
    """启动前检查 Playwright 和 Chromium 浏览器是否已安装"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError(
            "Playwright 未安装！请运行: pip install playwright"
        )

    try:
        with sync_playwright() as p:
            executable = p.chromium.executable_path
            if not executable or not os.path.exists(executable):
                raise FileNotFoundError(f"Chromium 未找到: {executable}")
    except Exception as e:
        raise RuntimeError(
            f"Playwright Chromium 浏览器未安装！请运行: playwright install chromium\n"
            f"错误详情: {e}"
        ) from e


class _SafeJsonProvider(Flask.json_provider_class):
    """NaN/Infinity → null，避免前端 JSON.parse 失败"""

    def dumps(self, obj, **kwargs):
        return super().dumps(_sanitize_nan(obj), **kwargs)


def _sanitize_nan(obj):
    import math
    if isinstance(obj, float):
        return None if (math.isnan(obj) or math.isinf(obj)) else obj
    if isinstance(obj, dict):
        return {k: _sanitize_nan(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_nan(v) for v in obj]
    return obj


def create_app(config_class=None):
    app = Flask(__name__)
    app.json_provider_class = _SafeJsonProvider
    app.json = _SafeJsonProvider(app)

    if config_class is None:
        from config import Config
        config_class = Config

    app.config.from_object(config_class)

    # Playwright 强制检查（只读模式跳过，不需要爬取新闻）
    if not app.config.get('READONLY_MODE'):
        check_playwright()

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

    if db_uri.startswith('sqlite:///'):
        from app.services.migration import check_migration_needed, migrate_to_dual_db, cleanup_legacy_tables, get_db_paths
        if check_migration_needed(app):
            logging.info("检测到需要数据迁移，开始执行...")
            migrate_to_dual_db(app)
            logging.info("数据迁移完成")
        else:
            stock_db_path, _ = get_db_paths(app)
            cleanup_legacy_tables(stock_db_path)

    from app.routes import main_bp, position_bp, advice_bp, category_bp, trade_bp, stock_bp, daily_record_bp, profit_bp, rebalance_bp, heavy_metals_bp, alert_bp, briefing_bp, stock_detail_bp, watch_bp, news_bp, value_dip_bp, earnings_page_bp, supply_chain_bp
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
    app.register_blueprint(alert_bp)
    app.register_blueprint(briefing_bp)
    app.register_blueprint(stock_detail_bp)
    app.register_blueprint(watch_bp)
    app.register_blueprint(news_bp)
    app.register_blueprint(value_dip_bp)
    app.register_blueprint(earnings_page_bp)
    app.register_blueprint(supply_chain_bp)

    with app.app_context():
        from app.models import Position, Advice, Category, StockCategory, Trade, Settlement, WyckoffReference, WyckoffAnalysis, Stock, StockAlias, StockWeight, DailySnapshot, PositionPlan, SignalCache, UnifiedStockCache, WatchList, WatchAnalysis, NewsItem, InterestKeyword, EarningsSnapshot

        # 一次性迁移：移除交易策略模块遗留表（2026-04-22 起）
        from sqlalchemy import inspect as sa_inspect, text
        _insp = sa_inspect(db.engine)
        _existing = set(_insp.get_table_names())
        for _t in ('strategy_executions', 'trading_strategies'):
            if _t in _existing:
                with db.engine.connect() as _conn:
                    _conn.execute(text(f'DROP TABLE IF EXISTS {_t}'))
                    _conn.commit()
                logging.info(f'[移除] 已删除交易策略遗留表 {_t}')

        db.create_all()

        migrate_position_table()
        migrate_daily_snapshot_table()
        migrate_trades_table()
        migrate_wyckoff_table()

        from app.seeds import seed_cpu_category, seed_worldcup_category, seed_ascend_category
        seed_cpu_category()
        seed_worldcup_category()
        seed_ascend_category()

        # news 表重建：source_id 列类型从 INT 改为 VARCHAR
        from sqlalchemy import inspect as sa_inspect, text
        inspector = sa_inspect(db.engine)
        if 'news_item' in inspector.get_table_names():
            cols = {c['name']: c for c in inspector.get_columns('news_item')}
            source_id_type = str(cols.get('source_id', {}).get('type', ''))
            if 'INT' in source_id_type.upper() or 'source_name' not in cols:
                logging.info('[迁移] 重建 news 相关表（修复 source_id 类型）')
                with db.engine.connect() as conn:
                    conn.execute(text('DROP TABLE IF EXISTS news_derivation'))
                    conn.execute(text('DROP TABLE IF EXISTS interest_keyword'))
                    conn.execute(text('DROP TABLE IF EXISTS news_item'))
                    conn.commit()
                db.create_all()
                logging.info('[迁移] news 相关表重建完成')

        # watch_analysis 表迁移：新增 period 字段
        if 'watch_analysis' in inspector.get_table_names():
            columns = [c['name'] for c in inspector.get_columns('watch_analysis')]
            if 'period' not in columns:
                db.session.execute(text("ALTER TABLE watch_analysis ADD COLUMN period VARCHAR(10) NOT NULL DEFAULT '30d'"))
                db.session.commit()
                logging.info('[迁移] watch_analysis 新增 period 字段')

        # 初始化市场状态缓存（仅 reloader 子进程，父进程不处理请求）
        if os.environ.get('WERKZEUG_RUN_MAIN') == 'true' or 'werkzeug' not in sys.modules:
            from app.services.market_status import market_status_service
            market_status_service.initialize()

    # 预加载 OCR 模型（仅 Windows，Linux 不安装 rapidocr-onnxruntime）
    if sys.platform == 'win32':
        from app.services.ocr import preload_model
        preload_model()

    # 添加只读模式上下文处理器
    @app.context_processor
    def inject_readonly_mode():
        from app.utils.readonly_mode import is_readonly_mode
        return {'readonly_mode': is_readonly_mode()}

    if app.config.get('READONLY_MODE'):
        logging.info("应用运行在只读模式：不从服务器获取数据，stock.db 只读")

    # 策略插件系统 + 调度引擎
    from app.strategies.registry import registry
    from app.scheduler.engine import scheduler_engine
    from app.scheduler.event_bus import event_bus
    from app.services.notification import NotificationService

    registry.discover()
    event_bus.subscribe(NotificationService.dispatch_signal)

    import os as _os
    if not app.debug or _os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        scheduler_engine.init_app(app)

    return app
