"""panel/chat_card.py — OpenClaw 协议 chat 卡片（继承 BaseChatCard）。"""
import logging

from PyQt5 import QtCore, QtGui, QtWidgets

try:
    from base_chat_card import BaseChatCard  # 直接运行：panel/ 在 sys.path
except ImportError:
    from panel.base_chat_card import BaseChatCard  # pytest：项目根在 sys.path

log = logging.getLogger(__name__)


class ChatCard(BaseChatCard):
    """OpenClaw 协议 chat 卡片。

    用法：
        card = ChatCard(
            openclaw_url="http://127.0.0.1:18789/v1/chat/completions",
            model="openclaw",
            session_key="agent:main:openai:...@topic:...",
            chat_url="http://127.0.0.1:18789/chat?lang=zh-CN&session=...",
        )
        card.set_token("4b54...")  # 没 token 输入框禁用
    """

    def __init__(self, openclaw_url, model, session_key, chat_url, parent=None):
        self._model = model
        self._session_key = session_key
        self._chat_url = chat_url
        self._token = None
        super().__init__(openclaw_url, parent)
        # 在基类默认的"新对话"按钮旁边追加一个"打开 web UI"按钮
        self._append_open_chat_button()

    def _append_open_chat_button(self):
        """基类默认放一个'新对话'按钮；这里追加一个'打开 web UI'按钮（v3.2 走全局 QSS）。"""
        outer = self.layout()
        input_row = outer.itemAt(outer.count() - 1).layout()
        self._open_chat_btn = QtWidgets.QPushButton("↗")
        self._open_chat_btn.setObjectName("GlassBtn")
        self._open_chat_btn.setFixedSize(34, 30)
        self._open_chat_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._open_chat_btn.setToolTip("在浏览器打开本 session 完整对话")
        self._open_chat_btn.clicked.connect(self._on_open_chat)
        input_row.addWidget(self._open_chat_btn)

    # ----- BaseChatCard 虚方法实现 -----

    def _title_text(self):
        return "对话 / OPENCLAW"

    def _input_placeholder(self):
        return "发送给 openclaw（Enter 发送）…"

    def _build_request_body(self, text):
        return {
            "model": self._model,
            "messages": [{"role": "user", "content": text}],
            "stream": True,
        }

    def _parse_sse_frame(self, data):
        return data.get("choices", [{}])[0].get("delta", {}).get("content")

    def _auth_headers(self):
        return [
            (b"Authorization", f"Bearer {self._token}".encode()),
            (b"x-openclaw-session-key", self._session_key.encode()),
        ]

    # ----- 旧 API：set_token -----

    def set_token(self, token):
        """启动后从配置读取的 token，传入后启用输入框。"""
        self._token = token
        if token:
            self._input.setEnabled(True)
            self._input.setPlaceholderText(self._input_placeholder())
        else:
            self._input.setEnabled(False)
            self._input.setPlaceholderText(
                "未找到 openclaw token（~/.openclaw/openclaw.json）"
            )

    # ----- 旧 API：打开 web UI -----

    def _on_open_chat(self):
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(self._chat_url))
