# -*- coding: utf-8 -*-
"""
YOLO 检测器封装：

- 优先使用 ultralytics YOLOv8；
- 若权重不存在或加载失败，可通过 close() 释放，再调用 ensure_loaded() 重试。
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any

import numpy as np

from utils.logger import get_logger

logger = get_logger()


class YoloDetector:
    """对 ultralytics YOLO 的轻量封装。"""

    def __init__(self, weights: str, conf: float = 0.35, iou: float = 0.45):
        self.weights = weights
        self.conf    = conf
        self.iou     = iou
        self._model  = None

        try:
            self._load()
        except Exception as e:
            logger.warning(f"YOLO 初始化失败：{e}")

    # ------------------------------------------------------------------
    def _load(self):
        from ultralytics import YOLO    # 延迟导入
        weight_path = Path(self.weights)
        # 1) 自定义权重
        # 2) 若不存在则下载使用通用模型（ultralytics 会自动下载到 ~/.cache）
        if not weight_path.exists():
            logger.info(f"权重 {self.weights} 不存在，改用 ultralytics 默认 yolov8n")
            self.weights = "yolov8n.pt"

        logger.info(f"加载 YOLO 模型：{self.weights}")
        self._model = YOLO(self.weights)
        # 预热
        try:
            dummy = np.zeros((640, 640, 3), dtype=np.uint8)
            self._model.predict(dummy, verbose=False, conf=self.conf, iou=self.iou)
        except Exception:
            pass

    # ------------------------------------------------------------------
    def detect(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """返回 [{box, class_id, class_name, confidence}, ...]"""
        if self._model is None:
            return []
        if image is None or image.size == 0:
            return []

        try:
            res = self._model.predict(
                image, verbose=False, conf=self.conf, iou=self.iou,
            )
        except Exception as e:
            logger.warning(f"YOLO 推理失败：{e}")
            return []

        out: List[Dict[str, Any]] = []
        if not res:
            return out

        r = res[0]
        names = r.names if hasattr(r, "names") else {}
        if r.boxes is None:
            return out

        for b in r.boxes:
            try:
                x1, y1, x2, y2 = b.xyxy[0].tolist()
                cls_id   = int(b.cls[0])
                cls_name = names.get(cls_id, str(cls_id))
                conf     = float(b.conf[0])
                out.append({
                    "box":        (x1, y1, x2, y2),
                    "class_id":   cls_id,
                    "class_name": cls_name,
                    "confidence": conf,
                })
            except Exception:
                continue
        return out