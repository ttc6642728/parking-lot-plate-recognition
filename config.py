# -*- coding: utf-8 -*-
"""
全局配置文件
集中管理路径、费率、车位数、YOLO 模型参数等，方便调参与维护。
"""

import os
from pathlib import Path

# ---------------------------------------------------------------------------
# 路径
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent

DATA_DIR       = PROJECT_ROOT / "data"
IMAGES_DIR     = DATA_DIR / "images"
MODELS_DIR     = PROJECT_ROOT / "models"
LOGS_DIR       = PROJECT_ROOT / "logs"
DB_DIR         = PROJECT_ROOT / "db"
DOCS_DIR       = PROJECT_ROOT / "docs"
UI_RES_DIR     = PROJECT_ROOT / "ui" / "resources"

DB_FILE        = DB_DIR / "parking.db"
LOG_FILE       = LOGS_DIR / "app.log"

# 确保目录存在
for _p in (DATA_DIR, IMAGES_DIR, MODELS_DIR, LOGS_DIR, DB_DIR,
           DOCS_DIR, UI_RES_DIR):
    _p.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Tesseract OCR 路径（可选组件，找不到也不影响运行）
# ---------------------------------------------------------------------------
def _detect_tesseract_dir() -> str:
    """
    按优先级自动探测 Tesseract 安装目录，避免把某一台机器的路径写死。

    顺序：环境变量 TESSERACT_DIR → 常见安装位置 → 空（交给内置 OCR）。
    """
    env = os.environ.get("TESSERACT_DIR", "").strip()
    if env and Path(env).exists():
        return env

    exe_name = "tesseract.exe" if os.name == "nt" else "tesseract"
    candidates = [
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Tesseract-OCR",
        Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Tesseract-OCR",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Tesseract-OCR",
        Path("/usr/bin"),
        Path("/usr/local/bin"),
    ]
    for c in candidates:
        if (c / exe_name).exists():
            return str(c)
    return ""


TESSERACT_DIR = _detect_tesseract_dir()

_TESS_EXE = "tesseract.exe" if os.name == "nt" else "tesseract"
TESSERACT_CMD = os.environ.get("TESSERACT_CMD") or (
    str(Path(TESSERACT_DIR) / _TESS_EXE) if TESSERACT_DIR else "tesseract"
)

# 语言数据目录（tessdata 里放 *.traineddata）
TESSDATA_DIR = (str(Path(TESSERACT_DIR) / "tessdata")
                if TESSERACT_DIR else "")

# 识别语言：中文（车牌省份汉字）+ 英文（字母数字）
TESSERACT_LANG = "chi_sim+eng"


# ---------------------------------------------------------------------------
# YOLO 模型
# ---------------------------------------------------------------------------
# 默认加载通用 yolov8n（首次），自行准备
# 运行时会自动从 ultralytics 官方下载。
YOLO_WEIGHTS = MODELS_DIR / "yolov8n.pt"   # 也可改成 yolov8n_plate.pt
YOLO_CONF    = 0.35                          # 置信度阈值
YOLO_IOU     = 0.45                          # NMS IOU 阈值
# 当 YOLO 不可用时，是否回退到 OpenCV 传统车牌检测
YOLO_FALLBACK_OPENCV = True


# ---------------------------------------------------------------------------
# 车牌识别引擎
# ---------------------------------------------------------------------------
# auto      —— 优先用 HyperLPR3 深度学习引擎，不可用时自动降级到内置管线
# hyperlpr3 —— 只用 HyperLPR3（缺失时报错，便于答辩演示深度学习方案）
# builtin   —— 只用内置管线（YOLO/OpenCV 定位 + 模板匹配 OCR），离线可控
PLATE_ENGINE = "auto"

