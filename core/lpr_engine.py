# -*- coding: utf-8 -*-
"""
HyperLPR3 深度学习引擎封装（可选高精度后端）

为什么需要它
------------
内置模板匹配 OCR 的原理是"渲染字体 → 逐字比对"，它在合成图上很准，
但真实抓拍图里有三个它扛不住的因素：

    1) 车牌字体不是系统字体 —— 国标 GA36 的专用字体（长黑体）与
       Windows 黑体的笔画、字宽差异明显，IoU 相似度只有 0.3~0.4；
    2) 车牌不是等距 7 格 —— 省份汉字更宽，且第 2、3 位之间有一个
       分隔圆点，按 7 等分切分必然错位；
    3) 真实场景有倾斜、透视畸变、反光、脏污。

HyperLPR3 是面向中文车牌的端到端方案：
    YOLO 检测车牌四点 → 透视矫正 → CNN+BiLSTM+CTC 序列识别
它在真实车牌数据集上训练，因此不需要切分字符，也不需要字体模板。

本模块只做封装，不改动第三方库；模型文件随项目放在
`models/hyperlpr3/20230229/onnx/`，无需联网。

依赖：hyperlpr3 + onnxruntime（未安装时 available 为 False，自动降级）
"""

from __future__ import annotations

import importlib.util
import sys
import threading
import types
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import numpy as np

from config import (
    HYPERLPR_DIR,
    HYPERLPR_MODEL_VERSION,
    HYPERLPR_DETECT_LEVEL,
)
from utils.logger import get_logger

logger = get_logger()


# 模型文件清单（缺任意一个就认为模型不完整）
_REQUIRED_MODELS = (
    "y5fu_320x_sim.onnx",        # 检测（320x320）
    "y5fu_640x_sim.onnx",        # 检测（640x640）
    "rpv3_mdict_160_r3.onnx",    # 识别（CRNN + CTC）
    "litemodel_cls_96x_r1.onnx", # 车牌颜色/类型分类
)


@dataclass
class LprDetection:
    """一次车牌检测 + 识别的结果。"""
    plate_text: str
    confidence: float
    box: tuple                    # (x1, y1, x2, y2)
    plate_type: int = -1          # 见 hyperlpr3.common.typedef

    def __post_init__(self):
        self.box = tuple(int(v) for v in self.box)


def _import_hyperlpr3(model_dir: Path):
    """
    导入 hyperlpr3，并把它的默认模型目录固定到项目内路径。

    为什么要这么绕
    --------------
    hyperlpr3 的 config/settings.py 在 Windows 上这样算模型目录：

        _DEFAULT_FOLDER_ = os.path.join(os.environ['HOMEPATH'], ".hyperlpr3")

    而 Windows 的 HOMEPATH 形如 ``\\Users\\86136``（**不含盘符**，
    盘符在 HOMEDRIVE 里）。这个字符串被 join 之后仍然是
    ``\\Users\\86136\\.hyperlpr3``，会被解析成"当前盘符根目录"下的路径。
    结果是：工作目录在 E: 盘时模型跑到 ``E:\\Users\\86136\\.hyperlpr3``，
    换个目录启动就找不到模型，又去联网下载 12MB。

    解决方式：在 ``import hyperlpr3`` 之前，先把它的 settings 模块
    手动载入 sys.modules 并改写 ``_DEFAULT_FOLDER_``。这样导入阶段执行的
    ``initialization()`` 会直接认可项目内模型，不会触发下载。
    """
    if "hyperlpr3" in sys.modules:
        return sys.modules["hyperlpr3"]

    spec = importlib.util.find_spec("hyperlpr3")
    if spec is None or not spec.submodule_search_locations:
        raise ImportError("未安装 hyperlpr3")

    pkg_dir = Path(next(iter(spec.submodule_search_locations)))
    settings_py = pkg_dir / "config" / "settings.py"
    if not settings_py.exists():
        # 目录结构与预期不符（版本差异）→ 退回普通导入
        import hyperlpr3
        return hyperlpr3

    # 1) 占位父包，避免导入 settings 时触发 hyperlpr3/__init__.py
    cfg_pkg = types.ModuleType("hyperlpr3.config")
    cfg_pkg.__path__ = [str(pkg_dir / "config")]
    sys.modules.setdefault("hyperlpr3.config", cfg_pkg)

    # 2) 单独载入 settings 并改写默认目录
    s_spec = importlib.util.spec_from_file_location(
        "hyperlpr3.config.settings", settings_py)
    settings = importlib.util.module_from_spec(s_spec)
    sys.modules["hyperlpr3.config.settings"] = settings
    s_spec.loader.exec_module(settings)
    settings._DEFAULT_FOLDER_ = str(model_dir.resolve())

    # 3) 此时再正常导入，initialization() 会认为模型已就位
    import hyperlpr3
    return hyperlpr3


