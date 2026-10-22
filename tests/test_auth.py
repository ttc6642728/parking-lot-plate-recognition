# -*- coding: utf-8 -*-
"""认证与密码存储测试。

回归重点：AuthManager 是单例，早期 __init__ 会在每次实例化时
把 current_user 重置为 None，导致登录后立刻"掉线"、权限全部失效。
"""

from auth import get_auth, get_current_user
from db.dao import UserDAO


def test_login_success(temp_db):
    assert get_auth().authenticate("admin", "admin123") is True
    user = get_current_user()
    assert user is not None
    assert user.username == "admin"
    assert user.is_admin is True


def test_singleton_does_not_reset_login_state(temp_db):
    """核心回归：重复取实例不能清空登录态。"""
    au = get_auth()
    assert au.authenticate("admin", "admin123") is True

    for _ in range(3):
        assert get_auth() is au
        assert get_current_user() is not None

    assert get_current_user().role == "admin"


def test_wrong_password(temp_db):
    assert get_auth().authenticate("admin", "wrong-password") is False
    assert get_current_user() is None


def test_unknown_user(temp_db):
    assert get_auth().authenticate("nobody", "whatever") is False


def test_operator_role(temp_db):
    assert get_auth().authenticate("operator", "123456") is True
    user = get_current_user()
    assert user.is_admin is False
    assert user.is_operator is True


def test_logout_clears_user(temp_db):
    au = get_auth()
    au.authenticate("admin", "admin123")
    assert get_current_user() is not None
    au.logout()
    assert get_current_user() is None


def test_password_is_stored_hashed(temp_db):
    """种子账号的密码必须是哈希，不能明文入库。"""
    row = UserDAO.find_by_username("admin")
    assert row["password"] != "admin123"
    assert row["password"].startswith("pbkdf2_sha256$")


def test_update_password_is_hashed(temp_db):
    row = UserDAO.find_by_username("operator")
    UserDAO.update_password(row["id"], "newpass456")

    fresh = UserDAO.find_by_username("operator")
    assert fresh["password"] != "newpass456"
    assert get_auth().authenticate("operator", "newpass456") is True
