"""Reads what you're currently doing on the Mac.

Everything here is read-only. It answers: which app is in front, what's its
window/file title, and — for browsers — which tab (title + URL). It also
reports how long you've been idle (no keyboard/mouse).

Getting window titles needs Accessibility permission; getting browser tabs
needs Automation permission. Both are one-time approvals macOS will prompt for.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field

from AppKit import NSWorkspace
import Quartz
from ApplicationServices import (
    AXIsProcessTrusted,
    AXUIElementCreateApplication,
    AXUIElementCopyAttributeValue,
)

from . import config

# AX attribute constants as raw strings (robust across pyobjc versions).
_AX_FOCUSED_WINDOW = "AXFocusedWindow"
_AX_TITLE = "AXTitle"

# Bundle IDs of browsers whose active tab we can read, mapped to their engine.
_CHROMIUM_BROWSERS = {
    "com.google.Chrome",
    "com.google.Chrome.canary",
    "com.brave.Browser",
    "com.brave.Browser.beta",
    "com.microsoft.edgemac",
    "com.vivaldi.Vivaldi",
    "company.thebrowser.Browser",  # Arc
    "com.operasoftware.Opera",
}
_SAFARI_BROWSERS = {"com.apple.Safari", "com.apple.SafariTechnologyPreview"}

# Media apps we can read "now playing" from even when they're in the background.
# Maps bundle id -> the app's AppleScript name.
_MEDIA_APPS = {
    "com.spotify.client": "Spotify",
    "com.apple.Music": "Music",
}

# A light category hint to help the message writer. Not exhaustive — anything
# unknown just falls through as "other" and the app name speaks for itself.
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


@dataclass
class Snapshot:
    app: str = "Unknown"
    bundle_id: str = ""
    window_title: str = ""
    tab_title: str = ""
    url: str = ""
    category: str = "other"
    music: str = ""          # what's playing in the background (Spotify/Music)
    music_url: str = ""      # shareable link to the track, so she can listen along
    idle_seconds: float = 0.0
    extras: dict = field(default_factory=dict)

    def signature(self) -> str:
        """A stable-ish fingerprint of the activity. Changes when you switch
        app, tab, file, or page — or when the background song changes — which
        is exactly when we want to update."""
        detail = self.url or self.tab_title or self.window_title
        sig = f"{self.bundle_id}|{detail}"
        if self.music:
            sig += f"|♪{self.music}"
        return sig.strip("|")


def accessibility_ok() -> bool:
    """Whether we have Accessibility permission (needed for window titles)."""
    return bool(AXIsProcessTrusted())


def _idle_seconds() -> float:
    try:
        return float(
            Quartz.CGEventSourceSecondsSinceLastEventType(
                Quartz.kCGEventSourceStateHIDSystemState,
                Quartz.kCGAnyInputEventType,
            )
        )
    except Exception:
        return 0.0


def _frontmost_window_title(pid: int) -> str:
    """Title of the frontmost window of the app with this pid (needs a11y)."""
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
        out = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if out.returncode != 0:
            return ""
        return out.stdout.strip()
    except Exception:
        return ""


def _chromium_tab(app_name: str) -> tuple[str, str]:
    script = f'''
    tell application "{app_name}"
        if (count of windows) = 0 then return ""
        set t to title of active tab of front window
        set u to URL of active tab of front window
        return t & linefeed & u
    end tell
    '''
    return _parse_tab(_run_osascript(script))


def _safari_tab(app_name: str) -> tuple[str, str]:
    script = f'''
    tell application "{app_name}"
        if (count of windows) = 0 then return ""
        set t to name of current tab of front window
        set u to URL of current tab of front window
        return t & linefeed & u
    end tell
    '''
    return _parse_tab(_run_osascript(script))


def _parse_tab(raw: str) -> tuple[str, str]:
    if not raw:
        return "", ""
    parts = raw.split("\n", 1)
    title = parts[0].strip()
    url = parts[1].strip() if len(parts) > 1 else ""
    return title, url


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
    """What's playing in a *background* media app.

    Returns (label, url) e.g. ('Song — Artist (Spotify)', 'https://open.spotify…'),
    or ('', '') if nothing's playing. Skips a media app if it's the frontmost one
    (the generic layer already reports it). We check `is running` inside the
    AppleScript so we never accidentally launch a closed app.
    """
    for bundle, app_name in _MEDIA_APPS.items():
        if bundle == frontmost_bundle or bundle not in running:
            continue
        # Spotify exposes a shareable track URI; Apple Music doesn't.
        url_expr = "spotify url of current track" if app_name == "Spotify" else '""'
        script = f'''
        if application "{app_name}" is running then
            tell application "{app_name}"
                if player state is playing then
                    return (name of current track) & "\\n" & (artist of current track) & "\\n" & ({url_expr})
                end if
            end tell
        end if
        return ""
        '''
        raw = _run_osascript(script)
        if not raw:
            continue
        parts = raw.split("\n")
        name = parts[0].strip() if parts else ""
        artist = parts[1].strip() if len(parts) > 1 else ""
        uri = parts[2].strip() if len(parts) > 2 else ""
        label = f"{name} — {artist}" if artist else name
        label = f"{label} ({'Spotify' if app_name == 'Spotify' else 'Apple Music'})"
        url = ""
        if uri.startswith("spotify:track:"):
            url = "https://open.spotify.com/track/" + uri.split(":")[-1]
        return label, url
    return "", ""


def collect() -> Snapshot:
    """Take one read of the current activity."""
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
        pid = int(app.processIdentifier())
        snap.window_title = _frontmost_window_title(pid)
    except Exception:
        pass

    # Extra detail for browsers: which tab.
    if snap.bundle_id in _CHROMIUM_BROWSERS:
        snap.category = "browsing"
        snap.tab_title, snap.url = _chromium_tab(snap.app)
    elif snap.bundle_id in _SAFARI_BROWSERS:
        snap.category = "browsing"
        snap.tab_title, snap.url = _safari_tab(snap.app)

    # Background music, so we can say "watching X while Y plays".
    if config.REPORT_MEDIA:
        snap.music, snap.music_url = _now_playing(running, snap.bundle_id)

    return snap


if __name__ == "__main__":
    # Quick self-test: prints one snapshot so you can confirm permissions work.
    import json

    print("Accessibility permission:", "OK" if accessibility_ok() else "MISSING")
    s = collect()
    print(
        json.dumps(
            {
                "app": s.app,
                "bundle_id": s.bundle_id,
                "window_title": s.window_title,
                "tab_title": s.tab_title,
                "url": s.url,
                "category": s.category,
                "music": s.music,
                "idle_seconds": round(s.idle_seconds, 1),
                "signature": s.signature(),
            },
            indent=2,
        )
    )
