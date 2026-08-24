"""Speak text aloud on his machine — the muscle behind `!say`.

macOS: the built-in `say` command. Windows: PowerShell's System.Speech (built
into every Windows 10/11 box, nothing to install). No third-party TTS deps.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys


def _resolve_mac() -> str | None:
    return shutil.which("say") or ("/usr/bin/say" if _ok("/usr/bin/say") else None)


def _resolve_win() -> str | None:
    return shutil.which("powershell") or shutil.which("powershell.exe")


def _ok(path: str) -> bool:
    return os.path.isfile(path) and os.access(path, os.X_OK)


def available() -> bool:
    if sys.platform == "darwin":
        return _resolve_mac() is not None
    if sys.platform.startswith("win"):
        return _resolve_win() is not None
    return False


def _speak_mac(text: str, voice: str | None) -> bool:
    say = _resolve_mac()
    if not say:
        return False
    cmd = [say]
    if voice:
        cmd += ["-v", voice]
    cmd.append(text)
    subprocess.run(cmd, check=True, capture_output=True, timeout=60)
    return True


def _speak_win(text: str, voice: str | None) -> bool:
    powershell = _resolve_win()
    if not powershell:
        return False
    # The text/voice are passed as trailing process arguments, bound to $args
    # inside the script — never string-interpolated into the script itself, so
    # there's no way for their message to be parsed as PowerShell code.
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "if ($args[0]) { try { $s.SelectVoice($args[0]) } catch {} }; "
        "$s.Speak($args[1])"
    )
    cmd = [powershell, "-NoProfile", "-NonInteractive", "-Command", script,
           "--", voice or "", text]
    subprocess.run(cmd, check=True, capture_output=True, timeout=60,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return True


def speak(text: str, voice: str | None = None) -> bool:
    """Say `text` out loud. `voice` is an optional platform voice name (macOS:
    e.g. "Samantha"; Windows: e.g. "Microsoft Zira Desktop") — blank/None uses
    the system default. Returns False (never raises) if TTS isn't available."""
    text = (text or "").strip()
    if not text:
        return False
    try:
        if sys.platform == "darwin":
            return _speak_mac(text, voice)
        if sys.platform.startswith("win"):
            return _speak_win(text, voice)
        return False
    except Exception:
        return False
