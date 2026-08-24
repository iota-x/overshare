"""Builds and posts the end-of-day recap card."""

from __future__ import annotations

import datetime as _dt

from . import config, history, notifier, sites, summarizer, timefmt
from .history import DailyLog, load as _load_day


def _streak() -> int:
    """Consecutive days (ending today) with real activity."""
    n = 0
    for i in range(365):
        day = (_dt.date.today() - _dt.timedelta(days=i)).isoformat()
        if not (config.DATA_DIR / f"day-{day}.json").exists():
            break
        if _load_day(day).active_seconds < config.RECAP_MIN_MINUTES * 60:
            break
        n += 1
    return n


def _hms(seconds: float) -> str:
    s = int(seconds)
    h, m = s // 3600, (s % 3600) // 60
    if h and m:
        return f"{h}h {m}m"
    if h:
        return f"{h}h"
    return f"{m}m" if m else "<1m"


def _clock(iso: str) -> str:
    try:
        return timefmt.clock(_dt.datetime.fromisoformat(iso))
    except Exception:
        return ""


def _top(d: dict, n: int) -> list[tuple[str, float]]:
    return sorted(d.items(), key=lambda kv: -kv[1])[:n]


def _lines(items: list[tuple[str, float]], trunc: int = 48) -> str:
    out = []
    for name, secs in items:
        label = (name[:trunc] + "…") if len(name) > trunc else name
        out.append(f"**{label}** · {_hms(secs)}")
    return "\n".join(out) or "—"


def _stats_text(log: DailyLog) -> str:
    parts = [f"active time: {_hms(log.active_seconds)}"]
    if history.save_error:
        parts.append("note: part of today's tally failed to save, so these "
                     "numbers are incomplete — don't call the day quiet")
    apps = _top(log.by_app, 4)
    if apps:
        parts.append("top apps: " + ", ".join(f"{k} {_hms(v)}" for k, v in apps))
    if log.youtube:
        vids = _top(log.youtube, 3)
        parts.append("watched: " + ", ".join(k for k, _ in vids))
    if log.tracks:
        parts.append(f"had music on for a while ({len(log.tracks)} tracks)")
    if log.love_score():
        parts.append(f"they reached out {log.pokes + log.messages_from_partner + log.peeks} times today")
    return "\n".join(parts)


def _love_line(log: DailyLog) -> str:
    bits = []
    if log.messages_from_partner:
        bits.append(f"{log.messages_from_partner} msg" + ("s" if log.messages_from_partner != 1 else ""))
    if log.pokes:
        bits.append(f"{log.pokes} poke" + ("s" if log.pokes != 1 else ""))
    if log.peeks:
        bits.append(f"{log.peeks} peek" + ("s" if log.peeks != 1 else ""))
    if log.permissions_asked:
        bits.append(f"{log.permissions_approved}/{log.permissions_asked} asks approved")
    return (", ".join(bits) + f" · score {log.love_score()}") if bits else "quiet day 🤍"


def build_message(log: DailyLog) -> tuple[str, dict]:
    """Returns (content, embed) for the recap."""
    intro = summarizer.recap_intro(_stats_text(log))

    pretty_date = timefmt.weekday(_dt.date.fromisoformat(log.date))

    fields = [{"name": "⏱ active", "value": _hms(log.active_seconds), "inline": True}]
    if log.first_active and log.last_active:
        span = f"{_clock(log.first_active)} → {_clock(log.last_active)}"
        fields.append({"name": "🕐 span", "value": span, "inline": True})
    streak = _streak()
    if streak >= 2:
        fields.append({"name": "🔥 streak", "value": f"{streak} days", "inline": True})
    if log.love_score():
        fields.append({"name": "💛 love-o-meter", "value": _love_line(log), "inline": True})
    if history.save_error:
        fields.append({"name": "⚠️ incomplete",
                       "value": "some of today's tally didn't save", "inline": True})

    fields.append({"name": "🖥️ where the time went", "value": _lines(_top(log.by_app, 5)), "inline": False})
    if log.youtube:
        fields.append({"name": "📺 watched", "value": _lines(_top(log.youtube, 4)), "inline": False})
    if log.sites:
        site_lines = "\n".join(
            f"{sites.label(dom)} · {_hms(secs)}" for dom, secs in _top(log.sites, 4)
        )
        fields.append({"name": "🌐 top sites", "value": site_lines or "—", "inline": False})
    if log.tracks:
        fields.append({"name": "🎧 soundtrack", "value": _lines(_top(log.tracks, 3)), "inline": False})

    embed = {
        "title": f"📊 my day — {pretty_date}",
        "description": intro,
        "color": 0x8B5CF6,
        "fields": fields,
        "footer": {"text": "in detail · daily recap"},
        "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(),
    }
    return "", embed


def due(log: DailyLog) -> bool:
    """Is it time to auto-post today's recap?"""
    if not config.RECAP_ENABLED or log.recap_posted:
        return False
    if log.active_minutes() < config.RECAP_MIN_MINUTES:
        return False
    try:
        hh, mm = (int(x) for x in config.RECAP_TIME.split(":"))
    except Exception:
        hh, mm = 23, 0
    now = _dt.datetime.now()
    return (now.hour, now.minute) >= (hh, mm)


def post(log: DailyLog) -> bool:
    """Build + send the recap. Returns True on success."""
    _content, embed = build_message(log)
    return notifier.post_embed(embed)


def worth_finalizing(log: DailyLog) -> bool:
    """On day-rollover: post yesterday's recap if it never went out."""
    return (
        config.RECAP_ENABLED
        and not log.recap_posted
        and log.active_minutes() >= config.RECAP_MIN_MINUTES
    )


def catch_up(max_days: int = 3) -> int:
    """Post recaps for days that ended while the app wasn't running.

    The normal path finalises a day when the clock rolls past midnight *with the
    app open*. That mostly holds on a Mac, which sleeps rather than shuts down —
    but a Windows machine gets switched off for the night, so the rollover never
    happens and yesterday's recap is simply lost. Nothing looks at that log again.

    So on startup, sweep the last few days and send anything that ended unposted.
    Only the most recent is actually sent — coming back from a week away
    shouldn't dump seven cards in their channel — but the others are marked too,
    so they can't pile up and arrive as a batch weeks later.

    Returns how many were sent (0 or 1).
    """
    if not config.RECAP_ENABLED:
        return 0

    today = _dt.date.today()
    pending: list[DailyLog] = []
    for i in range(1, max_days + 1):
        day = (today - _dt.timedelta(days=i)).isoformat()
        if not (config.DATA_DIR / f"day-{day}.json").exists():
            continue
        log = _load_day(day)
        if worth_finalizing(log):
            pending.append(log)

    if not pending:
        return 0

    pending.sort(key=lambda l: l.date, reverse=True)   # newest first
    newest, older = pending[0], pending[1:]

    for log in older:            # too stale to be worth sending; retire quietly
        log.recap_posted = True
        history.save(log)

    newest.recap_posted = True   # mark before sending, so a crash can't double-post
    history.save(newest)
    return 1 if post(newest) else 0
