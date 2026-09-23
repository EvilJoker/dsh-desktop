"""panel/global_shortcut.py — Nde 桌面全局快捷键。

Nde 桌面（NewStartOS / 统信 UOS）全局快捷键走 nde-globalkeysd
（org.nde.global_key_shortcuts /daemon）的 addMethodAction：
  1. 客户端先 publish 一个 dbus object（path + interface + method）
  2. 调 addMethodAction(shortcut, bus, path, iface, method, description)
  3. 用户按快捷键时 nde-globalkeysd 主动 call 那个 method
  4. method 在我们进程的 GLib MainLoop 里执行（pydbus 把 dbus
     派发复用 GLib 主循环，与 Qt 事件循环互通），直接 emit Qt 信号

为什么不用 KGlobalAccel：
  本机 dde-kwin（Deepin fork）下，KGlobalAccel 接口虽然暴露
  （kglobalaccel5 进程在跑），但 setForeignShortcut / setShortcut 调
  用回读 = []，从不触发外部 component 的 activate —— 是个 stub。

为什么不用 XGrabKey：
  KWin grab-all 模式独占所有键组合，XGrabKey 永远返回 AlreadyGrabbed。

设计：
  - 类名 NdeGlobalShortcut 直白反映只支持 Nde
  - nde-globalkeysd 不存在时（其他桌面）graceful 退化：不抛异常，
    log warning，window_manager 仍可工作，只是少了全局快捷键
  - 客户端 object 用 pydbus publish，nde 通过 well-known bus 找我们
  - 清理：连 QApplication.aboutToQuit + SIGTERM/SIGINT + atexit，
    主动 removeAction 防注册残留（__del__ 不可靠：cyclic ref + 解释
    器关闭时不一定调到，所以用三层显式 hook）

依赖：
  - pydbus（系统装好的 0.6.0）
  - PyQt5.QtCore
"""
import atexit
import logging
import signal

from PyQt5 import QtCore
from pydbus import SessionBus

log = logging.getLogger("panel.shortcut")

# nde-globalkeysd 服务的标准名字
NDE_DAEMON_BUS = "org.nde.global_key_shortcuts"
NDE_DAEMON_PATH = "/daemon"

# 我们暴露给 nde 的接口名（well-known，nde-globalkeysd 通过它 call 我们）
SHORTCUT_IFACE = "org.deskassistant.GlobalShortcut"
# nde 按下快捷键时调用的方法名
TRIGGER_METHOD = "Trigger"


class _ShortcutClient(object):
    """pydbus-published 对象，nde-globalkeysd 在按下时 call Trigger()。

    必须用 pydbus publish（不是简单继承 QObject），因为 dbus call
    通过 GLib MainLoop 派发，需要 pydbus 的 XML 接口描述做 introspection。
    """
    dbus = """
    <node>
      <interface name="org.deskassistant.GlobalShortcut">
        <method name="Trigger"/>
      </interface>
    </node>
    """

    def __init__(self, activated_signal):
        self._activated = activated_signal

    def Trigger(self):
        log.info("nde triggered global shortcut → emitting activated")
        self._activated.emit()


