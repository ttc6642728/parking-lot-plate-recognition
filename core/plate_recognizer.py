# -*- coding: utf-8 -*-
"""
车牌识别顶层封装：双引擎 + 自动仲裁

    PlateRecognizer.shared().recognize(image) → RecognitionResult

为什么是"双引擎"
----------------
两套识别方案各有擅长，单独用都会在某一类输入上翻车：

    ┌ HyperLPR3（深度学习）
    │   检测车牌四点 → 透视矫正 → CNN+BiLSTM+CTC 直接输出整串
    │   ✓ 真实抓拍图（车身上的车牌、有透视、光照不均）
    │   ✗ 纯车牌特写图（缺少车辆上下文，训练分布不同）
    │
    └ 内置管线（传统 CV）
        颜色/边缘定位 → 二值化 → 投影切分 → 字体模板匹配
        ✓ 字体规范、正面平整的车牌特写
        ✗ 真实抓拍（国标专用字体与系统字体差异大，IoU 只有 0.3~0.4）

仲裁依据
--------
不用"谁置信度高用谁"—— 两个引擎的置信度含义不同，不能直接比较。
而是看**内置管线对自己结果有多确信**（模板 IoU 得分）：

    真实车图   内置得分 ≈ 0.29（模板根本匹配不上）→ 采信 HyperLPR3
    标准特写图 内置得分 ≈ 0.67~0.77（模板高度吻合）→ 采信内置

这个信号量恰好反映了"输入字体与模板字体是否同源"，比拍脑袋定阈值可靠。

降级策略
--------
未安装 onnxruntime / 模型缺失 / PLATE_ENGINE="builtin" 时，
自动退回单引擎运行，功能不受影响。
"""

from __future__ import annotations

import random
import string
import threading
import time
from dataclasses import dataclass, field
from typing import List, Optional

import cv2
import numpy as np

from config import (
    YOLO_FALLBACK_OPENCV,
    YOLO_WEIGHTS,
    YOLO_CONF,
    YOLO_IOU,
    DEMO_MODE,
    DEMO_PLATE_PREFIXES,
    PLATE_ENGINE,
    PLATE_MIN_CONFIDENCE,
    PLATE_BUILTIN_SELF_TRUST,
)
from utils.constants import PROVINCE_PREFIXES
from utils.image_utils import crop_safe
from utils.logger import get_logger

logger = get_logger()


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------
@dataclass
class PlateBox:
    box:        tuple                # (x1, y1, x2, y2)
    plate_text: str     = ""
    confidence: float   = 0.0
    is_plate:   bool    = False      # 是否判定为车牌 (而非车辆)


@dataclass
class RecognitionResult:
    success:    bool = False
    message:    str  = ""
    boxes:      List[PlateBox] = field(default_factory=list)
    image:      Optional[np.ndarray] = None         # 带标注的 BGR 图
    elapsed_ms: float = 0.0
    engine:     str  = ""                            # 实际生效的识别引擎
    note:       str  = ""                            # 补充说明（如引擎分歧）

    def _sorted_plates(self) -> list:
        ok = [b for b in self.boxes if b.is_plate and b.plate_text]
        ok.sort(key=lambda b: b.confidence, reverse=True)
        return ok

    @property
    def best_plate(self) -> str:
        ok = self._sorted_plates()
        return ok[0].plate_text if ok else ""

    @property
    def confidence_of_best(self) -> float:
        ok = self._sorted_plates()
        return ok[0].confidence if ok else 0.0


# ---------------------------------------------------------------------------
# 车牌号校验
# ---------------------------------------------------------------------------
def _normalize_plate_text(text: str) -> str:
    """清洗 OCR 输出：去除空格、特殊符号，仅保留字母数字汉字。"""
    if not text:
        return ""
    # 去除常见错误字符
    bad_chars = " \n\r\t·.,。:：;；'`\"!?()-_+=*/\\|[]{}<>~@#$%^&"
    for c in bad_chars:
        text = text.replace(c, "")
    text = text.upper()
    # 把数字 0/1 与字母 O/I 的常见互换修复（保守处理）
    return text


