"""panel/config.py — 加载 desk-assistant 配置 + 暴露 chat 协议常量。"""
import json
import logging
import os
from copy import deepcopy
from pathlib import Path
from urllib.parse import quote

log = logging.getLogger(__name__)


# ---- 默认配置 ----

DEFAULT_CONFIG = {
    "openclaw": {
        "url": "http://127.0.0.1:18789/v1/chat/completions",
        "model": "openclaw",
        "session_key": "agent:main:openai:00000000-0000-4000-8000-000000000001@topic:desk-assistant",
        "chat_url": "http://127.0.0.1:18789/chat?lang=zh-CN&session=agent:main:openai:00000000-0000-4000-8000-000000000001@topic:desk-assistant",
    },
    "xiaoou": {
        "base_url": "http://10.90.30.228:22004",
        "model": "R-T-2-sun1-MiniMax-M2.7-highspeed",
        "topic_id": 1001,
        "source": "desk-assistant",
        "auth": {
            "header": "X-Emp-No",
            "value": "10312862",
        },
    },
}


# ---- 路径解析 ----

_USER_CONFIG = Path.home() / ".desk-assistant" / "config.json"
_DEV_CONFIG = Path(__file__).resolve().parent.parent / "data" / "config.json"


def _config_path():
    """优先级：env > 用户 home > 项目 data/（dev/测试）。"""
    env = os.environ.get("DESK_ASSISTANT_CONFIG")
    if env:
        return Path(env)
    if _USER_CONFIG.exists():
        return _USER_CONFIG
    return _DEV_CONFIG


# ---- 加载 ----


def load_config():
    """读 config.json；找不到/坏掉用 DEFAULT_CONFIG 兜底。

    加载策略：浅 merge。用户的整个 xiaoou 块覆盖默认（不深 merge）。
    """
    p = _config_path()
    if not p.exists():
        log.info("config.json 不存在 (%s)，用默认", p)
        return deepcopy(DEFAULT_CONFIG)
    try:
        user_cfg = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        log.warning("config.json 读/解析失败 (%s): %s，用默认", type(e).__name__, e)
        return deepcopy(DEFAULT_CONFIG)
    if not isinstance(user_cfg, dict):
        log.warning("config.json 顶层不是 dict，用默认")
        return deepcopy(DEFAULT_CONFIG)
    merged = deepcopy(DEFAULT_CONFIG)
    merged.update(user_cfg)  # 浅 merge
    return merged


# ---- chat 协议常量（从 load_config() 派生） ----

_CFG = load_config()
OPENCLAW_CFG = _CFG.get("openclaw", {})

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


def load_openclaw_token():
    """读 openclaw gateway.auth.token；找不到/读失败返回 None。"""
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
