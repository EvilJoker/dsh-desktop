# 桌面助手右边缘贴边悬浮（Edge Dock）实施计划

> **状态：✅ 已交付**（commit `4379164` 落地 + `02af186` UI 迭代）。本计划作为设计过程留档。
>
> **v3.1 变更（2026-06-15）**：UI 反馈后取消 HotZoneWatcher。下表中 `panel/hotzone.py` 行（Task 5/6/8/11）已被实际实现超越——`panel/hotzone.py` 和 `tests/test_hotzone.py` 在实施时已删除。展开/折叠完全靠 strip 按钮（toggle）+ panel › 按钮触发。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把桌面助手 panel 改造成「双窗口 + 边缘热区悬停/点击展开 + 左侧 ◀ 收起」模式，参考电脑管家 SMBMainWidget + SysMonitorBall 的架构。

**Architecture:** `panel/main.py` 缩成 ~30 行启动壳子，把现有 `Panel` 类搬到新文件 `panel/panel_window.py` 重命名为 `PanelWindow`（默认隐藏 + 去 `WindowStaysOnBottomHint` + 新增 collapse 按钮 + 滑入/滑出动画），新建 `panel/strip.py`（37×75 窄条，置顶）、`panel/hotzone.py`（50ms QTimer 轮询 QCursor.pos() 检测右 6-8px 热区）、`panel/window_manager.py`（拼装三部件 + 单例 SSEClient）。server、cards、构建脚本不动。

**Tech Stack:** Python 3.6.8 + PyQt5 5.13.1 + pytest 7.0.1 + coverage 4.5.1（沿用现有基建）

**Spec:** `docs/superpowers/specs/2026-06-13-right-edge-dock-design.md`（commit bf8713b）

---

## 文件结构

| 路径 | 角色 | 操作 |
|------|------|------|
| `desk-assistant/panel/main.py` | 启动壳子（缩成 ~30 行），构造 `WindowManager` 后 `app.exec_()` | 修改 |
| `desk-assistant/panel/panel_window.py` | `PanelWindow` 类，从 main.py 拆出；新增 collapse 按钮、slide_in/out、show_animated；构造时不 show | 新建 |
| `desk-assistant/panel/strip.py` | `Strip` 类，37×75，WindowStaysOnTopHint，自绘圆角矩形 + 图标 + 状态点 | 新建 |
| `desk-assistant/panel/hotzone.py` | `HotZoneWatcher(QObject)`，50ms 轮询 QCursor.pos() 检测热区 | 新建 |
| `desk-assistant/panel/window_manager.py` | `WindowManager(QObject)`，拼装三部件 + 单例 SSEClient + 连信号 | 新建 |
| `desk-assistant/tests/test_strip.py` | strip.py 单元测试 | 新建 |
| `desk-assistant/tests/test_hotzone.py` | hotzone.py 单元测试 | 新建 |
| `desk-assistant/tests/test_panel_window.py` | panel_window.py 单元测试 | 新建 |
| `desk-assistant/tests/test_window_manager.py` | window_manager.py 单元测试 | 新建 |
| `desk-assistant/tests/test_main.py` | 删掉原 `from panel.main import Panel` 相关测试（迁到 test_panel_window.py） | 修改 |

**不动**：`server/`、`panel/metrics_card.py`、`panel/events_card.py`、`panel/chat_card.py`、`panel/xiaoou_card.py`、`panel/base_chat_card.py`、`panel/config.py`、`script/`、其他 `tests/test_*.py`。

---

## Task 1: Strip 窗口骨架 + 贴右居中 + paintEvent

**Files:**
- Create: `desk-assistant/panel/strip.py`
- Create: `desk-assistant/tests/test_strip.py`

- [ ] **Step 1.1: 写失败测试**

新建 `desk-assistant/tests/test_strip.py`：

```python
"""panel/strip.py 单元测试：尺寸、位置、窗口标志、自绘。"""
import pytest
from PyQt5 import QtCore, QtGui, QtWidgets

from panel.strip import Strip, STRIP_WIDTH, STRIP_HEIGHT, EDGE_MARGIN


def test_strip_size_constants():
    """Strip 尺寸常量与电脑管家参考一致：37×75。"""
    assert STRIP_WIDTH == 37
    assert STRIP_HEIGHT == 75


def test_strip_window_flags_have_stays_on_top_and_tool(qapp):
    """Strip 必须 WindowStaysOnTopHint（永远在最前）+ Tool（不进任务栏）。"""
    s = Strip()
    flags = s.windowFlags()
    assert flags & QtCore.Qt.WindowStaysOnTopHint
    assert flags & QtCore.Qt.Tool
    assert flags & QtCore.Qt.FramelessWindowHint


def test_strip_default_size_37x75(qapp):
    """构造后 size = (37, 75)。"""
    s = Strip()
    assert s.width() == 37
    assert s.height() == 75


def test_strip_reposition_to_right_edge(qapp, monkeypatch):
    """_reposition_to_right_edge 把窗口贴到屏幕右边、垂直居中。"""
    class FakeScreen:
        def availableGeometry(self):
            return QtCore.QRect(0, 0, 1920, 1080)
    monkeypatch.setattr(
        QtWidgets.QApplication, "primaryScreen", lambda self=None: FakeScreen()
    )
    s = Strip()
    s._reposition_to_right_edge()
    # 期望：x = 1920 - 37 - EDGE_MARGIN, y = (1080 - 75) // 2
    assert s.x() == 1920 - 37 - EDGE_MARGIN
    assert s.y() == (1080 - 75) // 2


def test_strip_reposition_skips_when_screen_invalid(qapp, monkeypatch):
    """primaryScreen 返 0×0 → 跳过（log warning + 不动位置）。"""
    class FakeScreen:
        def availableGeometry(self):
            return QtCore.QRect(0, 0, 0, 0)
    monkeypatch.setattr(
        QtWidgets.QApplication, "primaryScreen", lambda self=None: FakeScreen()
    )
    s = Strip()
    before = s.pos()
    s._reposition_to_right_edge()
    assert s.pos() == before


def test_strip_paint_event_does_not_crash(qapp):
    """paintEvent 不抛异常（自绘半透明圆角矩形）。"""
    s = Strip()
    s.resize(37, 75)
    s.show()
    QtCore.QCoreApplication.processEvents()
    # 强制 paint
    s.repaint()
    # 不崩就行；不强验像素
    assert True
```

- [ ] **Step 1.2: 跑测试确认失败**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DESK_ASSISTANT_DB=state_test.db QT_QPA_PLATFORM=offscreen \
  /usr/bin/python3 -m pytest tests/test_strip.py -v
```

Expected: FAIL，`ModuleNotFoundError: No module named 'panel.strip'`。

- [ ] **Step 1.3: 实现 Strip 类骨架**

新建 `desk-assistant/panel/strip.py`：

```python
"""panel/strip.py — 桌面助手右边缘贴边窄条（37×75）。

架构（v3，Edge Dock）：
  1. WindowStaysOnTopHint + Tool 永远贴右、垂直居中
  2. 自绘圆角矩形 + 图标 + 状态点（v1 先占位图标）
  3. SSE connected/disconnected 信号驱动状态点颜色
  4. 鼠标左键 emit show_requested → WindowManager 唤起 Panel
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
EDGE_MARGIN = 20


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

    def _reposition_to_right_edge(self):
        screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
        if screen.width() <= 0 or screen.height() <= 0:
            log.warning("primary screen invalid, skip strip reposition")
            return
        self.move(
            screen.x() + screen.width() - self.width() - EDGE_MARGIN,
            screen.y() + (screen.height() - self.height()) // 2,
        )
        self._positioned = True

    def showEvent(self, event):
        super().showEvent(event)
        if not self._positioned:
            QtCore.QTimer.singleShot(0, self._reposition_to_right_edge)
            QtCore.QTimer.singleShot(100, self._reposition_to_right_edge)

    def paintEvent(self, _event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QColor(20, 20, 28, 200))
        p.drawRoundedRect(self.rect(), 8, 8)
        # 占位图标（v1 用 emoji；后续可换 SVG）
        p.setPen(QtGui.QColor(255, 255, 255))
        font = p.font()
        font.setPointSize(14)
        p.setFont(font)
        p.drawText(self.rect(), QtCore.Qt.AlignCenter, "📊")
```

- [ ] **Step 1.4: 跑测试确认通过**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DESK_ASSISTANT_DB=state_test.db QT_QPA_PLATFORM=offscreen \
  /usr/bin/python3 -m pytest tests/test_strip.py -v
```

Expected: 6 passed。

- [ ] **Step 1.5: 提交**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手
git add desk-assistant/panel/strip.py desk-assistant/tests/test_strip.py
git commit -m "feat(panel): Strip 窗口骨架（37×75 贴右居中 + 自绘 + WindowStaysOnTop）"
```

---

## Task 2: Strip 状态点 + on_connected / on_disconnected

**Files:**
- Modify: `desk-assistant/panel/strip.py`
- Modify: `desk-assistant/tests/test_strip.py`

- [ ] **Step 2.1: 写失败测试**

追加到 `desk-assistant/tests/test_strip.py`：

```python
def test_strip_status_dot_green_on_connected(qapp):
    """on_connected() → 状态点样式含 #77ff77（绿）。"""
    s = Strip()
    s.on_connected()
    style = s._status_dot.styleSheet()
    assert "#77ff77" in style


