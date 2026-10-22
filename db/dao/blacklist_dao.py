# -*- coding: utf-8 -*-
"""黑名单 DAO。"""

from __future__ import annotations

from typing import Optional

from db.database import query_all, query_one, exec_sql


class BlacklistDAO:
    TABLE = "blacklist"

    @classmethod
    def add(cls, plate_no: str, reason: str = "") -> int:
        cur = exec_sql(
            f"INSERT OR IGNORE INTO {cls.TABLE}(plate_no, reason) VALUES(?,?)",
            (plate_no, reason),
        )
        return cur.lastrowid

    @classmethod
    def delete(cls, black_id: int) -> None:
        exec_sql(f"DELETE FROM {cls.TABLE} WHERE id = ?", (black_id,))

    @classmethod
    def delete_by_plate(cls, plate_no: str) -> None:
        exec_sql(f"DELETE FROM {cls.TABLE} WHERE plate_no = ?", (plate_no,))

    @classmethod
    def contains(cls, plate_no: str) -> Optional[dict]:
        row = query_one(
            f"SELECT * FROM {cls.TABLE} WHERE plate_no = ?",
            (plate_no,),
        )
        # sqlite3.Row 与 dict 的 API 不同（没有 .get），统一转成 dict
        return dict(row) if row is not None else None

    @classmethod
    def list_all(cls) -> list[dict]:
        return query_all(f"SELECT * FROM {cls.TABLE} ORDER BY id DESC")