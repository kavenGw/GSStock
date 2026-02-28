"""新闻模块数据库迁移脚本"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'stock.db')

def migrate():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    for sql in [
        "ALTER TABLE news_item ADD COLUMN source_name TEXT DEFAULT 'wallstreetcn'",
        "ALTER TABLE news_item ADD COLUMN importance INTEGER DEFAULT 0",
        "ALTER TABLE news_item ADD COLUMN is_interest BOOLEAN DEFAULT 0",
        "ALTER TABLE news_item ADD COLUMN matched_keywords TEXT",
    ]:
        try:
            c.execute(sql)
        except sqlite3.OperationalError:
            pass

    c.execute("DROP TABLE IF EXISTS news_briefing")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == '__main__':
    migrate()
