"""Posts to the shared Discord channel.

Two shapes:
  send(text)                 - a plain one-line message (used by the self-test)
  send_update(msg, snap, ..) - a RICH embed: clickable link, YouTube thumbnail,
                               Discord channel/server, "now playing", duration,
                               color-coded by what you're doing.
"""

from __future__ import annotations

import datetime as _dt
import re

import requests

from . import config
from . import settings
from . import sites

# Embed colour per activity category.
_CATEGORY_COLOR = {
    "coding": 0x3B82F6,    # blue
    "terminal": 0x22C55E,  # green
    "browsing": 0xEF4444,  # red
    "discord": 0x5865F2,   # blurple
    "chat": 0x5865F2,
    "music": 0x1DB954,     # spotify green
    "gaming": 0xA855F7,    # purple
    "notes": 0xF59E0B,     # amber
    "design": 0xEC4899,    # pink
    "other": 0x9CA3AF,     # grey
}

_CATEGORY_EMOJI = {
    "coding": "💻",
    "terminal": "⌨️",
    "browsing": "🌐",
    "discord": "💬",
    "chat": "💬",
    "music": "🎵",
    "gaming": "🎮",
    "notes": "📝",
    "design": "🎨",
    "other": "🖥️",
}


def _timestamp() -> str:
    return _dt.datetime.now().strftime("%-I:%M %p").lower()  # "8:42 pm"


def _youtube_thumbnail(url: str) -> str:
    m = re.search(r"(?:v=|youtu\.be/|/shorts/|/embed/)([\w-]{11})", url or "")
    return f"https://img.youtube.com/vi/{m.group(1)}/hqdefault.jpg" if m else ""


def _domain(url: str) -> str:
    m = re.search(r"https?://(?:www\.)?([^/]+)", url or "")
    return m.group(1) if m else ""


def _discord_channel(title: str) -> tuple[str, str]:
    """Pull '#channel' and 'Server' out of Discord's window title.

    Handles forms like '(3) #general | My Server', '#general | My Server -
    Discord', '@friend | Direct Messages'. Returns (channel, server)."""
    t = re.sub(r"^\(\d+\)\s*", "", title or "")          # drop unread count
    t = re.sub(r"\s*[-–—]\s*Discord\s*$", "", t).strip()  # drop trailing app name
    if "|" in t:
        left, right = t.split("|", 1)
        return left.strip(), right.strip()
    return t.strip(), ""


_fail_streak = 0  # consecutive webhook post failures (for the health indicator)


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


def _deliver(content: str = "", embed: dict | None = None) -> bool:
    """Send to wherever she's chosen: the channel, her DMs, or both."""
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
    if dest in ("dm", "both") and config.HER_PRIMARY_ID:
        try:
            from . import companion
            if companion.enabled():
                companion.dm_user(config.HER_PRIMARY_ID, content, embed)
                sent = True
        except Exception:
            pass
    return sent


def send(message: str) -> bool:
    """Plain timestamped line — no embed."""
    return _deliver(f"**{_timestamp()}** · {message}"[:1900])


def post_embed(embed: dict, content: str = "") -> bool:
    """Post a standalone rich embed (used by the recaps)."""
    return _deliver(content, embed)


def _build_embed(snap, minutes: int) -> dict:
    category = snap.category
    emoji = _CATEGORY_EMOJI.get(category, "🖥️")
    color = _CATEGORY_COLOR.get(category, _CATEGORY_COLOR["other"])
    header = snap.app

    # Headline (embed title) + clickable link, tuned per activity.
    title = snap.tab_title or snap.window_title or snap.app
    url = snap.url or ""
    description = ""

    if category == "discord":
        channel, server = _discord_channel(snap.window_title)
        title = channel or "Discord"
        description = f"in **{server}**" if server else ""
    elif category == "browsing":
        # Per-site smarts: brand name, emoji, and colour for known sites.
        site = sites.lookup(url)
        if site:
            emoji, header, color = site.emoji, site.name, site.color
        else:
            header = _domain(url) or snap.app
        if not title:
            title = _domain(url) or snap.app
    elif category in ("coding", "terminal"):
        # window titles are often "file — project"; keep as-is, it's informative
        pass

    embed: dict = {
        "author": {"name": f"{emoji} {header}"},
        "title": (title or snap.app)[:250],
        "color": color,
        "footer": {"text": "in detail"},
        "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(),
    }
    if description:
        embed["description"] = description[:400]
    if url.startswith("http"):
        embed["url"] = url
    thumb = _youtube_thumbnail(url)
    if thumb:
        embed["thumbnail"] = {"url": thumb}

    fields = []
    if snap.music:
        # Listen-along: make the track a play link when we have one.
        val = snap.music[:200]
        if snap.music_url:
            val = f"[{val}]({snap.music_url})"
        fields.append({"name": "🎧 also playing", "value": val, "inline": True})
    if minutes >= 1:
        fields.append({"name": "⏱ for", "value": f"{minutes} min", "inline": True})

    # Watch-along: for video sites, invite her to join.
    site = sites.lookup(url)
    if site and site.verb == "watching" and url.startswith("http"):
        fields.append({"name": "▶️ watch along", "value": f"[join me on {site.name}]({url})", "inline": False})

    mood = settings.get("mood")
    if mood:
        fields.append({"name": "💭 mood", "value": mood[:100], "inline": True})

    if fields:
        embed["fields"] = fields

    return embed


def send_update(message: str, snap, minutes: int = 0, kind: str = "change") -> bool:
    """Rich update. 'away'/'back' stay plain — no card needed for those."""
    content = f"**{_timestamp()}** · {message}"[:1900]
    if snap is None or kind in ("away", "back", "morning", "night", "all_yours"):
        return _deliver(content)
    return _deliver(content, _build_embed(snap, minutes))


if __name__ == "__main__":
    ok = send("test message from in-detail 👋")
    print("sent!" if ok else "failed — check DISCORD_WEBHOOK_URL in .env")