def test_strip_status_dot_red_on_disconnected(qapp):
    """on_disconnected() → 状态点样式含 #ff7777（红）。"""
    s = Strip()
    s.on_disconnected()
    style = s._status_dot.styleSheet()
    assert "#ff7777" in style
```

- [ ] **Step 2.2: 跑测试确认失败**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DESK_ASSISTANT_DB=state_test.db QT_QPA_PLATFORM=offscreen \
  /usr/bin/python3 -m pytest tests/test_strip.py::test_strip_status_dot_green_on_connected tests/test_strip.py::test_strip_status_dot_red_on_disconnected -v
```

Expected: FAIL，`AttributeError: 'Strip' object has no attribute '_status_dot'`。

- [ ] **Step 2.3: 在 Strip.__init__ 末尾添加状态点，新增 on_connected / on_disconnected**

修改 `desk-assistant/panel/strip.py` 的 `Strip.__init__` 末尾（在 `self._positioned = False` 之后）追加：

```python
        # 状态点：右上角 6×6 圆点，SSE 连接态驱动颜色
        self._status_dot = QtWidgets.QLabel(self)
        self._status_dot.setFixedSize(6, 6)
        self._status_dot.move(self.width() - 9, 3)
        self._status_dot.setStyleSheet(
            "background: #ff7777; border-radius: 3px;"
        )
```

在 `Strip` 类新增两个方法（紧跟 `paintEvent` 之后）：

```python
    def on_connected(self):
        self._status_dot.setStyleSheet(
            "background: #77ff77; border-radius: 3px;"
        )

    def on_disconnected(self):
        self._status_dot.setStyleSheet(
            "background: #ff7777; border-radius: 3px;"
        )
```

- [ ] **Step 2.4: 跑测试确认通过**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DESK_ASSISTANT_DB=state_test.db QT_QPA_PLATFORM=offscreen \
  /usr/bin/python3 -m pytest tests/test_strip.py -v
```

Expected: 8 passed。

- [ ] **Step 2.5: 提交**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手
git add desk-assistant/panel/strip.py desk-assistant/tests/test_strip.py
git commit -m "feat(panel): Strip 状态点 + on_connected/on_disconnected 颜色切换"
```

---

## Task 3: Strip 左键 emit show_requested

**Files:**
- Modify: `desk-assistant/panel/strip.py`
- Modify: `desk-assistant/tests/test_strip.py`

- [ ] **Step 3.1: 写失败测试**

追加到 `desk-assistant/tests/test_strip.py`：

```python
def test_strip_left_click_emits_show_requested(qapp):
    """左键 mousePressEvent → emit show_requested。"""
    from PyQt5 import QtCore, QtGui
    s = Strip()
    received = []
    s.show_requested.connect(lambda: received.append(True))
    ev = QtGui.QMouseEvent(
        QtCore.QEvent.MouseButtonPress,
        QtCore.QPoint(10, 10),
        QtCore.QPoint(10, 10),
        QtCore.Qt.LeftButton,
        QtCore.Qt.LeftButton,
        QtCore.Qt.NoModifier,
    )
    s.mousePressEvent(ev)
    assert received == [True]


def test_strip_right_click_no_emit(qapp):
    """右键 mousePressEvent 不 emit show_requested。"""
    from PyQt5 import QtCore, QtGui
    s = Strip()
    received = []
    s.show_requested.connect(lambda: received.append(True))
    ev = QtGui.QMouseEvent(
        QtCore.QEvent.MouseButtonPress,
        QtCore.QPoint(10, 10),
        QtCore.QPoint(10, 10),
        QtCore.Qt.RightButton,
        QtCore.Qt.RightButton,
        QtCore.Qt.NoModifier,
    )
    s.mousePressEvent(ev)
    assert received == []
```

- [ ] **Step 3.2: 跑测试确认失败**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DESK_ASSISTANT_DB=state_test.db QT_QPA_PLATFORM=offscreen \
  /usr/bin/python3 -m pytest "tests/test_strip.py::test_strip_left_click_emits_show_requested" "tests/test_strip.py::test_strip_right_click_no_emit" -v
```

Expected: FAIL，`AttributeError: 'Strip' object has no attribute 'show_requested'` 或信号未连接。

- [ ] **Step 3.3: 在 Strip 类添加 mousePressEvent**

在 `desk-assistant/panel/strip.py` 的 `Strip` 类新增（紧跟 `on_disconnected` 之后）：

```python
    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_offset = event.globalPos() - self.frameGeometry().topLeft()
            self.show_requested.emit()
        # 右键不响应（保留供将来 menu 用）
```

- [ ] **Step 3.4: 跑测试确认通过**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DESK_ASSISTANT_DB=state_test.db QT_QPA_PLATFORM=offscreen \
  /usr/bin/python3 -m pytest tests/test_strip.py -v
```

Expected: 10 passed。

- [ ] **Step 3.5: 提交**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手
git add desk-assistant/panel/strip.py desk-assistant/tests/test_strip.py
git commit -m "feat(panel): Strip 左键 emit show_requested + 拖动 offset 记录"
```

---

## Task 4: Strip 拖动 + 屏外吸附

**Files:**
- Modify: `desk-assistant/panel/strip.py`
- Modify: `desk-assistant/tests/test_strip.py`

- [ ] **Step 4.1: 写失败测试**

追加到 `desk-assistant/tests/test_strip.py`：

```python
def test_strip_mouse_move_with_drag_reposition(qapp):
    """drag_offset 非空 + 左键 → 移到新位置。"""
    from PyQt5 import QtCore, QtGui
    s = Strip()
    s._drag_offset = QtCore.QPoint(0, 0)
    s.move(50, 50)
    ev = QtGui.QMouseEvent(
        QtCore.QEvent.MouseMove,
        QtCore.QPoint(200, 200),
        QtCore.QPoint(200, 200),
        QtCore.Qt.NoButton,
        QtCore.Qt.LeftButton,
        QtCore.Qt.NoModifier,
    )
    s.mouseMoveEvent(ev)
    assert abs(s.x() - 200) < 5
    assert abs(s.y() - 200) < 5


def test_strip_release_offscreen_snaps_back(qapp, monkeypatch):
    """拖到屏外（screenAt 返 None）→ release 后回到右边缘。"""
    from PyQt5 import QtCore, QtGui
    class FakeScreen:
        def availableGeometry(self):
            return QtCore.QRect(0, 0, 1920, 1080)
    monkeypatch.setattr(
        QtWidgets.QApplication, "primaryScreen", lambda self=None: FakeScreen()
    )
    monkeypatch.setattr(
        QtWidgets.QApplication, "screenAt", lambda self=None, pos: None
    )
    s = Strip()
    s._drag_offset = QtCore.QPoint(0, 0)
    # 假装被拖到屏外 (-9999, -9999)
    s.move(-9999, -9999)
    s.mouseReleaseEvent(QtGui.QMouseEvent(
        QtCore.QEvent.MouseButtonRelease,
        QtCore.QPoint(-9999, -9999),
        QtCore.QPoint(-9999, -9999),
        QtCore.Qt.LeftButton,
        QtCore.Qt.NoButton,
        QtCore.Qt.NoModifier,
    ))
    # 应被吸回右边缘
    assert s.x() == 1920 - 37 - EDGE_MARGIN
    assert s.y() == (1080 - 75) // 2
    assert s._drag_offset is None
```

- [ ] **Step 4.2: 跑测试确认失败**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DESK_ASSISTANT_DB=state_test.db QT_QPA_PLATFORM=offscreen \
  /usr/bin/python3 -m pytest "tests/test_strip.py::test_strip_mouse_move_with_drag_reposition" "tests/test_strip.py::test_strip_release_offscreen_snaps_back" -v
```

Expected: FAIL，`AttributeError` or `mouseMoveEvent`/`mouseReleaseEvent` 不存在。

- [ ] **Step 4.3: 添加 mouseMoveEvent + mouseReleaseEvent**

在 `desk-assistant/panel/strip.py` 的 `Strip` 类新增（紧跟 `mousePressEvent` 之后）：

```python
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
```

- [ ] **Step 4.4: 跑测试确认通过**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DESK_ASSISTANT_DB=state_test.db QT_QPA_PLATFORM=offscreen \
  /usr/bin/python3 -m pytest tests/test_strip.py -v
```

Expected: 12 passed。

- [ ] **Step 4.5: 提交**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手
git add desk-assistant/panel/strip.py desk-assistant/tests/test_strip.py
git commit -m "feat(panel): Strip 拖动 + 屏外释放吸附到右边缘"
```

---

## Task 5: HotZoneWatcher 骨架 + timer 启停

**Files:**
- Create: `desk-assistant/panel/hotzone.py`
- Create: `desk-assistant/tests/test_hotzone.py`

- [ ] **Step 5.1: 写失败测试**

新建 `desk-assistant/tests/test_hotzone.py`：

