"""A tiny sound board for `!sound <name>` — plays a chime on his Mac.

Maps cute names to macOS's built-in system sounds (System/Library/Sounds), so
there's nothing to bundle or download — every Mac already has these.
"""

from __future__ import annotations

import os
import shutil
import subprocess

_DIR = "/System/Library/Sounds"

# Cute name -> real macOS system sound. Several names can point at the same
# file; pick whichever the name/emoji suggests to her.
_MAP = {
    "kiss": "Pop", "muah": "Pop",
    "heart": "Glass", "love": "Glass",
    "hug": "Purr",
    "boop": "Tink", "poke": "Tink",
    "tada": "Hero", "yay": "Hero", "celebrate": "Hero",
    "knock": "Sosumi",
    "bell": "Glass",
    "pop": "Pop",
    "ding": "Ping",
}

NAMES = sorted(_MAP.keys())


def _resolve() -> str | None:
    return shutil.which("afplay") or ("/usr/bin/afplay" if _ok("/usr/bin/afplay") else None)


def _ok(path: str) -> bool:
    return os.path.isfile(path) and os.access(path, os.X_OK)


def available() -> bool:
    return _resolve() is not None


def play(name: str) -> bool:
    """Play the sound mapped to `name` (case-insensitive). Returns False if the
    name isn't recognized or afplay/the sound file is missing."""
    afplay = _resolve()
    if not afplay:
        return False
    system_sound = _MAP.get((name or "").strip().lower())
    if not system_sound:
        return False
    path = os.path.join(_DIR, f"{system_sound}.aiff")
    if not os.path.isfile(path):
        return False
    try:
        subprocess.run([afplay, path], check=True, capture_output=True, timeout=15)
        return True
    except Exception:
        return False
