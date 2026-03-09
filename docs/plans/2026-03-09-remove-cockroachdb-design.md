# 移除 CockroachDB，统一本地数据库

## 目标

移除所有 CockroachDB 相关代码和依赖，统一使用本地 SQLite（stock.db + private.db）。

## 变更清单

| 文件 | 操作 |
|------|------|
| `app/services/cockroach_migration.py` | 删除 |
| `app/utils/db_retry.py` | 删除 |
| `config.py` | 移除 `get_database_uri()`、`is_cockroach_configured()`、连接池配置 |
| `app/__init__.py` | 移除 cockroach 迁移、ALTER 语句、`setup_db_retry` |
| `app/models/unified_cache.py` | 移除 `@with_db_retry` 和导入 |
| `app/services/futures.py` | 同上 |
| `app/services/signal_cache.py` | 同上 |
| `requirements.txt` | 移除 `psycopg2-binary`、`sqlalchemy-cockroachdb` |
| `.env.sample` | 移除 `COCKROACH_URL` |
| `CLAUDE.md` / `README.md` / 技术文档 | 移除相关说明 |

## 保留不变

- `stock.db` + `private.db` 双库架构
- `app/services/migration.py`（本地双库迁移）
