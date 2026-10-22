# -*- coding: utf-8 -*-
"""
环境自检：运行前先跑这个脚本，它会告诉你缺什么、怎么补。

    python check_env.py
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

# 修复 Windows 控制台中文乱码（GBK 终端输出 UTF-8 会乱码）
if sys.platform == "win32":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from config import (TESSERACT_DIR, TESSERACT_CMD, TESSDATA_DIR,
                    TESSERACT_LANG, YOLO_WEIGHTS, IMAGES_DIR,
                    DB_FILE, DEMO_MODE, TOTAL_PARKING_SPOTS)

OK, WARN, BAD = "  [OK]  ", "  [WARN]", "  [FAIL]"


def _hr(title=""):
    if title:
        print(f"\n=== {title} ===")
    else:
        print("-" * 58)


# ---------------------------------------------------------------------------
def check_python_deps():
    _hr("1. Python 依赖")
    deps = [
        ("cv2",         "opencv-python",    True),
        ("numpy",       "numpy",            True),
        ("PyQt5",       "PyQt5",            True),
        ("matplotlib",  "matplotlib",       True),
        ("pandas",      "pandas",           True),
        ("openpyxl",    "openpyxl",         True),
        ("PIL",         "Pillow",           True),
        ("onnxruntime", "onnxruntime",      False),   # HyperLPR3 推理
        ("hyperlpr3",   "hyperlpr3",        False),   # 深度学习识别引擎
        ("ultralytics", "ultralytics",      False),
        ("pytesseract", "pytesseract",      True),
        ("loguru",      "loguru",           False),   # 非必需
    ]
    missing_required = []
    for mod, pkg, required in deps:
        # 用 find_spec 而不是 __import__：只判断"装没装"，不执行模块代码。
        # 这点对 hyperlpr3 尤其重要 —— 它一被 import 就会去下载 12MB 模型。
        try:
            installed = importlib.util.find_spec(mod) is not None
        except (ImportError, ValueError):
            installed = False

        if installed:
            print(f"{OK} {pkg}")
        else:
            tag = BAD if required else WARN
            print(f"{tag} {pkg} 未安装"
                  + ("" if required else "（可选，非必需）"))
            if required:
                missing_required.append(pkg)

    if missing_required:
        print(f"\n  → 安装缺失依赖：")
        print(f"    pip install -i https://pypi.tuna.tsinghua.edu.cn/simple "
              f"{' '.join(missing_required)}")
    return not missing_required


# ---------------------------------------------------------------------------
def check_tesseract() -> bool:
    _hr("2. Tesseract-OCR（可选 —— 已有内置 OCR 作为替代）")

    if not TESSERACT_DIR:
        print(f"{WARN} 未自动探测到 Tesseract-OCR 安装目录")
        print(f"  → 不影响使用：内置模板匹配 OCR 已可独立完成识别")
        print(f"  → 如需启用：设置环境变量 TESSERACT_DIR 指向安装目录")
        print(f"     （路径不能含中文，否则会报 Illegal byte sequence）")
        return False

    exe = Path(TESSERACT_CMD)
    td  = Path(TESSDATA_DIR)

    # 2.1 可执行文件
    if not exe.exists():
        print(f"{BAD} tesseract.exe 不存在：{exe}")
        print(f"  → 请检查环境变量 TESSERACT_DIR / TESSERACT_CMD")
        return False
    print(f"{OK} tesseract.exe：{exe}")

    # 2.2 能否运行（常见故障 0xC0000135）
    try:
        r = subprocess.run([str(exe), "--version"],
                           capture_output=True, timeout=30)
        rc = r.returncode
        out = (r.stdout.decode("utf-8", "replace")
               + r.stderr.decode("utf-8", "replace")).strip()
        if rc != 0:
            if rc == 3221225781:      # 0xC0000135
                vcrt = Path(r"C:\Windows\System32\vcruntime140.dll")
                if vcrt.exists():
                    print(f"{WARN} tesseract.exe 无法启动（0xC0000135）")
                    print(f"     VC++ 运行库已正常，故原因是"
                          f" Tesseract 自身安装不完整（缺依赖 DLL）")
                    print(f"  → 建议：重新下载完整版 Tesseract；")
                    print(f"     或忽略 —— 内置 OCR 已能独立完成识别。")
                else:
                    print(f"{WARN} tesseract.exe 无法启动（0xC0000135）")
                    print(f"     = 缺 VC++ 运行库")
                    print(f"  → 安装：https://aka.ms/vs/17/release/"
                          f"vc_redist.x64.exe（装完重启）")
            else:
                print(f"{WARN} tesseract.exe 返回码 {rc}")
                if out:
                    print(f"     {out[:200]}")
            return False
        first = out.splitlines()[0] if out else "unknown"
        print(f"{OK} 可运行：{first}")
    except Exception as e:
        print(f"{WARN} 调用失败：{e}")
        return False

    # 2.3 tessdata 语言数据
    if not td.exists():
        print(f"{BAD} 缺少语言数据目录：{td}")
        print(f"  → 重新运行 Tesseract 安装包 → 勾选 Additional language data")
        print(f"     或在下列地址下载 *.traineddata 放进该目录：")
        print(f"     https://github.com/tesseract-ocr/tessdata_fast")
        return False
    print(f"{OK} tessdata 目录：{td}")

    # 2.4 具体语言包
    need = [l for l in TESSERACT_LANG.split("+") if l]
    miss = []
    for lang in need:
        f = td / f"{lang}.traineddata"
        if f.exists():
            print(f"{OK} 语言包 {lang}.traineddata ({f.stat().st_size // 1024} KB)")
        else:
            print(f"{BAD} 缺少语言包 {lang}.traineddata")
            miss.append(lang)
    if miss:
        print(f"  → 下载：https://github.com/tesseract-ocr/tessdata_fast/raw/main/"
              f"{miss[0]}.traineddata")
        return False
    return True


# ---------------------------------------------------------------------------
def check_yolo():
    _hr("3. YOLO 权重（非必需）")
    w = Path(YOLO_WEIGHTS)
    if w.exists():
        print(f"{OK} 权重存在：{w.name}")
        return True
    print(f"{WARN} 未找到 {w.name}")
    print(f"  → 首次识别时 ultralytics 会自动下载通用 yolov8n.pt（需联网）")
    print(f"  → 或手动下载放到 models/ 目录")
    return False


# ---------------------------------------------------------------------------
def check_images():
    _hr("4. 测试图片")
    if not IMAGES_DIR.exists():
        print(f"{WARN} 目录不存在：{IMAGES_DIR}")
        return False
    files = [p for p in IMAGES_DIR.iterdir()
             if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".bmp")]
    if not files:
        print(f"{WARN} data/images/ 里没有图片")
        print(f"  → 运行 python make_samples.py 生成合成测试图")
        return False
    for f in sorted(files)[:6]:
        print(f"{OK} {f.name}")
    if len(files) > 6:
        print(f"     ...共 {len(files)} 张")
    return True


# ---------------------------------------------------------------------------
def check_db():
    _hr("5. 数据库")
    try:
        from db.database import init_database, get_conn
        init_database()
        cur = get_conn().cursor()
        cur.execute("SELECT COUNT(*) FROM users")
        users = cur.fetchone()[0]
        cur.execute("SELECT total_spots, used_spots FROM parking_lot WHERE id=1")
        row = cur.fetchone()
        print(f"{OK} 数据库可用：{DB_FILE.name}")
        print(f"     用户数 {users}，车位 已用 {row[1]} / 总计 {row[0]}")
        return True
    except Exception as e:
        print(f"{BAD} 数据库异常：{e}")
        return False


# ---------------------------------------------------------------------------
def check_ocr_runtime():
    """检查实际可用的识别引擎（深度学习 + 内置管线）。"""
    _hr("6. 识别引擎")

    deep_ok = False
    try:
        from core.lpr_engine import HyperLprEngine
        eng = HyperLprEngine.shared()
        deep_ok = eng.available
        if deep_ok:
            print(f"{OK} HyperLPR3 深度学习引擎就绪（检测 + 识别，真实车牌首选）")
        else:
            print(f"{WARN} HyperLPR3 不可用：{eng.error or '未知原因'}")
            print(f"  → 不影响使用：内置管线仍可识别标准车牌图")
    except Exception as e:
        print(f"{WARN} HyperLPR3 异常：{e}")

    tmpl_ok = False
    try:
        from core.template_ocr import TemplateOcr
        t = TemplateOcr()
        tmpl_ok = t.available
        if tmpl_ok:
            print(f"{OK} 内置模板匹配 OCR 就绪（{len(t.templates)} 个模板，零外部依赖）")
        else:
            print(f"{BAD} 内置模板 OCR 不可用（缺中文字体？）")
    except Exception as e:
        print(f"{BAD} 内置模板 OCR 异常：{e}")

    tess_ok = False
    try:
        from core.ocr_recognizer import OcrRecognizer
        tess_ok = OcrRecognizer().available
        if tess_ok:
            print(f"{OK} Tesseract OCR 可用（语言 {TESSERACT_LANG}），作为补充")
        else:
            print(f"{WARN} Tesseract 不可用 —— 不影响使用")
    except Exception as e:
        print(f"{WARN} Tesseract 异常：{e}")

    return deep_ok or tmpl_ok


def check_recognition():
    """实跑一次识别，验证端到端可用。"""
    _hr("7. 识别实跑")
    try:
        from core import PlateRecognizer
        from utils.image_utils import load_image

        imgs = sorted(list(IMAGES_DIR.glob("*.png"))
                      + list(IMAGES_DIR.glob("*.jpg")))
        if not imgs:
            print(f"{WARN} 没有测试图片，跳过")
            return False

        rec = PlateRecognizer()
        ok_cnt = 0
        for p in imgs[:3]:
            img = load_image(p)
            if img is None:
                continue
            r = rec.recognize(img, draw_on_image=False)
            if r.success:
                ok_cnt += 1
            print(f"{OK if r.success else WARN} {p.name} -> "
                  f"{r.best_plate or '(未识别)'}"
                  f"  [{r.engine}]")
        print(f"     实跑 {min(3, len(imgs))} 张，成功 {ok_cnt} 张")
        return ok_cnt > 0
    except Exception as e:
        print(f"{BAD} 识别实跑异常：{e}")
        return False


# ---------------------------------------------------------------------------
def main():
    print("=" * 58)
    print(" 车牌识别与停车场管理系统 —— 环境自检")
    print("=" * 58)
    print(f" Python {sys.version.split()[0]}")

    r1 = check_python_deps()
    r2 = check_tesseract()
    r3 = check_yolo()
    r4 = check_images()
    r5 = check_db()
    r6 = check_ocr_runtime()
    r7 = check_recognition() if (r4 and r6) else False

    _hr("结论")
    print(f" 演示模式 DEMO_MODE = {DEMO_MODE}（config.py 中可切换）")
    print(f" 总车位 TOTAL_PARKING_SPOTS = {TOTAL_PARKING_SPOTS}\n")

    if not r1:
        print("  ❌ Python 依赖缺失，请先安装。")
    elif r6 and r7:
        print("  ✅ 识别引擎就绪，可以真实识别车牌。")
        print("     运行：        python main.py")
        print("     准确率评估：  python eval_recognition.py --augment")
    elif r5:
        print("  ⚠ 识别引擎不可用，将使用演示模式（模拟车牌）。")
        print("     运行：python main.py")
    else:
        print("  ❌ 请先按上面 [FAIL] 项的提示修复。")

    print("=" * 58)


if __name__ == "__main__":
    main()