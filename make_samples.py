# -*- coding: utf-8 -*-
"""
生成合成车牌测试图片（无需准备真实素材即可演示）。

运行：
    python make_samples.py

会在 data/images/ 下生成若干张"照片 + 车牌"的合成图。
"""

from pathlib import Path

import cv2
import numpy as np

from config import IMAGES_DIR

IMG_DIR = IMAGES_DIR
IMG_DIR.mkdir(parents=True, exist_ok=True)

# 常见的车牌配色
PLATE_COLORS = {
    "blue":   ((200, 100, 30),  (255, 255, 255)),   # 蓝底白字（小型车）
    "green":  ((80, 170, 60),   (255, 255, 255)),   # 绿底（新能源）
    "yellow": ((30, 190, 230),  (20, 20, 20)),      # 黄底黑字（大型车）
}

PLATES = [
    ("京A8X3K7", "blue"),
    ("沪B5M2N9", "blue"),
    ("粤C3Q8L1", "green"),
    ("苏D9K4R6", "blue"),
    ("浙E7T1V5", "yellow"),
    ("川F2H6W8", "blue"),
]


def _put_cn(img, text, org, color, scale):
    """用 OpenCV 画中文（cv2.putText 不支持中文，这里用近似处理）。"""
    # OpenCV 无法直接渲染中文，这里使用 PIL 渲染后贴回
    from PIL import Image, ImageDraw, ImageFont
    pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil)
    # 尝试找系统中文字体
    font = None
    for fp in (
            r"C:\Windows\Fonts\simhei.ttf",
            r"C:\Windows\Fonts\msyh.ttc",
            r"C:\Windows\Fonts\simsun.ttc",
            "/System/Library/Fonts/PingFang.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(fp).exists():
            try:
                font = ImageFont.truetype(fp, int(scale * 40))
                break
            except Exception:
                continue
    if font is None:
        font = ImageFont.load_default()
    draw.text(org, text, font=font, fill=color[::-1])   # RGB
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)


def _render_char(ch: str, target_h: int, color_bgr):
    """用 PIL 渲染单个字符，缩放至指定高度，返回彩色 BGR 图。"""
    from PIL import Image, ImageDraw, ImageFont

    font = None
    for fp in (r"C:\Windows\Fonts\simhei.ttf",
               r"C:\Windows\Fonts\msyh.ttc",
               r"C:\Windows\Fonts\simsun.ttc",
               "/System/Library/Fonts/PingFang.ttc",
               "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if Path(fp).exists():
            try:
                font = ImageFont.truetype(fp, 96)
                break
            except Exception:
                continue
    if font is None:
        return None

    img = Image.new("L", (200, 200), 0)
    ImageDraw.Draw(img).text((50, 40), ch, fill=255, font=font)
    arr = np.array(img)

    coords = cv2.findNonZero(arr)
    if coords is None:
        return None
    x, y, w, h = cv2.boundingRect(coords)
    crop = arr[y:y + h, x:x + w]
    if h <= 0 or w <= 0:
        return None

    sc = target_h / h
    crop = cv2.resize(crop, (max(1, int(w * sc)), target_h),
                      interpolation=cv2.INTER_AREA)

    bgr = cv2.cvtColor(crop, cv2.COLOR_GRAY2BGR)
    bgr[crop > 0] = color_bgr
    return bgr


def draw_plate(plate_text: str, style="blue"):
    """
    绘制一块标准比例车牌（440x140）。
    7 个字符等距排列 —— 与真实车牌布局一致，
    也让基于位置先验的 OCR 能稳定工作。
    """
    W, H = 440, 140
    bg, fg = PLATE_COLORS[style]
    plate = np.zeros((H, W, 3), dtype=np.uint8)
    plate[:] = bg

    # 白色内边框
    cv2.rectangle(plate, (0, 0), (W - 1, H - 1), (255, 255, 255), 6)

    # 标准布局
    CH_H, CH_W, GAP = 90, 45, 12
    total = 7 * CH_W + 6 * GAP
    x0 = (W - total) // 2
    y0 = (H - CH_H) // 2

    for i, ch in enumerate(plate_text[:7]):
        cimg = _render_char(ch, CH_H, fg)
        if cimg is None:
            continue
        ch_h, ch_w = cimg.shape[:2]
        cx = x0 + i * (CH_W + GAP) + (CH_W - ch_w) // 2
        cy = y0
        cx = max(0, min(W - ch_w, cx))
        # 贴字（只覆盖字符笔画部分）
        idx = cimg.sum(axis=2) > 0
        region = plate[cy:cy + ch_h, cx:cx + ch_w]
        if region.shape[:2] == idx.shape[:2]:
            region[idx] = cimg[idx]

    return plate


def compose(plate_text: str, style="blue", idx=0):
    """把车牌贴到一个模拟的'车身'背景上。"""
    h, w = 560, 860
    # 车身背景（不同颜色模拟不同车）
    body_colors = [(60, 60, 70), (140, 145, 150), (35, 45, 90),
                   (170, 170, 175), (50, 60, 55)]
    body = np.zeros((h, w, 3), dtype=np.uint8)
    body[:] = body_colors[idx % len(body_colors)]

    # 加一些噪点，模拟真实照片
    noise = np.random.normal(0, 6, body.shape).astype(np.int16)
    body = np.clip(body.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    # 地面
    body[h - 90:, :] = (70, 70, 75)

    plate_img = draw_plate(plate_text, style)
    ph, pw = plate_img.shape[:2]

    # 车牌放在车身中下部（模拟前/后保险杠位置）
    x = (w - pw) // 2 + random_x(idx)
    y = h - 190
    x = max(0, min(w - pw, x))

    body[y:y + ph, x:x + pw] = plate_img
    return body


def random_x(idx):
    return (idx * 37) % 60 - 30


def main():
    for i, (text, style) in enumerate(PLATES):
        img = compose(text, style, i)
        out = IMG_DIR / f"test_plate_{i + 1}.png"
        # 用 imencode + tofile 保存，规避 OpenCV 对中文路径的支持问题
        ok, buf = cv2.imencode(".png", img)
        if ok:
            buf.tofile(str(out))
        print(f"生成：{out.name}  ({text}, {style})  -> {ok}")

    print(f"\n共 {len(PLATES)} 张，已保存到 {IMG_DIR}")


if __name__ == "__main__":
    main()