# -*- coding: utf-8 -*-
"""
内置模板匹配 OCR —— 不依赖 Tesseract，只用 OpenCV + PIL。

原理（课程设计讲解要点）：
    1) 用 PIL 把 0-9 / A-Z / 省份简称渲染成标准字符模板；
    2) 对车牌图二值化并统一极性（保证字符为白、背景为黑）；
    3) 用垂直投影法把车牌切成单个字符；
    4) 每个字符归一化到统一尺寸后，与模板逐一比对，取最高分。

优点：零外部依赖、离线可用、原理清晰（适合答辩讲解）。
缺点：对字体/形变敏感，真实抓拍场景不如 Tesseract / 专用模型。
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Tuple

import cv2
import numpy as np

if sys.platform == "win32":
    for _s in (sys.stdout, sys.stderr):
        try:
            _s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# 车牌上可能出现的字符（排除易混淆的 I 和 O）
DIGITS   = "0123456789"
LETTERS  = "ABCDEFGHJKLMNPQRSTUVWXYZ"
PROVINCES = "京沪津渝冀豫云辽黑湘皖鲁新苏浙赣鄂桂甘晋蒙陕吉闽贵粤青藏川宁琼"

# 归一化尺寸（汉字笔画复杂，分辨率太低会混淆形近字如 浙/渝、川/甘）
_N = 64

# 画布尺寸与字符高度
_CANVAS = 64
_CHAR_H = 48


def _to_canvas(bin_img: np.ndarray) -> np.ndarray | None:
    """
    把二值字符图**保持宽高比**地放进 _CANVAS×_CANVAS 画布中央。

    ⚠ 关键：不能直接 resize 成正方形 —— 那样窄字符『1』会被拉成方块，
       与『T』『4』等混淆。保持比例才能区分。
    """
    if bin_img is None or bin_img.size == 0:
        return None
    h, w = bin_img.shape
    if h == 0 or w == 0:
        return None

    sc = _CHAR_H / h
    nw = int(round(w * sc))
    nw = max(1, min(nw, _CANVAS))
    r = cv2.resize(bin_img, (nw, _CHAR_H), interpolation=cv2.INTER_AREA)

    out = np.zeros((_CANVAS, _CANVAS), np.uint8)
    x = (_CANVAS - nw) // 2
    y = (_CANVAS - _CHAR_H) // 2
    out[y:y + _CHAR_H, x:x + nw] = r[:, :nw]
    return out


# 常见中文字体候选（按顺序尝试）
_FONT_CANDIDATES = [
    r"C:\Windows\Fonts\simhei.ttf",      # 黑体（车牌字体接近黑体）
    r"C:\Windows\Fonts\msyh.ttc",        # 微软雅黑
    r"C:\Windows\Fonts\simsun.ttc",      # 宋体
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


class TemplateOcr:
    """纯 Python 的车牌字符识别器。"""

    def __init__(self, font_path: str | None = None, size: int = 96):
        self.available = False
        self.templates: Dict[str, np.ndarray] = {}
        self._size = size
        self._font = font_path or self._find_font()
        if not self._font:
            return
        try:
            self._build()
            self.available = bool(self.templates)
        except Exception:
            self.available = False

    # ------------------------------------------------------------------
    @staticmethod
    def _find_font() -> str | None:
        for f in _FONT_CANDIDATES:
            if Path(f).exists():
                return f
        return None

    def _render(self, ch: str) -> np.ndarray | None:
        """把单个字符渲染成二值图（白字黑底）。"""
        from PIL import Image, ImageDraw, ImageFont

        try:
            font = ImageFont.truetype(self._font, self._size)
        except Exception:
            return None

        box = self._size * 2
        img = Image.new("L", (box, box), 0)
        draw = ImageDraw.Draw(img)
        try:
            draw.text((self._size // 2, self._size // 2),
                      ch, fill=255, font=font)
        except Exception:
            return None

        arr = np.array(img)
        coords = cv2.findNonZero(arr)
        if coords is None:
            return None
        x, y, w, h = cv2.boundingRect(coords)
        crop = arr[y:y + h, x:x + w]
        if crop.size == 0:
            return None
        return _to_canvas(crop)

    def _build(self):
        chars = list(DIGITS) + list(LETTERS) + list(PROVINCES)
        for ch in chars:
            t = self._render(ch)
            if t is not None:
                _, t = cv2.threshold(t, 100, 255, cv2.THRESH_BINARY)
                self.templates[ch] = t

    # ------------------------------------------------------------------
    @staticmethod
    def _binarize_by_bg(img: np.ndarray):
        """
        底色差分二值化：
        取车牌四边（跳过白色外框）的颜色作为底色，
        与底色差异大的像素即为字符 → 字符白、底板黑。
        返回 None 表示不适用（如灰度图、底色不纯）。
        """
        if img is None or img.size == 0 or len(img.shape) != 3:
            return None

        h, w = img.shape[:2]
        if h < 20 or w < 60:
            return None

        # 跳过白色外框，向内取窄带
        off = max(3, int(min(h, w) * 0.10))
        band = max(2, int(min(h, w) * 0.04))
        if off + band >= h // 2 or off + band >= w // 2:
            return None

        strips = np.vstack([
            img[off:off + band, :].reshape(-1, 3),
            img[h - off - band:h - off, :].reshape(-1, 3),
            img[:, off:off + band].reshape(-1, 3),
            img[:, w - off - band:w - off].reshape(-1, 3),
        ])
        bg = np.median(strips, axis=0).astype(np.int16)

        diff = np.abs(img.astype(np.int16) - bg).sum(axis=2)
        mask = (diff > 90).astype(np.uint8) * 255

        ratio = float((mask > 0).mean())
        # 合理性检查：字符面积应在 4%~60% 之间
        if not (0.04 < ratio < 0.60):
            return None

        mask = cv2.morphologyEx(
            mask, cv2.MORPH_OPEN,
            cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2)))
        return mask

    @staticmethod
    def _binarize(img: np.ndarray) -> np.ndarray:
        """
        二值化 + 统一极性，保证『字符为白(255)，背景为黑(0)』。

        用 Otsu 全局阈值而非自适应阈值 —— 自适应会把大片纯色车牌底板
        也二值成白色，导致字符全部粘连无法分割。
        """
        if img is None or img.size == 0:
            return np.zeros((0, 0), np.uint8)
        gray = (cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                if len(img.shape) == 3 else img)

        # 放大，便于分割
        h, w = gray.shape
        if max(h, w) < 200:
            gray = cv2.resize(gray, (w * 2, h * 2),
                              interpolation=cv2.INTER_CUBIC)

        # 优先用"底色差分"：车牌底板是纯色，字符与底色差异明显。
        # 这比通用阈值更精确，能保住字符细节。
        bw = TemplateOcr._binarize_by_bg(img)
        if bw is not None:
            return bw

        # 兜底：Otsu 全局阈值
        blur = cv2.GaussianBlur(gray, (3, 3), 0)
        _, bw = cv2.threshold(
            blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # 极性统一：车牌上字符面积占比小，故"白色"应是少数派
        if (bw > 0).mean() > 0.5:
            bw = 255 - bw

        # 去掉孤立噪点
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, kernel)
        return bw

    @staticmethod
    def _split_wide(bw: np.ndarray, x1: int, x2: int,
                    depth: int = 0) -> List[Tuple[int, int]]:
        """
        对过宽的片段（多个字符粘连）递归切分：
        在中间区域找列投影的"谷底"作为切点。
        """
        h = bw.shape[0]
        w = x2 - x1
        if w <= h * 0.38 or depth >= 3:
            return [(x1, x2)]

        col = (bw[:, x1:x2] > 0).sum(axis=0)
        n = len(col)
        s, e = int(n * 0.25), int(n * 0.75)
        if e <= s:
            return [(x1, x2)]

        sub = col[s:e]
        minv = sub.min()
        # 谷底不明显（字符确实连在一起）就不再切
        if minv > sub.mean() * 0.6:
            return [(x1, x2)]

        cut = x1 + int(np.argmin(sub)) + s
        return (TemplateOcr._split_wide(bw, x1, cut, depth + 1)
                + TemplateOcr._split_wide(bw, cut, x2, depth + 1))

    @staticmethod
    def _split_chars(bw: np.ndarray) -> List[Tuple[int, int]]:
        """垂直投影法切分字符，返回 [(x1, x2), ...]。"""
        if bw.size == 0:
            return []

        col = (bw > 0).sum(axis=0)
        if col.max() == 0:
            return []

        thr = max(1.0, col.max() * 0.12)
        segs: List[Tuple[int, int]] = []
        start = -1
        for x, v in enumerate(col):
            if v > thr and start < 0:
                start = x
            elif v <= thr and start >= 0:
                segs.append((start, x))
                start = -1
        if start >= 0:
            segs.append((start, len(col)))

        h = bw.shape[0]
        # 先丢弃明显的噪点
        segs = [(a, b) for a, b in segs if (b - a) >= h * 0.06]

        # 再把粘连的宽片段递归切开
        out: List[Tuple[int, int]] = []
        for a, b in segs:
            out += TemplateOcr._split_wide(bw, a, b)

        # 最终尺寸过滤
        out = [(a, b) for a, b in out
               if h * 0.10 <= (b - a) <= h * 0.85]
        return out

    def _match_in_pool(self, ch_img: np.ndarray,
                       pool: str) -> Tuple[str, float]:
        """在指定字符集（位置先验）内匹配，返回 (字符, 得分)。"""
        c = _to_canvas(ch_img)
        if c is None:
            return "", 0.0
        cf = c.astype(np.float32) / 255.0

        best_ch, best_score = "", -1.0
        for ch in pool:
            t = self.templates.get(ch)
            if t is None:
                continue
            tf = t.astype(np.float32) / 255.0
            # 用 IoU（交并比）衡量相似度，对笔画粗细不敏感
            inter = np.logical_and(cf > 0.5, tf > 0.5).sum()
            union = np.logical_or(cf > 0.5, tf > 0.5).sum()
            score = inter / union if union > 0 else 0.0
            if score > best_score:
                best_score, best_ch = score, ch
        return best_ch, float(best_score)

    def _match_slide(self, bw: np.ndarray, ytop: int, ybot: int,
                     cx: float, w: float, pool: str) -> Tuple[str, float]:
        """
        在中心 cx 附近左右滑动窗口取最佳匹配。

        字符宽度不一（如『1』窄『8』宽）、均分位置会有偏移，
        滑动可以自动对齐到字符实际位置。
        """
        H, W = bw.shape
        ybot = min(ybot, H)
        best_ch, best_sc = "", -1.0
        step = max(1, int(w * 0.10))
        span = int(w * 0.35)

        for off in range(-span, span + 1, step):
            x1 = int(cx - w / 2) + off
            x2 = x1 + int(w)
            if x1 < 0 or x2 > W or x2 <= x1:
                continue
            sub = bw[ytop:ybot, x1:x2]
            r = np.where((sub > 0).sum(axis=1) > 0)[0]
            if r.size == 0:
                continue
            s = sub[r.min():r.max() + 1, :]
            if s.size == 0:
                continue
            ch, sc = self._match_in_pool(s, pool)
            if sc > best_sc:
                best_sc, best_ch = sc, ch

        return best_ch, max(best_sc, 0.0)

    def _match_one(self, ch_img: np.ndarray) -> Tuple[str, float]:
        """单字符与全部模板比对（无位置先验）。"""
        c = _to_canvas(ch_img)
        if c is None:
            return "", 0.0
        cf = c.astype(np.float32) / 255.0

        best_ch, best_score = "", -1.0
        for ch, t in self.templates.items():
            tf = t.astype(np.float32) / 255.0
            inter = np.logical_and(cf > 0.5, tf > 0.5).sum()
            union = np.logical_or(cf > 0.5, tf > 0.5).sum()
            score = inter / union if union > 0 else 0.0
            if score > best_score:
                best_score, best_ch = score, ch
        return best_ch, float(best_score)

    # ------------------------------------------------------------------
    def _crop_border(self, bw: np.ndarray) -> np.ndarray:
        """
        去掉车牌四周的白边框。

        ⚠ 早期版本按固定比例（7%）裁边，对"车牌占满画面"的裁剪图会把
          最外侧的字符切掉一半（实测最后一个『8』被裁没，导致只识别出
          6 位字符）。这里改为按投影判断：车牌边框是**横贯整幅**的连续
          高密度行/列，只有满足该条件的行列才裁掉。
        """
        if bw is None or bw.size == 0:
            return bw
        H, W = bw.shape
        if H < 16 or W < 32:
            return bw

        row = (bw > 0).sum(axis=1) / float(W)
        col = (bw > 0).sum(axis=0) / float(H)

        def _trim(density: np.ndarray, n: int) -> Tuple[int, int]:
            s, e = 0, n
            limit = max(2, int(n * 0.20))
            while s < limit and density[s] > 0.80:
                s += 1
            while e > n - limit and density[e - 1] > 0.80:
                e -= 1
            return s, e

        y1, y2 = _trim(row, H)
        x1, x2 = _trim(col, W)

        # 裁掉太多说明这不是"带边框的车牌图"，保持原样更安全
        if (y2 - y1) < H * 0.5 or (x2 - x1) < W * 0.5:
            return bw
        return bw[y1:y2, x1:x2]

    @staticmethod
    def _crop_border_fixed(bw: np.ndarray) -> np.ndarray:
        """按固定 7% 比例裁边（规整排版图上的经验值，作为交叉校验用）。"""
        h, w = bw.shape
        m = max(3, int(min(h, w) * 0.07))
        if h > 4 * m and w > 4 * m:
            return bw[m:h - m, m:w - m]
        return bw

    # ------------------------------------------------------------------
    # 两种切分策略：按投影真实切分 / 按 7 等分网格
    #
    # 它们各有擅长，必须同时保留：
    #   · 投影切分 —— 适合真实车牌（字符宽窄不一、中间有分隔圆点）
    #   · 等分网格 —— 适合规整排版的图（等宽等距，投影容易被笔画断开）
    # 早期只保留等分网格，真实车牌错位；只保留投影切分，规整图过分割。
    # ------------------------------------------------------------------
    def _recognize_projection(self, bw: np.ndarray) -> Tuple[str, float]:
        """
        按垂直投影切分字符，再用位置先验缩小候选集。

        ⚠ 早期版本用"7 等分"定位字符，这是错的。真实车牌并非等距排列：
          ① 省份汉字宽度约为字母的 1.5 倍；
          ② 第 2、3 位之间有一个分隔圆点；
          ③ 汉字高度通常略高于字母数字。
        7 等分会让每个格子都偏移半个字符，切出来全是"半字符拼接"，
        实测同一张清晰车牌只能得到 `甘H1HMDN` 这类乱码。
        """
        segs = self._split_chars(bw)
        if not segs:
            return "", 0.0

        H = bw.shape[0]
        items: List[Tuple[int, int, int, int]] = []
        for x1, x2 in segs:
            sub = bw[:, x1:x2]
            rows = np.where((sub > 0).sum(axis=1) > 0)[0]
            if rows.size == 0:
                continue
            y1, y2 = int(rows.min()), int(rows.max()) + 1
            w, h = x2 - x1, y2 - y1
            if h < H * 0.45:            # 太矮：上下边框残留、噪点
                continue
            if w / max(h, 1) < 0.22:    # 太窄：分隔圆点、铆钉、竖线
                continue
            items.append((x1, x2, y1, y2))

        if not items:
            return "", 0.0
        items = items[:8]               # 车牌最多 8 位（新能源）

        chars: List[str] = []
        scores: List[float] = []
        for i, (x1, x2, y1, y2) in enumerate(items):
            ch_img = bw[y1:y2, x1:x2]
            if ch_img.size == 0:
                continue
            # 位置先验：第 1 位省份汉字，第 2 位字母，其余字母或数字
            if i == 0:
                pool = PROVINCES
            elif i == 1:
                pool = LETTERS
            else:
                pool = LETTERS + DIGITS
            ch, sc = self._match_in_pool(ch_img, pool)
            if ch:
                chars.append(ch)
                scores.append(sc)

        if not chars:
            return "", 0.0
        return "".join(chars), float(sum(scores) / len(scores))

    def _recognize_grid(self, bw: np.ndarray) -> Tuple[str, float]:
        """按 7 等分网格切字符（适合等宽等距的规整车牌图）。"""
        cols = (bw > 0).sum(axis=0)
        if cols.max() == 0:
            return "", 0.0

        xs = np.where(cols > cols.max() * 0.08)[0]
        if xs.size == 0:
            return "", 0.0
        xl, xr = xs.min(), xs.max()
        total = xr - xl + 1
        if total < 40:
            return "", 0.0

        rows = np.where((bw > 0).sum(axis=1) > 0)[0]
        if rows.size == 0:
            return "", 0.0
        ytop, ybot = rows.min(), rows.max() + 1

        n = 7
        w = total / n
        # 位置先验：位0=省份汉字，位1=字母，位2~6=字母或数字
        pools = [PROVINCES, LETTERS] + [LETTERS + DIGITS] * 5

        chars: List[str] = []
        scores: List[float] = []
        for i in range(n):
            cx = xl + (i + 0.5) * w
            # 在中心附近滑动，容忍字符宽度差异与切分偏移
            ch, sc = self._match_slide(bw, ytop, ybot, cx, w * 1.15, pools[i])
            if ch:
                chars.append(ch)
                scores.append(sc)

        if not chars:
            return "", 0.0
        return "".join(chars), float(sum(scores) / len(scores))

    def _recognize_uniform(self, bw: np.ndarray) -> Tuple[str, float]:
        """
        两种切分策略择优。

        规则：
          1. 网格法切出合法位数（7/8）且匹配得分够高 → 直接用（最稳）；
          2. 否则看投影法，得分比网格高才换；
          3. 都不理想时返回网格结果，交上层按置信度决定是否采信。

        这里用 0.55 作为"有把握"的门槛，与 config.PLATE_BUILTIN_SELF_TRUST
        保持一致：低于它的结果在双层仲裁中会被 HyperLPR3 取代。
        """
        grid_text, grid_conf = self._recognize_grid(bw)
        if len(grid_text) in (7, 8) and grid_conf >= 0.55:
            return grid_text, grid_conf

        proj_text, proj_conf = self._recognize_projection(bw)
        if proj_text and (not grid_text or proj_conf > grid_conf):
            return proj_text, proj_conf
        if grid_text:
            return grid_text, grid_conf
        return proj_text, proj_conf

    # ------------------------------------------------------------------
    def recognize(self, plate_img: np.ndarray) -> Tuple[str, float]:
        """
        识别车牌图，返回 (文本, 平均置信度)。

        用两种裁边方式各跑一次再交叉校验：
          · 投影裁边 —— 只裁真正横贯整幅的边框，不会切掉最外侧字符，
                        适合车牌几乎占满画面的真实抓拍裁剪；
          · 固定裁边 —— 按 7% 比例裁，适合规整排版的标准车牌图。
        两者结果一致时可信度最高；不一致时取匹配得分明显更高的一方，
        分数接近则偏向固定裁边（规整图上的历史表现更稳）。
        """
        if not self.available or plate_img is None or plate_img.size == 0:
            return "", 0.0

        bw = self._binarize(plate_img)
        if bw.size == 0:
            return "", 0.0

        proj_text, proj_conf = "", 0.0
        bwp = self._crop_border(bw)
        if bwp.size:
            proj_text, proj_conf = self._recognize_uniform(bwp)

        fixed_text, fixed_conf = "", 0.0
        bwf = self._crop_border_fixed(bw)
        if bwf.size:
            fixed_text, fixed_conf = self._recognize_uniform(bwf)

        if not proj_text and not fixed_text:
            return "", 0.0
        if proj_text == fixed_text:
            return proj_text, max(proj_conf, fixed_conf)
        if not fixed_text:
            return proj_text, proj_conf
        if not proj_text:
            return fixed_text, fixed_conf
        # 不一致：得分明显更高才换，否则用固定裁边的结果
        if proj_conf > fixed_conf + 0.02:
            return proj_text, proj_conf
        return fixed_text, fixed_conf