def _validate_plate(text: str) -> bool:
    """
    校验车牌格式是否基本合法。

    规则：省份简称 + 发牌机关字母 + 4~6 位字母数字。

    ⚠ 第 2 位必须是 A-Z 全字母范围：京N、京P、京Q、京Y、沪C 等都是
      真实存在的号段。早期版本限制为 A-H，会把大量真实车牌误判为非法，
      进而被 DEMO 兜底逻辑覆盖，掩盖了识别错误。
    """
    if not text or len(text) < 6 or len(text) > 8:
        return False
    if text[0] not in PROVINCE_PREFIXES:
        return False
    if not ("A" <= text[1] <= "Z"):
        return False
    tail = text[2:]
    if len(tail) < 4:
        return False
    return all(c.isdigit() or ("A" <= c <= "Z") for c in tail)


def validate_plate(text: str) -> bool:
    """公开接口：标准化后判断车牌格式（供 UI 校验手动输入）。"""
    return _validate_plate(_normalize_plate_text(text))


def _mock_plate() -> str:
    """演示模式：生成一个合法格式的模拟车牌，如 京A·8X3K7。"""
    prefix = random.choice(DEMO_PLATE_PREFIXES)
    tail = "".join(random.choices(
        string.ascii_uppercase.replace("I", "").replace("O", "")
        + string.digits, k=5,
    ))
    return prefix + tail