class NdeGlobalShortcut(QtCore.QObject):
    """注册一个 Nde 全局快捷键，按下时 emit activated。

    Usage:
        shortcut = NdeGlobalShortcut(
            shortcut_str="Alt+M",
            bus_name="org.deskassistant.panel",
            object_path="/deskassistant/shortcut",
            description="Toggle desk-assistant panel",
            parent=app,
        )
        shortcut.activated.connect(on_toggle)
        # 进程退出时自动清理（aboutToQuit + SIGTERM/SIGINT）

    约束：
      - 仅 Nde 桌面（带 nde-globalkeysd）可用
      - nde-globalkeysd 不存在时静默跳过，不抛异常
    """

    activated = QtCore.pyqtSignal()

    def __init__(self, shortcut_str, bus_name, object_path,
                 description, parent=None):
        super().__init__(parent)
        self._shortcut_str = shortcut_str
        self._bus_name = bus_name
        self._object_path = object_path
        self._action_id = None
        self._registered = False
        self._released = False
        self._publication = None
        # SIGTERM/SIGINT 标志位：signal handler 只 set，不调 Qt/pydbus
        # （async-signal-safe 约束：handler 里只能 set flag + write）
        self._shutdown_requested = False
        # 内部 client object —— nde call 的就是这个的 Trigger
        self._client = _ShortcutClient(self.activated)

        try:
            bus = SessionBus()
        except Exception as e:
            log.warning("SessionBus unavailable: %s: %s — global shortcut disabled",
                        type(e).__name__, e)
            return

        # 1. publish client object
        try:
            self._publication = bus.publish(
                bus_name, (object_path, self._client),
            )
            log.info("published client: bus=%s path=%s", bus_name, object_path)
        except Exception as e:
            log.warning("publish client failed: %s: %s — global shortcut disabled",
                        type(e).__name__, e)
            return

        # 2. connect to nde daemon
        try:
            nde = bus.get(NDE_DAEMON_BUS, NDE_DAEMON_PATH)
        except Exception as e:
            log.warning("nde-globalkeysd unavailable: %s: %s — global shortcut disabled",
                        type(e).__name__, e)
            self._unpublish_only()  # bus.publish 已成功，避免 client 残留
            return

        # 3. addMethodAction: 注册快捷键 → nde 收到时 call 我们的 Trigger
        try:
            used_shortcut, action_id = nde.addMethodAction(
                shortcut_str,
                bus_name,
                object_path,
                SHORTCUT_IFACE,
                TRIGGER_METHOD,
                description,
            )
            self._action_id = action_id
            self._registered = True
            log.info(
                "global shortcut registered: %r → %s.%s (id=%d)",
                used_shortcut, SHORTCUT_IFACE, TRIGGER_METHOD, action_id,
            )
        except Exception as e:
            log.warning("addMethodAction FAIL: %s: %s — global shortcut disabled",
                        type(e).__name__, e)
            self._unpublish_only()  # 同上，unpublish client
            return

        # 4. 注册清理 hook：三层兜底
        #
        # 路径 A：aboutToQuit —— 主循环正常退出（用户点 X、QApplication.quit()）
        # 路径 B：QTimer 轮询 flag —— SIGTERM/SIGINT 触发
        #   signal handler 只 set flag（async-signal-safe 约束），
        #   QTimer 在主线程里检测到后调 QApplication.quit() 走路径 A
        # 路径 C：atexit —— 解释器正常退出兜底（覆盖 sys.exit / 未捕获异常）
        #
        # __del__ 不可靠（cyclic ref + 解释器关闭顺序），用显式 hook
        app = QtCore.QCoreApplication.instance()
        if app is not None:
            app.aboutToQuit.connect(self.release)
            # QTimer 200ms 间隔：信号延迟可接受，开销可忽略
            self._poll_timer = QtCore.QTimer(self)
            self._poll_timer.setInterval(200)
            self._poll_timer.timeout.connect(self._check_shutdown_flag)
            self._poll_timer.start()
        # SIGTERM/SIGINT：handler 只 set flag，不调 Qt 不调 pydbus
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                prev = signal.signal(sig, self._on_signal)
                if prev == signal.SIG_DFL or prev == signal.SIG_IGN:
                    # 之前没人装，prev 反映的是 OS 默认；这次成功接管
                    pass
                else:
                    # 之前有别的 handler 装着（Qt 可能装过 C-level handler），
                    # Python 的 signal.signal() 仍能盖掉它，但记下来方便排查
                    log.info("signal %d had prior handler %r, replaced with our _on_signal",
                             sig, prev)
            except (ValueError, OSError) as e:
                # ValueError: not main thread; OSError: signal already used by C lib
                log.warning("signal.signal(%d) failed: %s: %s — SIGTERM/SIGINT path broken",
                            sig, type(e).__name__, e)
        # atexit 兜底：Python 解释器正常退出时调，覆盖 sys.exit/未捕获异常路径
        atexit.register(self.release)

    def _on_signal(self, signum, _frame):
        """SIGTERM/SIGINT 处理：只 set flag，QTimer 在主线程里检测。

        不能在 signal handler 里调 Qt/pydbus（async-signal-unsafe，可能 hang/crash）。
        旧版本直接调 release() 后 os.kill 自己，会导致进程不死不活。
        """
        log.info("received signal %d, requesting shutdown via flag", signum)
        self._shutdown_requested = True

    def _check_shutdown_flag(self):
        """QTimer 回调（主线程）：flag set 后调 QApplication.quit()。

        quit() 会让 app.exec_() 返回 → 走 aboutToQuit → 走 release。
        停掉 timer 避免重复触发（虽然 flag 不会重置，但保险起见）。
        """
        if self._shutdown_requested:
            log.info("shutdown flag detected, calling QApplication.quit()")
            self._poll_timer.stop()
            QtCore.QCoreApplication.quit()

    def is_registered(self):
        """快捷键是否成功注册。WindowManager 据此决定要不要连 _toggle_panel。"""
        return self._registered

    def _unpublish_only(self):
        """只 unpublish client（不调 nde removeAction，因为 addMethodAction 还没成功）。

        用于 __init__ 失败路径：publish 成功但 nde 不可用 / addMethodAction 失败时
        防止 GIO Publication 残留。
        """
        if self._publication is not None:
            try:
                self._publication.unpublish()
            except Exception as e:
                log.warning("unpublish-on-fail failed: %s", e)
            self._publication = None

    def release(self):
        """主动释放：nde 注销快捷键 + unpublish 客户端。"""
        if self._released:
            return
        self._released = True
        if self._registered and self._action_id is not None:
            try:
                bus = SessionBus()
                nde = bus.get(NDE_DAEMON_BUS, NDE_DAEMON_PATH)
                ok = nde.removeAction(self._action_id)
                log.info("global shortcut removed: id=%d ok=%s",
                         self._action_id, ok)
            except Exception as e:
                log.warning("removeAction FAIL: %s", e)
            self._registered = False
            self._action_id = None
        if self._publication is not None:
            try:
                self._publication.unpublish()
            except Exception as e:
                log.warning("unpublish failed: %s", e)
            self._publication = None
        # 停掉 QTimer 防止它在 release 后还在跳（虽然 _shutdown_requested 不会再 set）
        # atexit 在解释器关闭时跑，QApplication 已死 → QTimer C++ 析构 → RuntimeError
        if getattr(self, "_poll_timer", None) is not None:
            try:
                self._poll_timer.stop()
            except RuntimeError:
                pass  # C++ object 已析构，无所谓
