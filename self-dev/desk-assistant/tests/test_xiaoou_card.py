"""panel/xiaoou_card.py 单元测试：覆盖 body / auth / SSE 解析 / 安全拦截。"""
import json

from panel.xiaoou_card import XiaoouCard


def _make_card(qapp):
    return XiaoouCard(
        base_url="http://xiaoou:22004",
        model="R-T-2-sun1-MiniMax-M2.7-highspeed",
        topic_id=1001,
        source="desk-assistant",
        auth_header=(b"X-Emp-No", b"10312862"),
    )


# ---- 构造 ----


def test_init_uses_config(qapp):
    card = _make_card(qapp)
    assert card._url == "http://xiaoou:22004"
    assert card._model == "R-T-2-sun1-MiniMax-M2.7-highspeed"
    assert card._topic_id == 1001
    assert card._source == "desk-assistant"
    assert card._auth_header == (b"X-Emp-No", b"10312862")
    # chatUuid 在 __init__ 生成，uuid4 字符串
    assert isinstance(card._chat_uuid, str)
    assert len(card._chat_uuid) == 36  # uuid4 标准长度


# ---- body 构造 ----


def test_build_request_body_has_required_fields(qapp):
    card = _make_card(qapp)
    body = card._build_request_body("你好")
    assert body["chatUuid"] == card._chat_uuid
    assert body["topicId"] == 1001
    assert body["source"] == "desk-assistant"
    assert body["keep"] is True
    assert body["stream"] is True
    assert body["text"] == "你好"
    assert body["model"] == "R-T-2-sun1-MiniMax-M2.7-highspeed"


def test_build_request_body_chatUuid_is_uuid_string(qapp):
    """两次构造 → chatUuid 不同（每次都是新 uuid4）。"""
    c1 = _make_card(qapp)
    c2 = _make_card(qapp)
    assert c1._chat_uuid != c2._chat_uuid


# ---- auth header ----


def test_auth_headers_returns_configured_header(qapp):
    card = _make_card(qapp)
    headers = dict(card._auth_headers())
    assert headers == {b"X-Emp-No": b"10312862"}


# ---- SSE 帧解析 ----


def test_parse_sse_frame_extracts_result(qapp):
    card = _make_card(qapp)
    delta = card._parse_sse_frame(
        {"chatUuid": "x", "finishReason": "", "result": "你好"}
    )
    assert delta == "你好"


def test_parse_sse_frame_skips_stop_marker(qapp):
    """finishReason=='stop' 且 result 为空 → 返回 None（不累加）。"""
    card = _make_card(qapp)
    delta = card._parse_sse_frame(
        {"chatUuid": "x", "finishReason": "stop", "result": ""}
    )
    assert delta is None


def test_parse_sse_frame_marks_safety_block(qapp):
    """result 含'检测到高危指令' → 置 _safety_blocked = True。"""
    card = _make_card(qapp)
    assert card._safety_blocked is False
    card._parse_sse_frame(
        {"chatUuid": "x", "finishReason": "", "result": "检测到高危指令，请求已被安全策略拦截。"}
    )
    assert card._safety_blocked is True


# ---- 业务错误码 & 错误格式化（覆盖率门禁需要） ----


def test_parse_sse_frame_records_biz_error(qapp):
    """code.code != '0000' → 记到 _last_biz_error。"""
    card = _make_card(qapp)
    delta = card._parse_sse_frame(
        {"code": {"code": "9999", "msg": "rate limited"}, "result": ""}
    )
    assert delta is None
    assert card._last_biz_error == "rate limited"


def test_format_error_with_status_includes_body(qapp):
    card = _make_card(qapp)
    msg = card._format_error(None, 500, b"<html>internal error</html>")
    assert "500" in msg
    assert "internal error" in msg


def test_format_error_without_status(qapp):
    """无 status 时只显示 body 前 200 字符（_format_error 的 plan 行为）。"""
    card = _make_card(qapp)
    msg = card._format_error("ConnectionRefused", None, b"upstream-down")
    assert "upstream-down" in msg
    assert "status=" not in msg


def test_reset_session_increments_topic_id_and_rotates_uuid(qapp):
    """点'新会话'：topicId 递增 + 换 chatUuid + 清 _last_biz_error / _safety_blocked。"""
    card = _make_card(qapp)
    card._last_biz_error = "some err"
    card._safety_blocked = True
    old_uuid = card._chat_uuid
    old_topic = card._topic_id

    card._reset_session()

    assert card._chat_uuid != old_uuid
    assert len(card._chat_uuid) == 36
    assert card._topic_id == old_topic + 1
    assert card._last_biz_error is None
    assert card._safety_blocked is False


# ---- web UI 跳转 ----


def test_open_chat_button_builds_url_with_current_session(qapp, monkeypatch):
    """'打开 web UI'按钮的 URL 用当前 chatUuid + topicId 拼出，并被 quote 处理。"""
    card = _make_card(qapp)
    # 假设点击时还未"新会话"，uuid/topic 还是初始值
    captured = {}
    def fake_open(url):
        captured["url"] = url.toString()
    monkeypatch.setattr("PyQt5.QtGui.QDesktopServices.openUrl", fake_open)
    card._on_open_chat()
    expected_session = "agent:main:openai:{}@topic:{}".format(card._chat_uuid, card._topic_id)
    from urllib.parse import quote
    assert captured["url"] == "http://10.90.30.228:18789/chat?session=" + quote(expected_session, safe="")


def test_open_chat_button_picks_up_new_session_after_reset(qapp, monkeypatch):
    """'新会话'之后再点跳转按钮，URL 用最新的 uuid/topic。"""
    card = _make_card(qapp)
    captured = {}
    def fake_open(url):
        captured["url"] = url.toString()
    monkeypatch.setattr("PyQt5.QtGui.QDesktopServices.openUrl", fake_open)
    card._reset_session()  # topicId += 1, chatUuid 换
    card._on_open_chat()
    expected_session = "agent:main:openai:{}@topic:{}".format(card._chat_uuid, card._topic_id)
    from urllib.parse import quote
    assert captured["url"] == "http://10.90.30.228:18789/chat?session=" + quote(expected_session, safe="")
    # topicId 应该是 1002
    assert card._topic_id == 1002


def test_open_chat_button_uses_custom_web_ui_base(qapp):
    """构造时传 web_ui_base 用自定义地址（测试/部署用）。"""
    card = XiaoouCard(
        base_url="http://xiaoou:22004",
        model="R-T-2-sun1-MiniMax-M2.7-highspeed",
        topic_id=1001,
        source="desk-assistant",
        auth_header=(b"X-Emp-No", b"10312862"),
        web_ui_base="http://custom.example.com:9999",
    )
    assert card._web_ui_base == "http://custom.example.com:9999"
