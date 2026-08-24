"""Discord delivery — the webhook, and their DMs via the bot.

This is the original sender, lifted out of notifier.py unchanged so the fan-out
in __init__.py has something uniform to talk to.
"""

from __future__ import annotations

import requests

from .. import config, settings

_fail_streak = 0  # consecutive webhook post failures (for the health indicator)


def configured() -> bool:
    return bool(config.DISCORD_WEBHOOK_URL)


def enabled() -> bool:
    return bool(config.DISCORD_ENABLED) and configured()


def healthy() -> bool:
    return _fail_streak < 3


def _post(payload: dict) -> bool:
    global _fail_streak
    if not config.DISCORD_WEBHOOK_URL:
        return False
    payload.setdefault("username", config.WEBHOOK_USERNAME)
    payload.setdefault("allowed_mentions", {"parse": []})
    if config.WEBHOOK_AVATAR_URL:
        payload.setdefault("avatar_url", config.WEBHOOK_AVATAR_URL)
    try:
        r = requests.post(config.DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        code = r.status_code
    except Exception:
        code = 0
    ok = code in (200, 204)
    if code == 429:
        pass  # rate-limited but reachable — not a health failure
    elif ok:
        _fail_streak = 0
    else:
        _fail_streak += 1
    return ok


def send(content: str = "", embed: dict | None = None) -> bool:
    """Send to wherever they've chosen: the channel, their DMs, or both."""
    if not enabled():
        return False
    dest = settings.get("card_destination")  # channel | dm | both
    sent = False
    if dest in ("channel", "both"):
        payload: dict = {}
        if content:
            payload["content"] = content[:1900]
        if embed:
            payload["embeds"] = [embed]
        if payload:
            sent = _post(payload)
    if dest in ("dm", "both") and config.PARTNER_PRIMARY_ID:
        try:
            from .. import companion
            if companion.enabled():
                companion.dm_user(config.PARTNER_PRIMARY_ID, content, embed)
                sent = True
        except Exception:
            pass
    return sent