```python
"""panel/hotzone.py 单元测试：轮询 timer 启停 + emit 条件。"""
import pytest
from PyQt5 import QtCore, QtWidgets

from panel.hotzone import HotZoneWatcher, HOTZONE_WIDTH_PX, POLL_INTERVAL_MS


def test_constants():
    """热区常量符合 spec：6-8px + 50ms 轮询。"""
    assert 6 <= HOTZONE_WIDTH_PX <= 8
    assert POLL_INTERVAL_MS == 50


def test_hotzone_starts_polling_on_init(qapp):
    """构造后 timer 处于 active 状态。"""
    hz = HotZoneWatcher()
    assert hz._timer.isActive()


def test_hotzone_timer_stops_when_parent_destroyed(qapp):
    """parent 销毁后 timer 自动停（Qt 父子机制）。"""
    hz = HotZoneWatcher()
    parent = QtCore.QObject()
    hz.setParent(parent)
    assert hz._timer.isActive()
    parent.deleteLater()
    QtCore.QCoreApplication.processEvents()
    assert not hz._timer.isActive()
```

- [ ] **Step 5.2: 跑测试确认失败**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DESK_ASSISTANT_DB=state_test.db QT_QPA_PLATFORM=offscreen \
  /usr/bin/python3 -m pytest tests/test_hotzone.py -v
```

Expected: FAIL，`ModuleNotFoundError: No module named 'panel.hotzone'`。

- [ ] **Step 5.3: 实现 HotZoneWatcher 骨架**

新建 `desk-assistant/panel/hotzone.py`：

```python
"""panel/hotzone.py — 屏幕右边缘隐形热区监听器。

架构：50ms QTimer 轮询 QCursor.pos()，判断鼠标 x 是否在 primary screen
右边缘 HOTZONE_WIDTH_PX 像素内。是 → emit hover_right_edge。

父对象销毁时 Qt 自动停 timer（QObject 父子机制）。
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PyQt5 import QtCore, QtGui, QtWidgets  # noqa: E402

log = logging.getLogger("panel.hotzone")

HOTZONE_WIDTH_PX = 8
POLL_INTERVAL_MS = 50


class HotZoneWatcher(QtCore.QObject):
    """轮询 QCursor.pos()，emit hover_right_edge 当鼠标进入右热区。"""

    hover_right_edge = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(POLL_INTERVAL_MS)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    def _poll(self):
        # v1 实现见 Task 6；Task 5 骨架先空
        pass
```

- [ ] **Step 5.4: 跑测试确认通过**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DESK_ASSISTANT_DB=state_test.db QT_QPA_PLATFORM=offscreen \
  /usr/bin/python3 -m pytest tests/test_hotzone.py -v
```

Expected: 3 passed。

- [ ] **Step 5.5: 提交**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手
git add desk-assistant/panel/hotzone.py desk-assistant/tests/test_hotzone.py
git commit -m "feat(panel): HotZoneWatcher 骨架 + 50ms 轮询 timer 启停"
```

---

## Task 6: HotZoneWatcher emit 逻辑

**Files:**
- Modify: `desk-assistant/panel/hotzone.py`
- Modify: `desk-assistant/tests/test_hotzone.py`

- [ ] **Step 6.1: 写失败测试**

追加到 `desk-assistant/tests/test_hotzone.py`：

```python
def test_hotzone_emits_when_cursor_in_zone(qapp, monkeypatch):
    """鼠标在右 8px 内 → emit hover_right_edge。"""
    from PyQt5 import QtCore
    class FakeScreen:
        def availableGeometry(self):
            return QtCore.QRect(0, 0, 1920, 1080)
    monkeypatch.setattr(
        QtWidgets.QApplication, "primaryScreen", lambda self=None: FakeScreen()
    )
    monkeypatch.setattr(QtGui.QCursor, "pos", lambda: QtCore.QPoint(1918, 500))
    hz = HotZoneWatcher()
    received = []
    hz.hover_right_edge.connect(lambda: received.append(True))
    hz._poll()
    assert received == [True]


def test_hotzone_no_emit_when_cursor_outside(qapp, monkeypatch):
    """鼠标在右 8px 外 → 不 emit。"""
    from PyQt5 import QtCore
    class FakeScreen:
        def availableGeometry(self):
            return QtCore.QRect(0, 0, 1920, 1080)
    monkeypatch.setattr(
        QtWidgets.QApplication, "primaryScreen", lambda self=None: FakeScreen()
    )
    monkeypatch.setattr(QtGui.QCursor, "pos", lambda: QtCore.QPoint(1800, 500))
    hz = HotZoneWatcher()
    received = []
    hz.hover_right_edge.connect(lambda: received.append(True))
    hz._poll()
    assert received == []


def test_hotzone_no_emit_when_cursor_offscreen(qapp, monkeypatch):
    """鼠标不在任何 screen → 不 emit。"""
    from PyQt5 import QtCore
    class FakeScreen:
        def availableGeometry(self):
            return QtCore.QRect(0, 0, 1920, 1080)
    monkeypatch.setattr(
        QtWidgets.QApplication, "primaryScreen", lambda self=None: FakeScreen()
    )
    monkeypatch.setattr(QtGui.QCursor, "pos", lambda: QtCore.QPoint(-9999, -9999))
    monkeypatch.setattr(
        QtWidgets.QApplication, "screenAt", lambda self=None, pos: None
    )
    hz = HotZoneWatcher()
    received = []
    hz.hover_right_edge.connect(lambda: received.append(True))
    hz._poll()
    assert received == []
```

- [ ] **Step 6.2: 跑测试确认失败**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DESK_ASSISTANT_DB=state_test.db QT_QPA_PLATFORM=offscreen \
  /usr/bin/python3 -m pytest "tests/test_hotzone.py::test_hotzone_emits_when_cursor_in_zone" "tests/test_hotzone.py::test_hotzone_no_emit_when_cursor_outside" "tests/test_hotzone.py::test_hotzone_no_emit_when_cursor_offscreen" -v
```

Expected: FAIL（3 个测试都失败，`_poll` 当前是空函数）。

- [ ] **Step 6.3: 实现 _poll 逻辑**

修改 `desk-assistant/panel/hotzone.py` 的 `_poll` 方法：

```python
    def _poll(self):
        cursor_pos = QtGui.QCursor.pos()
        # 鼠标不在任何屏幕内 → 不响应
        cursor_screen = QtWidgets.QApplication.screenAt(cursor_pos)
        if cursor_screen is None:
            return
        screen = cursor_screen.availableGeometry()
        # 鼠标在屏幕右边缘 HOTZONE_WIDTH_PX 像素内 → emit
        if cursor_pos.x() >= screen.x() + screen.width() - HOTZONE_WIDTH_PX:
            self.hover_right_edge.emit()
```

- [ ] **Step 6.4: 跑测试确认通过**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DESK_ASSISTANT_DB=state_test.db QT_QPA_PLATFORM=offscreen \
  /usr/bin/python3 -m pytest tests/test_hotzone.py -v
```

Expected: 6 passed。

- [ ] **Step 6.5: 提交**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手
git add desk-assistant/panel/hotzone.py desk-assistant/tests/test_hotzone.py
git commit -m "feat(panel): HotZoneWatcher 热区 emit 逻辑（screenAt + 边界判断）"
```

---

## Task 7: 拆分 Panel → PanelWindow（默认隐藏 + 去掉 WindowStaysOnBottomHint）

**Files:**
- Create: `desk-assistant/panel/panel_window.py`
- Create: `desk-assistant/tests/test_panel_window.py`
- Modify: `desk-assistant/panel/main.py`（导入路径变化）
- Modify: `desk-assistant/tests/test_main.py`（删除原 Panel 引用，保留 SSEClient 测试）

- [ ] **Step 7.1: 写失败测试**

新建 `desk-assistant/tests/test_panel_window.py`：

```python
"""panel/panel_window.py 单元测试：构造、窗口标志、隐藏态、collapse 按钮、slide 动画。"""
import pytest
from PyQt5 import QtCore, QtGui, QtWidgets

from panel.panel_window import (
    PanelWindow,
    PANEL_WIDTH,
    PANEL_HEIGHT,
    EDGE_MARGIN,
    SLIDE_DURATION_MS,
)


def test_panel_size_constants():
    """PanelWindow 尺寸保持现状 960×800。"""
    assert PANEL_WIDTH == 960
    assert PANEL_HEIGHT == 800


def test_panel_starts_hidden_after_init(qapp):
    """PanelWindow.__init__ 不调 show()，构造后 isHidden() == True。"""
    p = PanelWindow()
    assert p.isHidden()


def test_panel_no_window_stays_on_bottom_hint(qapp):
    """PanelWindow 不再用 WindowStaysOnBottomHint（按需弹出而非常驻沉底）。"""
    p = PanelWindow()
    flags = p.windowFlags()
    assert not (flags & QtCore.Qt.WindowStaysOnBottomHint)


def test_panel_has_close_btn_on_top_right(qapp):
    """close_btn 仍在右上角（✕ 退出 app）。"""
    p = PanelWindow()
    p.resize(PANEL_WIDTH, PANEL_HEIGHT)
    p.show()
    QtCore.QCoreApplication.processEvents()
    expected_x = p.width() - p.close_btn.width() - 8
    assert p.close_btn.x() == expected_x
    assert p.close_btn.y() == 8


def test_panel_collapse_btn_exists_on_left(qapp):
    """collapse_btn（◀）位于面板左侧 8px 处。"""
    p = PanelWindow()
    p.resize(PANEL_WIDTH, PANEL_HEIGHT)
    p.show()
    QtCore.QCoreApplication.processEvents()
    assert p.collapse_btn.x() == 8
    assert p.collapse_btn.y() > 0
    # ◀ 字符
    assert "◀" in p.collapse_btn.text()
```

- [ ] **Step 7.2: 跑测试确认失败**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DESK_ASSISTANT_DB=state_test.db QT_QPA_PLATFORM=offscreen \
  /usr/bin/python3 -m pytest tests/test_panel_window.py -v
```

Expected: FAIL，`ModuleNotFoundError: No module named 'panel.panel_window'`。

- [ ] **Step 7.3: 创建 panel_window.py，把 Panel 类搬过来并重命名**

新建 `desk-assistant/panel/panel_window.py`：

```python
"""panel/panel_window.py — 桌面助手主面板（960×800）。

