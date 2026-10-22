# -*- coding: utf-8 -*-
"""会员 DAO。"""

from __future__ import annotations

from typing import Optional

from db.database import query_all, query_one, exec_sql


class MemberDAO:
    TABLE = "members"

    @classmethod
    def add(cls, plate_no: str, valid_from: str, valid_to: str,
            name: str = "", phone: str = "",
            discount: float = 1.0) -> int:
        cur = exec_sql(
            f"INSERT INTO {cls.TABLE}"
            "(plate_no, name, phone, valid_from, valid_to, discount) "
            "VALUES(?,?,?,?,?,?)",
            (plate_no, name, phone, valid_from, valid_to, discount),
        )
        return cur.lastrowid

    @classmethod
    def update(cls, member_id: int, **fields) -> None:
        allowed = {"plate_no", "name", "phone",
                   "valid_from", "valid_to", "discount"}
        cols = []
        vals = []
        for k, v in fields.items():
            if k not in allowed:
                continue
            cols.append(f"{k} = ?")
            vals.append(v)
        if not cols:
            return
        vals.append(member_id)
        sql = f"UPDATE {cls.TABLE} SET {', '.join(cols)} WHERE id = ?"
        exec_sql(sql, tuple(vals))

    @classmethod
    def delete(cls, member_id: int) -> None:
        exec_sql(f"DELETE FROM {cls.TABLE} WHERE id = ?", (member_id,))

    @classmethod
    def delete_by_plate(cls, plate_no: str) -> None:
        exec_sql(f"DELETE FROM {cls.TABLE} WHERE plate_no = ?", (plate_no,))

    @classmethod
    def find_by_plate(cls, plate_no: str) -> Optional[dict]:
        return query_one(
            f"SELECT * FROM {cls.TABLE} WHERE plate_no = ?",
            (plate_no,),
        )

    @classmethod
    def list_all(cls) -> list[dict]:
        return query_all(f"SELECT * FROM {cls.TABLE} ORDER BY id DESC")

    @classmethod
    def is_member_valid(cls, plate_no: str, today: str) -> Optional[dict]:
        """今天是否仍在有效期内。"""
        return query_one(
            f"SELECT * FROM {cls.TABLE} "
            "WHERE plate_no = ? AND valid_from <= ? AND valid_to >= ?",
            (plate_no, today, today),
        )