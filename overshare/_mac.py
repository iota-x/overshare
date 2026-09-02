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
    AXIsProcessTrustedWithOptions,
    kAXTrustedCheckOptionPrompt,
    AXUIElementCreateApplication,
    AXUIElementCopyAttributeValue,
)

from . import config
from .collectors import Snapshot

_AX_FOCUSED_WINDOW = "AXFocusedWindow"
_AX_MAIN_WINDOW = "AXMainWindow"
_AX_WINDOWS = "AXWindows"
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
    # Every Discord release channel, not just stable — they are separate apps
    # with separate bundle ids, and someone on PTB is on Discord as far as this
    # is concerned. With PTB missing it fell through to "other": a grey card
    # with the generic 🖥️, and the raw window title handed to the summarizer,
    # which echoed it back verbatim as "on Discord PTB — General | Gooner
    # hideout - Discord" instead of naming the channel. The browser sets above
    # already cover their beta/canary builds for the same reason.
    "com.hnc.Discord": "discord",
    "com.hnc.DiscordPTB": "discord",
    "com.hnc.DiscordCanary": "discord",
    "com.hnc.DiscordDevelopment": "discord",
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


def ask_for_permission() -> bool:
    """Ask macOS to show its own Accessibility prompt.

    The prompting variant of the same check. It puts up the system dialog with
    a button that goes straight to the right pane, which is the difference
    between "go and find this in System Settings" and one click.

    macOS shows it at most once per app per launch, so calling it when the
    permission is noticed missing costs nothing when it's already granted.
    """
    try:
        return bool(AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: True}))
    except Exception:
        return permission_ok()


def _idle_seconds() -> float:
    try:
        return float(Quartz.CGEventSourceSecondsSinceLastEventType(
            Quartz.kCGEventSourceStateHIDSystemState, Quartz.kCGAnyInputEventType))
    except Exception:
        return 0.0


def _ax_title(element) -> str:
    try:
        err, title = AXUIElementCopyAttributeValue(element, _AX_TITLE, None)
    except Exception:
        return ""
    return str(title).strip() if err == 0 and title else ""


def _cg_window_title(pid: int) -> str:
    """Ask the window server for the title, as a last resort.

    Independent of Accessibility, so this still answers for apps that hand AX an
    untitled window — without it those updates collapse to a bare app name."""
    try:
        infos = Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly
            | Quartz.kCGWindowListExcludeDesktopElements,
            Quartz.kCGNullWindowID) or []
    except Exception:
        return ""
    for info in infos:
        try:
            if int(info.get("kCGWindowOwnerPID", -1)) != pid:
                continue
            if int(info.get("kCGWindowLayer", 0)) != 0:
                continue  # panels, menus and overlays aren't the real window
            name = str(info.get("kCGWindowName") or "").strip()
        except Exception:
            continue
        if name:
            return name
    return ""


def _frontmost_window_title(pid: int) -> str:
    """The frontmost window's title, trying every source before giving up.

    Electron apps (Discord, Slack, VS Code) routinely leave AXFocusedWindow
    empty while AXMainWindow is perfectly good, so one failed lookup is not an
    answer — it's why a Discord update could arrive saying only "Discord"
    instead of the channel or DM you were actually in."""
    try:
        ax_app = AXUIElementCreateApplication(pid)
        for attr in (_AX_FOCUSED_WINDOW, _AX_MAIN_WINDOW):
            err, window = AXUIElementCopyAttributeValue(ax_app, attr, None)
            if err == 0 and window is not None:
                title = _ax_title(window)
                if title:
                    return title
        err, windows = AXUIElementCopyAttributeValue(ax_app, _AX_WINDOWS, None)
        if err == 0 and windows:
            for window in windows:
                title = _ax_title(window)
                if title:
                    return title
    except Exception:
        pass
    return _cg_window_title(pid)


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
