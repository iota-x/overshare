"""A tiny sound board for `!sound <name>` — plays a chime on their machine.

macOS: maps names to the built-in system sounds in /System/Library/Sounds.
Windows: maps names to `winsound.MessageBeep` icon tones (stdlib, no file
path to guess at — MessageBeep tones exist on every Windows install/theme,
unlike a specific .wav filename which can vary).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

_DIR = "/System/Library/Sounds"

# Cute name -> real macOS system sound (several names may share a file).
_MAC_MAP = {
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

# Cute name -> a winsound.MessageBeep(...) constant name (resolved lazily,
# since winsound only importable on Windows).
_WIN_MAP = {
    "kiss": "MB_ICONASTERISK", "muah": "MB_ICONASTERISK",
    "heart": "MB_OK", "love": "MB_OK",
    "hug": "MB_ICONASTERISK",
    "boop": "MB_OK", "poke": "MB_OK",
    "tada": "MB_ICONEXCLAMATION", "yay": "MB_ICONEXCLAMATION", "celebrate": "MB_ICONEXCLAMATION",
    "knock": "MB_ICONHAND",
    "bell": "MB_OK",
    "pop": "MB_OK",
    "ding": "MB_ICONASTERISK",
}

NAMES = sorted(set(_MAC_MAP) | set(_WIN_MAP))


def _resolve_afplay() -> str | None:
    return shutil.which("afplay") or ("/usr/bin/afplay" if _ok("/usr/bin/afplay") else None)


def _ok(path: str) -> bool:
    return os.path.isfile(path) and os.access(path, os.X_OK)


def available() -> bool:
    if sys.platform == "darwin":
        return _resolve_afplay() is not None
    if sys.platform.startswith("win"):
        try:
            import winsound  # noqa: F401
            return True
        except Exception:
            return False
    return False


def _play_mac(name: str) -> bool:
    afplay = _resolve_afplay()
    system_sound = _MAC_MAP.get(name)
    if not afplay or not system_sound:
        return False
    path = os.path.join(_DIR, f"{system_sound}.aiff")
    if not os.path.isfile(path):
        return False
    subprocess.run([afplay, path], check=True, capture_output=True, timeout=15)
    return True


def _play_win(name: str) -> bool:
    import winsound
    const_name = _WIN_MAP.get(name)
    if not const_name:
        return False
    tone = getattr(winsound, const_name, None)
    if tone is None:
        return False
    winsound.MessageBeep(tone)
    return True


def play(name: str) -> bool:
    """Play the sound mapped to `name` (case-insensitive). Returns False if the
    name isn't recognized or the platform has no sound backend."""
    name = (name or "").strip().lower()
    if not name:
        return False
    try:
        if sys.platform == "darwin":
            return _play_mac(name)
        if sys.platform.startswith("win"):
            return _play_win(name)
        return False
    except Exception:
        return False