架构（v3，Edge Dock）：
  - 构造后默认隐藏，由 WindowManager 在收到 Strip.show_requested 或
    HotZoneWatcher.hover_right_edge 时调 show_animated() 唤起
  - 不再用 WindowStaysOnBottomHint；靠 raise_() + activateWindow() 强制置顶
  - 左侧 ◀ collapse_btn 发 collapse_requested 信号
  - 右上 ✕ close_btn 仍调 QApplication.quit（保留现状）
  - slide_in/out 用 QPropertyAnimation 200ms 从右滑入/滑出
  - SSEClient 由 WindowManager 持有并传入，PanelWindow 不持有所有权
"""
import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PyQt5 import QtCore, QtGui, QtNetwork, QtWidgets  # noqa: E402

from chat_card import ChatCard  # noqa: E402
from config import load_config  # noqa: E402
from events_card import EventsCard  # noqa: E402
from metrics_card import MetricsCard  # noqa: E402
from xiaoou_card import XiaoouCard  # noqa: E402

log = logging.getLogger("panel.window")

# ---- server 配置 ----
SSE_URL = "http://127.0.0.1:18675/events"
SERVER_BASE = "http://127.0.0.1:18675"
SERVER_METRICS_URL = SERVER_BASE + "/api/metrics"
SERVER_EVENTS_URL = SERVER_BASE + "/api/events"
RECONNECT_DELAY_MS = 5000
REFRESH_DEBOUNCE_MS = 150

# ---- panel 几何 ----
PANEL_WIDTH = 960
PANEL_HEIGHT = 800
EDGE_MARGIN = 20
SLIDE_DURATION_MS = 200
SLIDE_EASING = QtCore.QEasingCurve.OutCubic

# ---- 配置加载 ----
_CFG = load_config()
OPENCLAW_CFG = _CFG.get("openclaw", {})
XIAOOU_CFG = _CFG.get("xiaoou")

OPENCLAW_URL = OPENCLAW_CFG.get("url", "http://127.0.0.1:18789/v1/chat/completions")
OPENCLAW_MODEL = OPENCLAW_CFG.get("model", "openclaw")
OPENCLAW_SESSION_KEY = OPENCLAW_CFG.get(
    "session_key",
    "agent:main:openai:00000000-0000-4000-8000-000000000001@topic:desk-assistant",
)
OPENCLAW_CHAT_URL = OPENCLAW_CFG.get(
    "chat_url",
    "http://127.0.0.1:18789/chat?lang=zh-CN&session=" + quote(OPENCLAW_SESSION_KEY, safe=""),
)
OPENCLAW_CONFIG_PATH = Path.home() / ".openclaw" / "openclaw.json"


def _load_openclaw_token():
    if not OPENCLAW_CONFIG_PATH.exists():
        return None
    try:
        cfg = json.loads(OPENCLAW_CONFIG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        log.warning("openclaw config read/parse failed: %s: %s", type(e).__name__, e)
        return None
    if not isinstance(cfg, dict):
        log.warning("openclaw config: expected object, got %s", type(cfg).__name__)
        return None
    return cfg.get("gateway", {}).get("auth", {}).get("token") or None


class PanelWindow(QtWidgets.QWidget):
    """主面板：壳子 + 4 张卡片 + 关闭按钮 + 收起按钮 + 滑入/滑出动画。"""

    # WindowManager 连这个信号：Panel.collapse → WindowManager.hide panel
    collapse_requested = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DeskAssistantPanel")
        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint
            | QtCore.Qt.Tool
            # 删除 WindowStaysOnBottomHint
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.resize(PANEL_WIDTH, PANEL_HEIGHT)
        self._positioned = False
        self._drag_offset = None
        self._anim = None
        self._http_nam = QtNetwork.QNetworkAccessManager(self)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(6)

        # 标题行（标题 + SSE 连接状态）。右侧留 30px 给浮动关闭按钮。
        header = QtWidgets.QHBoxLayout()
        header.setSpacing(8)
        header.setContentsMargins(0, 0, 30, 0)
        self.title = QtWidgets.QLabel("桌面助手 · 等待连接…")
        self.title.setStyleSheet(
            "color: #ffffff; font-size: 13px; font-weight: bold;"
        )
        header.addWidget(self.title, 1)
        self.status = QtWidgets.QLabel("○ disconnected")
        self.status.setStyleSheet("color: #ff7777; font-size: 10px;")
        header.addWidget(self.status)
        layout.addLayout(header)

        # 4 张卡片
        self.metrics_card = MetricsCard()
        self.events_card = EventsCard()
        self.events_card.toggle_requested.connect(self._on_event_toggle)
        self.chat_card = ChatCard(
            openclaw_url=OPENCLAW_URL,
            model=OPENCLAW_MODEL,
            session_key=OPENCLAW_SESSION_KEY,
            chat_url=OPENCLAW_CHAT_URL,
        )
        self.chat_card.set_token(_load_openclaw_token())

        self.xiaoou_card = None
        if XIAOOU_CFG:
            self.xiaoou_card = XiaoouCard(
                base_url=XIAOOU_CFG["base_url"],
                model=XIAOOU_CFG["model"],
                topic_id=XIAOOU_CFG["topic_id"],
                source=XIAOOU_CFG["source"],
                auth_header=(
                    XIAOOU_CFG["auth"]["header"].encode("utf-8"),
                    XIAOOU_CFG["auth"]["value"].encode("utf-8"),
                ),
            )

        cards = [self.metrics_card, self.events_card, self.chat_card]
        if self.xiaoou_card is not None:
            cards.append(self.xiaoou_card)
        for card in cards:
            card.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding,
                QtWidgets.QSizePolicy.Expanding,
            )

        self._stack = QtWidgets.QStackedWidget()
        for card in cards:
            self._stack.addWidget(card)
        layout.addWidget(self._stack, 1)

        # tab 栏
        self._tab_group = QtWidgets.QButtonGroup(self)
        self._tab_group.setExclusive(True)
        self._tab_group.buttonClicked[int].connect(self._set_tab)
        self._tabs = []
        tab_bar = QtWidgets.QHBoxLayout()
        tab_bar.setContentsMargins(0, 0, 0, 0)
        tab_bar.setSpacing(0)
        tab_labels = ["指标", "事件", "对话"]
        if self.xiaoou_card is not None:
            tab_labels.append("小欧")
        for i, label in enumerate(tab_labels):
            btn = QtWidgets.QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(28)
            btn.setCursor(QtCore.Qt.PointingHandCursor)
            btn.setStyleSheet(
                "QPushButton {"
                "  background: transparent;"
                "  color: rgba(255,255,255,160);"
                "  border: 0;"
                "  border-bottom: 2px solid transparent;"
                "  padding: 4px 14px;"
                "  font-size: 12px;"
                "}"
                "QPushButton:checked {"
                "  color: #ffffff;"
                "  font-weight: bold;"
                "  border-bottom: 2px solid #6bb6ff;"
                "}"
                "QPushButton:hover:!checked {"
                "  color: rgba(255,255,255,220);"
                "}"
            )
            self._tab_group.addButton(btn, i)
            self._tabs.append(btn)
            tab_bar.addWidget(btn)
        tab_bar.addStretch(1)
        layout.addLayout(tab_bar)

        # 右上角关闭按钮（✕ 退出整个 app）
        self.close_btn = QtWidgets.QPushButton("✕", self)
        self.close_btn.setFixedSize(22, 22)
        self.close_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.close_btn.setToolTip("关闭看板（后台服务继续运行）")
        self.close_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(255, 80, 80, 180);"
            "  color: #ffffff;"
            "  font-size: 13px;"
            "  font-weight: bold;"
            "  border: none;"
            "  border-radius: 11px;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(255, 50, 50, 230);"
            "}"
        )
        self.close_btn.clicked.connect(QtWidgets.QApplication.quit)
        self.close_btn.raise_()

        # 左侧 ◀ 收起按钮（emit collapse_requested → WindowManager.hide panel）
        self.collapse_btn = QtWidgets.QPushButton("◀", self)
        self.collapse_btn.setFixedSize(22, 22)
        self.collapse_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self.collapse_btn.setToolTip("收起面板（保留后台）")
        self.collapse_btn.setStyleSheet(
            "QPushButton {"
            "  background: rgba(80, 80, 80, 180);"
            "  color: #ffffff;"
            "  font-size: 12px;"
            "  border: none;"
            "  border-radius: 11px;"
            "}"
            "QPushButton:hover {"
            "  background: rgba(120, 120, 120, 220);"
            "}"
        )
        self.collapse_btn.clicked.connect(self._on_collapse_clicked)
        self.collapse_btn.raise_()

        # SSE → REST debounce timers
        self._refresh_metrics_timer = QtCore.QTimer(self)
        self._refresh_metrics_timer.setSingleShot(True)
        self._refresh_metrics_timer.setInterval(REFRESH_DEBOUNCE_MS)
        self._refresh_metrics_timer.timeout.connect(self._refresh_metrics)
        self._refresh_events_timer = QtCore.QTimer(self)
        self._refresh_events_timer.setSingleShot(True)
        self._refresh_events_timer.setInterval(REFRESH_DEBOUNCE_MS)
        self._refresh_events_timer.timeout.connect(self._refresh_events)

        self._current_tab_index = 2
        self._tabs[2].setChecked(True)
        self._stack.setCurrentIndex(2)

        QtWidgets.QApplication.instance().installEventFilter(self)

        # v3：默认隐藏，等 WindowManager 调 show_animated()
        self.hide()

    # ----- tab 切换（从 main.py 搬过来，零改动）-----

    def _set_tab(self, i):
        if not 0 <= i < self._stack.count():
            return
        if i == self._current_tab_index:
            return
        self._current_tab_index = i
        self._stack.setCurrentIndex(i)
        self._tabs[i].setChecked(True)

    def _set_tab_if_not_input(self, i):
        focus = QtWidgets.QApplication.focusWidget()
        if isinstance(focus, QtWidgets.QLineEdit):
            return
        self._set_tab(i)

    def eventFilter(self, watched, event):
        if event.type() == QtCore.QEvent.KeyPress:
            if event.modifiers() & QtCore.Qt.ControlModifier:
                focus = QtWidgets.QApplication.focusWidget()
                if not isinstance(focus, QtWidgets.QLineEdit):
                    key = event.key()
                    if key == QtCore.Qt.Key_1:
                        self._set_tab(0)
                        return True
                    if key == QtCore.Qt.Key_2:
                        self._set_tab(1)
                        return True
                    if key == QtCore.Qt.Key_3:
                        self._set_tab(2)
                        return True
                    if key == QtCore.Qt.Key_4:
                        self._set_tab(3)
                        return True
        return super().eventFilter(watched, event)

    # ----- collapse -----

    def _on_collapse_clicked(self):
        self.collapse_requested.emit()

    # ----- SSE 事件派发 -----

    def on_sse_event(self, name, data):
        if name == "hello":
            self._refresh_metrics_timer.stop()
            self._refresh_events_timer.stop()
            self._refresh_metrics()
            self._refresh_events()
        elif name == "metrics.changed":
            self._refresh_metrics_timer.start()
        elif name == "events.changed":
            self._refresh_events_timer.start()

    def _refresh_metrics(self):
        req = QtNetwork.QNetworkRequest(QtCore.QUrl(SERVER_METRICS_URL))
        reply = self._http_nam.get(req)
        reply.finished.connect(lambda r=reply: self._on_metrics_reply(r))

    def _on_metrics_reply(self, reply):
        try:
            if reply.error() == QtNetwork.QNetworkReply.NoError:
                body = bytes(reply.readAll()).decode("utf-8", errors="replace")
                data = json.loads(body) if body else []
                if isinstance(data, list):
                    self.metrics_card.update_indicators(data)
                    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
                    self.title.setText("桌面助手 · " + now)
            else:
                log.warning("GET /api/metrics failed: err=%s", reply.error())
                self.status.setText("✕ metrics error")
                self.status.setStyleSheet("color: #ff7777; font-size: 10px;")
        finally:
            reply.deleteLater()

    def _refresh_events(self):
        req = QtNetwork.QNetworkRequest(QtCore.QUrl(SERVER_EVENTS_URL))
        reply = self._http_nam.get(req)
        reply.finished.connect(lambda r=reply: self._on_events_reply(r))

    def _on_events_reply(self, reply):
        try:
            if reply.error() == QtNetwork.QNetworkReply.NoError:
                body = bytes(reply.readAll()).decode("utf-8", errors="replace")
                data = json.loads(body) if body else []
                if isinstance(data, list):
                    self.events_card.update_events(data)
            else:
                log.warning("GET /api/events failed: err=%s", reply.error())
                self.status.setText("✕ events error")
                self.status.setStyleSheet("color: #ff7777; font-size: 10px;")
        finally:
            reply.deleteLater()

    def on_connected(self):
        self.status.setText("● connected")
        self.status.setStyleSheet("color: #77ff77; font-size: 10px;")

    def on_disconnected(self):
        self.status.setText("○ reconnecting in 5s…")
        self.status.setStyleSheet("color: #ff7777; font-size: 10px;")

    # ----- 事件勾选回写 -----

    def _on_event_toggle(self, event_id, checked):
        url = "%s/%d" % (SERVER_EVENTS_URL, int(event_id))
        body = json.dumps({"done": bool(checked)}).encode("utf-8")
        req = QtNetwork.QNetworkRequest(QtCore.QUrl(url))
        req.setHeader(
            QtNetwork.QNetworkRequest.ContentTypeHeader,
            "application/json",
        )
        reply = self._http_nam.sendCustomRequest(req, b"PATCH", body)
        reply.finished.connect(lambda r=reply, eid=event_id: self._on_patch_reply(r, eid))

    def _on_patch_reply(self, reply, event_id):
        try:
            err = reply.error()
            if err != QtNetwork.QNetworkReply.NoError:
                status = reply.attribute(
                    QtNetwork.QNetworkRequest.HttpStatusCodeAttribute
                )
                body = bytes(reply.readAll())[:200]
                print(
                    "[panel] PATCH /api/events/%s failed: err=%s status=%s body=%r"
                    % (event_id, err, status, body),
                    file=sys.stderr,
                    flush=True,
                )
        finally:
            reply.deleteLater()

    # ----- 绘制 / 位置 / 交互 -----

    def paintEvent(self, _event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QColor(20, 20, 28, 160))
        p.drawRoundedRect(self.rect(), 12, 12)

    def _reposition_to_right_edge(self):
        screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
        if screen.width() <= 0 or screen.height() <= 0:
            return
        self.move(
            screen.x() + screen.width() - self.width() - EDGE_MARGIN,
            screen.y() + (screen.height() - self.height()) // 2,
        )
        self._positioned = True

    def showEvent(self, event):
        super().showEvent(event)
        if not self._positioned:
            QtCore.QTimer.singleShot(0, self._reposition_to_right_edge)
            QtCore.QTimer.singleShot(100, self._reposition_to_right_edge)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.close_btn.move(self.width() - self.close_btn.width() - 8, 8)
        # collapse_btn 垂直居中
        self.collapse_btn.move(
            8,
            (self.height() - self.collapse_btn.height()) // 2,
        )

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._drag_offset = event.globalPos() - self.frameGeometry().topLeft()
        elif event.button() == QtCore.Qt.RightButton:
            QtWidgets.QApplication.quit()

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & QtCore.Qt.LeftButton:
            self.move(event.globalPos() - self._drag_offset)

    def mouseReleaseEvent(self, _event):
        self._drag_offset = None
```

- [ ] **Step 7.4: 更新 main.py 重新导出 Panel 别名以保持向后兼容**

修改 `desk-assistant/panel/main.py` 顶部 import 区域（在现有 from ... import 之后）追加：

```python
# v3 拆分后，Panel 别名指向 PanelWindow 以兼容现有测试。
from panel_window import PanelWindow as Panel  # noqa: E402, F401
```

注意：这一步**只是兼容测试**，后续 Task 15 会把 main.py 缩成启动壳子。

- [ ] **Step 7.5: 删除 test_main.py 中迁移走的测试，保留 SSEClient 测试**

修改 `desk-assistant/tests/test_main.py`：
- 删除文件开头的 `from panel.main import (..., Panel, ...)` 中的 `Panel` 字段
- 删除文件中所有 `def test_panel_*` 和 `class _FakeNam` 等 Panel 相关 fixture
- 保留 `def test_sse_*` 系列（4 个左右）

操作：用 Edit 工具删除 `Panel` 相关 import 和 `@pytest.fixture def panel` 块及所有 `def test_panel_*` 函数。如果文件只剩 SSEClient 测试代码就行。

- [ ] **Step 7.6: 把原 test_main.py 中的 Panel 测试整体搬到 test_panel_window.py 末尾**

追加到 `desk-assistant/tests/test_panel_window.py` 末尾：

```python
# ---- 原 test_main.py 中的 Panel 测试（搬过来）----


@pytest.fixture
def panel(qapp):
    """构造 PanelWindow 并用调用计数替身替换 _refresh_* 方法。"""
    p = PanelWindow()
    calls = {"metrics": 0, "events": 0}
    p._refresh_metrics = lambda: calls.__setitem__("metrics", calls["metrics"] + 1)
    p._refresh_events = lambda: calls.__setitem__("events", calls["events"] + 1)
    p._test_calls = calls
    return p


def test_panel_sse_hello_dispatches_immediate_refresh(panel):
    panel.on_sse_event("hello", {"protocol": 1})
    assert panel._test_calls["metrics"] == 1
    assert panel._test_calls["events"] == 1
    assert not panel._refresh_metrics_timer.isActive()
    assert not panel._refresh_events_timer.isActive()


def test_panel_sse_metrics_changed_starts_metrics_timer(panel):
    panel.on_sse_event("metrics.changed", {"id": "cpu"})
    assert panel._refresh_metrics_timer.isActive()
    assert panel._test_calls["metrics"] == 0


def test_panel_sse_events_changed_starts_events_timer(panel):
    panel.on_sse_event("events.changed", {"reason": "insert", "id": 1})
    assert panel._refresh_events_timer.isActive()
    assert panel._test_calls["events"] == 0


def test_panel_sse_unknown_event_ignored(panel):
    panel.on_sse_event("something.else", {})
    assert not panel._refresh_metrics_timer.isActive()
    assert not panel._refresh_events_timer.isActive()
    assert panel._test_calls == {"metrics": 0, "events": 0}


def test_panel_on_connected_sets_status_green(panel):
    panel.on_connected()
    assert "connected" in panel.status.text()
    assert "#77ff77" in panel.status.styleSheet()


def test_panel_on_disconnected_sets_status_red(panel):
    panel.on_disconnected()
    assert "reconnecting" in panel.status.text()
    assert "#ff7777" in panel.status.styleSheet()


def test_panel_tab_default_is_chat(qapp):
    p = PanelWindow()
    assert p._current_tab_index == 2
    assert p._stack.currentIndex() == 2
    assert p._tabs[2].isChecked()
    assert not p._tabs[0].isChecked()
    assert not p._tabs[1].isChecked()
```

- [ ] **Step 7.7: 跑全量测试确认零回归**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手
bash test.sh
```

Expected: 全部通过，行覆盖 ≥85%，分支覆盖 ≥70%。原有的 Panel 测试现在通过 `panel.Panel` 别名（指向 PanelWindow）跑通。

- [ ] **Step 7.8: 提交**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手
git add desk-assistant/panel/panel_window.py desk-assistant/panel/main.py \
        desk-assistant/tests/test_main.py desk-assistant/tests/test_panel_window.py
git commit -m "refactor(panel): Panel 拆到 panel_window.py 重命名 PanelWindow，默认隐藏 + collapse 按钮"
```

---

## Task 8: PanelWindow show_animated + slide_in

**Files:**
- Modify: `desk-assistant/panel/panel_window.py`
- Modify: `desk-assistant/tests/test_panel_window.py`

- [ ] **Step 8.1: 写失败测试**

追加到 `desk-assistant/tests/test_panel_window.py`：

```python
def test_panel_show_animated_triggers_refresh(qapp, monkeypatch):
    """show_animated 触发一次 _refresh_metrics + _refresh_events（不等 debounce）。"""
    p = PanelWindow()
    calls = {"metrics": 0, "events": 0}
    p._refresh_metrics = lambda: calls.__setitem__("metrics", calls["metrics"] + 1)
    p._refresh_events = lambda: calls.__setitem__("events", calls["events"] + 1)
    monkeypatch.setattr(QtWidgets.QApplication, "primaryScreen", lambda self=None: type(
        "S", (), {"availableGeometry": lambda self: QtCore.QRect(0, 0, 1920, 1080)}
    )())
    p.show_animated()
    # 立即调用一次（不等 debounce timer）
    assert calls["metrics"] == 1
    assert calls["events"] == 1


def test_panel_show_animated_results_in_visible_and_on_screen(qapp, monkeypatch):
    """show_animated 完成后 panel 可见，pos 在屏幕内。"""
    class FakeScreen:
        def availableGeometry(self):
            return QtCore.QRect(0, 0, 1920, 1080)
    monkeypatch.setattr(QtWidgets.QApplication, "primaryScreen", lambda self=None: FakeScreen())
    p = PanelWindow()
    p.show_animated()
    # 等动画结束（200ms + buffer）
    QtCore.QCoreApplication.processEvents()
    QtCore.QTest.qWait(SLIDE_DURATION_MS + 100)
    QtCore.QCoreApplication.processEvents()
    assert p.isVisible()
    # x 应小于 1920（在屏内）
    assert p.x() < 1920
```

- [ ] **Step 8.2: 跑测试确认失败**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DESK_ASSISTANT_DB=state_test.db QT_QPA_PLATFORM=offscreen \
  /usr/bin/python3 -m pytest "tests/test_panel_window.py::test_panel_show_animated_triggers_refresh" "tests/test_panel_window.py::test_panel_show_animated_results_in_visible_and_on_screen" -v
```

Expected: FAIL，`AttributeError: 'PanelWindow' object has no attribute 'show_animated'`。

- [ ] **Step 8.3: 在 PanelWindow 类添加 show_animated + _slide_in**

在 `desk-assistant/panel/panel_window.py` 的 `PanelWindow` 类 `_on_collapse_clicked` 方法之后新增：

```python
    # ----- 滑入/滑出动画 -----

    def _cancel_anim_if_running(self):
        if self._anim is not None and self._anim.state() == QtCore.QPropertyAnimation.Running:
            self._anim.stop()
            try:
                self._anim.finished.disconnect(self.hide)
            except (TypeError, RuntimeError):
                pass

    def _slide_in(self):
        self._cancel_anim_if_running()
        screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
        if screen.width() <= 0 or screen.height() <= 0:
            log.warning("primary screen invalid, skip slide in")
            return
        final_x = screen.x() + screen.width() - self.width() - EDGE_MARGIN
        final_y = screen.y() + (screen.height() - self.height()) // 2
        off_screen_x = screen.x() + screen.width() + 1

        self.move(off_screen_x, final_y)
        self.show()
        self.raise_()
        self.activateWindow()

        self._anim = QtCore.QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(SLIDE_DURATION_MS)
        self._anim.setEasingCurve(SLIDE_EASING)
        self._anim.setStartValue(QtCore.QPoint(off_screen_x, final_y))
        self._anim.setEndValue(QtCore.QPoint(final_x, final_y))
        self._anim.start()

    def show_animated(self):
        """WindowManager 调用：强制刷新一次 + 滑入。"""
        self._refresh_metrics()
        self._refresh_events()
        self._slide_in()
```

- [ ] **Step 8.4: 跑测试确认通过**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DESK_ASSISTANT_DB=state_test.db QT_QPA_PLATFORM=offscreen \
  /usr/bin/python3 -m pytest tests/test_panel_window.py -v
```

Expected: 全部通过（包括 Task 7 加的所有测试）。

- [ ] **Step 8.5: 提交**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手
git add desk-assistant/panel/panel_window.py desk-assistant/tests/test_panel_window.py
git commit -m "feat(panel): PanelWindow.show_animated + _slide_in（200ms 从右滑入 + 强制刷新）"
```

---

## Task 9: PanelWindow slide_out + hide + 动画衔接

**Files:**
- Modify: `desk-assistant/panel/panel_window.py`
- Modify: `desk-assistant/tests/test_panel_window.py`

- [ ] **Step 9.1: 写失败测试**

追加到 `desk-assistant/tests/test_panel_window.py`：

```python
def test_panel_slide_out_then_hide(qapp, monkeypatch):
    """_slide_out 完成后（动画 200ms）panel 自动 hide()。"""
    class FakeScreen:
        def availableGeometry(self):
            return QtCore.QRect(0, 0, 1920, 1080)
    monkeypatch.setattr(QtWidgets.QApplication, "primaryScreen", lambda self=None: FakeScreen())
    p = PanelWindow()
    p.show()  # 先 show 才能 slide_out
    p._slide_out()
    # 等动画结束
    QtCore.QTest.qWait(SLIDE_DURATION_MS + 100)
    QtCore.QCoreApplication.processEvents()
    assert p.isHidden()


def test_panel_slide_in_then_slide_out_overlap_ends_hidden(qapp, monkeypatch):
    """slide_in 中调 slide_out 不会动画叠加，最终状态是隐藏。"""
    class FakeScreen:
        def availableGeometry(self):
            return QtCore.QRect(0, 0, 1920, 1080)
    monkeypatch.setattr(QtWidgets.QApplication, "primaryScreen", lambda self=None: FakeScreen())
    p = PanelWindow()
    p.show_animated()
    # 立刻调 slide_out（动画进行中）
    p._slide_out()
    QtCore.QTest.qWait(SLIDE_DURATION_MS + 100)
    QtCore.QCoreApplication.processEvents()
    assert p.isHidden()
```

- [ ] **Step 9.2: 跑测试确认失败**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DESK_ASSISTANT_DB=state_test.db QT_QPA_PLATFORM=offscreen \
  /usr/bin/python3 -m pytest "tests/test_panel_window.py::test_panel_slide_out_then_hide" "tests/test_panel_window.py::test_panel_slide_in_then_slide_out_overlap_ends_hidden" -v
```

Expected: FAIL，`AttributeError: '_slide_out'` 不存在。

- [ ] **Step 9.3: 添加 _slide_out 方法**

在 `desk-assistant/panel/panel_window.py` 的 `_slide_in` 方法之后新增：

```python
    def _slide_out(self):
        self._cancel_anim_if_running()
        screen = QtWidgets.QApplication.primaryScreen().availableGeometry()
        if screen.width() <= 0 or screen.height() <= 0:
            log.warning("primary screen invalid, skip slide out")
            self.hide()
            return
        current = self.pos()
        off_screen_x = screen.x() + screen.width() + 1

        self._anim = QtCore.QPropertyAnimation(self, b"pos", self)
        self._anim.setDuration(SLIDE_DURATION_MS)
        self._anim.setEasingCurve(SLIDE_EASING)
        self._anim.setStartValue(current)
        self._anim.setEndValue(QtCore.QPoint(off_screen_x, current.y()))
        self._anim.finished.connect(self.hide)
        self._anim.start()
```

- [ ] **Step 9.4: 跑测试确认通过**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DESK_ASSISTANT_DB=state_test.db QT_QPA_PLATFORM=offscreen \
  /usr/bin/python3 -m pytest tests/test_panel_window.py -v
```

Expected: 全部通过。

- [ ] **Step 9.5: 提交**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手
git add desk-assistant/panel/panel_window.py desk-assistant/tests/test_panel_window.py
git commit -m "feat(panel): PanelWindow._slide_out + 动画衔接（避免叠加）"
```

---

## Task 10: WindowManager 骨架 + SSEClient 单例化

**Files:**
- Create: `desk-assistant/panel/window_manager.py`
- Create: `desk-assistant/tests/test_window_manager.py`

- [ ] **Step 10.1: 写失败测试**

新建 `desk-assistant/tests/test_window_manager.py`：

```python
"""panel/window_manager.py 单元测试：拼装三部件 + SSEClient 单例。"""
import pytest
from PyQt5 import QtCore, QtWidgets

from panel.window_manager import WindowManager
from panel.panel_window import PanelWindow
from panel.strip import Strip


def test_window_manager_creates_strip_and_panel(qapp):
    """WindowManager 持有 strip + panel 实例。"""
    wm = WindowManager()
    assert isinstance(wm.strip, Strip)
    assert isinstance(wm.panel, PanelWindow)


def test_window_manager_panel_starts_hidden(qapp):
    """PanelWindow 构造后 isHidden（不在 WindowManager 里临时 show）。"""
    wm = WindowManager()
    assert wm.panel.isHidden()


def test_window_manager_strip_is_visible(qapp, monkeypatch):
    """Strip 在 WindowManager 里被 show。"""
    class FakeScreen:
        def availableGeometry(self):
            return QtCore.QRect(0, 0, 1920, 1080)
    monkeypatch.setattr(QtWidgets.QApplication, "primaryScreen", lambda self=None: FakeScreen())
    wm = WindowManager()
    assert wm.strip.isVisible()


def test_window_manager_sse_client_singleton(qapp, monkeypatch):
    """SSEClient 只 new 一次（被 strip + panel 共享引用）。"""
    from panel import window_manager as wm_mod
    constructed = {"count": 0}
    real_sse = wm_mod.SSEClient

    class CountingSSE(real_sse):
        def __init__(self, *a, **kw):
            constructed["count"] += 1
            super().__init__(*a, **kw)

    monkeypatch.setattr(wm_mod, "SSEClient", CountingSSE)
    wm = WindowManager()
    # strip 和 panel 拿到的是同一个 sse 实例引用
    assert wm._sse is wm._sse_reference  # 见实现
    assert constructed["count"] == 1
```

- [ ] **Step 10.2: 跑测试确认失败**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DESK_ASSISTANT_DB=state_test.db QT_QPA_PLATFORM=offscreen \
  /usr/bin/python3 -m pytest tests/test_window_manager.py -v
```

Expected: FAIL，`ModuleNotFoundError: No module named 'panel.window_manager'`。

- [ ] **Step 10.3: 实现 WindowManager 骨架**

新建 `desk-assistant/panel/window_manager.py`：

```python
"""panel/window_manager.py — 桌面助手三部件拼装器。

