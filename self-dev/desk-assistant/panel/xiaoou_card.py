"""panel/xiaoou_card.py — 小欧（igptproxy）iGPT 协议 chat 卡片。"""
import logging
import uuid
from urllib.parse import quote

from PyQt5 import QtCore, QtGui, QtWidgets

try:
    from base_chat_card import BaseChatCard  # 直接运行：panel/ 在 sys.path
except ImportError:
    from panel.base_chat_card import BaseChatCard  # pytest：项目根在 sys.path

log = logging.getLogger(__name__)


class XiaoouCard(BaseChatCard):
    """小欧 chat 卡片，对接 igptproxy（iGPT 私有协议）。

    入站协议（iGPT）：
      POST /
      Headers: X-Emp-No: <工号>  (本类用 _auth_header 配置)
      Body: {chatUuid, topicId, source, keep, stream, text, model, ...}
      SSE: data: {"chatUuid":..., "finishReason":..., "result": "<增量>"}

    用法：
        card = XiaoouCard(
            base_url="http://10.90.30.228:22004",
            model="R-T-2-sun1-MiniMax-M2.7-highspeed",
            topic_id=1001,
            source="desk-assistant",
            auth_header=(b"X-Emp-No", b"10312862"),
        )
    """

    def __init__(self, base_url, model, topic_id, source, auth_header, web_ui_base=None, parent=None):
        self._model = model
        self._topic_id = topic_id
        self._source = source
        self._auth_header = auth_header
        self._chat_uuid = str(uuid.uuid4())
        self._web_ui_base = web_ui_base or "http://10.90.30.228:18789"
        super().__init__(base_url, parent)
        # 小欧不需要 token 注入：启用输入框
        self._input.setEnabled(True)
        # 在基类"新会话"按钮旁追加一个"打开 web UI"按钮
        self._append_open_chat_button()

    # ----- BaseChatCard 虚方法实现 -----

    def _title_text(self):
        return "对话 / 小欧"

    # ----- 打开 web UI 按钮（复用 ChatCard 的样式） -----

    def _append_open_chat_button(self):
        outer = self.layout()
        input_row = outer.itemAt(outer.count() - 1).layout()
        self._open_chat_btn = QtWidgets.QPushButton("↗")
        self._open_chat_btn.setObjectName("GlassBtn")
        self._open_chat_btn.setFixedSize(34, 30)
        self._open_chat_btn.setCursor(QtCore.Qt.PointingHandCursor)
        self._open_chat_btn.setToolTip("在浏览器打开本 session 完整对话")
        self._open_chat_btn.clicked.connect(self._on_open_chat)
        input_row.addWidget(self._open_chat_btn)

    def _on_open_chat(self):
        session = "agent:main:openai:{}@topic:{}".format(self._chat_uuid, self._topic_id)
        url = "{}/chat?session={}".format(self._web_ui_base, quote(session, safe=""))
        log.info("xiaoou: open web UI: %s", url)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl(url))

    def _input_placeholder(self):
        return "发送给 小欧（Enter 发送）…"

    def _build_request_body(self, text):
        return {
            "chatUuid": self._chat_uuid,
            "topicId": self._topic_id,
            "source": self._source,
            "keep": True,
            "stream": True,
            "text": text,
            "model": self._model,
        }

    def _parse_sse_frame(self, data):
        # 业务错误：SSE 帧可能带 code.code != "0000"
        code = data.get("code")
        if isinstance(code, dict):
            code_val = code.get("code")
            if code_val and code_val != "0000":
                self._last_biz_error = code.get("msg", "未知错误")
        # 安全拦截：result 含"检测到高危指令"
        result = data.get("result") or ""
        if "检测到高危指令" in result or "安全策略拦截" in result:
            self._safety_blocked = True
        return result if result else None

    def _auth_headers(self):
        return [self._auth_header]

    def _format_error(self, err, status, body):
        """状态码后接 body 前 200 字符（小欧错误消息常在 body）。"""
        body_str = body.decode("utf-8", errors="replace")[:200]
        if status:
            return "✕ error: status=%s %s" % (status, body_str)
        return "✕ error: %s" % body_str

    # ----- "新会话" hook：topicId 递增 + 换 chatUuid + 清 flag -----

    def _reset_session(self):
        old_topic = self._topic_id
        self._topic_id += 1
        self._chat_uuid = str(uuid.uuid4())
        self._last_biz_error = None
        self._safety_blocked = False
        log.info("xiaoou: new session: topic_id %s → %s, chatUuid=%s",
                 old_topic, self._topic_id, self._chat_uuid)
