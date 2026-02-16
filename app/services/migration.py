"""数据库迁移服务 - 将单一数据库拆分为共享数据库和私有数据库"""
import os
import shutil
import logging
import sqlite3

logger = logging.getLogger(__name__)

PRIVATE_TABLES = [
    'positions',
    'trades',
    'settlements',
    'advices',
    'daily_snapshots',
    'stock_weights',
    'wyckoff_analysis',
    'configs',
]


def get_db_paths(app):
    """获取数据库文件路径"""
    stock_db_uri = app.config['SQLALCHEMY_DATABASE_URI']
    private_db_uri = app.config['SQLALCHEMY_BINDS']['private']

    stock_db_path = stock_db_uri.replace('sqlite:///', '')
    private_db_path = private_db_uri.replace('sqlite:///', '')

    return stock_db_path, private_db_path


def check_migration_needed(app):
    """检查是否需要执行数据迁移

    Returns:
        bool: True 如果 stock.db 包含 PRIVATE_TABLES 中的任何表
    """
    stock_db_path, _ = get_db_paths(app)

    if not os.path.exists(stock_db_path):
        return False

    try:
        conn = sqlite3.connect(stock_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        for table in PRIVATE_TABLES:
            if table in existing_tables:
                logger.info(f"[数据迁移] 检测到 stock.db 包含私有表 {table}，需要迁移")
                return True

        return False
    except Exception as e:
        logger.error(f"[数据迁移] 检查迁移状态失败: {e}", exc_info=True)
        return False


def backup_database(db_path):
    """备份数据库文件

    Args:
        db_path: 数据库文件路径

    Returns:
        str: 备份文件路径
    """
    backup_path = db_path + '.backup'
    shutil.copy2(db_path, backup_path)
    logger.info(f"[数据迁移] 已备份: {db_path} -> {backup_path}")
    return backup_path


def migrate_to_dual_db(app):
    """执行数据迁移：将私有数据从 stock.db 迁移到 private.db

    Returns:
        bool: 迁移是否成功
    """
    stock_db_path, private_db_path = get_db_paths(app)
    backup_path = None

    try:
        backup_path = backup_database(stock_db_path)
        logger.info("[数据迁移] 开始迁移...")

        os.makedirs(os.path.dirname(private_db_path), exist_ok=True)

        stock_conn = sqlite3.connect(stock_db_path)
        stock_cursor = stock_conn.cursor()

        private_conn = sqlite3.connect(private_db_path)
        private_cursor = private_conn.cursor()

        stock_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in stock_cursor.fetchall()}

        private_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        private_existing = {row[0] for row in private_cursor.fetchall()}

        for table in PRIVATE_TABLES:
            if table not in existing_tables:
                continue

            logger.info(f"[数据迁移] 迁移表: {table}")

            stock_cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table}'")
            create_sql = stock_cursor.fetchone()[0]
            if table not in private_existing:
                private_cursor.execute(create_sql)

            stock_cursor.execute(f"SELECT * FROM {table}")
            rows = stock_cursor.fetchall()

            if rows:
                stock_cursor.execute(f"PRAGMA table_info({table})")
                columns = [col[1] for col in stock_cursor.fetchall()]
                placeholders = ','.join(['?' for _ in columns])
                columns_str = ','.join(columns)

                private_cursor.executemany(
                    f"INSERT INTO {table} ({columns_str}) VALUES ({placeholders})",
                    rows
                )
                logger.info(f"[数据迁移] 迁移了 {len(rows)} 条记录")

            stock_cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='{table}'")
            for idx_row in stock_cursor.fetchall():
                if idx_row[0]:
                    try:
                        private_cursor.execute(idx_row[0])
                    except sqlite3.OperationalError:
                        pass

        private_conn.commit()
        private_conn.close()

        for table in PRIVATE_TABLES:
            if table in existing_tables:
                stock_cursor.execute(f"DROP TABLE IF EXISTS {table}")
                logger.info(f"[数据迁移] 从 stock.db 删除表: {table}")

        stock_conn.commit()
        stock_conn.close()

        cleanup_legacy_tables(stock_db_path)

        logger.info("[数据迁移] 完成")
        return True

    except Exception as e:
        logger.error(f"[数据迁移] 迁移失败: {e}", exc_info=True)

        if backup_path and os.path.exists(backup_path):
            shutil.copy2(backup_path, stock_db_path)
            logger.info("[数据迁移] 已从备份恢复 stock.db")

        if os.path.exists(private_db_path):
            os.remove(private_db_path)
            logger.info("[数据迁移] 已删除不完整的 private.db")

        raise


LEGACY_TABLES = ['ratings']


def cleanup_legacy_tables(stock_db_path):
    """清理 stock.db 中的遗留表"""
    try:
        conn = sqlite3.connect(stock_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in cursor.fetchall()}

        for table in LEGACY_TABLES:
            if table in existing_tables:
                cursor.execute(f"DROP TABLE {table}")
                logger.info(f"[数据迁移] 清理遗留表: {table}")

        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"[数据迁移] 清理遗留表失败: {e}", exc_info=True)