架构：
  - 持有 SSEClient（单例）
  - 创建 Strip + PanelWindow + HotZoneWatcher
  - 连接信号：strip.show_requested → panel.show_animated
              hotzone.hover_right_edge → panel.show_animated
              panel.collapse_requested → panel._slide_out
              sse.connected → strip.on_connected + panel.on_connected
              sse.disconnected → strip.on_disconnected + panel.on_disconnected
  - 监听 QScreen.geometryChanged → strip + panel 重新定位
  - SSEClient.start() 由 WindowManager 触发（所有者）
"""
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from PyQt5 import QtCore, QtWidgets  # noqa: E402

from hotzone import HotZoneWatcher  # noqa: E402
from panel_window import PanelWindow  # noqa: E402
from strip import Strip  # noqa: E402

# 复用 main.py 现有 SSEClient（不重新实现）
from main import SSEClient, SSE_URL  # noqa: E402

log = logging.getLogger("panel.manager")


class WindowManager(QtCore.QObject):
    """三部件 + SSEClient 拼装器。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        # 单例 SSEClient
        self._sse = SSEClient(SSE_URL)
        self._sse_reference = self._sse  # 仅供 test 断言引用相等

        # 三部件
        self.strip = Strip()
        self.panel = PanelWindow()
        self.hotzone = HotZoneWatcher()

        # Strip 永远显示；Panel 默认隐藏
        self.strip.show()

        # 监听屏分辨率变化
        screen = QtWidgets.QApplication.primaryScreen()
        if screen is not None:
            screen.geometryChanged.connect(self._on_screen_changed)

        # 信号连接
        self.strip.show_requested.connect(self.panel.show_animated)
        self.hotzone.hover_right_edge.connect(self.panel.show_animated)
        self.panel.collapse_requested.connect(self.panel._slide_out)
        self._sse.connected.connect(self.strip.on_connected)
        self._sse.connected.connect(self.panel.on_connected)
        self._sse.disconnected.connect(self.strip.on_disconnected)
        self._sse.disconnected.connect(self.panel.on_disconnected)
        self._sse.sse_event.connect(self.panel.on_sse_event)

        # SSE 启动（所有者）
        self._sse.start()

    def _on_screen_changed(self, _geo):
        self.strip._reposition_to_right_edge()
        if self.panel.isVisible():
            self.panel._reposition_to_right_edge()
