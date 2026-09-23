"""panel/config.py 单元测试：覆盖 5 种加载场景。"""
import json

import pytest

from panel.config import DEFAULT_CONFIG, load_config


def test_load_default_when_file_missing(monkeypatch, tmp_path):
    """env 指向不存在的文件 + home 不存在 → 用 DEFAULT_CONFIG。"""
    monkeypatch.setenv("DESK_ASSISTANT_CONFIG", str(tmp_path / "nope.json"))
    monkeypatch.setattr("panel.config._USER_CONFIG", tmp_path / "nope-home.json")
    cfg = load_config()
    assert cfg == DEFAULT_CONFIG


def test_load_default_when_file_bad_json(monkeypatch, tmp_path):
    """文件存在但 JSON 坏 → 用 DEFAULT_CONFIG。"""
    p = tmp_path / "bad.json"
    p.write_text("{not valid json", encoding="utf-8")
    monkeypatch.setenv("DESK_ASSISTANT_CONFIG", str(p))
    cfg = load_config()
    assert cfg == DEFAULT_CONFIG


def test_load_default_when_file_not_dict(monkeypatch, tmp_path):
    """文件顶层不是 dict（是 list）→ 用 DEFAULT_CONFIG。"""
    p = tmp_path / "list.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    monkeypatch.setenv("DESK_ASSISTANT_CONFIG", str(p))
    cfg = load_config()
    assert cfg == DEFAULT_CONFIG


def test_user_config_overrides_defaults(monkeypatch, tmp_path):
    """用户配置覆盖默认。"""
    p = tmp_path / "user.json"
    p.write_text(json.dumps({
        "xiaoou": {
            "base_url": "http://custom:9999",
            "model": "custom-model",
            "topic_id": 42,
            "source": "test",
            "auth": {"header": "X-Test", "value": "v"},
        },
    }), encoding="utf-8")
    monkeypatch.setenv("DESK_ASSISTANT_CONFIG", str(p))
    cfg = load_config()
    assert cfg["xiaoou"]["base_url"] == "http://custom:9999"
    assert cfg["xiaoou"]["model"] == "custom-model"
    # openclaw 没被用户覆盖 → 用默认
    assert cfg["openclaw"]["url"] == DEFAULT_CONFIG["openclaw"]["url"]


def test_user_partial_xiaoou_block_fully_replaces_default(monkeypatch, tmp_path):
    """浅 merge：用户 xiaoou 块整体替换默认。"""
    p = tmp_path / "partial.json"
    p.write_text(json.dumps({
        "xiaoou": {"base_url": "http://only-url"},
    }), encoding="utf-8")
    monkeypatch.setenv("DESK_ASSISTANT_CONFIG", str(p))
    cfg = load_config()
    # 用户整个 xiaoou 块只有 base_url，其他键被覆盖没了
    assert cfg["xiaoou"] == {"base_url": "http://only-url"}
