"""Does this machine have everything the app needs to send an update?

Written because a Windows install got as far as a working test message and then
sent nothing, and there was no way to tell from the outside whether the webhook
was wrong, the app was paused, or the activity backend hadn't loaded at all.

Every check returns the same shape, so the settings page can render them without
knowing what any of them mean:

    Check(name, state, detail, fix)
        state: "good" | "warn" | "bad" | "off"

Pure inspection — nothing here sends a message or changes a setting.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field


@dataclass
class Check:
    name: str
    state: str
    detail: str = ""
    fix: str = ""              # what the reader should do about it
    critical: bool = False     # updates cannot flow without this


def _delivery() -> list[Check]:
    from . import config

    out: list[Check] = []
    hook = (config.DISCORD_WEBHOOK_URL or "").strip()
    if not hook:
        out.append(Check(
            "Discord webhook", "bad", "not set",
            "Setup → paste a webhook link. This is where their cards go.",
            critical=True))
    elif not hook.startswith("https://"):
        out.append(Check("Discord webhook", "bad", "doesn't look like a URL",
                         "Setup → re-copy the webhook link from Discord.",
                         critical=True))
    else:
        out.append(Check("Discord webhook", "good", "set"))

    tg = bool((config.TELEGRAM_BOT_TOKEN or "").strip()
              and str(config.TELEGRAM_CHAT_ID or "").strip())
    out.append(Check("Telegram", "good" if tg else "off",
                     "set up" if tg else "not set up — optional"))
    return out


def _sharing() -> list[Check]:
    from . import config, settings

    paused = bool(settings.get("paused")) or bool(config.START_PAUSED)
    return [Check(
        "Sharing", "warn" if paused else "good",
        "paused — nothing is being sent" if paused else "on",
        "Activity → turn off Pause sharing." if paused else "",
        critical=True)]


def _activity() -> list[Check]:
    """The part that reads what you're doing. Silence here explains everything."""
    out: list[Check] = []

    if sys.platform.startswith("win"):
        from . import _win
        if _win.win32gui is None:
            out.append(Check(
                "Reading your activity", "bad", "pywin32 didn't load",
                "The app can't see any window, so there is nothing to send. "
                "Reinstall from the latest release and report this if it "
                "persists — the log has the details.",
                critical=True))
        else:
            out.append(Check("Reading your activity", "good",
                             "pywin32 loaded — Windows needs no permission for this"))
        out.append(Check(
            "Browser address bar", "good" if _win._auto is not None else "off",
            "uiautomation loaded" if _win._auto is not None
            else "uiautomation not loaded — window titles only, which is usually enough"))
    else:
        from . import _mac
        ok = _mac.permission_ok()
        out.append(Check(
            "Accessibility", "good" if ok else "bad",
            "granted" if ok else "not granted",
            "" if ok else "System Settings → Privacy & Security → Accessibility → "
                          "turn on Overshare, then quit and reopen it.",
            critical=True))

    # The real proof: ask for a snapshot and see whether anything comes back.
    try:
        from . import collectors, config
        snap = collectors.collect()
        if snap.app:
            out.append(Check("Right now it can see", "good", snap.app))
            title = snap.tab_title or snap.window_title
            if not config.REPORT_TITLES:
                out.append(Check("Titles", "off",
                                 "turned off — they get app names only",
                                 "Activity → Window and document titles."))
            elif title:
                out.append(Check("Titles", "good", title[:70]))
            else:
                out.append(Check(
                    "Titles", "warn", "on, but nothing readable from this window",
                    "Some windows genuinely have no title. If it says this for "
                    "every app, the app can't read titles at all — on macOS "
                    "that's Accessibility."))

            # The link and the video thumbnail on a card both come from the URL.
            # Without it a browsing card is just a title, which is the whole of
            # "it showed the video name but no link".
            if snap.category == "browsing":
                if snap.url:
                    out.append(Check("Browser link", "good", snap.url[:70]))
                elif sys.platform.startswith("win") and not config.READ_BROWSER_URL:
                    out.append(Check(
                        "Browser link", "off", "address bar reading is turned off",
                        "Activity → Read the browser address bar. It's what "
                        "gives cards their link and video thumbnail."))
                else:
                    out.append(Check(
                        "Browser link", "warn", "no URL read from this window",
                        "Cards will show the page title but no link or "
                        "thumbnail. Recent activity below says what went wrong."))
        else:
            out.append(Check(
                "Right now it can see", "bad", "nothing",
                "No foreground app is being detected, so no updates can be sent.",
                critical=True))
    except Exception as e:
        out.append(Check("Right now it can see", "bad", f"the check failed: {e}",
                         critical=True))
    return out