```

- [ ] **Step 10.4: 跑测试确认通过**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DESK_ASSISTANT_DB=state_test.db QT_QPA_PLATFORM=offscreen \
  /usr/bin/python3 -m pytest tests/test_window_manager.py -v
```

Expected: 4 passed。

- [ ] **Step 10.5: 提交**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手
git add desk-assistant/panel/window_manager.py desk-assistant/tests/test_window_manager.py
git commit -m "feat(panel): WindowManager 拼装三部件 + SSEClient 单例化"
```

---

## Task 11: WindowManager 信号连接详细测试 + screen geometryChanged

**Files:**
- Modify: `desk-assistant/tests/test_window_manager.py`

- [ ] **Step 11.1: 追加信号连接详细测试**

追加到 `desk-assistant/tests/test_window_manager.py`：

```python
def test_window_manager_strip_show_requested_triggers_panel(qapp, monkeypatch):
    """strip.show_requested → panel.show_animated 被调。"""
    class FakeScreen:
        def availableGeometry(self):
            return QtCore.QRect(0, 0, 1920, 1080)
    monkeypatch.setattr(QtWidgets.QApplication, "primaryScreen", lambda self=None: FakeScreen())
    wm = WindowManager()
    called = {"show": 0}
    wm.panel.show_animated = lambda: called.__setitem__("show", called["show"] + 1)
    wm.strip.show_requested.emit()
    assert called["show"] == 1


