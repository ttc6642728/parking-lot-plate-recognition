# models/ 模型权重说明

本目录存放两类模型，用途完全不同：

```
models/
├── yolov8n.pt              # 车辆检测（可选，内置管线用）
└── hyperlpr3/              # 车牌 detects + 识别（主力，随项目提供）
    └── 20230229/onnx/
        ├── y5fu_320x_sim.onnx        # 车牌检测 320×320
        ├── y5fu_640x_sim.onnx        # 车牌检测 640×640（小目标更准）
        ├── rpv3_mdict_160_r3.onnx    # 字符识别（CRNN + CTC）
        └── litemodel_cls_96x_r1.onnx # 车牌颜色/类型分类
```

---

## 1. HyperLPR3（主力识别引擎）

**已随项目提供，不需要下载。**

- 来源：[HyperLPR3](https://github.com/szad670401/HyperLPR)（Apache-2.0）
- 作用：车牌检测 → 透视矫正 → 字符识别，端到端输出整串车牌号
- 路径配置：`config.HYPERLPR_DIR`
- 依赖：`onnxruntime` + `hyperlpr3`（见 requirements.txt）

> ⚠ 若这 4 个 onnx 文件缺失，程序不会报错，而是自动降级到内置模板匹配管线，
> 但真实车牌的识别率会明显下降。判断当前用的是哪个引擎：
> `python eval_recognition.py` 看输出的「引擎」列。

---

## 2. YOLO 权重（可选，内置管线用）

仅当 HyperLPR3 不可用时才会走这条路径，用于**车辆**粗定位。

- `yolov8n.pt`：Ultralytics 官方通用模型（COCO 80 类，含 car/truck/bus）。
  被 `.gitignore` 排除，缺失时程序自动改用 OpenCV 颜色/边缘定位。
- `yolov8n_plate.pt`：车牌检测专用权重（可选，需自行准备）。

> 注意：COCO 通用权重**不含 "plate" 类**，它的职责是
> 「定位车辆 → 在车框内用 OpenCV 二次定位车牌」，不是直接检测车牌。

### 切换权重

```python
# config.py
YOLO_WEIGHTS = MODELS_DIR / "yolov8n_plate.pt"
```

### 自训练（如需）

```bash
yolo detect train data=plate.yaml model=yolov8n.pt epochs=50 imgsz=640
```

把 `best.pt` 重命名放到本目录并修改 `config.py` 即可。
