# -*- coding: utf-8 -*-
"""
数据库连接 + 初始化。

- SQLite3 标准库
- 单例化连接
- 首次启动时执行 init_db.sql 建表，并插入默认账号 / 车位配置
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Optional

from config import DB_FILE
from utils.constants import ROLE_ADMIN, ROLE_OPERATOR
from utils.logger    import get_logger

logger = get_logger()

_lock = threading.Lock()

# 缓存连接（每个线程一份）
_local = threading.local()


# ---------------------------------------------------------------------------
# 连接
# ---------------------------------------------------------------------------
def _new_connection() -> sqlite3.Connection:
    """创建新的 SQLite 连接。"""
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        DB_FILE,
        detect_types=sqlite3.PARSE_DECLTYPES,
        check_same_thread=False,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def get_conn() -> sqlite3.Connection:
    """获取当前线程的连接。"""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = _new_connection()
        _local.conn = conn
    return conn


def close_conn() -> None:
    conn = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn.close()
        finally:
            _local.conn = None


# ---------------------------------------------------------------------------
# 初始化
# ---------------------------------------------------------------------------
def _read_sql_script() -> str:
    sql_path = Path(__file__).resolve().parent / "init_db.sql"
    return sql_path.read_text(encoding="utf-8")


def init_database() -> None:
    """建表 + 插入默认数据。"""
    with _lock:
        conn = _new_connection()
        try:
            conn.executescript(_read_sql_script())
            conn.commit()
            _seed_default_data(conn)
            conn.commit()
        finally:
            conn.close()
        logger.info(f"数据库初始化完成：{DB_FILE}")


def _seed_default_data(conn: sqlite3.Connection) -> None:
    """插入默认账号与停车场配置。"""
    from config import DEFAULT_USERS, TOTAL_PARKING_SPOTS
    from utils.security import hash_password

    cur = conn.cursor()

    # 默认账号（仅当表为空时）—— 密码以 PBKDF2 加盐哈希存储
    cur.execute("SELECT COUNT(*) FROM users")
    if cur.fetchone()[0] == 0:
        for username, password, role in DEFAULT_USERS:
            cur.execute(
                "INSERT INTO users(username, password, role, real_name) "
                "VALUES(?,?,?,?)",
                (username, hash_password(password), role, username),
            )
        logger.info(f"创建默认账号：{[u[0] for u in DEFAULT_USERS]}")

    # 停车场配置：以 config.py 为唯一配置源，改完重启即生效
    cur.execute("SELECT total_spots FROM parking_lot WHERE id = 1")
    row = cur.fetchone()
    if row is None:
        cur.execute(
            "INSERT INTO parking_lot(id, total_spots, used_spots) "
            "VALUES(?, ?, 0)",
            (1, TOTAL_PARKING_SPOTS),
        )
        logger.info(f"初始化停车场车位：{TOTAL_PARKING_SPOTS} 个")
    elif int(row[0]) != TOTAL_PARKING_SPOTS:
        cur.execute(
            "UPDATE parking_lot SET total_spots = ? WHERE id = 1",
            (TOTAL_PARKING_SPOTS,),
        )
        logger.info(
            f"车位总数已按 config.py 同步：{row[0]} → {TOTAL_PARKING_SPOTS}"
        )


def exec_sql(sql: str, params: tuple = ()) -> sqlite3.Cursor:
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()
    return cur


def query_all(sql: str, params: tuple = ()) -> list[dict]:
    """查询多行，统一返回 dict 列表。

    ⚠ 关键：sqlite3.Row 不支持 .get()，而 UI 层大量使用 row.get("字段")。
    这里在数据出口统一转成 dict，避免各调用方分别兼容两种类型。
    """
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(sql, params)
    return [dict(r) for r in cur.fetchall()]


def query_one(sql: str, params: tuple = ()) -> Optional[dict]:
    rows = query_all(sql, params)
    return rows[0] if rows else None