def test_window_manager_hotzone_triggers_panel(qapp, monkeypatch):
    """hotzone.hover_right_edge → panel.show_animated 被调。"""
    class FakeScreen:
        def availableGeometry(self):
            return QtCore.QRect(0, 0, 1920, 1080)
    monkeypatch.setattr(QtWidgets.QApplication, "primaryScreen", lambda self=None: FakeScreen())
    wm = WindowManager()
    called = {"show": 0}
    wm.panel.show_animated = lambda: called.__setitem__("show", called["show"] + 1)
    wm.hotzone.hover_right_edge.emit()
    assert called["show"] == 1


def test_window_manager_panel_collapse_triggers_slide_out(qapp, monkeypatch):
    """panel.collapse_requested → panel._slide_out 被调。"""
    class FakeScreen:
        def availableGeometry(self):
            return QtCore.QRect(0, 0, 1920, 1080)
    monkeypatch.setattr(QtWidgets.QApplication, "primaryScreen", lambda self=None: FakeScreen())
    wm = WindowManager()
    called = {"slide": 0}
    wm.panel._slide_out = lambda: called.__setitem__("slide", called["slide"] + 1)
    wm.panel.collapse_requested.emit()
    assert called["slide"] == 1


def test_window_manager_sse_connected_propagates_to_strip_and_panel(qapp):
    """sse.connected → strip.on_connected + panel.on_connected 都被调。"""
    wm = WindowManager()
    strip_called = {"c": 0}
    panel_called = {"c": 0}
    wm.strip.on_connected = lambda: strip_called.__setitem__("c", strip_called["c"] + 1)
    wm.panel.on_connected = lambda: panel_called.__setitem__("c", panel_called["c"] + 1)
    wm._sse.connected.emit()
    assert strip_called["c"] == 1
    assert panel_called["c"] == 1


