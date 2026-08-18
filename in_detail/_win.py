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

try:  # optional: only needed to read the browser's address bar
    import uiautomation as _auto
except Exception:
    _auto = None

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
# Chromium appends resource warnings to the title; they aren't part of the page.
_BROWSER_NOISE = re.compile(
    r"\s*[-–—]\s*(High memory usage[^-–—]*|\d+(\.\d+)?\s*[KMG]B)\s*", re.I)


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


def _window_text(hwnd) -> str:
    """Window title as real Unicode.

    Goes straight to the wide-character API: the ANSI one substitutes '?' for
    anything outside the active code page, which quietly mangles CJK names and
    emoji in titles like '(3) Discord | @\u3081 michiyo'."""
    try:
        user32 = ctypes.windll.user32
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value.strip()
    except Exception:
        try:
            return (win32gui.GetWindowText(hwnd) or "").strip()
        except Exception:
            return ""


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
            t = _window_text(hwnd)
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


_URL_SCHEMES = ("http://", "https://", "about:", "file://", "chrome://", "edge://")
_url_cache: tuple[str, str] = ("", "")  # (window+title key, url)


def _normalise_url(text: str) -> str:
    """Address bars hide the scheme — 'github.com/x' means 'https://github.com/x'."""
    t = (text or "").strip()
    if not t or " " in t:
        return ""              # a search phrase, not a URL
    if t.startswith(_URL_SCHEMES):
        return t
    host = t.split("/", 1)[0]
    return f"https://{t}" if "." in host and not host.endswith(".") else ""


def _browser_url(hwnd, title: str) -> str:
    """The active tab's URL, read out of the address bar via UI Automation.

    Windows has no API for this. Walking the accessibility tree costs real time,
    so the result is cached against the window title — which changes exactly
    when the tab does, so a stale URL can't outlive the page it belongs to."""
    global _url_cache
    if _auto is None:
        return ""
    key = f"{hwnd}|{title}"
    if _url_cache[0] == key:
        return _url_cache[1]
    url = ""
    try:
        window = _auto.ControlFromHandle(hwnd)
        if window is not None:
            edit = window.EditControl(searchDepth=8)
            if edit.Exists(maxSearchSeconds=0.4, searchIntervalSeconds=0.1):
                url = _normalise_url(edit.GetValuePattern().Value)
    except Exception:
        url = ""
    _url_cache = (key, url)
    return url


def collect() -> Snapshot:
    snap = Snapshot(idle_seconds=_idle_seconds())
    if win32gui is None:
        return snap
    try:
        hwnd = win32gui.GetForegroundWindow()
        title = _window_text(hwnd)
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
        snap.tab_title = _BROWSER_SUFFIX.sub("", _BROWSER_NOISE.sub(" ", title)).strip()
        if config.READ_BROWSER_URL:
            snap.url = _browser_url(hwnd, title)

    if config.REPORT_MEDIA and proc != "spotify.exe":
        snap.music, snap.music_url = _spotify_now_playing()

    return snap
