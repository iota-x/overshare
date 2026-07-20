"""Runtime settings she can toggle from Discord (persisted to data/settings.json).

Shared across threads in one process: the bot thread writes (when she toggles),
the app/notifier reads (when delivering). Simple dict ops — safe enough here.
"""

from __future__ import annotations

import json

from . import config

# card_destination: "channel" | "dm" | "both"
# tone: "default" | "cutesy" | "chill" | "detailed"
# mood: free text (his current status), "" = none
_DEFAULTS = {"card_destination": "channel", "tone": "default", "mood": ""}
_cache: dict | None = None


def _path():
    return config.DATA_DIR / "settings.json"


def _load() -> dict:
    global _cache
    if _cache is None:
        try:
            _cache = {**_DEFAULTS, **json.loads(_path().read_text())}
        except Exception:
            _cache = dict(_DEFAULTS)
    return _cache


def get(key: str):
    return _load().get(key, _DEFAULTS.get(key))


def set(key: str, value) -> None:
    d = _load()
    d[key] = value
    try:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        _path().write_text(json.dumps(d))
    except Exception:
        pass