# A bot needs to be invited before it can do anything, and the invite link is
# built from the application id — which is the first dot-separated part of the
# token, base64'd. Deriving it means nobody has to go and find it.
BOT_SCOPES = "bot"
# view channels, send messages, embed links, attach files, read history, react
BOT_PERMISSIONS = 117824


def bot_client_id(token: str = "") -> str:
    import base64

    from . import config
    token = (token or config.DISCORD_BOT_TOKEN or "").strip()
    head = token.split(".")[0]
    if not head:
        return ""
    try:
        pad = "=" * (-len(head) % 4)
        raw = base64.b64decode(head + pad).decode("ascii")
        return raw if raw.isdigit() else ""
    except Exception:
        return ""


def bot_invite_url(token: str = "") -> str:
    cid = bot_client_id(token)
    if not cid:
        return ""
    return ("https://discord.com/api/oauth2/authorize"
            f"?client_id={cid}&permissions={BOT_PERMISSIONS}&scope={BOT_SCOPES}")


def _in_tray_app() -> bool:
    """True in the menu-bar/tray process, false in the settings window."""
    import os
    return os.environ.get("OVERSHARE_GUI") != "1"


def _bot() -> list[Check]:
    """The two-way half. Optional, but it fails in confusing ways when half-set."""
    from . import config

    token = (config.DISCORD_BOT_TOKEN or "").strip()
    if not token:
        return [Check("Their replies", "off",
                      "no bot token — they can read cards but not reply. Optional.")]

    out = [Check("Bot token", "good", "set")]

    # Only meaningful inside the tray app; the settings window is a separate
    # process and never runs a bot of its own, so don't claim it's offline there.
    from . import companion
    if companion.enabled() and _in_tray_app():
        out.append(Check(
            "Bot online", "good" if companion.connected() else "bad",
            "connected" if companion.connected() else "not connected",
            "" if companion.connected() else
            "Almost always the privileged intent below. Check the log for the "
            "exact reason Discord gave.",
            critical=False))
    if not bot_client_id(token):
        out.append(Check("Bot token", "warn", "doesn't look like a bot token",
                         "Bot tab → Reset Token, then copy the whole thing."))
    if not str(config.DISCORD_HOME_CHANNEL_ID or "").strip():
        out.append(Check("Their channel", "warn", "no channel id",
                         "Partner → paste the channel the bot should listen in."))
    # There is no way to see the portal's intent switches from here, so this is
    # stated rather than measured — it's the single most common reason a bot
    # connects and then ignores every command.
    out.append(Check(
        "Message Content Intent", "warn", "must be on in the Developer Portal",
        "Developer Portal → your app → Bot → Privileged Gateway Intents → turn on "
        "MESSAGE CONTENT INTENT. Without it the bot starts but never sees a command."))
    return out


def _tray() -> list[Check]:
    """What the *other* process is doing.

    Everything above runs wherever it's called from. The tray app is a separate
    process, and it's the one that actually sends — so a settings window can
    report a perfectly healthy machine while the sender quietly throws on every
    pass. The log is the only channel between them.
    """
    from . import log

    line = log.last_send()
    if not line:
        return [Check(
            "Updates going out", "warn", "nothing in the log yet",
            "Give it a minute with the app in the foreground, then Run again. "
            "If it stays empty, the tray app isn't reaching the send step.")]
    if "send: sent" in line:
        return [Check("Updates going out", "good", line.split("|")[-1].strip()[:70])]
    return [Check("Updates going out", "bad", line[:110],
                  "This is the last thing the sender recorded.", critical=True)]


def run() -> list[Check]:
    """Every check, in the order they matter."""
    out: list[Check] = []
    for part in (_delivery, _sharing, _activity, _bot, _tray):
        try:
            out.extend(part())
        except Exception as e:                       # a broken check is a finding
            out.append(Check(part.__name__.strip("_").title(), "bad",
                             f"couldn't be checked: {e}"))
    return out


def blocking() -> list[Check]:
    """The ones actually stopping updates from going out."""
    return [c for c in run() if c.critical and c.state == "bad"] + \
           [c for c in run() if c.critical and c.state == "warn"]