def test_window_manager_screen_change_repositions_strip(qapp, monkeypatch):
    """geometryChanged → strip 重新定位（Panel 隐藏时不调）。"""
    class FakeScreen:
        def availableGeometry(self):
            return QtCore.QRect(0, 0, 1920, 1080)
    monkeypatch.setattr(QtWidgets.QApplication, "primaryScreen", lambda self=None: FakeScreen())
    wm = WindowManager()
    # 把 _reposition 替成计数
    strip_called = {"c": 0}
    panel_called = {"c": 0}
    wm.strip._reposition_to_right_edge = lambda: strip_called.__setitem__("c", strip_called["c"] + 1)
    wm.panel._reposition_to_right_edge = lambda: panel_called.__setitem__("c", panel_called["c"] + 1)
    wm._on_screen_changed(None)
    assert strip_called["c"] == 1
    assert panel_called["c"] == 0  # panel 隐藏时不调
```

- [ ] **Step 11.2: 跑测试确认通过**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DESK_ASSISTANT_DB=state_test.db QT_QPA_PLATFORM=offscreen \
  /usr/bin/python3 -m pytest tests/test_window_manager.py -v
```

Expected: 9 passed。

- [ ] **Step 11.3: 提交**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手
git add desk-assistant/tests/test_window_manager.py
git commit -m "test(panel): WindowManager 信号连接 + 屏变化重定位测试"
```

---

## Task 12: main.py 缩成启动壳子

**Files:**
- Modify: `desk-assistant/panel/main.py`

- [ ] **Step 12.1: 重写 main.py**

整文件替换 `desk-assistant/panel/main.py`：

```python
"""panel/main.py — 桌面助手启动壳子（v3 Edge Dock）。

构造 WindowManager（拼装 Strip + PanelWindow + HotZoneWatcher + SSEClient），
启动 QApplication 进入事件循环。

启动：
  1. 先起 server：python3 server/app.py
  2. 再起看板：DISPLAY=:0 /usr/bin/python3 panel/main.py
"""
import logging
import sys
from pathlib import Path

# 把 panel/ 加入 sys.path 以便导入同目录的 *_card / *_window 模块
sys.path.insert(0, str(Path(__file__).resolve().parent))

from PyQt5 import QtNetwork, QtWidgets  # noqa: E402

from window_manager import WindowManager  # noqa: E402

# panel 启动时统一 logging 配置：launcher 已把 stderr 重定向到 panel.log
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("panel")


def main():
    app = QtWidgets.QApplication(sys.argv)
    # 关掉 Qt 系统代理读取：panel 只连内网/本机（127.0.0.1:18675/18789、10.90.30.228:22004），
    # shell 的 http_proxy 会让 Qt 把内网请求发到外网代理导致 RemoteHostClosed。
    QtNetwork.QNetworkProxyFactory.setUseSystemConfiguration(False)

    manager = WindowManager()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
```

- [ ] **Step 12.2: 验证 main.py 可正常 import**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DESK_ASSISTANT_DB=state_test.db QT_QPA_PLATFORM=offscreen \
  /usr/bin/python3 -c "import panel.main; print('import ok')"
```

Expected: 输出 `import ok`，无错误。

- [ ] **Step 12.3: 跑全量测试**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手
bash test.sh
```

Expected: 全部通过，覆盖率 ≥85% / ≥70%。**注意**：如果覆盖率下降，可能是新增代码没被覆盖，回去看 WindowManager 是否都被引用到了。

- [ ] **Step 12.4: 提交**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手
git add desk-assistant/panel/main.py
git commit -m "refactor(panel): main.py 缩成启动壳子，构造 WindowManager 后 exec_"
```

---

## Task 13: 端到端集成测试（手工 + 全量 test.sh）

**Files:**
- Modify: `desk-assistant/tests/test_window_manager.py`（追加集成场景）

- [ ] **Step 13.1: 追加集成测试**

追加到 `desk-assistant/tests/test_window_manager.py`：

```python
def test_window_manager_full_flow_collapse_after_show(qapp, monkeypatch):
    """完整流程：show_animated → panel 可见 → collapse_requested → panel 隐藏。"""
    class FakeScreen:
        def availableGeometry(self):
            return QtCore.QRect(0, 0, 1920, 1080)
    monkeypatch.setattr(QtWidgets.QApplication, "primaryScreen", lambda self=None: FakeScreen())
    wm = WindowManager()
    # 模拟 Strip 点击 → panel.show_animated
    wm.panel.show_animated()
    QtCore.QTest.qWait(SLIDE_DURATION_MS + 100)
    QtCore.QCoreApplication.processEvents()
    assert wm.panel.isVisible()
    # 模拟 ◀ 点击 → panel._slide_out
    wm.panel.collapse_requested.emit()
    QtCore.QTest.qWait(SLIDE_DURATION_MS + 100)
    QtCore.QCoreApplication.processEvents()
    assert wm.panel.isHidden()
```

- [ ] **Step 13.2: 跑测试确认通过**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DESK_ASSISTANT_DB=state_test.db QT_QPA_PLATFORM=offscreen \
  /usr/bin/python3 -m pytest tests/test_window_manager.py::test_window_manager_full_flow_collapse_after_show -v
```

Expected: PASS。

- [ ] **Step 13.3: 跑全量 test.sh**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手
bash test.sh
```

Expected:
- 全部 pytest 用例通过
- 行覆盖率 ≥ 85%
- 分支覆盖率 ≥ 70%
- 最终输出 `✓ OK  通过`

- [ ] **Step 13.4: 提交**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手
git add desk-assistant/tests/test_window_manager.py
git commit -m "test(panel): 端到端集成测试（show → collapse 完整流程）"
```

---

## Task 14: 真机手动验收

**Files:** 无（手动验证）

- [ ] **Step 14.1: 启动 server**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
/usr/bin/python3 server/app.py &
SERVER_PID=$!
sleep 2
echo "server pid: $SERVER_PID"
```

- [ ] **Step 14.2: 启动 panel**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant
DISPLAY=:0 /usr/bin/python3 panel/main.py &
PANEL_PID=$!
echo "panel pid: $PANEL_PID"
```

Expected: 看到屏幕右边出现一个 37×75 的窄条，垂直居中，带 📊 图标和红色状态点。

- [ ] **Step 14.3: 验收清单**

- [ ] 启动只看到窄条（没有完整面板）
- [ ] 鼠标贴右 6-8px → 面板从右滑入
- [ ] 点窄条 → 面板滑入
- [ ] 面板左侧 ◀ → 面板滑出
- [ ] 面板右上 ✕ → app 退出
- [ ] SSE 断 → 状态点变红（停 server 验证）
- [ ] SSE 重连 → 状态点变绿（重启 server 验证）
- [ ] 拖窄条到副屏 → 跟着过去

每项不通过就回头排查，记录到 commit 前的「已知问题」。

- [ ] **Step 14.4: 清理**

```bash
kill $PANEL_PID $SERVER_PID 2>/dev/null
```

---

## Task 15: README + project.md 同步

**Files:**
- Modify: `/home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手/desk-assistant/README.md`
- Modify: `/home/10312862@zte.intra/.pkm/20_Project/P_20260422_桌面助手/project.md`（如存在）

- [ ] **Step 15.1: 更新 README.md**

在 README.md 的「文件结构」section 里，把 `panel/main.py` 描述改为「启动壳子」，并新增 `panel_window.py`、`strip.py`、`hotzone.py`、`window_manager.py` 四个新文件的描述。同时新增一段说明：

```markdown
## Edge Dock（v3）

启动后只看到右边缘一个 37×75 的窄条；鼠标贴右 6-8px 热区或点窄条可唤起完整面板；
面板左侧 ◀ 收起，右侧 ✕ 退出 app。三部件（Strip / PanelWindow / HotZoneWatcher）由
`window_manager.py` 拼装，共享同一个 SSEClient。
```

- [ ] **Step 15.2: 更新 project.md**

在 project.md 的「文件结构」code block 里同步 panel/ 目录的最新文件清单；在「关键决策」section 追加：

```
- **v3 Edge Dock（2026-06）**：把 Panel 从单窗口常驻拆成 Strip+PanelWindow 双窗口；Panel 默认隐藏，靠 QPropertyAnimation 从右滑入；新增 HotZoneWatcher 50ms 轮询鼠标
```

- [ ] **Step 15.3: 提交**

```bash
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手
git add desk-assistant/README.md project.md
git commit -m "docs: README + project.md 同步 v3 Edge Dock 架构"
```

---

## 验收门槛

```bash
# 全量测试 + 覆盖率
cd /home/10312862@zte.intra/.pkm/20_Projects/P_20260422_桌面助手
bash test.sh

# 真机手测（DISPLAY=:0）
DISPLAY=:0 /usr/bin/python3 desk-assistant/panel/main.py
```

预期：
- [ ] test.sh 输出 `✓ OK  通过`，行覆盖 ≥85%，分支覆盖 ≥70%
- [ ] 真机：窄条默认显示；悬停/点击展开；◀ 收起；✕ 退出
- [ ] git log 干净：15 个 commit，每个聚焦一个 task

---

## 后续（明确不在 v3 范围）

- 多屏独立贴条（每屏一条）
- 启动状态持久化（记忆上次展开/收起）
- 智能延迟收起（hover out 后等 1s 再收）
- 圆形悬浮球变体

这些写入 `docs/superpowers/specs/2026-06-13-right-edge-dock-design.md` 的 Future Work 段，作为 v4 候选。