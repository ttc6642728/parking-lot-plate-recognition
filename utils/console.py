# -*- coding: utf-8 -*-
"""
控制台编码兜底。

背景
----
Windows 的 Python 在**管道/重定向**场景下按 ANSI 代码页编码 stdout（英文版是
cp1252，中文版是 cp936），而不是 UTF-8。CI 里 `python eval_recognition.py`
的输出被管道接走，打印中文即抛 UnicodeEncodeError：

    UnicodeEncodeError: 'charmap' codec can't encode characters in position 0-4

本地中文 Windows（cp936）能编码汉字，但编码不了 ✓ ✗ 这类符号，
所以这个问题只在"别人的机器/CI"上暴露。

用法
----
在任何会向终端打印非 ASCII 内容的独立脚本入口处最先调用：

    from utils.console import ensure_utf8_stdout
    ensure_utf8_stdout()
"""

from __future__ import annotations

import sys


def ensure_utf8_stdout() -> None:
    """把 stdout/stderr 切到 UTF-8；失败时降级为替换不可编码字符，绝不抛异常。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