# HyperLPR3 模型目录（内含 20230229/onnx/*.onnx，随项目一起提交）
HYPERLPR_DIR           = MODELS_DIR / "hyperlpr3"
HYPERLPR_MODEL_VERSION = "20230229"
# low = 320x320 输入，约 50ms；high = 640x640，小目标更准但更慢
HYPERLPR_DETECT_LEVEL  = "low"

# 识别结果的最低可信置信度：低于此值视为"没认准"，不再当成识别成功。
# HyperLPR3 在清晰车片上通常 >0.95，模糊/脏污会掉到 0.5 以下。
PLATE_MIN_CONFIDENCE = 0.70

# 双引擎仲裁阈值：内置模板管线自评置信度高于此值时，说明输入字体
# 与模板字体高度吻合（如程序渲染的标准车牌），此时采信内置结果；
# 低于此值说明模板匹配不上真实车牌字体，改用 HyperLPR3。
PLATE_BUILTIN_SELF_TRUST = 0.55


# ---------------------------------------------------------------------------
# 摄像头
# ---------------------------------------------------------------------------
# 设备索引：0 通常是内置摄像头或第一个 USB 摄像头；外接多个时按需改 1 / 2
CAMERA_INDEX = 0

# 采集后端：
#   auto    —— Windows 上依次尝试 DSHOW → MSMF → 默认（DSHOW 打开最快、兼容性最好）
#   dshow   —— 强制 DirectShow（Windows）
#   msmf    —— 强制 Media Foundation（Windows）
#   default —— 交给 OpenCV 自己选
CAMERA_BACKEND = "auto"

# 摄像头模式下的最低显示置信度：低于此值不当作"识别成功"，
# 避免镜头里没有车牌时，把噪点硬拼成一个格式合法的乱码车牌。
CAMERA_MIN_CONFIDENCE = 0.55


# ---------------------------------------------------------------------------
# 演示模式
# ---------------------------------------------------------------------------
# 开启后：真实识别失败时会随机编造一个"格式合法"的车牌，保证业务流程能走通。
# ⚠ 提交 / 正式运行时必须为 False —— 否则识别结果并非真实识别所得。
#
# 答辩现场若摄像头或光线条件不理想，可临时改 True 演示 UI 流程，
# 但务必主动向老师说明"此处为演示兜底，不是识别结果"。
DEMO_MODE = False

# 演示模式下随机生成的车牌前缀（用于模拟）
DEMO_PLATE_PREFIXES = ("京A", "沪B", "粤C", "苏D", "浙E", "川F", "鲁G", "闽H")


# ---------------------------------------------------------------------------
# 停车场 / 计费规则
# ---------------------------------------------------------------------------
TOTAL_PARKING_SPOTS = 50        # 总车位
SMALL_CAR_RATE       = 2.0      # 元 / 小时
LARGE_CAR_RATE       = 4.0      # 元 / 小时
MEMBER_DISCOUNT      = 0.5      # 会员 5 折（0~1，1 表示不打折）
MIN_BILLING_HOURS    = 1        # 不足 1 小时按 1 小时计费

VEHICLE_TYPES = ("小型车", "大型车")


# ---------------------------------------------------------------------------
# 默认账号（首次启动自动创建）
# ---------------------------------------------------------------------------
DEFAULT_USERS = [
    # (username, password, role)
    ("admin",    "admin123", "admin"),
    ("operator", "123456",   "operator"),
]


# ---------------------------------------------------------------------------
# UI 主题
# ---------------------------------------------------------------------------
APP_TITLE = "车牌识别与停车场管理系统 v1.0"
ORG_NAME  = "CourseDesign"
# 全局 QSS 已迁移到 ui/theme.py（设计令牌 + 组件样式统一管理）。
# 这里不再保留样式字符串：config 会被 core / db / 测试脚本在无 GUI 环境下导入，
# 若在 config 里 import PyQt5，会让 onnxruntime 的加载顺序失控（见 main.py 顶部说明）。
# 需要样式的入口请写：from ui.theme import QSS
