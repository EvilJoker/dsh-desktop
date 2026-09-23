"""panel/strip.py — 桌面助手右边缘贴边窄条（37×75）。

架构（v3.1，Edge Dock 简化版）：
  1. WindowStaysOnTopHint + Tool 永远贴右、垂直居中
  2. 自绘圆角矩形 + 图标 + 状态点（v1 先占位图标）
  3. SSE connected/disconnected 信号驱动状态点颜色
  4. 鼠标左键 emit show_requested → WindowManager 唤起 Panel
     （不再有 HotZoneWatcher 触发的"贴右自动展开"）
  5. 拖动支持 + 释放时屏外吸附
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PyQt5 import QtCore, QtGui, QtWidgets  # noqa: E402

log = logging.getLogger("panel.strip")

# ---- 几何常量 ----
STRIP_WIDTH = 37
STRIP_HEIGHT = 75
EDGE_MARGIN = 0  # 贴右：strip 右边缘对齐到主屏右边界
BOTTOM_MARGIN = 40  # 距主屏底边距离（右下角悬浮）


class Strip(QtWidgets.QWidget):
    """贴右悬浮的窄条窗口。"""

    # WindowManager 连这个信号：Strip.click → Panel.show_animated
    show_requested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.WindowStaysOnTopHint
            | QtCore.Qt.Tool
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.resize(STRIP_WIDTH, STRIP_HEIGHT)
        self._drag_offset = None
        self._positioned = False
        # 状态点：右上角 6×6 圆点，SSE 连接态驱动颜色（v3.2 走全局 QSS）
        self._status_dot = QtWidgets.QLabel(self)
        self._status_dot.setObjectName("StripStatusDot")
        self._status_dot.setProperty("connected", "false")
        self._status_dot.setFixedSize(6, 6)
        self._status_dot.move(self.width() - 9, 3)
        # 鼠标悬停提示：快捷键 + 点击两种唤起方式
        self.setToolTip("Alt+M / 点击展开")

    def _reposition_to_right_edge(self):
        screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
        if screen.width() <= 0 or screen.height() <= 0:
            log.warning("primary screen invalid, skip strip reposition")
            return
        self.move(
            screen.x() + screen.width() - self.width() - EDGE_MARGIN,
            screen.y() + screen.height() - self.height() - BOTTOM_MARGIN,
        )
        self._positioned = True
        log.info("strip reposition: pos=(%d,%d) %dx%d",
                 self.x(), self.y(), self.width(), self.height())

    def showEvent(self, event):
        super().showEvent(event)
        if not self._positioned:
            QtCore.QTimer.singleShot(0, self._reposition_to_right_edge)
            QtCore.QTimer.singleShot(100, self._reposition_to_right_edge)

    def paintEvent(self, _event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        # v3.4：天蓝色背景 + 1px 白色边框（用户要求）
        # adjusted(0,0,-1,-1) 让边框完全在 widget 范围内（不超出 1px）
        rect = self.rect().adjusted(0, 0, -1, -1)
        p.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 220), 1))
        p.setBrush(QtGui.QColor(79, 195, 247, 230))  # 天蓝 #4FC3F7
        p.drawRoundedRect(rect, 8, 8)
        # 占位图标（v1 用 emoji；后续可换 SVG）
        p.setPen(QtGui.QColor(255, 255, 255))
        font = p.font()
        font.setPointSize(14)
        p.setFont(font)
        p.drawText(self.rect(), QtCore.Qt.AlignCenter, "📊")

    def on_connected(self):
        # v3.2：状态点颜色走全局 QSS，用 setProperty + refresh 触发重算
        self._status_dot.setProperty("connected", "true")
        self._status_dot.style().unpolish(self._status_dot)
        self._status_dot.style().polish(self._status_dot)
        log.info("strip status: green (SSE connected)")

    def on_disconnected(self):
        self._status_dot.setProperty("connected", "false")
        self._status_dot.style().unpolish(self._status_dot)
        self._status_dot.style().polish(self._status_dot)
        log.info("strip status: red (SSE disconnected)")

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_offset = event.globalPos() - self.frameGeometry().topLeft()
            self.show_requested.emit()
            log.info("strip click: show_requested emitted, drag start")
        # 右键不响应（保留供将来 menu 用）

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & QtCore.Qt.LeftButton:
            self.move(event.globalPos() - self._drag_offset)

    def mouseReleaseEvent(self, _event):
        self._drag_offset = None
        # 屏外吸附：screenAt 返 None 表示窗口被拖到所有屏幕外
        cursor_screen = QtWidgets.QApplication.screenAt(self.pos())
        if cursor_screen is None:
            log.warning("strip released offscreen, snapping back")
            self._positioned = False  # 强制重新定位
            self._reposition_to_right_edge()
        else:
            log.info("strip mouse release: drag end at pos=(%d,%d)",
                     self.x(), self.y())