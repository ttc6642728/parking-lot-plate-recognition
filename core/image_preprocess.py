# -*- coding: utf-8 -*-
"""
传统图像预处理与车牌区域定位（YOLO 不可用时的兜底）。

思路：
    1) 灰度 → 高斯模糊
    3) Sobel 边缘 → 自适应阈值二值化
    4) 闭运算 → 寻找轮廓
    5) 按面积 / 长宽比筛选疑似车牌矩形
"""

from __future__ import annotations

from typing import List, Tuple

import cv2
import numpy as np


def preprocess_for_plate(image: np.ndarray) -> np.ndarray:
    """返回预处理后的二值图，用于后续轮廓/车牌定位。"""
    if image is None or image.size == 0:
        return np.zeros((0, 0), dtype=np.uint8)

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 \
        else image
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    sobel = cv2.Sobel(blur, cv2.CV_8U, 1, 0, ksize=3)

    # 自适应阈值
    bw = cv2.adaptiveThreshold(
        sobel, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 31, 10,
    )

    # 闭运算
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (17, 5))
    closed = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, kernel)
    return closed


# ----------------------------------------------------------------------
# 车牌底色 HSV 范围（OpenCV H ∈ 0~179）
#   蓝牌（小型车）/ 黄牌（大型车）/ 绿牌（新能源）
# ----------------------------------------------------------------------
PLATE_COLOR_RANGES = [
    ("蓝牌", np.array([90,  60, 50]),  np.array([130, 255, 255])),
    ("黄牌", np.array([11,  80, 80]),  np.array([34,  255, 255])),
    ("绿牌", np.array([35,  50, 50]),  np.array([85,  255, 255])),
    ("白牌", np.array([0,    0, 180]), np.array([179,  40, 255])),
]


def _boxes_from_mask(mask: np.ndarray,
                     img_area: float,
                     img_w: int, img_h: int) -> List[Tuple[int, int, int, int]]:
    """从二值掩膜里按面积+宽高比筛出候选车牌框。"""
    boxes: List[Tuple[int, int, int, int]] = []

    contours, _ = cv2.findContours(
        mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE,
    )
    for cnt in contours:
        area = cv2.contourArea(cnt)
        # 太小（噪声）/ 太大（把整片车身背景框进来）都排除
        if area < img_area * 0.0008 or area > img_area * 0.35:
            continue

        x, y, w, h = cv2.boundingRect(cnt)
        if w <= 0 or h <= 0:
            continue

        aspect = w / h
        # 中国车牌长宽比约 3.1（440x140），放宽到 1.6~7 兼容斜视
        if aspect < 1.6 or aspect > 7.0:
            continue

        # 边界保护
        x1, y1 = max(0, x), max(0, y)
        x2, y2 = min(img_w - 1, x + w), min(img_h - 1, y + h)
        if (x2 - x1) < 24 or (y2 - y1) < 8:
            continue

        boxes.append((x1, y1, x2, y2))

    return boxes


def _detect_by_color(image: np.ndarray) -> List[Tuple[int, int, int, int]]:
    """策略一：按车牌底色（蓝/黄/绿/白）在 HSV 空间分割。"""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    img_h, img_w = image.shape[:2]
    img_area = float(img_h * img_w)

    # 闭运算把车牌连成整块
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (17, 5))

    all_boxes: List[Tuple[int, int, int, int]] = []
    for _name, lower, upper in PLATE_COLOR_RANGES:
        mask = cv2.inRange(hsv, lower, upper)
        # 白色车牌容易和车身/背景混淆，容差收紧
        if _name == "白牌":
            continue
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,
                                cv2.getStructuringElement(
                                    cv2.MORPH_RECT, (3, 3)))
        all_boxes += _boxes_from_mask(mask, img_area, img_w, img_h)

    return all_boxes


def _detect_by_morph(image: np.ndarray) -> List[Tuple[int, int, int, int]]:
    """策略二：Sobel 边缘 + 形态学（颜色策略失效时的补充）。"""
    closed = preprocess_for_plate(image)
    if closed.size == 0:
        return []
    img_h, img_w = image.shape[:2]
    return _boxes_from_mask(closed, float(img_h * img_w), img_w, img_h)


def _nms(boxes: List[Tuple[int, int, int, int]],
         iou_thr: float = 0.5) -> List[Tuple[int, int, int, int]]:
    """简单 NMS 去重（按面积从大到小保留）。"""
    if not boxes:
        return []
    # 优先保留宽高比最接近标准车牌（≈3.1）的框
    def score(b):
        w, h = b[2] - b[0], b[3] - b[1]
        area = w * h
        ratio = w / max(1, h)
        return -(abs(ratio - 3.1) * 1000) + area / 1000.0

    boxes = sorted(set(boxes), key=score, reverse=True)
    keep: List[Tuple[int, int, int, int]] = []
    for b in boxes:
        dup = False
        for k in keep:
            ix1, iy1 = max(b[0], k[0]), max(b[1], k[1])
            ix2, iy2 = min(b[2], k[2]), min(b[3], k[3])
            inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
            union = ((b[2] - b[0]) * (b[3] - b[1])
                     + (k[2] - k[0]) * (k[3] - k[1]) - inter)
            if union > 0 and inter / union > iou_thr:
                dup = True
                break
        if not dup:
            keep.append(b)
    return keep


def detect_plates_opencv(image: np.ndarray) -> List[Tuple[int, int, int, int]]:
    """
    返回候选车牌框列表 (x1, y1, x2, y2)。

    双策略：颜色分割（主） + 形态学边缘（辅），最后 NMS 去重。
    """
    if image is None or image.size == 0:
        return []

    boxes = _detect_by_color(image)
    if not boxes:
        boxes = _detect_by_morph(image)

    return _nms(boxes)[:5]