# ---------------------------------------------------------------------------
# PlateRecognizer
# ---------------------------------------------------------------------------
class PlateRecognizer:
    """
    顶层接口：

        recognizer = PlateRecognizer.shared()   # 推荐：进程内共享
        result = recognizer.recognize(bgr_image)

    ⚠ 请优先使用 shared()：YOLO 与 HyperLPR3 加载都要数秒且占用数百 MB 内存，
      识别/入场/出场三个页面各 new 一个会导致模型被加载多次。
    """

    _shared: Optional["PlateRecognizer"] = None

    @classmethod
    def shared(cls) -> "PlateRecognizer":
        """进程内单例（首次调用时创建）。"""
        if cls._shared is None:
            cls._shared = cls()
        return cls._shared

    def __init__(self,
                 yolo_weights: str = str(YOLO_WEIGHTS),
                 yolo_conf: float = YOLO_CONF,
                 yolo_iou:  float = YOLO_IOU,
                 fallback_opencv: bool = YOLO_FALLBACK_OPENCV):
        self._yolo_weights     = yolo_weights
        self._yolo_conf        = yolo_conf
        self._yolo_iou         = yolo_iou
        self._fallback_opencv  = fallback_opencv

        self._yolo   = None
        self._ocr    = None      # Tesseract OCR
        self._tmpl   = None      # 内置模板匹配 OCR
        self._loaded = False
        self._deep_ok = False
        # 加载锁：UI 会从后台线程预热，用户又可能同时点"识别"，
        # 没有锁会并发加载两份模型（多占几百 MB、启动更慢）。
        self._load_lock = threading.Lock()

    def status(self) -> dict:
        """
        各引擎的可用状态（只读，不触发任何加载）。

        界面用它刷新"引擎状态"面板。早期版本是直接 new 一个 OcrRecognizer()
        来探测，等于在主线程把 Tesseract 又初始化一遍，界面会卡 1~2 秒。
        """
        return {
            "loaded":    self._loaded,
            "deep":      self._deep_ok,
            "tesseract": self._ocr is not None,
            "template":  self._tmpl is not None,
        }

    # ------------------------------------------------------------------
    # 加载
    # ------------------------------------------------------------------
    def warmup(self) -> None:
        """
        预热：只加载模型，不做推理。

        界面进入识别页时在后台线程调用一次，把"首次识别卡十几秒"
        提前到用户还在看界面的阶段（加载 YOLO + 两个 OCR + onnx 约 15~20 秒）。
        """
        try:
            self._ensure_loaded()
        except Exception as e:
            logger.warning(f"模型预热失败（不影响后续重试）：{e}")

    def _ensure_loaded(self):
        if self._loaded:
            return
        with self._load_lock:
            if self._loaded:          # 等锁期间可能已被别的线程加载完
                return
            self._load_impl()
            self._loaded = True

    def _load_impl(self):
        # 延迟 import
        from .yolo_detector  import YoloDetector
        from .ocr_recognizer import OcrRecognizer

        try:
            self._yolo = YoloDetector(
                weights=self._yolo_weights,
                conf=self._yolo_conf,
                iou=self._yolo_iou,
            )
            logger.info("YOLO 模型加载成功")
        except Exception as e:
            logger.warning(f"YOLO 加载失败：{e}")
            self._yolo = None

        # Tesseract OCR（可选，仅作为内置管线的补充）
        try:
            ocr = OcrRecognizer()
            if ocr.available:
                self._ocr = ocr
                logger.info("OCR 初始化成功：Tesseract")
            else:
                logger.warning("Tesseract 不可用")
        except Exception as e:
            logger.warning(f"Tesseract 初始化失败：{e}")
            self._ocr = None

        # 内置模板匹配 OCR（零外部依赖）：既作为主力，也是 Tesseract 的兜底。
        # ⚠ 必须无条件初始化 —— Tesseract 可能"能报版本但实际识别报错"
        #   （如安装路径含中文），此时只有模板 OCR 能顶上。
        try:
            from .template_ocr import TemplateOcr
            tmpl = TemplateOcr()
            if tmpl.available:
                self._tmpl = tmpl
                logger.info("内置模板 OCR 就绪")
            else:
                logger.warning("内置模板 OCR 不可用（缺中文字体？）")
        except Exception as e:
            logger.warning(f"模板 OCR 初始化失败：{e}")
            self._tmpl = None

        # 加载深度学习引擎。
        # ⚠ 关于 onnxruntime 的加载顺序：若本进程尚未 import onnxruntime 就
        #   开始构造 InferenceSession，且 PyQt5 已加载，会抛
        #   "DLL load failed while importing onnxruntime_pybind11_state"。
        #   main.py / conftest.py 已在导入 PyQt5 之前预先加载 onnxruntime，
        #   因此这里即使在后台线程执行也是安全的；本模块自身也做了异常降级。
        if PLATE_ENGINE in ("auto", "hyperlpr3"):
            try:
                from .lpr_engine import HyperLprEngine
                engine = HyperLprEngine.shared()
                self._deep_ok = bool(engine.available)
                if not engine.available:
                    logger.warning(f"深度学习引擎不可用：{engine.error}")
            except Exception as e:
                self._deep_ok = False
                logger.warning(f"深度学习引擎预热失败：{e}")

    # ------------------------------------------------------------------
    # OCR 统一入口：内置模板匹配 → Tesseract
    # ------------------------------------------------------------------
    def _do_ocr(self, crop: np.ndarray) -> tuple[str, float]:
        """
        对已定位的车牌裁剪图做字符识别。

        优先级：内置模板匹配 OCR → Tesseract。

        原因：模板 OCR 针对中国车牌做了位置先验（首位省份汉字、次位字母），
              在标准车牌上明显优于通用 OCR；Tesseract 更适合作为兜底，
              直接让它优先会把 粤C3Q8L1 识别成 ZCSQSE 这类乱码。
        """
        tmpl_text, tmpl_conf = "", 0.0

        if self._tmpl is not None:
            try:
                tmpl_text, tmpl_conf = self._tmpl.recognize(crop)
                if tmpl_text and _validate_plate(_normalize_plate_text(tmpl_text)):
                    return tmpl_text, tmpl_conf
            except Exception as e:
                logger.warning(f"模板 OCR 失败：{e}")

        if self._ocr is not None:
            try:
                text, conf = self._ocr.recognize(crop)
                if text:
                    return text, conf
            except Exception as e:
                logger.warning(f"Tesseract OCR 失败：{e}")

        return tmpl_text, tmpl_conf

    # ------------------------------------------------------------------
    # 深度学习引擎（HyperLPR3）
    # ------------------------------------------------------------------
    def _run_deep_engine(self, image: np.ndarray) -> list:
        """
        调用 HyperLPR3 做端到端检测 + 识别。

        未启用（PLATE_ENGINE="builtin"）、未安装或模型缺失时返回空列表，
        由内置管线接管 —— 保证在没有 onnxruntime 的机器上也能运行。
        """
        if PLATE_ENGINE not in ("auto", "hyperlpr3"):
            return []
        try:
            from .lpr_engine import HyperLprEngine
            engine = HyperLprEngine.shared()
            if not engine.available:
                return []
            return engine.detect(image)
        except Exception as e:
            logger.warning(f"深度学习引擎调用失败：{e}")
            return []

    @staticmethod
    def _annotate(image: np.ndarray, boxes: list) -> np.ndarray:
        """在图上画出候选框与识别文本。"""
        out = image.copy()
        for pb in boxes:
            color = (0, 200, 0) if pb.is_plate else (200, 200, 0)
            label = pb.plate_text if pb.plate_text else "Plate?"
            cv2.rectangle(out,
                          (int(pb.box[0]), int(pb.box[1])),
                          (int(pb.box[2]), int(pb.box[3])),
                          color, 2)
            cv2.putText(out, label,
                        (int(pb.box[0]), max(0, int(pb.box[1]) - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, color, 2, cv2.LINE_AA)
        return out

    # ------------------------------------------------------------------
    # 内置管线：定位 + 模板 OCR
    # ------------------------------------------------------------------
    def _recognize_builtin(self, image: np.ndarray) -> RecognitionResult:
        """传统 CV 管线：YOLO/OpenCV 定位车牌 → 字符识别。"""
        out = RecognitionResult(message="识别中…")
        candidates: list[tuple] = []   # (box, is_plate_candidate)

        # 1) YOLO 检测
        if self._yolo is not None:
            try:
                detections = self._yolo.detect(image)
                for det in detections:
                    candidates.append((det["box"],
                                       "plate" in det["class_name"].lower()))
            except Exception as e:
                logger.warning(f"YOLO 检测失败：{e}")

        # 2) 兜底：OpenCV 传统车牌定位
        if not candidates and self._fallback_opencv:
            from .image_preprocess import detect_plates_opencv
            for b in detect_plates_opencv(image):
                candidates.append((b, True))

        if not candidates:
            out.message = "内置管线未检测到车牌"
            return out

        from .image_preprocess import detect_plates_opencv

        # 3) 对每个候选框处理
        #    若是"车辆框"，先在框内二次定位车牌；若是"车牌框"，直接 OCR。
        for box, is_plate_candidate in candidates:
            crop = crop_safe(image, box)
            if crop is None:
                continue

            targets: list[tuple] = []      # [(裁剪图, 原图绝对坐标box)]

            if is_plate_candidate:
                targets.append((crop, box))
            else:
                # 车辆框 → 框内二次定位车牌
                sub_boxes = detect_plates_opencv(crop)
                if sub_boxes:
                    for sb in sub_boxes[:3]:
                        sc = crop_safe(crop, sb)
                        if sc is None:
                            continue
                        abs_box = (box[0] + sb[0], box[1] + sb[1],
                                   box[0] + sb[2], box[1] + sb[3])
                        targets.append((sc, abs_box))
                else:
                    # 无候选：取车身下部区域（车牌多在保险杠附近）
                    ch = crop.shape[0]
                    y_off = int(ch * 0.55)
                    lower = crop[y_off:, :]
                    if lower is not None and lower.size > 0:
                        abs_box = (box[0], box[1] + y_off, box[2], box[3])
                        targets.append((lower, abs_box))

            for t_crop, t_box in targets:
                plate_text, ocr_conf = self._do_ocr(t_crop)
                plate_text_clean = _normalize_plate_text(plate_text)
                valid = _validate_plate(plate_text_clean)

                out.boxes.append(PlateBox(
                    box=t_box,
                    plate_text=plate_text_clean,
                    confidence=ocr_conf,
                    is_plate=valid or is_plate_candidate,
                ))

        out.engine = "内置管线"
        return out

    # ------------------------------------------------------------------
    # 仲裁
    # ------------------------------------------------------------------
    @staticmethod
    def _arbitrate(result: RecognitionResult,
                   builtin: RecognitionResult,
                   deep) -> None:
        """
        在"深度学习结果"和"内置管线结果"之间做选择。

        deep 为 LprDetection 或 None（已通过 PLATE_MIN_CONFIDENCE 过滤）。
        """
        b_text = builtin.best_plate
        b_conf = builtin.confidence_of_best
        d_text = _normalize_plate_text(deep.plate_text) if deep else ""
        d_conf = deep.confidence if deep else 0.0

        def _use_deep(note: str = ""):
            result.boxes = [PlateBox(box=deep.box, plate_text=d_text,
                                     confidence=d_conf, is_plate=True)]
            result.engine = "HyperLPR3"
            result.success = True
            result.message = f"识别成功：{d_text}（置信度 {d_conf:.1%}）"
            result.note = note

        def _use_builtin(note: str = ""):
            result.boxes = builtin.boxes
            result.engine = "内置管线"
            result.success = True
            result.message = f"识别成功：{b_text}"
            result.note = note

        # 情况一：两者都没结果
        if not d_text and not b_text:
            result.boxes = builtin.boxes
            result.message = "未检测到车牌"
            return

        # 情况二：只有深度学习有结果
        if d_text and not b_text:
            _use_deep()
            return

        # 情况三：只有内置管线有结果
        if b_text and not d_text:
            _use_builtin()
            return

        # 情况四：两者一致 —— 最可信，取深度引擎的框与置信度
        if b_text == d_text:
            _use_deep("两个引擎结果一致")
            result.engine = "双引擎一致"
            return

        # 情况五：两者不一致 —— 看内置管线对自己有多确信
        #   模板 IoU 高 = 输入字体与模板字体同源 = 内置结果可信
        #   模板 IoU 低 = 模板匹配不上真实字形 = 改用深度学习
        if b_conf >= PLATE_BUILTIN_SELF_TRUST:
            _use_builtin(
                f"引擎分歧：内置={b_text}(自评 {b_conf:.2f})，"
                f"HyperLPR3={d_text}({d_conf:.1%})，采用内置结果")
        else:
            _use_deep(
                f"引擎分歧：HyperLPR3={d_text}({d_conf:.1%})，"
                f"内置={b_text}(自评 {b_conf:.2f})，采用 HyperLPR3 结果")

        if result.note:
            logger.warning(result.note)

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------
    def recognize(self, image: np.ndarray,
                  draw_on_image: bool = True) -> RecognitionResult:
        self._ensure_loaded()
        t0 = time.time()
        result = RecognitionResult(message="识别中…")

        if image is None or image.size == 0:
            result.message = "图像为空"
            result.elapsed_ms = (time.time() - t0) * 1000
            return result

        # A+B) 两个引擎并行跑，总耗时取较慢的那个而不是相加。
        #      onnxruntime 与 OpenCV 都会释放 GIL，双线程确有收益
        #      （实测 1.4s → 0.7s）。任一引擎抛错不影响另一个。
        deep_results: list = []
        builtin = RecognitionResult(message="识别中…")
        try:
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(max_workers=2) as pool:
                f_deep = pool.submit(self._run_deep_engine, image)
                f_built = pool.submit(self._recognize_builtin, image)
                deep_results = f_deep.result(timeout=30)
                builtin = f_built.result(timeout=30)
        except Exception as e:
            logger.warning(f"并行识别失败，回退串行：{e}")
            deep_results = self._run_deep_engine(image)
            builtin = self._recognize_builtin(image)

        # 置信度不足的深度结果直接丢弃，不让它污染后续判断
        deep_best = None
        if deep_results:
            trusted = [d for d in deep_results
                       if d.confidence >= PLATE_MIN_CONFIDENCE]
            if trusted:
                deep_best = trusted[0]
            else:
                logger.info(
                    f"HyperLPR3 置信度不足（最高 {deep_results[0].confidence:.2f}"
                    f" < {PLATE_MIN_CONFIDENCE}），转内置管线复核")

        # C) 仲裁
        self._arbitrate(result, builtin, deep_best)

        # D) 演示模式兜底：两个引擎都没结果时才伪造车牌，保证流程可演示。
        #    ⚠ 正式提交/运行必须保持 DEMO_MODE = False。
        if (not result.success) and DEMO_MODE and result.boxes:
            mock = _mock_plate()
            first = result.boxes[0]
            first.plate_text = mock
            first.is_plate   = True
            first.confidence = max(first.confidence, 0.9)
            result.success   = True
            result.engine    = "演示模式"
            result.message   = f"识别成功（演示模式）：{mock}"
            logger.info(f"演示模式生成车牌：{mock}")

        if draw_on_image:
            result.image = self._annotate(image, result.boxes)

        result.elapsed_ms = (time.time() - t0) * 1000
        if result.success:
            logger.info(f"[{result.engine}] {result.best_plate} "
                        f"({result.elapsed_ms:.0f}ms)")
        return result
