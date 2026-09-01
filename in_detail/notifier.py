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

from . import channels, timefmt
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
    "private": 0x6B7280,   # deliberately dull — it says nothing
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
    "private": "🔒",
    "other": "🖥️",
}


def _timestamp() -> str:
    return timefmt.clock()  # "8:42 pm"


def _youtube_thumbnail(url: str) -> str:
    m = re.search(r"(?:v=|youtu\.be/|/shorts/|/embed/)([\w-]{11})", url or "")
    return f"https://img.youtube.com/vi/{m.group(1)}/hqdefault.jpg" if m else ""


def _domain(url: str) -> str:
    m = re.search(r"https?://(?:www\.)?([^/]+)", url or "")
    return m.group(1) if m else ""


def _discord_channel(title: str) -> tuple[str, str]:
    """Pull '#channel' and 'Server' out of Discord's window/tab title.

    Handles forms like '(3) #general | My Server', '#general | My Server -
    Discord', '@friend | Direct Messages', '@friend - Discord', and the web/DM
    form '(1466) Discord | @friend' where the app name sits on the *left* and
    the conversation on the right. Returns (channel, server)."""
    t = re.sub(r"^\(\d+\)\s*", "", title or "")          # drop unread count
    t = re.sub(r"\s*[-–—]\s*Discord\s*$", "", t).strip()  # drop trailing app name
    if not t or t.lower() == "discord":
        return "", ""                                     # home / friends list
    if "|" in t:
        left, right = (part.strip() for part in t.split("|", 1))
        if left.lower() == "discord":
            # '(1466) Discord | @sam' — the conversation is the interesting half.
            return right, ""
        return left, right
    return t, ""


# Most apps title their window "<what> <sep> <where>": "notifier.py — in-detail",
# "Roadmap – Acme", "report.pdf | Drive". Splitting on the first separator turns a
# flat string into a headline plus context, which is what makes the card read rich.
_TITLE_SEP = re.compile(r"\s+[—–|]\s+|\s+-\s+")

# Trailing app-name noise Chromium/Electron windows append to their titles.
_TITLE_NOISE = re.compile(
    r"\s*[-–—]\s*(High memory usage[^-–—]*|\d+(\.\d+)?\s*[KMG]B)\s*", re.I)


def _split_title(title: str) -> list[str]:
    """Break a window title into its parts, minus the browser's own noise."""
    t = _TITLE_NOISE.sub(" ", title or "").strip()
    t = re.sub(r"^\(\d+\)\s*", "", t)          # unread/notification counter
    return [s.strip() for s in _TITLE_SEP.split(t) if s.strip()]


def _words(*names: str) -> set[str]:
    return {w for n in names for w in re.split(r"\W+", (n or "").lower()) if w}


def _context_of(title: str, *names: str) -> tuple[str, str]:
    """Split a window title into a headline and the context it lives in.

    Apps sign their own windows at the *end* — "notifier.py - in-detail - Visual
    Studio Code", "iota-x/overshare - Brave - ankit". Everything from that
    signature onwards is chrome, not context, so it gets cut; what sits between
    it and the headline ("in-detail") is the part actually worth showing."""
    segments = _split_title(title)
    if not segments:
        return "", ""
    known = _words(*names)
    for i in range(1, len(segments)):        # never cut the headline itself
        if _words(segments[i]) & known:
            segments = segments[:i]
            break
    return segments[0], " — ".join(segments[1:])


def healthy() -> bool:
    """Is delivery working? Answered across every destination in use."""
    return channels.healthy()


def _deliver(content: str = "", embed: dict | None = None) -> bool:
    """Send one card to every destination that's set up.

    Cards are built as Discord embeds throughout — that stays true, because
    every builder already speaks it and it carries more structure than a plain
    string. Channels that aren't Discord render it down themselves.
    """
    return channels.deliver(content, embed)


def send(message: str) -> bool:
    """Plain timestamped line — no embed."""
    return _deliver(f"**{_timestamp()}** · {message}"[:1900])


def post_embed(embed: dict, content: str = "") -> bool:
    """Post a standalone rich embed (used by the recaps)."""
    return _deliver(content, embed)


def describe(snap) -> tuple[str, str, str, str, int]:
    """What this activity *is*, in card-ready pieces.

    Returns (emoji, header, title, context, color) — e.g. ("💬", "Discord",
    "#general", "Gooner hideout", 0x5865F2). The card and the bot's presence
    both read from here so they can never disagree about what you're doing."""
    category = snap.category
    if category == "private":
        # Everything else in here exists to add detail. There isn't any.
        return "🔒", snap.app, snap.app, "", _CATEGORY_COLOR["private"]
    emoji = _CATEGORY_EMOJI.get(category, "🖥️")
    color = _CATEGORY_COLOR.get(category, _CATEGORY_COLOR["other"])
    header = snap.app

    title = snap.tab_title or snap.window_title or snap.app
    url = snap.url or ""
    context = ""

    if category == "discord":
        channel, server = _discord_channel(snap.window_title)
        title = channel or "Discord"
        context = server
    elif category == "browsing":
        # Per-site smarts: brand name, emoji, and colour for known sites. Windows
        # can't read the URL, so fall back to recognising the site by its title.
        site = sites.lookup(url) or sites.lookup_title(snap.tab_title or snap.window_title)
        if site:
            emoji, header, color = site.emoji, site.name, site.color
        else:
            header = _domain(url) or snap.app
        if site and site.name == "Discord":
            # Discord in a tab should read like Discord in the app, not like a URL.
            channel, server = _discord_channel(snap.tab_title)
            if channel:
                title, context = channel, server
        else:
            head, tail = _context_of(title, snap.app, header)
            if head:
                title, context = head, tail
        if not title:
            title = _domain(url) or snap.app
    else:
        # Everything else — editors, terminals, notes, design, chat apps. Their
        # window titles carry the real detail ("file — project", "doc – vault"),
        # so lift the first half into the headline and show the rest as context
        # instead of dumping the raw string or falling back to the bare app name.
        head, tail = _context_of(title, snap.app)
        if head:
            title, context = head, tail

    return emoji, header, title or snap.app, context, color


def presence_label(snap) -> str:
    """Short "playing …" line for the bot's Discord presence."""
    _emoji, header, title, context, _color = describe(snap)
    # Discord reads the same whether it's the app or a tab — the conversation is
    # the whole point, so it stands alone rather than being prefixed by the app.
    if snap.category == "discord" or header == "Discord":
        return f"{title} · {context}" if context else title
    if title and title.lower() != header.lower():
        return f"{header}: {title}"
    return header


def _build_embed(snap, minutes: int) -> dict:
    emoji, header, title, context, color = describe(snap)
    url = snap.url or ""
    description = f"in **{context}**" if context else ""

    embed: dict = {
        "author": {"name": f"{emoji} {header}"},
        "title": title[:250],
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

    # Watch-along: for video sites, invite them to join.
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
    ok = send("test message from Overshare 👋")
    print("sent!" if ok else "failed — check DISCORD_WEBHOOK_URL in .env")
