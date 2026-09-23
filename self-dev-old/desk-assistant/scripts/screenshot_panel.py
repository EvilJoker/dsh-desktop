"""scripts/screenshot_panel.py — 启动 panel 并截图，验证 v3.2 样式。

offscreen 模式下 grab() panel，不依赖 X server。
需要 panel 可正常 import + 构造。
"""
import os
import sys

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DESK_ASSISTANT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, DESK_ASSISTANT)

from PyQt5 import QtCore, QtWidgets  # noqa: E402

from panel.theme import GLOBAL_QSS  # noqa: E402
from panel.window_manager import WindowManager  # noqa: E402

# 1. QApplication + 全局 QSS
app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
app.setStyleSheet(GLOBAL_QSS)
print("[1/3] QSS applied (len=%d)" % len(GLOBAL_QSS))

# 2. WindowManager
wm = WindowManager()
print("[2/3] WindowManager constructed: panel=%r, strip=%r" % (wm.panel, wm.strip))

# 3. 强制 show panel + 等事件循环处理后 grab
wm.panel.show()
QtCore.QTimer.singleShot(0, lambda: None)
app.processEvents()
app.processEvents()  # 多 pump 几次让 layout 完成

# 4. 截图
out = os.path.join(DESK_ASSISTANT, '_demo', 'panel-real.png')
pixmap = wm.panel.grab()
pixmap.save(out)
print("[3/3] saved: %s (%dx%d)" % (out, pixmap.width(), pixmap.height()))

# 5. 也截 strip
out2 = os.path.join(DESK_ASSISTANT, '_demo', 'strip-real.png')
pixmap2 = wm.strip.grab()
pixmap2.save(out2)
print("[bonus] saved: %s (%dx%d)" % (out2, pixmap2.width(), pixmap2.height()))
