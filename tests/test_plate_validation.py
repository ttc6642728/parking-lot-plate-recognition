# -*- coding: utf-8 -*-
"""车牌格式校验测试。

回归重点：早期只允许第 2 位为 A-H，
导致 京N / 京P / 京Q / 京Y 等真实号段被判为非法车牌。
"""

import pytest

from core import validate_plate


@pytest.mark.parametrize("plate", [
    "京A8X3K7",   # 普通蓝牌
    "京N12345",   # 北京 N 号段（曾被误判）
    "京P88888",   # 北京 P 号段（曾被误判）
    "沪B5M2N9",
    "粤C3Q8L1",
    "川F2H6W8",
    "沪AD12345",  # 新能源 8 位
])
def test_valid_plates(plate):
    assert validate_plate(plate) is True


@pytest.mark.parametrize("plate", [
    "",
    "   ",
    "ABC123",          # 首位不是省份简称
    "京A123",          # 长度不足
    "京A123456789",    # 长度超限
    "北京A12345",      # 省份写成了全称
])
def test_invalid_plates(plate):
    assert validate_plate(plate) is False


def test_lowercase_is_normalized():
    """小写输入应自动转大写后通过。"""
    assert validate_plate("京a8x3k7") is True


def test_separator_is_stripped():
    """带分隔符/空格的输入应清洗后通过。"""
    assert validate_plate("京A·8X3K7") is True
    assert validate_plate(" 京A 8X3 K7 ") is True
