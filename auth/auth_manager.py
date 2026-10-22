# -*- coding: utf-8 -*-
"""
权限管理：
- 登录验证（基于 db/dao/user_dao.py）
- 保存当前登录用户
- 角色判断：admin / operator
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from utils.constants import ROLE_ADMIN, ROLE_OPERATOR
from utils.logger import get_logger

logger = get_logger()


@dataclass
class CurrentUser:
    user_id:   int
    username:  str
    role:      str            # 'admin' / 'operator'

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN

    @property
    def is_operator(self) -> bool:
        return self.role == ROLE_OPERATOR


class AuthManager:
    """简单的会话级单例。"""

    _instance: Optional["AuthManager"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            inst = super().__new__(cls)
            inst.current_user = None
            cls._instance = inst
        return cls._instance

    def __init__(self):
        # 单例只初始化一次：重复 AuthManager() 绝不能重置登录态，
        # 否则 get_current_user() 每次调用都会把 current_user 清空。
        if getattr(self, "_initialized", False):
            return
        self._initialized = True

    # ------------------------------------------------------------------
    # 登录
    # ------------------------------------------------------------------
    def authenticate(self, username: str, password: str) -> bool:
        from db.dao.user_dao import UserDAO   # 延迟导入
        from utils.security import needs_rehash, verify_password

        row = UserDAO.find_by_username(username)
        if row is None:
            logger.warning(f"登录失败：用户不存在 [{username}]")
            return False
        if not verify_password(password, row["password"]):
            logger.warning(f"登录失败：密码错误 [{username}]")
            return False

        # 历史明文 / 低强度哈希 → 登录成功后静默升级为加盐哈希
        if needs_rehash(row["password"]):
            try:
                # update_password 内部会做哈希，这里传明文
                UserDAO.update_password(row["id"], password)
                logger.info(f"已升级密码存储为 PBKDF2 哈希：{username}")
            except Exception as e:
                logger.warning(f"密码哈希升级失败（不影响本次登录）：{e}")

        self.current_user = CurrentUser(
            user_id=row["id"],
            username=row["username"],
            role=row["role"],
        )
        logger.info(f"登录成功：{username} ({row['role']})")
        return True

    def logout(self):
        if self.current_user:
            logger.info(f"注销：{self.current_user.username}")
        self.current_user = None

    # ------------------------------------------------------------------
    # 权限
    # ------------------------------------------------------------------
    def require_admin(self) -> bool:
        return self.current_user is not None and self.current_user.is_admin


def get_auth() -> AuthManager:
    return AuthManager()


def get_current_user() -> Optional[CurrentUser]:
    return AuthManager().current_user