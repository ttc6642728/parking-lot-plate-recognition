# -*- coding: utf-8 -*-
"""
识别功能测试：对 data/images/ 下的合成车牌图跑一遍完整识别。

    python test_recognition.py
"""

from __future__ import annotations

import sys
import time

from utils.console import ensure_utf8_stdout

ensure_utf8_stdout()

from core import PlateRecognizer
from core.template_ocr import TemplateOcr
from utils.image_utils import load_image

# 合成图的真实车牌（与 make_samples.py 中的 PLATES 对应）
EXPECT = {
    1: "京A8X3K7",
    2: "沪B5M2N9",
    3: "粤C3Q8L1",
    4: "苏D9K4R6",
    5: "浙E7T1V5",
    6: "川F2H6W8",
}


def main():
    rec = PlateRecognizer()
    # 跳过 YOLO 加载（避免联网下载），直接验证 OpenCV 定位 + OCR 链路
    rec._loaded = True
    rec._yolo = None
    rec._ocr = None
    rec._tmpl = TemplateOcr()

    print("=" * 56)
    print(" 车牌识别测试（内置 OCR）")
    print("=" * 56)

    total = 0
    t0 = time.time()
    for i in sorted(EXPECT):
        img = load_image(f"data/images/test_plate_{i}.png")
        if img is None:
            print(f"  plate_{i}: 图片读取失败")
            continue

        r = rec.recognize(img, draw_on_image=False)
        got, exp = r.best_plate, EXPECT[i]
        ok = (got == exp)
        total += ok
        mark = "✓" if ok else "✗"
        print(f"  {mark} plate_{i}: 识别={got or '(空)':<8s} "
              f"期望={exp}  置信={r.confidence_of_best:.2f} "
              f"耗时={r.elapsed_ms:.0f}ms")

    n = len(EXPECT)
    print("-" * 56)
    print(f"  完全一致：{total}/{n}  （{total / n * 100:.0f}%）")
    print(f"  总耗时  ：{time.time() - t0:.2f}s")
    print("=" * 56)


if __name__ == "__main__":
    main()