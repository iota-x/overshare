"""Per-site smarts: recognise popular sites and give them a name, emoji, a
natural verb ("watching"/"scrolling"/…), and a brand colour, so browsing
updates read richer than a generic "on Brave".
"""

from __future__ import annotations

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
