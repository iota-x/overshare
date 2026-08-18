"""Per-site smarts: recognise popular sites and give them a name, emoji, a
natural verb ("watching"/"scrolling"/…), and a brand colour, so browsing
updates read richer than a generic "on Brave".
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Site:
    name: str
    emoji: str
    verb: str      # how you "do" this site: watching / scrolling / reading …
    color: int     # brand-ish embed colour


# First match wins; keys are matched as substrings of the lowercased URL.
_TABLE: list[tuple[tuple[str, ...], Site]] = [
    (("youtube.com", "youtu.be"), Site("YouTube", "📺", "watching", 0xFF0033)),
    (("twitch.tv",), Site("Twitch", "🟣", "watching", 0x9146FF)),
    (("netflix.com",), Site("Netflix", "🎬", "watching", 0xE50914)),
    (("primevideo.com", "amazon.com/gp/video"), Site("Prime Video", "🎬", "watching", 0x00A8E1)),
    (("disneyplus.com", "hotstar.com"), Site("Disney+ / Hotstar", "🎬", "watching", 0x113CCF)),
    (("crunchyroll.com",), Site("Crunchyroll", "🍥", "watching", 0xF47521)),
    (("reddit.com",), Site("Reddit", "👽", "scrolling", 0xFF4500)),
    (("twitter.com", "x.com"), Site("X", "🐦", "scrolling", 0x1DA1F2)),
    (("instagram.com",), Site("Instagram", "📸", "scrolling", 0xE1306C)),
    (("tiktok.com",), Site("TikTok", "🎵", "scrolling", 0x69C9D0)),
    (("facebook.com",), Site("Facebook", "👥", "scrolling", 0x1877F2)),
    (("github.com",), Site("GitHub", "🐙", "on", 0x6E5494)),
    (("stackoverflow.com", "stackexchange.com"), Site("Stack Overflow", "🧠", "on", 0xF48024)),
    (("mail.google.com", "gmail.com", "outlook."), Site("email", "📧", "checking", 0xEA4335)),
    (("docs.google.com", "sheets.google.com", "slides.google.com"), Site("Google Docs", "📝", "on", 0x4285F4)),
    (("notion.so",), Site("Notion", "📝", "on", 0x64748B)),
    (("chatgpt.com", "chat.openai.com"), Site("ChatGPT", "🤖", "chatting with", 0x10A37F)),
    (("claude.ai",), Site("Claude", "🤖", "chatting with", 0xCC785C)),
    (("open.spotify.com",), Site("Spotify", "🎧", "listening on", 0x1DB954)),
    (("soundcloud.com",), Site("SoundCloud", "🔊", "listening on", 0xFF5500)),
    (("music.youtube.com",), Site("YouTube Music", "🎧", "listening on", 0xFF0033)),
    (("wikipedia.org",), Site("Wikipedia", "📚", "reading", 0x94A3B8)),
    (("amazon.", "flipkart.com"), Site("shopping", "🛒", "shopping on", 0xFF9900)),
    (("linkedin.com",), Site("LinkedIn", "💼", "on", 0x0A66C2)),
    (("google.com/search", "google.com/webhp", "bing.com/search"), Site("a search", "🔍", "searching", 0x4285F4)),
    (("discord.com", "discordapp.com"), Site("Discord", "💬", "on", 0x5865F2)),
]


_BY_NAME = {site.name.lower(): site for _keys, site in _TABLE}

# Windows has no clean cross-browser way to read the URL, so the tab title is
# all we get. Browsers still sign the title with the site's own name, which is
# enough to recover the brand, emoji and colour a URL would have given us.
_TITLE_HINTS: tuple[tuple[str, str], ...] = (
    ("youtube music", "YouTube Music"),
    ("youtube", "YouTube"),
    ("twitch", "Twitch"),
    ("netflix", "Netflix"),
    ("prime video", "Prime Video"),
    ("hotstar", "Disney+ / Hotstar"),
    ("disney+", "Disney+ / Hotstar"),
    ("crunchyroll", "Crunchyroll"),
    ("reddit", "Reddit"),
    ("instagram", "Instagram"),
    ("tiktok", "TikTok"),
    ("facebook", "Facebook"),
    ("github", "GitHub"),
    ("stack overflow", "Stack Overflow"),
    ("gmail", "email"),
    ("outlook", "email"),
    ("google docs", "Google Docs"),
    ("notion", "Notion"),
    ("chatgpt", "ChatGPT"),
    ("soundcloud", "SoundCloud"),
    ("spotify", "Spotify"),
    ("wikipedia", "Wikipedia"),
    ("linkedin", "LinkedIn"),
    ("discord", "Discord"),
)

_SEGMENT = re.compile(r"\s+[—–|]\s+|\s+-\s+")


def lookup_title(title: str) -> Site | None:
    """Recognise the site from a tab title, for when there's no URL to go on.

    Only the first and last segments count: a video *called* "I love Netflix"
    is not Netflix, but "… - YouTube" and "Discord | @her" are."""
    t = re.sub(r"^\(\d+\)\s*", "", (title or "").strip()).lower()
    if not t:
        return None
    segments = [s.strip() for s in _SEGMENT.split(t) if s.strip()]
    if not segments:
        return None
    edges = {segments[0], segments[-1]}
    for hint, name in _TITLE_HINTS:
        if any(hint in edge for edge in edges):
            return _BY_NAME.get(name.lower())
    return None


def lookup(url: str) -> Site | None:
    u = (url or "").lower()
    if not u:
        return None
    for keys, site in _TABLE:
        if any(k in u for k in keys):
            return site
    return None


def label(url_or_domain: str) -> str:
    """'📺 YouTube' for a known site, else the bare domain/text."""
    site = lookup(url_or_domain)
    return f"{site.emoji} {site.name}" if site else url_or_domain
