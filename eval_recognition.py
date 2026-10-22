# -*- coding: utf-8 -*-
"""
识别准确率评估脚本

用途
----
量化比较两套识别方案在同一批图片上的表现，并输出逐张明细：

    内置管线（builtin） —— OpenCV 定位 + 字体模板匹配，不含深度学习
    双引擎（auto）      —— HyperLPR3 + 内置管线 + 置信度仲裁

用法
----
    python eval_recognition.py                 # 基础测试集
    python eval_recognition.py --augment       # 额外跑退化增强样本
    python eval_recognition.py --mode builtin  # 只测某一套方案
    python eval_recognition.py --mode auto --augment

测试集与真值见 data/labels.json。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import cv2
import numpy as np

from config import IMAGES_DIR
from utils.image_utils import load_image
import core.plate_recognizer as recognizer_module


# ---------------------------------------------------------------------------
# 测试集
# ---------------------------------------------------------------------------
def load_labels() -> list[dict]:
    path = ROOT / "data" / "labels.json"
    if not path.exists():
        print(f"[错误] 找不到真值表：{path}")
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for item in data.get("images", []):
        f = IMAGES_DIR / item["file"]
        if f.exists():
            rows.append({"path": f, "plate": item["plate"],
                         "type": item.get("type", "unknown")})
        else:
            print(f"[跳过] 图片不存在：{f}")
    return rows


def make_augmentations(img: np.ndarray) -> list[tuple[str, np.ndarray]]:
    """
    对真实照片做退化增强，模拟现场常见的不利条件：
    车身倾斜、逆光/欠曝、镜头虚焦、拍摄距离远、传感器噪声。
    """
    def rotate(im, angle):
        m = cv2.getRotationMatrix2D((im.shape[1] / 2, im.shape[0] / 2),
                                    angle, 1.0)
        return cv2.warpAffine(im, m, (im.shape[1], im.shape[0]),
                              borderMode=cv2.BORDER_REPLICATE)

    def bright(im, factor):
        return np.clip(im.astype(np.float32) * factor, 0, 255).astype(np.uint8)

    cases: list[tuple[str, np.ndarray]] = []
    for a in (-8, -4, 4, 8, 12, -12):
        cases.append((f"旋转 {a:+d}°", rotate(img, a)))
    for f in (0.55, 0.75, 1.35):
        cases.append((f"亮度 ×{f}", bright(img, f)))
    for k in (5, 9, 13):
        cases.append((f"模糊 {k}×{k}", cv2.GaussianBlur(img, (k, k), 0)))
    for s in (0.5, 0.3, 0.2):
        cases.append((f"缩放到 {int(s*100)}%",
                      cv2.resize(img, None, fx=s, fy=s,
                                 interpolation=cv2.INTER_AREA)))
    noise = np.random.default_rng(0).normal(0, 18, img.shape)
    cases.append(("高斯噪声 σ=18",
                  np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)))
    cases.append(("组合退化(转4°+糊+暗)",
                  bright(cv2.GaussianBlur(rotate(img, 4), (5, 5), 0), 0.8)))
    return cases


# ---------------------------------------------------------------------------
# 评估
# ---------------------------------------------------------------------------
def run_suite(rows: list[dict], mode: str) -> list[dict]:
    recognizer_module.PLATE_ENGINE = mode
    rec = recognizer_module.PlateRecognizer()

    out = []
    for item in rows:
        img = load_image(str(item["path"]))
        if img is None:
            continue
        r = rec.recognize(img, draw_on_image=False)
        out.append({
            "name": item["path"].name,
            "truth": item["plate"],
            "got": r.best_plate,
            "ok": r.best_plate == item["plate"],
            "conf": r.confidence_of_best,
            "engine": r.engine,
            "type": item["type"],
        })
    return out


def run_augmented(row: dict, mode: str) -> list[dict]:
    recognizer_module.PLATE_ENGINE = mode
    rec = recognizer_module.PlateRecognizer()
    img = load_image(str(row["path"]))
    if img is None:
        return []

    out = []
    for name, aug in make_augmentations(img):
        r = rec.recognize(aug, draw_on_image=False)
        out.append({
            "name": name,
            "truth": row["plate"],
            "got": r.best_plate,
            "ok": r.best_plate == row["plate"],
            "conf": r.confidence_of_best,
            "engine": r.engine,
        })
    return out


def _width(text: str) -> int:
    """按终端显示宽度计算（中日韩字符占 2 列）。"""
    return sum(2 if ord(c) > 0x2E80 else 1 for c in text)


def _pad(text: str, width: int) -> str:
    return text + " " * max(0, width - _width(text))


def print_table(title: str, runs: dict[str, list[dict]]):
    modes = list(runs.keys())
    if title:
        print(f"\n{title}")

    name_w = 24
    col_w = 22
    header = _pad("样本", name_w) + "".join(_pad(m, col_w) for m in modes)
    print(header)
    print("-" * _width(header))

    for i in range(len(runs[modes[0]])):
        line = _pad(runs[modes[0]][i]["name"], name_w)
        for m in modes:
            r = runs[m][i]
            mark = "✓" if r["ok"] else "✗"
            cell = f"{mark} {r['got']} ({r['conf']:.2f})"
            line += _pad(cell, col_w)
        print(line)

    print("-" * _width(header))
    for m in modes:
        ok = sum(1 for r in runs[m] if r["ok"])
        total = len(runs[m])
        pct = 100.0 * ok / total if total else 0.0
        print(f"  {m:>10s} 准确率：{ok}/{total}  ({pct:.0f}%)")


# ---------------------------------------------------------------------------
def samples_font_mismatch() -> str:
    """合成样例图的渲染字体与当前模板字体是否不一致。

    内置模板匹配依赖「样例图与模板同字体」（见 utils/font_utils.py）。
    GitHub Actions 的 Windows 镜像没有黑体，落回微软雅黑后合成样本必然失准，
    因此这种情况下门槛只校验真实照片，避免把环境差异误判成代码回归。
    """
    info = IMAGES_DIR / "render_info.json"
    if not info.exists():
        return ""
    try:
        recorded = json.loads(info.read_text(encoding="utf-8")).get("font", "")
    except Exception:
        return ""
    from utils.font_utils import find_cjk_font, font_name

    current = font_name(find_cjk_font())
    if recorded and current and recorded != current:
        return f"合成样例图由 {recorded} 渲染，本机模板用 {current}"
    return ""


def main():
    parser = argparse.ArgumentParser(description="车牌识别准确率评估")
    parser.add_argument("--mode", choices=["auto", "builtin", "hyperlpr3"],
                        default=None, help="只评估指定方案")
    parser.add_argument("--augment", action="store_true",
                        help="额外对真实照片做退化增强测试")
    parser.add_argument("--fail-below", type=float, default=0.0, metavar="ACC",
                        help="基础集准确率低于该值(0~1)时以退出码 2 结束，供 CI 做回归断言")
    args = parser.parse_args()

    rows = load_labels()
    if not rows:
        return 1

    modes = [args.mode] if args.mode else ["builtin", "auto"]

    print("=" * 78)
    print("基础测试集")
    print("=" * 78)
    base_runs = {m: run_suite(rows, m) for m in modes}
    print_table("", base_runs)

    # CI 用：对最终方案（auto）做准确率门槛校验
    if args.fail_below > 0:
        checked = "auto" if "auto" in base_runs else modes[-1]
        result = base_runs[checked]

        mismatch = samples_font_mismatch()
        if mismatch:
            real_only = [r for r in result if r.get("type") == "real"]
            if real_only:
                print(f"\n[提示] {mismatch}，合成样本不参与门槛校验")
                result = real_only

        acc = sum(1 for r in result if r["ok"]) / max(1, len(result))
        if acc < args.fail_below:
            print(f"\n[FAIL] {checked} 基础集准确率 {acc:.1%} "
                  f"低于门槛 {args.fail_below:.0%}")
            return 2
        print(f"\n[OK] {checked} 基础集准确率 {acc:.1%} ≥ 门槛 {args.fail_below:.0%}")

    if args.augment:
        real_rows = [r for r in rows if r["type"] == "real"]
        if not real_rows:
            print("\n[提示] 没有真实拍摄样本，跳过增强测试")
        else:
            print("\n" + "=" * 78)
            print(f"退化增强测试（基于 {real_rows[0]['path'].name}，"
                  f"真值 {real_rows[0]['plate']}）")
            print("=" * 78)
            aug_runs = {m: run_augmented(real_rows[0], m) for m in modes}
            print_table("", aug_runs)

    return 0


if __name__ == "__main__":
    sys.exit(main())
