# -*- coding: utf-8 -*-
"""双引擎仲裁逻辑测试。

`PlateRecognizer._arbitrate` 是纯函数，不加载任何模型，因此可以完全用
构造出来的假结果覆盖所有分支 —— 这是识别模块里最值得单测的部分：
识别错了不会崩，但"哪个引擎说了算"判断错了，业务就会用错车牌。

覆盖场景：
    1. 两个引擎都给结果且一致
    2. 只有深度学习给结果
    3. 只有内置管线给结果
    4. 两个都没有结果
    5. 结果不一致，内置管线自评高 → 采信内置
    6. 结果不一致，内置管线自评低 → 采信深度学习
"""

import pytest

from core.plate_recognizer import (
    PlateBox,
    PlateRecognizer,
    RecognitionResult,
)
from config import PLATE_BUILTIN_SELF_TRUST

BOX = (0, 0, 400, 130)


def _builtin(text: str, conf: float) -> RecognitionResult:
    r = RecognitionResult()
    if text:
        r.boxes = [PlateBox(box=BOX, plate_text=text,
                            confidence=conf, is_plate=True)]
    return r


class _FakeDeep:
    """模拟 lpr_engine.LprDetection。"""

    def __init__(self, text: str, conf: float):
        self.plate_text = text
        self.confidence = conf
        self.box = BOX
        self.plate_type = 0


def _run(builtin_text, builtin_conf, deep_text=None, deep_conf=0.0):
    result = RecognitionResult()
    deep = _FakeDeep(deep_text, deep_conf) if deep_text else None
    PlateRecognizer._arbitrate(result, _builtin(builtin_text, builtin_conf), deep)
    return result


# ---------------------------------------------------------------------------
def test_both_agree():
    r = _run("京A8X3K7", 0.72, "京A8X3K7", 0.99)
    assert r.success is True
    assert r.best_plate == "京A8X3K7"
    assert "双引擎" in r.engine
    # 一致时采用深度引擎的高置信度
    assert r.confidence_of_best == pytest.approx(0.99)


def test_only_deep_engine():
    r = _run("", 0.0, "冀T15888", 0.99)
    assert r.success is True
    assert r.best_plate == "冀T15888"
    assert r.engine == "HyperLPR3"


def test_only_builtin():
    r = _run("粤C3Q8L1", 0.70, None, 0.0)
    assert r.success is True
    assert r.best_plate == "粤C3Q8L1"
    assert r.engine == "内置管线"


def test_neither_has_result():
    r = _run("", 0.0, None, 0.0)
    assert r.success is False
    assert r.best_plate == ""


def test_disagree_builtin_confident():
    """内置自评高 → 说明输入字体与模板同源 → 采信内置。"""
    conf = PLATE_BUILTIN_SELF_TRUST + 0.15
    r = _run("沪B5M2N9", conf, "沪B5N2N9", 0.94)
    assert r.best_plate == "沪B5M2N9"
    assert r.engine == "内置管线"
    assert r.note, "分歧时应当记录说明，便于排查"


def test_disagree_builtin_unsure():
    """内置自评低 → 模板匹配不上真实字形 → 采信深度学习。"""
    conf = max(0.0, PLATE_BUILTIN_SELF_TRUST - 0.25)
    r = _run("津T1111", conf, "冀T15888", 0.99)
    assert r.best_plate == "冀T15888"
    assert r.engine == "HyperLPR3"
    assert r.note


def test_disagreement_always_recorded():
    """任何分歧都应写入 note，UI 会据此提示用户人工确认。"""
    r = _run("川F2H6W8", 0.67, "桂F2H6W8", 0.97)
    assert r.note
    assert "HyperLPR3" in r.note and "内置" in r.note


# ---------------------------------------------------------------------------
def test_hyperlpr_engine_optional():
    """装了 HyperLPR3 且模型齐全时，应能识别真实车牌。"""
    from core.lpr_engine import HyperLprEngine
    from utils.image_utils import load_image
    from pathlib import Path

    engine = HyperLprEngine.shared()
    if not engine.available:
        pytest.skip(f"HyperLPR3 不可用：{engine.error}")

    path = Path(__file__).resolve().parent.parent / "data" / "images" / "1KS31404-0.jpg"
    if not path.exists():
        pytest.skip("缺少真实车牌测试图")

    dets = engine.detect(load_image(str(path)))
    assert dets, "真实车牌图应当至少检出一个车牌"
    assert dets[0].plate_text == "冀T15888"
    assert dets[0].confidence > 0.9
