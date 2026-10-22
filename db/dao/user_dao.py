# -*- coding: utf-8 -*-
"""用户 DAO。"""

from __future__ import annotations

from typing import Optional

from db.database import query_all, query_one, exec_sql


class UserDAO:
    TABLE = "users"

    @classmethod
    def find_by_username(cls, username: str) -> Optional[dict]:
        return query_one(
            f"SELECT * FROM {cls.TABLE} WHERE username = ?",
            (username,),
        )

    @classmethod
    def find_by_id(cls, user_id: int) -> Optional[dict]:
        return query_one(
            f"SELECT * FROM {cls.TABLE} WHERE id = ?",
            (user_id,),
        )

    @classmethod
    def list_all(cls) -> list[dict]:
        return query_all(f"SELECT * FROM {cls.TABLE} ORDER BY id ASC")

    @classmethod
    def add(cls, username: str, password: str,
            role: str = "operator", real_name: str = "") -> int:
        """新增用户（password 传明文，内部做加盐哈希）。"""
        from utils.security import hash_password

        cur = exec_sql(
            f"INSERT INTO {cls.TABLE}(username, password, role, real_name) "
            f"VALUES(?,?,?,?)",
            (username, hash_password(password), role, real_name or username),
        )
        return cur.lastrowid

    @classmethod
    def add_hashed(cls, username: str, password_hash: str,
                   role: str = "operator", real_name: str = "") -> int:
        """新增用户（password 已是哈希值，不再二次哈希）。"""
        cur = exec_sql(
            f"INSERT INTO {cls.TABLE}(username, password, role, real_name) "
            f"VALUES(?,?,?,?)",
            (username, password_hash, role, real_name or username),
        )
        return cur.lastrowid

    @classmethod
    def update_password(cls, user_id: int, new_password: str) -> None:
        """修改密码（new_password 传明文，内部做加盐哈希）。"""
        from utils.security import hash_password

        exec_sql(
            f"UPDATE {cls.TABLE} SET password = ? WHERE id = ?",
            (hash_password(new_password), user_id),
        )

    @classmethod
    def delete(cls, user_id: int) -> None:
        exec_sql(f"DELETE FROM {cls.TABLE} WHERE id = ?", (user_id,))