class HyperLprEngine:
    """
    HyperLPR3 推理封装（进程内单例）。

        engine = HyperLprEngine.shared()
        if engine.available:
            for d in engine.detect(image):
                print(d.plate_text, d.confidence, d.box)

    推理模型首次加载约 1~2 秒，之后单张图 30~80ms（320x 档）。
    """

    _shared: Optional["HyperLprEngine"] = None
    _lock = threading.Lock()

    @classmethod
    def shared(cls) -> "HyperLprEngine":
        with cls._lock:
            if cls._shared is None:
                cls._shared = cls()
        return cls._shared

    def __init__(self,
                 model_dir: str | Path | None = None,
                 detect_level: str | None = None):
        self._model_dir = Path(model_dir) if model_dir else Path(HYPERLPR_DIR)
        self._detect_level = (detect_level or HYPERLPR_DETECT_LEVEL).lower()
        self._catcher = None
        self._loaded = False
        self._error = ""

    # ------------------------------------------------------------------
    @property
    def available(self) -> bool:
        self._ensure_loaded()
        return self._catcher is not None

    @property
    def error(self) -> str:
        return self._error

    @property
    def name(self) -> str:
        return "HyperLPR3"

    def _model_root(self) -> Path:
        return self._model_dir / HYPERLPR_MODEL_VERSION / "onnx"

    def models_present(self) -> bool:
        root = self._model_root()
        return all((root / m).exists() for m in _REQUIRED_MODELS)

    # ------------------------------------------------------------------
    def _ensure_loaded(self):
        if self._loaded:
            return
        self._loaded = True

        if not self.models_present():
            self._error = f"模型文件缺失：{self._model_root()}"
            logger.warning(self._error)
            return

        try:
            lpr3 = _import_hyperlpr3(self._model_dir)
            level = (lpr3.DETECT_LEVEL_HIGH
                     if self._detect_level == "high"
                     else lpr3.DETECT_LEVEL_LOW)
            # logger_level=4 关闭 onnxruntime 的 INFO 刷屏
            self._catcher = lpr3.LicensePlateCatcher(
                folder=str(self._model_dir),
                detect_level=level,
                logger_level=4,
            )
            logger.info(f"HyperLPR3 引擎就绪（detect_level={self._detect_level}）")
        except Exception as e:
            self._error = f"{type(e).__name__}: {e}"
            # 最常见的失败其实不是"没装"，而是加载顺序冲突：
            # PyQt5 先于 onnxruntime 加载时，onnxruntime 的 DLL 初始化会失败。
            # 这种失败看起来像"模型坏了"，很容易误判，所以单独点出来。
            if "onnxruntime" in str(e).lower() and "dll" in str(e).lower():
                self._error += (
                    "｜这是 PyQt5 与 onnxruntime 的 DLL 加载顺序冲突："
                    "必须在 import PyQt5 之前先 import onnxruntime。"
                    "main.py 与 tests/conftest.py 已做前置处理，"
                    "自写脚本请照做。"
                )
            logger.warning(f"HyperLPR3 初始化失败，将降级到内置管线：{self._error}")
            self._catcher = None

    # ------------------------------------------------------------------
    def detect(self, image: np.ndarray) -> List[LprDetection]:
        """
        对整张图做车牌检测 + 识别。

        返回按置信度降序排列的结果；无车牌或不可用时返回空列表。
        """
        self._ensure_loaded()
        if self._catcher is None or image is None or image.size == 0:
            return []

        try:
            raw = self._catcher(image)
        except Exception as e:
            logger.warning(f"HyperLPR3 推理失败：{e}")
            return []

        out: List[LprDetection] = []
        for item in raw or []:
            try:
                code, conf, ptype, box = item[0], item[1], item[2], item[3]
            except Exception:
                continue
            if not code or len(box) < 4:
                continue
            out.append(LprDetection(
                plate_text=str(code),
                confidence=float(conf),
                box=(box[0], box[1], box[2], box[3]),
                plate_type=int(ptype),
            ))

        out.sort(key=lambda d: d.confidence, reverse=True)
        return out
