# -*- coding: utf-8 -*-
"""
ui 图形界面包。

⚠ 这里刻意不 import 任何子模块。

原因：若在包初始化里把 9 个界面模块全部导入，那么任意
`import ui.record_widget` 都会连带加载登录窗、主窗、matplotlib 等
全部依赖，既拖慢启动，也让单个模块的导入失败波及整个包，
还容易触发 `ui <-> main_window` 的循环导入。

需要哪个界面，请显式写 `from ui.xxx import Yyy`。
"""
