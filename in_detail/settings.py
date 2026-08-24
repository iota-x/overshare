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
# camera_device: pin a specific macOS camera by name (substring match, e.g.
#   "FaceTime") so a virtual cam like OBS can't hijack `!peek`. "" = auto-pick
#   the first non-virtual camera.
# pet_name: what she wants the bot to call her (set with !petname), overrides
#   config.HER_NAME in good-morning/goodnight lines when set.
# mood_emoji: replaces the menu-bar glyph when set (blank = default 💌).
# selfie_enabled/selfie_time: a once-daily automatic webcam check-in photo.
# daily_question_enabled/daily_question_time: a once-daily "question of the day".
# her_timezone: IANA name (e.g. "America/New_York") to show her local time.
_DEFAULTS = {
    # Master switch. Lives here rather than in memory so the menu bar and the
    # settings window always agree, and so a pause survives a restart — pausing
    # then quitting should not quietly resume sharing tomorrow.
    "paused": False,
    "card_destination": "channel",
    "tone": "default",
    "mood": "",
    "prefix": "",
    "camera_enabled": True,
    "screen_enabled": True,
    "mirror_capture": True,
    "camera_device": "",   # pin macOS camera by name; "" = auto-skip virtual cams
    "say_voice": "",       # macOS voice name for !say; "" = system default
    "exact_status": False, # send exactly-what's-detected, skip AI phrasing
    "pet_name": "",
    "mood_emoji": "",
    "selfie_enabled": False,
    "selfie_time": "09:00",
    "daily_question_enabled": False,
    "daily_question_time": "12:00",
    "her_timezone": "",
}
_cache: dict | None = None


def _path():
    return config.DATA_DIR / "settings.json"


def _load() -> dict:
    global _cache
    if _cache is None:
        try:
            _cache = {**_DEFAULTS, **json.loads(_path().read_text(encoding="utf-8"))}
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
        _path().write_text(json.dumps(d), encoding="utf-8")
    except Exception:
        pass
