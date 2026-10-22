# -*- coding: utf-8 -*-
"""
通用常量：
- 车辆类型
- 车牌省份简称（用于校验 / 颜色分类）
- 角色
"""

VEHICLE_TYPES = ("小型车", "大型车")

# 中国大陆车牌省份简称（用于校验首字）
PROVINCE_PREFIXES = (
    "京", "沪", "津", "渝", "冀", "豫", "云", "辽", "黑", "湘",
    "皖", "鲁", "新", "苏", "浙", "赣", "鄂", "桂", "甘", "晋",
    "蒙", "陕", "吉", "闽", "贵", "粤", "青", "藏", "川", "宁",
    "琼",
)

ROLE_ADMIN    = "admin"
ROLE_OPERATOR = "operator"
ALL_ROLES     = (ROLE_ADMIN, ROLE_OPERATOR)