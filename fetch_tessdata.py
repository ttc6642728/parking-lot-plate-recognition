# -*- coding: utf-8 -*-
"""
下载 Tesseract 语言数据包（tessdata）到 Tesseract 安装目录。

    python fetch_tessdata.py

默认下载 eng + chi_sim（tessdata_fast 版本，体积小、速度快）。
"""

from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

if sys.platform == "win32":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

from config import TESSDATA_DIR

BASE = ("https://ghproxy.net/https://raw.githubusercontent.com"
        "/tesseract-ocr/tessdata_fast/refs/heads/main/")
MIRRORS = [BASE,
           "https://cdn.jsdelivr.net/gh/tesseract-ocr/tessdata_fast@main/"]

LANGS = ["eng", "chi_sim"]


def download(lang: str, dest_dir: Path) -> bool:
    dest_dir.mkdir(parents=True, exist_ok=True)
    out = dest_dir / f"{lang}.traineddata"
    if out.exists() and out.stat().st_size > 100_000:
        print(f"  已存在，跳过：{out.name} "
              f"({out.stat().st_size // 1024} KB)")
        return True

    for base in MIRRORS:
        url = base + f"{lang}.traineddata"
        try:
            print(f"  下载 {lang} ... {url[:60]}...")
            req = urllib.request.Request(
                url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=180) as resp:
                data = resp.read()
            if len(data) < 100_000:
                print(f"    内容异常（{len(data)} 字节），换源")
                continue
            out.write_bytes(data)
            print(f"  [OK] {out.name}  {len(data) // 1024} KB")
            return True
        except Exception as e:
            print(f"    失败：{type(e).__name__} {e}")

    return False


def main():
    td = Path(TESSDATA_DIR)
    print("=" * 54)
    print(" Tesseract 语言包下载")
    print("=" * 54)
    print(f" 目标目录：{td}\n")

    ok = True
    for lang in LANGS:
        if not download(lang, td):
            ok = False

    print("\n" + "=" * 54)
    if ok:
        print(" 完成！请再运行 python check_env.py 验证。")
    else:
        print(" 部分语言包下载失败，请手动下载：")
        print(" https://github.com/tesseract-ocr/tessdata_fast")
    print("=" * 54)


if __name__ == "__main__":
    main()