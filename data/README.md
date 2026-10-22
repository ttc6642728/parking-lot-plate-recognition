# 测试图片目录

`data/images/` 存放用于「图片识别」模式的车牌图片，支持 `.png` / `.jpg` / `.jpeg` / `.bmp`。

## 当前内容

| 文件 | 类型 | 说明 |
|---|---|---|
| `test_plate_1~6.png` | 合成 | 由 `make_samples.py` 渲染生成，字体与内置模板 OCR 同源 |
| `1KS31404-0.jpg` | 真实 | 带车身背景的实拍照片，用于验证深度引擎与退化增强 |

真值表见 `data/labels.json`，`eval_recognition.py` 依据它计算准确率。

## 想加自己的图片

文件名随意，能被 `QFileDialog` 打开即可。推荐来源：

- **CCPD 数据集**（https://github.com/detectRecog/CCPD）：大规模中文车牌数据集，可直接补充评测集
- **自己用手机拍摄**：最有说服力，也能规避版权问题

## 关于真实车牌照片

仓库内的 `1KS31404-0.jpg` 仅用于验证识别效果与复现 `eval_recognition.py --augment`
的退化测试（17/17 依赖它）。真实车牌属于他人信息，**版权归原拍摄者**，
不包含在本项目的 MIT 许可范围内（见根目录 `LICENSE` 的第三方说明）。

如果你不希望公开这张照片，可以：

```bash
git rm --cached data/images/1KS31404-0.jpg
rm data/images/1KS31404-0.jpg
```

代价是 `eval_recognition.py --augment` 会因缺少真实样本而跳过退化测试，
基础集的 6 张合成图不受影响。若要保留真实场景评测能力，建议换成自己拍的照片，
并同步修改 `data/labels.json` 里的文件名与真值。
