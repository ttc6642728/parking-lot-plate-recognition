# 车牌识别与停车场管理系统

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![PyQt5](https://img.shields.io/badge/GUI-PyQt5-41CD52?logo=qt&logoColor=white)](https://pypi.org/project/PyQt5/)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.x-5C3EE8?logo=opencv&logoColor=white)](https://opencv.org/)
[![ONNX](https://img.shields.io/badge/ONNX-HyperLPR3-005CED?logo=onnx&logoColor=white)](https://github.com/szad670401/HyperLPR)
[![License](https://img.shields.io/badge/License-MIT-3DA639.svg)](./LICENSE)
[![Tests](https://img.shields.io/badge/tests-79%20passed-brightgreen.svg)](./tests)
[![Platform](https://img.shields.io/badge/platform-Windows-0078D6?logo=windows&logoColor=white)](#环境要求)

一个可离线运行的停车场管理系统：**开源双引擎车牌识别 + 入场/出场计费 + 会员与黑名单 + 数据看板**，
桌面端基于 PyQt5，数据落在本地 SQLite，不依赖任何云服务。

<p align="center">
  <img src="docs/shots/09-recognition-success.png" width="49%" alt="车牌识别成功态" />
  <img src="docs/shots/08-stats.png" width="49%" alt="数据统计看板" />
</p>

<p align="center">
  <sub>左：识别成功态（号牌 + 置信度 + 引擎来源） · 右：数据统计看板</sub>
</p>

---

## 一、这个项目想解决什么

课程设计常见的做法是"调个库、跑通就行"，但这个项目真正花时间的是三件在真实场景里会翻车的事：

| 问题 | 通常的做法 | 本项目的做法 |
|---|---|---|
| **真实车牌识别不出来** | 用模板匹配硬扛 | 诊断出根因是"字符等距切分"假设错误 + 字体不同源，接入深度引擎并与传统管线**仲裁** |
| **界面卡死** | 直接在 UI 线程里跑 OpenCV | 采集与识别全部搬进后台线程，打开摄像头从 **2.4s 阻塞**降到 **<3ms 返回** |
| **结果不可信** | 认错也当成功返回 | 引入置信度门槛与**拒识**，宁可返回"未识别"，也不把乱码灌进业务表 |

## 二、核心难点：为什么一个引擎不够

单独用任何一个引擎，都会在某一类输入上翻车，这不是调参能解决的。

| 引擎 | 原理 | 强项 | 弱项（实测） |
|---|---|---|---|
| **HyperLPR3**（深度） | YOLO 检测车牌四点 → 透视矫正 → CNN+BiLSTM+CTC 整串输出 | 真实抓拍：倾斜、光照不均、车牌在车身上 | 纯车牌特写、无车身上下文时反而不稳（`沪B5M2N9` → `沪B5N2N9`） |
| **内置管线**（传统） | 颜色/边缘定位 → 二值化 → 投影切分 → 字体模板匹配 | 标准车牌特写、完全离线 | 模板是系统黑体，真实车牌是国标 GA36 专用字体，单字相似度仅 **0.33~0.43**，清晰图也会认成 `津T1111` |

**仲裁规则**不看"谁置信度高"（两个引擎的置信度不同量纲，没法比），而是看一个物理意义明确的信号：

> 内置管线对自己结果有多确信？
> 模板相似度高 → 输入字体与模板同源 → 采信内置；
> 相似度低 → 模板根本匹配不上真实字形 → 改用 HyperLPR3。
> 这个信号恰好反映"字体是否同源"，比拍脑袋定阈值可靠。

同时加了**拒识**：深度引擎置信度低于 0.70、摄像头模式下内置管线低于 0.55，一律返回"未识别"。
代价是偶尔漏识，收益是不会把 `冀MMMMMM` 这种格式合法的乱码写进停车记录。

## 三、实测结果

全部可用 `python eval_recognition.py --augment` 复现，真值表在 `data/labels.json`。

| 场景 | 仅内置管线 | 双引擎仲裁 |
|---|---|---|
| 基础测试集（1 张真实 + 6 张合成） | 6/7 (86%) | **7/7 (100%)** |
| 真实照片的 17 种退化增强<br><sub>旋转 ±12°、亮度 0.55~1.35、模糊 13×13、缩放 20%、噪声、组合退化</sub> | 0/17 (0%) | **17/17 (100%)** |

边界表现：缩小 18%、旋转 15°、模糊 17×17、亮度降到 0.2 时仍可识别；单张稳态耗时约 **1.4s**（双引擎并行）。

> **关于这组数字的诚实说明**：17/17 来自**同一张照片的退化变体**，它证明的是"抗干扰能力"，
> 不能直接外推成"任意车型都准"。严谨的结论需要在 CCPD 等数据集上批量评测，
> 这也是本项目下一步计划。

## 四、功能与技术栈

| 模块 | 说明 |
|---|---|
| 车牌识别 | 图片 / 摄像头实时识别，双引擎仲裁 + 置信度拒识 + 结果叠加 |
| 入场登记 | 自动分配车位、写入入场时间，会员/黑名单实时校验 |
| 出场结算 | 按车型与时长计费，会员折扣自动生效，输出结算单 |
| 停车记录 | 条件筛选、增删改、导出 Excel / CSV |
| 会员 / 黑名单 | 有效期管理、折扣率、实时预警 |
| 数据统计 | 车流与营收趋势（按日历补齐空缺日）、指标卡、导出 |
| 权限 | 管理员 / 操作员两级，导航项按角色禁用 |

**技术栈**：Python 3.12 · PyQt5 · OpenCV · HyperLPR3 / ONNX Runtime · SQLite3 · Matplotlib · Pandas / openpyxl · pytest

## 五、环境要求

- Windows 10/11（摄像头采集用 DirectShow，其他平台会自动回退到默认后端）
- Python 3.12（3.10+ 应该都可以，但只在 3.12 上完整验证）
- 无需联网：HyperLPR3 的 4 个 ONNX 模型（17.5 MB）随仓库分发

## 六、快速开始

```bash
pip install -r requirements.txt
python check_env.py     # 可选：逐项自检，缺什么会直接告诉你
python main.py
```

首次启动自动建库并创建默认账号：`admin / admin123`（管理员）、`operator / 123456`（操作员）。
密码以 PBKDF2-SHA256 加盐哈希存储，库里看不到明文。

运行测试与评估：

```bash
python -m pytest tests -q                       # 79 passed, 1 skipped
python eval_recognition.py --augment            # 准确率对比：内置管线 vs 双引擎
python test_recognition.py                      # 逐张打印识别结果
```

## 七、项目结构

```
core/          识别与业务核心
  plate_recognizer.py   双引擎仲裁主流程
  lpr_engine.py         HyperLPR3 封装（单例、显式模型路径）
  template_ocr.py       内置模板 OCR（投影 + 网格双策略择优）
  camera.py             摄像头采集（多后端回退、真实读帧校验）
  billing.py            计费规则
  parking_lot.py        车位管理
ui/            界面层
  theme.py              设计令牌 + 全局 QSS
  components.py         通用组件（卡片 / 指标卡 / 号牌 / 徽章）
  icons.py              QPainter 现画的矢量图标
  *_widget.py           七个功能页
db/            SQLite 访问层（DAO 分层，出口统一转 dict）
auth/          登录、角色权限、密码哈希
tests/         pytest（79 项）
docs/          文档与界面截图
```

## 八、几个值得记下的坑

开发过程中踩过、并已固化在代码注释里的问题：

1. **PyQt5 比 onnxruntime 先加载会导致识别静默降级** —— Windows 上 `DLL load failed while importing onnxruntime_pybind11_state`。必须在 `from PyQt5...` 之前 `import onnxruntime`（`main.py` 顶部有说明，`tests/conftest.py` 同样处理）。
2. **QSS 不支持 CSS 变量 / `box-shadow` / `letter-spacing` / 单边圆角** —— 分别用 `string.Template` 注入颜色、`QGraphicsDropShadowEffect`、`QFont.setLetterSpacing`、objectName 规则替代。
3. **父控件 `setStyleSheet` 会级联到所有子控件** —— 曾因此把主按钮的渐变底盖掉，表现为"白底白字看不见按钮"。
4. **`stretchLastSection` 与 `ResizeToContents` 混用会让末列被拉伸两次** —— 总宽超出视口，出现横向滚动条，统一改为"中间列吸收剩余宽度"。
5. **单元测试必须让 `sys.exit()` 变成异常** —— 否则一个 `SystemExit` 直接带走整个 pytest 进程。

## 九、已知局限

写在明面上，比被追问出来好：

- 抗干扰指标基于单张真实照片的退化变体，样本量有限，**不等于**真实场景准确率
- 仲裁阈值（0.70 / 0.55）由实测归纳得出，样本扩大后可能需要调整
- 内置管线的 YOLOv8 用的是 COCO 通用权重（无 plate 类），实际是"检出车框 → 框内二次定位"，真实车牌主要靠 HyperLPR3
- 仅支持中国大陆蓝牌/黄牌，未覆盖新能源绿牌、双层黄牌
- 单机 SQLite，未做并发压力测试
- 界面只在 Windows 上验证，macOS / Linux 需要自行调整摄像头后端

## 十、文档

| 文档 | 内容 |
|---|---|
| [`docs/系统介绍.md`](./docs/系统介绍.md) | 架构、模块、双引擎设计、数据库、部署（主文档） |
| [`docs/识别准确率报告.md`](./docs/识别准确率报告.md) | 识别问题的四段诊断与量化验证过程 |
| [`docs/功能模块说明.md`](./docs/功能模块说明.md) | 逐页面功能与操作流程 |
| [`docs/数据库设计.md`](./docs/数据库设计.md) | 表结构、索引、初始化 |
| [`docs/运行步骤.md`](./docs/运行步骤.md) | 环境配置、常见报错、摄像头排查 |
| [`docs/技术选型.md`](./docs/技术选型.md) | 选型理由与有意不做的选择 |
| [`目录结构说明.md`](./目录结构说明.md) | 逐文件说明 |

界面截图全部在 [`docs/shots/`](./docs/shots)，由 `make_ui_shots.py` 批量生成（用临时库灌样例数据，不碰你的 `db/parking.db`）。

## 十一、License

[MIT](./LICENSE) © 2026

> 第三方组件：HyperLPR3（Apache-2.0）、Ultralytics YOLOv8（AGPL-3.0，未随仓库分发权重）。
> `data/images/` 中的真实车牌照片仅用于识别效果验证，版权归原拍摄者，不在 MIT 授权范围内。
