"""把项目文档渲染成一个预览页（便于在浏览器中查看中文文档）。"""
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def md_to_html(s):
    s = re.sub(r'```([\s\S]*?)```',
               lambda m: '<pre><code>' + m.group(1).replace('<', '&lt;') + '</code></pre>',
               s)
    s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s)
    s = re.sub(r'^# (.*)$', r'<h1>\1</h1>', s, flags=re.M)
    s = re.sub(r'^## (.*)$', r'<h2>\1</h2>', s, flags=re.M)
    s = re.sub(r'^### (.*)$', r'<h3>\1</h3>', s, flags=re.M)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'^- (.*)$', r'<li>\1</li>', s, flags=re.M)
    s = s.replace("\n", "<br/>\n")
    return s


CSS = """
body{font-family:'Segoe UI','Microsoft YaHei',Arial,sans-serif;max-width:980px;margin:32px auto;padding:0 24px 80px;line-height:1.75;color:#1f2d3d;background:#fafbfc;}
h1{color:#2d8cf0;border-bottom:2px solid #2d8cf0;padding-bottom:8px;margin-top:40px;}
h1:first-child{margin-top:0;}
h2{color:#1f2d3d;margin-top:36px;border-top:1px solid #e8eaec;padding-top:18px;}
h3{color:#1f2d3d;}
table{border-collapse:collapse;margin:12px 0;width:100%;}
td,th{border:1px solid #dcdee3;padding:6px 10px;text-align:left;}
th{background:#f0f4f8;}
code{background:#f6f8fa;padding:1px 5px;border-radius:3px;font-family:Consolas,monospace;color:#c7254e;}
pre{background:#f6f8fa;padding:14px;border-radius:6px;overflow-x:auto;border:1px solid #e8eaec;}
pre code{color:#1f2d3d;background:none;}
hr{border:0;border-top:1px solid #e8eaec;margin:36px 0;}
li{margin-left:18px;}
.card{background:#fff;border:1px solid #e8eaec;border-left:4px solid #2d8cf0;border-radius:6px;padding:14px 18px;margin:16px 0;}
.card.warn{border-left-color:#ff9900;}
.card.ok{border-left-color:#19be6b;}
.card.bad{border-left-color:#ed4014;}
"""


def read(rel):
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def tree_html():
    lines = []
    for p in sorted(ROOT.rglob("*")):
        skip_dirs = {"__pycache__", ".git", ".pytest_cache", ".workbuddy",
                     "logs"}
        if any(part in skip_dirs for part in p.parts):
            continue
        if p.is_file():
            rel = str(p.relative_to(ROOT))
            if rel in ("preview.html", "make_preview.py"):
                continue
            lines.append(rel)
    return "<pre><code>" + "\n".join(lines) + "</code></pre>"


tess_card = """
<div class="card ok">
<strong>识别链路：内置模板匹配 OCR（零外部依赖、离线可用）</strong><br/><br/>
针对中国车牌做了位置先验（固定 7 位、首位省份汉字、次位字母、
其余字母数字），不依赖任何外部 OCR 引擎。<br/>
在 <code>data/images</code> 的 6 张合成车牌上命中 6/6。
</div>

<div class="card warn">
<strong>Tesseract（可选组件）</strong><br/>
仅在内置 OCR 无法给出合法车牌号时作为兜底。
若 Tesseract 安装路径包含中文，可能报
<code>Illegal byte sequence</code>；程序启动时会自检并自动跳过，
不影响正常使用。<br/>
如需启用：设置环境变量 <code>TESSERACT_DIR</code> 指向<strong>纯英文路径</strong>的安装目录。
</div>
"""

parts = [
    "<!doctype html><html><head><meta charset=utf-8>"
    "<title>车牌识别与停车场管理系统</title><style>" + CSS + "</style></head><body>",
    "<h1>项目总览</h1>",
    tess_card,
    md_to_html(read("README.md")),
    "<hr/><h1>目录结构说明</h1>",
    md_to_html(read("目录结构说明.md")),
    "<hr/><h1>运行步骤</h1>",
    md_to_html(read("docs/运行步骤.md")),
    "<hr/><h1>工程文件清单</h1>",
    tree_html(),
    "</body></html>",
]

html = "".join(parts)
(ROOT / "preview.html").write_text(html, encoding="utf-8")
print("Wrote preview.html,", len(html), "bytes")