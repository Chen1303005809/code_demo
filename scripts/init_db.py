"""数据库初始化脚本 —— 创建 SQLite 数据库文件和表结构。

用法：
    cd backend
    py scripts/init_db.py

也可通过 --db-path 指定自定义路径：
    py scripts/init_db.py --db-path ./custom/history.db
"""

import argparse
import os
import sys

# 确保 backend 目录在 sys.path 中，以便导入 config
_scripts_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_scripts_dir)
sys.path.insert(0, os.path.join(_project_root, "backend"))


def main() -> None:
    parser = argparse.ArgumentParser(description="初始化 LightRag 查询面板数据库")
    parser.add_argument(
        "--db-path",
        default=None,
        help="数据库文件路径（默认读取 .env 中的 DB_PATH）",
    )
    parser.add_argument(
        "--drop",
        action="store_true",
        help="删除已有表后重建",
    )
    args = parser.parse_args()

    # 加载配置（自动读取 .env）
    from config import get_config

    config = get_config()
    db_path = args.db_path or config.db_path

    # 确保目录存在
    db_dir = os.path.dirname(db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    print(f"数据库路径: {os.path.abspath(db_path)}")

    import sqlite3

    conn = sqlite3.connect(db_path)

    if args.drop:
        print("删除已有表 ...")
        conn.execute("DROP TABLE IF EXISTS queries")
        conn.execute("DROP INDEX IF EXISTS idx_queries_created_at")

    print("创建表结构 ...")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS queries (
            id          TEXT PRIMARY KEY,
            query       TEXT NOT NULL,
            summary     TEXT NOT NULL,
            full_answer TEXT NOT NULL,
            created_at  TEXT NOT NULL,
            total_ms    INTEGER NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_queries_created_at
        ON queries(created_at DESC)
    """)
    conn.commit()
    conn.close()

    print("初始化完成。")


if __name__ == "__main__":
    main()
