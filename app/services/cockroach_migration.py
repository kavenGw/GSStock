"""CockroachDB 迁移服务

负责将本地 SQLite stock.db 数据迁移到 CockroachDB 云数据库。
"""
import os
import logging
import sqlite3
from datetime import datetime, date

logger = logging.getLogger(__name__)

# stock.db 中需要迁移的表（缓存表跳过，应用运行后会自动重新获取）
STOCK_DB_TABLES = [
    'stock',
    'stock_alias',
    'categories',
    'stock_categories',
    'wyckoff_reference',
]


def check_local_db_exists(local_db_path: str) -> bool:
    """检查本地数据库是否存在且不为空"""
    if not os.path.exists(local_db_path):
        return False

    try:
        conn = sqlite3.connect(local_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        conn.close()
        return len(tables) > 0
    except Exception as e:
        logger.error(f"[CockroachDB迁移] 检查本地数据库失败: {e}", exc_info=True)
        return False


def get_table_data(conn: sqlite3.Connection, table_name: str) -> tuple:
    """获取表的所有数据和列信息

    Returns:
        tuple: (columns, rows)
    """
    cursor = conn.cursor()
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns_info = cursor.fetchall()
        columns = [col[1] for col in columns_info]

        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()

        return columns, rows
    except Exception as e:
        logger.warning(f"[CockroachDB迁移] 获取表 {table_name} 数据失败: {e}")
        return [], []


def convert_value_for_postgres(value, col_name: str = None):
    """转换 SQLite 值为 PostgreSQL 兼容格式"""
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return value
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    return str(value)


def migrate_table_to_cockroach(sqlite_conn: sqlite3.Connection, pg_engine, table_name: str) -> int:
    """迁移单个表到 CockroachDB

    Returns:
        int: 迁移的记录数
    """
    from sqlalchemy import text, inspect

    columns, rows = get_table_data(sqlite_conn, table_name)

    if not columns or not rows:
        logger.info(f"[CockroachDB迁移] 表 {table_name} 为空或不存在，跳过")
        return 0

    # 查询目标表的布尔类型列（SQLite 存 0/1，CockroachDB 需要 bool）
    bool_columns = set()
    try:
        inspector = inspect(pg_engine)
        for col_info in inspector.get_columns(table_name):
            if str(col_info['type']).upper() == 'BOOLEAN':
                bool_columns.add(col_info['name'])
    except Exception:
        pass

    # 构建插入语句
    placeholders = ', '.join([f':{col}' for col in columns])
    columns_str = ', '.join([f'"{col}"' for col in columns])

    insert_sql = f'INSERT INTO "{table_name}" ({columns_str}) VALUES ({placeholders}) ON CONFLICT DO NOTHING'

    migrated = 0
    for row in rows:
        try:
            params = {}
            for i, col in enumerate(columns):
                val = convert_value_for_postgres(row[i], col)
                if col in bool_columns and isinstance(val, int):
                    val = bool(val)
                params[col] = val

            with pg_engine.connect() as conn:
                conn.execute(text(insert_sql), params)
                conn.commit()
            migrated += 1
        except Exception as e:
            logger.warning(f"[CockroachDB迁移] 插入记录到 {table_name} 失败: {e}")
            continue

    logger.info(f"[CockroachDB迁移] 表 {table_name} 完成 {migrated}/{len(rows)} 条")
    return migrated


def migrate_local_to_cockroach(app) -> bool:
    """执行本地数据库到 CockroachDB 的迁移

    Returns:
        bool: 迁移是否成功
    """
    from config import is_cockroach_configured, get_local_stock_db_path
    from app import db

    if not is_cockroach_configured():
        logger.info("[CockroachDB迁移] 未配置 CockroachDB，跳过")
        return False

    local_db_path = get_local_stock_db_path()

    if not check_local_db_exists(local_db_path):
        logger.info("[CockroachDB迁移] 本地数据库不存在或为空，无需迁移")
        return True

    logger.info(f"[CockroachDB迁移] 开始迁移: {local_db_path}")

    try:
        # 连接本地 SQLite 数据库
        sqlite_conn = sqlite3.connect(local_db_path)
        sqlite_cursor = sqlite_conn.cursor()

        # 获取本地数据库中存在的表
        sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = {row[0] for row in sqlite_cursor.fetchall()}

        # 获取 CockroachDB 引擎
        pg_engine = db.engine

        # 迁移每个表
        total_migrated = 0
        for table in STOCK_DB_TABLES:
            if table in existing_tables:
                count = migrate_table_to_cockroach(sqlite_conn, pg_engine, table)
                total_migrated += count

        sqlite_conn.close()

        logger.info(f"[CockroachDB迁移] 完成，共 {total_migrated} 条记录")

        # 删除本地数据库
        try:
            os.remove(local_db_path)
            logger.info(f"[CockroachDB迁移] 已删除本地数据库: {local_db_path}")
        except Exception as e:
            logger.warning(f"[CockroachDB迁移] 删除本地数据库失败: {e}")

        return True

    except Exception as e:
        logger.error(f"[CockroachDB迁移] 迁移失败: {e}", exc_info=True)
        return False


def check_cockroach_migration_needed(app) -> bool:
    """检查是否需要执行 CockroachDB 迁移

    Returns:
        bool: True 如果配置了 CockroachDB 且本地数据库存在
    """
    from config import is_cockroach_configured, get_local_stock_db_path

    if not is_cockroach_configured():
        return False

    local_db_path = get_local_stock_db_path()
    return check_local_db_exists(local_db_path)
