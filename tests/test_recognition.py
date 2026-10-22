# -*- coding: utf-8 -*-
"""内置识别管线测试（不依赖深度学习模型，保证测试快且可离线）。

说明：
    这里刻意固定 PLATE_ENGINE="builtin"，只验证「OpenCV 车牌定位 + 字体模板
    匹配」这条传统链路。它是没有 onnxruntime 时的兜底方案，也不受模型文件
    与网络影响，因此适合作为快速回归测试。

    双引擎仲裁的行为由 test_dual_engine.py 单独覆盖。

⚠ 注意：data/images 下的合成图与模板是同字体渲染的，
   100% 识别率只代表链路正确，不代表真实抓拍场景的准确率。
"""

from pathlib import Path

import json

import pytest

from utils.image_utils import load_image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
IMAGES_DIR = PROJECT_ROOT / "data" / "images"
RENDER_INFO = IMAGES_DIR / "render_info.json"

EXPECTED = {
    1: "京A8X3K7",
    2: "沪B5M2N9",
    3: "粤C3Q8L1",
    4: "苏D9K4R6",
    5: "浙E7T1V5",
    6: "川F2H6W8",
}


@pytest.fixture(scope="module", autouse=True)
def force_builtin_engine():
    """整个模块只测内置管线，避免受模型是否安装影响。"""
    import core.plate_recognizer as pr

    old = pr.PLATE_ENGINE
    pr.PLATE_ENGINE = "builtin"
    yield
    pr.PLATE_ENGINE = old


def _font_mismatch(tmpl) -> str:
    """样例图的渲染字体与当前模板字体不一致时，返回原因说明。

    内置模板匹配靠「字形归一化后逐像素比对」，跨字体时形近字（浙/渝、8/B）
    必然混淆，这不是代码缺陷而是该方案的前提。此时跳过而不是误报失败。
    """
    if not RENDER_INFO.exists():
        return ""
    try:
        recorded = json.loads(RENDER_INFO.read_text(encoding="utf-8")).get("font", "")
    except Exception:
        return ""
    current = tmpl.font_name
    if recorded and current and recorded != current:
        return (f"样例图由 {recorded} 渲染，本机模板用的是 {current}；"
                f"内置模板匹配要求两者一致")
    return ""


@pytest.fixture(scope="module")
def recognizer():
    from core import PlateRecognizer
    from core.template_ocr import TemplateOcr

    tmpl = TemplateOcr()
    if not tmpl.available:
        pytest.skip("内置模板 OCR 不可用（缺少中文字体）")

    reason = _font_mismatch(tmpl)
    if reason:
        pytest.skip(reason)

    rec = PlateRecognizer()
    # 跳过 YOLO：测试只验证定位 + OCR，避免加载权重
    rec._loaded = True
    rec._yolo = None
    rec._ocr = None
    rec._tmpl = tmpl
    return rec


@pytest.mark.parametrize("index,expected", sorted(EXPECTED.items()))
def test_recognize_synthetic_plate(recognizer, index, expected):
    path = IMAGES_DIR / f"test_plate_{index}.png"
    if not path.exists():
        pytest.skip(f"缺少测试图 {path.name}（可运行 make_samples.py 生成）")

    img = load_image(path)
    assert img is not None

    result = recognizer.recognize(img, draw_on_image=False)

    assert result.success is True
    assert result.best_plate == expected


def test_blank_image_returns_no_plate(recognizer):
    """纯色图不应编造车牌（DEMO_MODE 关闭后）。"""
    import numpy as np

    blank = np.full((240, 320, 3), 128, dtype=np.uint8)
    result = recognizer.recognize(blank, draw_on_image=False)

    assert result.success is False
    assert result.best_plate == ""


def test_empty_image_handled(recognizer):
    import numpy as np

    result = recognizer.recognize(np.zeros((0, 0, 3), dtype=np.uint8))
    assert result.success is False


def test_recognizer_shared_is_singleton():
    from core import PlateRecognizer

    assert PlateRecognizer.shared() is PlateRecognizer.shared()
