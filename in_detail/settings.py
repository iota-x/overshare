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
# prefix: bot command prefix override ("" = use config.BOT_PREFIX)
# camera_enabled / screen_enabled: his live privacy switches for `!peek`/`!screen`/
#   `!live` (toggled from the menu bar). config.PEEK_ENABLED is the master off.
# mirror_capture: flip webcam photos left-to-right so they read like a mirror
#   (the natural selfie view) instead of imagesnap's reversed-feeling raw frame.
_DEFAULTS = {
    "card_destination": "channel",
    "tone": "default",
    "mood": "",
    "prefix": "",
    "camera_enabled": True,
    "screen_enabled": True,
    "mirror_capture": True,
    "say_voice": "",       # macOS voice name for !say; "" = system default
    "exact_status": False, # send exactly-what's-detected, skip AI phrasing
}
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


def peek_source_enabled(source: str) -> bool:
    """Is she allowed to use this peek source right now? source: 'cam' | 'screen'."""
    key = "camera_enabled" if source == "cam" else "screen_enabled"
    return bool(get(key))


def set(key: str, value) -> None:
    d = _load()
    d[key] = value
    try:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        _path().write_text(json.dumps(d))
    except Exception:
        pass
