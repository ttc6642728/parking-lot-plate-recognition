# -*- coding: utf-8 -*-
"""
密码安全工具：加盐 PBKDF2 哈希存储 / 校验。

存储格式（单字段自描述，便于以后升级迭代次数）：
    pbkdf2_sha256$<迭代次数>$<salt_hex>$<hash_hex>

兼容策略：
    早期版本把密码明文存在 users.password 里。verify_password 遇到不带
    前缀的值时按明文比较（仍可登录），并由上层调用 needs_rehash 后自动
    升级为哈希，避免老数据无法登录。
"""

from __future__ import annotations

import hashlib
import hmac
import os

_ALGO = "pbkdf2_sha256"
_ITERATIONS = 260_000
_SALT_BYTES = 16


def hash_password(password: str, iterations: int = _ITERATIONS) -> str:
    """生成加盐哈希（每次结果不同）。"""
    if password is None:
        password = ""
    salt = os.urandom(_SALT_BYTES)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                             salt, iterations)
    return f"{_ALGO}${iterations}${salt.hex()}${dk.hex()}"


def is_hashed(stored: str) -> bool:
    """判断库里的值是否已经是哈希格式。"""
    return isinstance(stored, str) and stored.startswith(_ALGO + "$")


def verify_password(password: str, stored: str) -> bool:
    """校验密码。兼容历史明文记录。"""
    if not stored:
        return False
    if not is_hashed(stored):
        # 历史明文数据：直接比较（登录后会被自动升级）
        return hmac.compare_digest(str(stored), str(password or ""))

    try:
        _, iters, salt_hex, hash_hex = stored.split("$", 3)
        iterations = int(iters)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, TypeError):
        return False

    dk = hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"),
                             salt, iterations)
    return hmac.compare_digest(dk, expected)


def needs_rehash(stored: str) -> bool:
    """是否需要把明文 / 低强度哈希升级为当前参数。"""
    if not is_hashed(stored):
        return True
    try:
        _, iters, _, _ = stored.split("$", 3)
        return int(iters) < _ITERATIONS
    except (ValueError, TypeError):
        return True
