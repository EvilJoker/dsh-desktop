"""panel/main.py — 桌面助手启动壳子。

构造 WindowManager（拼装 Strip + PanelWindow + SSEClient），启动 QApplication
进入事件循环。

启动：
  1. 先起 server：python3 server/app.py
  2. 再起看板：DISPLAY=:0 /usr/bin/python3 panel/main.py
"""
import logging
import sys
from pathlib import Path

# 把 panel/ 父目录加进 sys.path，让 `from panel.window_manager import ...`
# 这种包式绝对导入能找到顶层 `panel` 包。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt5 import QtCore, QtNetwork, QtWidgets  # noqa: E402

from panel.theme import GLOBAL_QSS  # noqa: E402
from panel.window_manager import WindowManager  # noqa: E402

# panel 启动时统一 logging 配置：launcher 已把 stderr 重定向到 panel.log
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("panel.main")


def main():
    log.info("panel main() entered, argv=%r, pid=%d", sys.argv, os.getpid())
    app = QtWidgets.QApplication(sys.argv)
    # v3.2 样式大改：先注入全局 QSS（设计 token + 玻璃拟态）
    app.setStyleSheet(GLOBAL_QSS)
    log.info("global QSS applied (len=%d)", len(GLOBAL_QSS))
    log.info("QApplication created, primaryScreen=%r",
             QtWidgets.QApplication.primaryScreen())
    log.info("QApplication.applicationFilePath=%r", app.applicationFilePath())
    # 关掉 Qt 系统代理读取：panel 只连内网/本机（127.0.0.1:18675/18789、10.90.30.228:22004），
    # shell 的 http_proxy 会让 Qt 把内网请求发到外网代理导致 RemoteHostClosed。
    QtNetwork.QNetworkProxyFactory.setUseSystemConfiguration(False)
    log.info("setUseSystemConfiguration(False) done")
    wm = WindowManager()
    log.info("WindowManager constructed: strip winId=0x%x visible=%s, panel winId=0x%x visible=%s",
             int(wm.strip.winId()), wm.strip.isVisible(),
             int(wm.panel.winId()), wm.panel.isVisible())
    # 注意：不要 processEvents()。Qt 5.12 + xcb + fcitx/搜狗 XIM 下，exec_()
    # 开始前提前 pump 事件会让 XIM 提前 attach 到不稳定的窗口，导致后续用户点
    # chat 输入框时搜狗切英文、中文进不来。直接进 exec_() 让事件循环自然处理。
    sys.exit(app.exec_())


import os  # noqa: E402

if __name__ == "__main__":
    main()