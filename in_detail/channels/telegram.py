"""Telegram delivery.

The cards are built as Discord embed dicts everywhere in this app, and that's
worth keeping — every card builder already speaks it. So rather than inventing a
neutral format and rewriting all of them, this renders an embed into Telegram's
HTML and sends it. The mapping is close enough that nothing is lost: title and
fields become bold headings, and an embed image becomes a real photo.
"""

from __future__ import annotations

import html
import re

import requests

from .. import config

_API = "https://api.telegram.org/bot{token}/{method}"
_TIMEOUT = 10
# Telegram's caption limit is 1024; a plain message is 4096.
_CAPTION_MAX = 1024
_TEXT_MAX = 4096

_fail_streak = 0


def configured() -> bool:
    return bool(config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID)


def enabled() -> bool:
    return bool(config.TELEGRAM_ENABLED) and configured()


def healthy() -> bool:
    return _fail_streak < 3


# --- Rendering ----------------------------------------------------------------
# Discord markdown and Telegram HTML overlap badly, so translate rather than
# passing text through and hoping.
_BOLD = re.compile(r"\*\*(.+?)\*\*", re.S)
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def _inline(text: str) -> str:
    """Discord-flavoured markdown -> Telegram HTML, escaped."""
    if not text:
        return ""
    # Pull links out first so their URLs don't get escaped into uselessness.
    placeholders: list[tuple[str, str]] = []

    def _stash(m: re.Match) -> str:
        placeholders.append((m.group(1), m.group(2)))
        return f"\x00{len(placeholders) - 1}\x00"

    text = _LINK.sub(_stash, text)
    text = html.escape(text)
    text = _BOLD.sub(lambda m: f"<b>{m.group(1)}</b>", text)
    for i, (label, url) in enumerate(placeholders):
        text = text.replace(
            f"\x00{i}\x00", f'<a href="{html.escape(url, quote=True)}">{html.escape(label)}</a>')
    return text


def render(embed: dict | None, content: str = "") -> tuple[str, str]:
    """(html_message, image_url). Either may be empty."""
    lines: list[str] = []
    if content:
        lines.append(_inline(content))

    embed = embed or {}
    title = embed.get("title") or ""
    url = embed.get("url") or ""
    if title:
        heading = _inline(title)
        if url:
            heading = f'<a href="{html.escape(url, quote=True)}">{heading}</a>'
        lines.append(f"<b>{heading}</b>")

    if embed.get("description"):
        lines.append(_inline(embed["description"]))

    for field in embed.get("fields", []):
        name, value = field.get("name", ""), field.get("value", "")
        if not (name or value):
            continue
        lines.append("")                      # blank line keeps fields readable
        if name:
            lines.append(f"<b>{_inline(name)}</b>")
        if value:
            lines.append(_inline(value))

    footer = (embed.get("footer") or {}).get("text", "")
    if footer:
        lines.append("")
        lines.append(f"<i>{_inline(footer)}</i>")

    image = (embed.get("image") or {}).get("url") or \
            (embed.get("thumbnail") or {}).get("url") or ""
    return "\n".join(lines).strip(), image


# --- Sending -------------------------------------------------------------------
def _call(method: str, payload: dict, files: dict | None = None) -> bool:
    global _fail_streak
    try:
        r = requests.post(
            _API.format(token=config.TELEGRAM_BOT_TOKEN, method=method),
            data=payload, files=files, timeout=_TIMEOUT)
        ok = r.status_code == 200
        code = r.status_code
    except Exception:
        ok, code = False, 0
    if code == 429:
        pass                    # rate-limited but reachable — not a health failure
    elif ok:
        _fail_streak = 0
    else:
        _fail_streak += 1
    return ok


def send(content: str = "", embed: dict | None = None) -> bool:
    if not enabled():
        return False
    text, image = render(embed, content)
    if not text and not image:
        return False

    base = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }
    if image:
        # A photo carries its text as a caption, which is capped much lower —
        # fall back to a plain message rather than silently truncating a recap.
        if len(text) <= _CAPTION_MAX:
            return _call("sendPhoto", {**base, "photo": image, "caption": text})
        if _call("sendPhoto", {**base, "photo": image}):
            return _call("sendMessage", {**base, "text": text[:_TEXT_MAX]})
        return False
    return _call("sendMessage", {**base, "text": text[:_TEXT_MAX]})


def send_photo(path: str, caption: str = "") -> bool:
    """Upload a local file — the webcam/screen peeks."""
    if not enabled():
        return False
    try:
        with open(path, "rb") as fh:
            return _call(
                "sendPhoto",
                {"chat_id": config.TELEGRAM_CHAT_ID, "caption": _inline(caption)[:_CAPTION_MAX],
                 "parse_mode": "HTML"},
                files={"photo": fh},
            )
    except OSError:
        return False
