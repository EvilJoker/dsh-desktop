"""panel/chat_card.py 单元测试：OpenClaw 协议（body / SSE 解析 / auth / set_token）。"""
import pytest

from panel.chat_card import ChatCard


def _make_card(qapp, token="tok-abc"):
    return ChatCard(
        openclaw_url="http://openclaw:18789/v1/chat/completions",
        model="openclaw",
        session_key="agent:main:openai:00000000-0000-4000-8000-000000000001@topic:desk-assistant",
        chat_url="http://openclaw:18789/chat?lang=zh-CN&session=agent:main:openai:00000000-0000-4000-8000-000000000001@topic:desk-assistant",
    )._set_token_for_test(token)


# Monkey-patch: 给 ChatCard 加一个 _set_token_for_test 直接调 set_token，
# 绕开外部 panel 调用。生产代码不需要这个方法。
# 注意：pytest 在 Python 3.6 上 monkeypatch.setattr 不能给类加新属性，
# 所以这里直接用 setattr（pytest 会在测试后自动清理，见 teardown）。
@pytest.fixture(autouse=True)
def _add_test_hook(request):
    """给 ChatCard 加 _set_token_for_test 测试钩子，避免改生产代码。"""
    def _set_token_for_test(self, token):
        self.set_token(token)
        return self
    ChatCard._set_token_for_test = _set_token_for_test
    request.addfinalizer(lambda: delattr(ChatCard, "_set_token_for_test"))


# ---- body 构造 ----


def test_build_request_body_has_openai_shape(qapp):
    card = _make_card(qapp, token="tok")
    body = card._build_request_body("hello")
    assert body["model"] == "openclaw"
    assert body["messages"] == [{"role": "user", "content": "hello"}]
    assert body["stream"] is True


# ---- SSE 帧解析 ----


def test_parse_sse_frame_extracts_delta_content(qapp):
    card = _make_card(qapp)
    delta = card._parse_sse_frame(
        {"choices": [{"delta": {"content": "你好"}}]}
    )
    assert delta == "你好"


def test_parse_sse_frame_missing_delta_returns_none(qapp):
    card = _make_card(qapp)
    delta = card._parse_sse_frame({"choices": [{"delta": {}}]})
    assert delta is None


# ---- auth header ----


def test_auth_headers_include_bearer_and_session_key(qapp):
    card = _make_card(qapp, token="tok-xyz")
    headers = card._auth_headers()
    headers_dict = dict(headers)
    assert headers_dict[b"Authorization"] == b"Bearer tok-xyz"
    assert headers_dict[b"x-openclaw-session-key"] == b"agent:main:openai:00000000-0000-4000-8000-000000000001@topic:desk-assistant"


# ---- set_token 行为 ----


def test_set_token_enables_input(qapp):
    card = _make_card(qapp, token=None)
    assert not card._input.isEnabled()
    card.set_token("abc")
    assert card._token == "abc"
    assert card._input.isEnabled()


def test_set_token_empty_keeps_disabled_and_sets_placeholder(qapp):
    card = _make_card(qapp, token=None)
    card.set_token(None)
    assert not card._input.isEnabled()
    assert "未找到" in card._input.placeholderText()
