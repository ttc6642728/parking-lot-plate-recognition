# -*- coding: utf-8 -*-
"""
中文字体定位 —— 模板 OCR 与样例图生成共用同一份候选列表。

为什么必须共用
--------------
内置模板匹配引擎的原理是「把样例字符与渲染模板逐一比对」，
所以**样例图的渲染字体必须与模板字体一致**：
同一个「浙」在微软雅黑与黑体下的笔画宽度、字面大小都不同，
归一化到 64×64 后相似度会掉到相近字（浙→渝、川→甘）之上。

历史教训：这两处曾各自维护一份字体列表且顺序不同，
本地（有黑体）测试 6/6 通过，而 GitHub Actions 的 Windows 镜像
没有 simhei.ttf、回落到微软雅黑，6 张样例图全部识别错误。
统一到本模块后，样例图绑定到「当前字体」，测试再校验字体签名。

字体优先级
----------
黑体优先：字形方正、笔画等宽，最接近真实车牌字体，也是模板匹配最稳的字库。
微软雅黑作为兜底 —— 实测雅黑的 W/P、M/N 归一化后极易混淆，
6 张样例图会有 3~4 张识别错误，因此只在没有黑体时使用。
"""

from __future__ import annotations

from pathlib import Path

# 按顺序尝试；顺序即优先级
FONT_CANDIDATES: tuple[str, ...] = (
    r"C:\Windows\Fonts\simhei.ttf",                                  # 黑体（首选，字形最接近车牌）
    r"C:\Windows\Fonts\msyh.ttc",                                    # 微软雅黑（兜底，字形偏圆，易混淆）
    r"C:\Windows\Fonts\simsun.ttc",                                  # 宋体
    "/System/Library/Fonts/PingFang.ttc",                            # macOS
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",        # Linux
    "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)

# 实测能稳定支撑模板匹配的字体（用于判断本机是否具备条件）
PREFERRED_FONT = "simhei.ttf"


def find_cjk_font() -> str | None:
    """返回第一个存在的中文字体路径；全都不存在时返回 None。"""
    for f in FONT_CANDIDATES:
        if Path(f).exists():
            return f
    return None


def font_name(path: str | Path | None) -> str:
    """字体标识（文件名），用于记录与比对字体签名。"""
    if not path:
        return ""
    return Path(path).name
