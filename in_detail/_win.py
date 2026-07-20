"""Windows activity backend — frontmost app, window title, idle, Spotify.

Uses pywin32 + psutil (no special permission needed on Windows). Browser tab
URLs aren't read here (Windows has no clean cross-browser API for it) — the
window title still carries the page title, so you get e.g. "FIFA - YouTube".
Background Spotify is read from its window title ("Artist - Song").
"""

from __future__ import annotations

import ctypes
import re

from . import config
from .collectors import Snapshot

try:
    import win32gui
    import win32process
    import psutil
except Exception:  # not on Windows / deps missing
    win32gui = None

# exe name (lowercase) -> (friendly name, category)
_PROC = {
    "chrome.exe": ("Chrome", "browsing"),
    "msedge.exe": ("Edge", "browsing"),
    "brave.exe": ("Brave", "browsing"),
    "firefox.exe": ("Firefox", "browsing"),
    "opera.exe": ("Opera", "browsing"),
    "vivaldi.exe": ("Vivaldi", "browsing"),
    "arc.exe": ("Arc", "browsing"),
    "code.exe": ("VS Code", "coding"),
    "cursor.exe": ("Cursor", "coding"),
    "devenv.exe": ("Visual Studio", "coding"),
    "pycharm64.exe": ("PyCharm", "coding"),
    "idea64.exe": ("IntelliJ", "coding"),
    "sublime_text.exe": ("Sublime Text", "coding"),
    "windowsterminal.exe": ("Terminal", "terminal"),
    "cmd.exe": ("Command Prompt", "terminal"),
    "powershell.exe": ("PowerShell", "terminal"),
    "wt.exe": ("Terminal", "terminal"),
    "discord.exe": ("Discord", "discord"),
    "slack.exe": ("Slack", "chat"),
    "spotify.exe": ("Spotify", "music"),
    "steam.exe": ("Steam", "gaming"),
    "notion.exe": ("Notion", "notes"),
    "obsidian.exe": ("Obsidian", "notes"),
    "figma.exe": ("Figma", "design"),
}
_BROWSERS = {"chrome.exe", "msedge.exe", "brave.exe", "firefox.exe",
             "opera.exe", "vivaldi.exe", "arc.exe"}
_BROWSER_SUFFIX = re.compile(
    r"\s*[-–—]\s*(Google Chrome|Microsoft.?Edge|Brave|Mozilla Firefox|"
    r"Opera|Vivaldi|Arc)\s*$", re.I)


def permission_ok() -> bool:
    return win32gui is not None  # Windows needs no special permission


def _idle_seconds() -> float:
    class LII(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
    try:
        lii = LII()
        lii.cbSize = ctypes.sizeof(lii)
        if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
            return 0.0
        return max(0.0, (ctypes.windll.kernel32.GetTickCount() - lii.dwTime) / 1000.0)
    except Exception:
        return 0.0


def _proc_name(pid: int) -> str:
    try:
        return psutil.Process(pid).name().lower()
    except Exception:
        return ""


def _spotify_now_playing() -> tuple[str, str]:
    """Read Spotify's track from its window title, even in the background."""
    found = [""]

    def cb(hwnd, _):
        try:
            if not win32gui.IsWindowVisible(hwnd):
                return
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            if _proc_name(pid) != "spotify.exe":
                return
            t = (win32gui.GetWindowText(hwnd) or "").strip()
            if " - " in t and t.lower() not in ("spotify", "spotify premium", "spotify free"):
                artist, song = t.split(" - ", 1)
                found[0] = f"{song.strip()} — {artist.strip()} (Spotify)"
        except Exception:
            pass

    try:
        win32gui.EnumWindows(cb, None)
    except Exception:
        pass
    return found[0], ""  # no shareable URL from the title


def collect() -> Snapshot:
    snap = Snapshot(idle_seconds=_idle_seconds())
    if win32gui is None:
        return snap
    try:
        hwnd = win32gui.GetForegroundWindow()
        title = (win32gui.GetWindowText(hwnd) or "").strip()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        proc = _proc_name(pid)
    except Exception:
        return snap

    friendly, category = _PROC.get(
        proc, (proc[:-4].title() if proc.endswith(".exe") else (proc or "Unknown"), "other"))
    snap.app = friendly
    snap.bundle_id = proc
    snap.category = category
    snap.window_title = title

    if proc in _BROWSERS:
        snap.category = "browsing"
        snap.tab_title = _BROWSER_SUFFIX.sub("", title).strip()

    if config.REPORT_MEDIA and proc != "spotify.exe":
        snap.music, snap.music_url = _spotify_now_playing()

    return snap
