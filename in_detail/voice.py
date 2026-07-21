"""Speak text aloud on his Mac — the muscle behind `!say`.

Uses the built-in `say` command (no dependency, always present on macOS). The
caller runs this off the main thread so a long sentence never stalls the app.
"""

from __future__ import annotations

import os
import shutil
import subprocess


def _resolve() -> str | None:
    return shutil.which("say") or ("/usr/bin/say" if _ok("/usr/bin/say") else None)


def _ok(path: str) -> bool:
    return os.path.isfile(path) and os.access(path, os.X_OK)


def available() -> bool:
    return _resolve() is not None


def speak(text: str, voice: str | None = None) -> bool:
    """Say `text` out loud. `voice` is an optional macOS voice name (e.g.
    "Samantha"); blank/None uses the system default. Text is passed as an argv
    element, never a shell string, so there's nothing to inject."""
    say = _resolve()
    if not say or not text.strip():
        return False
    cmd = [say]
    if voice:
        cmd += ["-v", voice]
    cmd.append(text)
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=60)
        return True
    except Exception:
        return False
