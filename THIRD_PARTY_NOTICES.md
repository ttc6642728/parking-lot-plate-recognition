# 第三方组件说明

本项目自身代码以 [MIT](./LICENSE) 许可发布。下列第三方组件的版权与许可归各自作者所有，
不受本项目 MIT 许可的影响。

## 1. HyperLPR3 — Apache License 2.0

- 项目主页：<https://github.com/szad670401/HyperLPR>
- 使用方式：本项目在 `models/hyperlpr3/` 下**分发其预训练 ONNX 模型**，用于离线运行深度识别引擎。
- 义务：再分发时需保留其许可证与版权声明，详见 <http://www.apache.org/licenses/LICENSE-2.0>。

## 2. Ultralytics YOLOv8 — AGPL-3.0

- 项目主页：<https://github.com/ultralytics/ultralytics>
- 使用方式：作为**可选依赖**，仅用于检测图片中的车牌区域；权重文件未随仓库分发
  （`models/*.pt` 已被 `.gitignore` 排除，首次使用时由脚本下载）。
- 提示：AGPL-3.0 的要求强于 MIT。若你计划将本项目用于商业或闭源分发，需自行评估
  并遵守 AGPL-3.0 的相关条款（例如以 AGPL 兼容方式开源衍生作品）。

## 3. 其他依赖库

OpenCV、PyQt5、NumPy、SciPy、Matplotlib、Pandas、pytest 等均为独立的开源项目，
遵循其各自的原始许可证，详见 `requirements.txt` 与各项目仓库。

## 4. 数据集与示例图片

- `data/images/` 中由 `make_samples.py` 生成的合成车牌图，与本项目代码同受 MIT 许可。
- 其余真实车牌照片仅用于识别效果验证，**版权归原拍摄者所有**，不包含在本项目所授予的
  MIT 许可范围内，请勿单独提取用于其他用途。
