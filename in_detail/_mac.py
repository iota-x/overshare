"""macOS activity backend — frontmost app, window titles, browser tabs, media.

Window titles need Accessibility permission; browser tabs & background media need
Automation permission. Both are one-time macOS approvals.
"""

from __future__ import annotations

import subprocess

from AppKit import NSWorkspace
import Quartz
from ApplicationServices import (
    AXIsProcessTrusted,
    AXUIElementCreateApplication,
    AXUIElementCopyAttributeValue,
)

from . import config
from .collectors import Snapshot

_AX_FOCUSED_WINDOW = "AXFocusedWindow"
_AX_TITLE = "AXTitle"

_CHROMIUM_BROWSERS = {
    "com.google.Chrome", "com.google.Chrome.canary", "com.brave.Browser",
    "com.brave.Browser.beta", "com.microsoft.edgemac", "com.vivaldi.Vivaldi",
    "company.thebrowser.Browser", "com.operasoftware.Opera",
}
_SAFARI_BROWSERS = {"com.apple.Safari", "com.apple.SafariTechnologyPreview"}
_MEDIA_APPS = {"com.spotify.client": "Spotify", "com.apple.Music": "Music"}

_CATEGORY_BY_BUNDLE = {
    "com.microsoft.VSCode": "coding",
    "com.todesktop.230313mzl4w4u92": "coding",  # Cursor
    "com.apple.dt.Xcode": "coding",
    "com.googlecode.iterm2": "terminal",
    "com.apple.Terminal": "terminal",
    "com.hnc.Discord": "discord",
    "com.tinyspeck.slackmacgap": "chat",
    "com.spotify.client": "music",
    "com.apple.Music": "music",
    "com.figma.Desktop": "design",
    "notion.id": "notes",
    "md.obsidian": "notes",
}


def permission_ok() -> bool:
    """Accessibility permission (needed for window titles)."""
    return bool(AXIsProcessTrusted())


def _idle_seconds() -> float:
    try:
        return float(Quartz.CGEventSourceSecondsSinceLastEventType(
            Quartz.kCGEventSourceStateHIDSystemState, Quartz.kCGAnyInputEventType))
    except Exception:
        return 0.0


def _frontmost_window_title(pid: int) -> str:
    try:
        ax_app = AXUIElementCreateApplication(pid)
        err, window = AXUIElementCopyAttributeValue(ax_app, _AX_FOCUSED_WINDOW, None)
        if err != 0 or window is None:
            return ""
        err, title = AXUIElementCopyAttributeValue(window, _AX_TITLE, None)
        if err != 0 or title is None:
            return ""
        return str(title)
    except Exception:
        return ""


def _run_osascript(script: str, timeout: float = 3.0) -> str:
    try:
        out = subprocess.run(["osascript", "-e", script], capture_output=True,
                             text=True, timeout=timeout)
        return out.stdout.strip() if out.returncode == 0 else ""
    except Exception:
        return ""


def _parse_tab(raw: str) -> tuple[str, str]:
    if not raw:
        return "", ""
    parts = raw.split("\n", 1)
    return parts[0].strip(), (parts[1].strip() if len(parts) > 1 else "")


def _chromium_tab(app_name: str) -> tuple[str, str]:
    return _parse_tab(_run_osascript(f'''
    tell application "{app_name}"
        if (count of windows) = 0 then return ""
        set t to title of active tab of front window
        set u to URL of active tab of front window
        return t & linefeed & u
    end tell'''))


def _safari_tab(app_name: str) -> tuple[str, str]:
    return _parse_tab(_run_osascript(f'''
    tell application "{app_name}"
        if (count of windows) = 0 then return ""
        set t to name of current tab of front window
        set u to URL of current tab of front window
        return t & linefeed & u
    end tell'''))


def _running_bundle_ids() -> set[str]:
    ids: set[str] = set()
    try:
        for app in NSWorkspace.sharedWorkspace().runningApplications():
            bid = app.bundleIdentifier()
            if bid:
                ids.add(str(bid))
    except Exception:
        pass
    return ids


def _now_playing(running: set[str], frontmost_bundle: str) -> tuple[str, str]:
    for bundle, app_name in _MEDIA_APPS.items():
        if bundle == frontmost_bundle or bundle not in running:
            continue
        url_expr = "spotify url of current track" if app_name == "Spotify" else '""'
        raw = _run_osascript(f'''
        if application "{app_name}" is running then
            tell application "{app_name}"
                if player state is playing then
                    return (name of current track) & "\\n" & (artist of current track) & "\\n" & ({url_expr})
                end if
            end tell
        end if
        return ""''')
        if not raw:
            continue
        parts = raw.split("\n")
        name = parts[0].strip() if parts else ""
        artist = parts[1].strip() if len(parts) > 1 else ""
        uri = parts[2].strip() if len(parts) > 2 else ""
        label = f"{name} — {artist}" if artist else name
        label += f" ({'Spotify' if app_name == 'Spotify' else 'Apple Music'})"
        url = "https://open.spotify.com/track/" + uri.split(":")[-1] if uri.startswith("spotify:track:") else ""
        return label, url
    return "", ""


def collect() -> Snapshot:
    snap = Snapshot(idle_seconds=_idle_seconds())
    running = _running_bundle_ids()
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    if app is None:
        snap.music, snap.music_url = _now_playing(running, "")
        return snap
    snap.app = str(app.localizedName() or "Unknown")
    snap.bundle_id = str(app.bundleIdentifier() or "")
    snap.category = _CATEGORY_BY_BUNDLE.get(snap.bundle_id, "other")
    try:
        snap.window_title = _frontmost_window_title(int(app.processIdentifier()))
    except Exception:
        pass
    if snap.bundle_id in _CHROMIUM_BROWSERS:
        snap.category = "browsing"
        snap.tab_title, snap.url = _chromium_tab(snap.app)
    elif snap.bundle_id in _SAFARI_BROWSERS:
        snap.category = "browsing"
        snap.tab_title, snap.url = _safari_tab(snap.app)
    if config.REPORT_MEDIA:
        snap.music, snap.music_url = _now_playing(running, snap.bundle_id)
    return snap
