# -*- coding: utf-8 -*-
"""密码哈希工具测试。"""

from utils.security import (
    hash_password, is_hashed, needs_rehash, verify_password,
)


def test_hash_roundtrip():
    h = hash_password("abc123")
    assert is_hashed(h)
    assert verify_password("abc123", h) is True
    assert verify_password("wrong", h) is False


def test_same_password_produces_different_hash():
    """加盐：相同明文每次哈希结果应不同。"""
    assert hash_password("same") != hash_password("same")


def test_empty_password():
    h = hash_password("")
    assert verify_password("", h) is True
    assert verify_password("x", h) is False


def test_plaintext_backward_compatible():
    """历史明文记录仍需能登录，并标记为待升级。"""
    assert verify_password("admin123", "admin123") is True
    assert verify_password("bad", "admin123") is False
    assert needs_rehash("admin123") is True


def test_hashed_value_does_not_need_rehash():
    assert needs_rehash(hash_password("x")) is False


def test_malformed_hash_is_rejected():
    assert verify_password("x", "pbkdf2_sha256$broken") is False
    assert verify_password("x", "") is False
