"""Weekly "Wrapped" — a Sunday summary of the whole week, Spotify-Wrapped style."""

from __future__ import annotations

import datetime as _dt
import json

from . import config, notifier, sites, summarizer, timefmt
from .history import DailyLog, load as _load_day
from .recap import _hms, _top

_WEEKDAYS = {
    "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
}


def _marker_path():
    return config.DATA_DIR / "weekly.json"


def _last_posted_week() -> str:
    try:
        return json.loads(_marker_path().read_text(encoding="utf-8")).get("last_week", "")
    except Exception:
        return ""


def _mark_posted(week_id: str) -> None:
    try:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        _marker_path().write_text(json.dumps({"last_week": week_id}), encoding="utf-8")
    except Exception:
        pass


def _week_id(d: _dt.date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def _last_7_logs(end: _dt.date | None = None) -> tuple[list[DailyLog], int]:
    """The seven days ending at `end`, plus how many left no file at all.

    `end` is the day the wrap is *for*, which isn't always today — a machine
    that was off on Sunday posts Sunday's wrap when it next boots, and it should
    still cover Mon–Sun rather than whatever seven days happen to precede the
    boot.

    A missing file is not a quiet day — it means the tally never reached disk.
    Folding those in as zeros silently understates the week, so they're counted
    separately and reported."""
    today = end or _dt.date.today()
    logs, missing = [], 0
    for i in range(7):
        day = (today - _dt.timedelta(days=i)).isoformat()
        p = config.DATA_DIR / f"day-{day}.json"
        if p.exists():
            logs.append(_load_day(day))
        else:
            missing += 1
    return logs, missing


def _merge(target: dict, src: dict) -> None:
    for k, v in src.items():
        target[k] = target.get(k, 0.0) + v


def _aggregate(logs: list[DailyLog]) -> dict:
    agg = {
        "active": 0.0, "by_app": {}, "youtube": {}, "sites": {}, "tracks": {},
        "days_active": 0, "late_nights": 0,
        "pokes": 0, "messages_from_partner": 0, "peeks": 0,
        "permissions_asked": 0, "permissions_approved": 0,
    }
    for log in logs:
        if log.active_seconds < config.RECAP_MIN_MINUTES * 60:
            continue
        agg["days_active"] += 1
        agg["active"] += log.active_seconds
        _merge(agg["by_app"], log.by_app)
        _merge(agg["youtube"], log.youtube)
        _merge(agg["sites"], log.sites)
        _merge(agg["tracks"], log.tracks)
        agg["pokes"] += log.pokes
        agg["messages_from_partner"] += log.messages_from_partner
        agg["peeks"] += log.peeks
        agg["permissions_asked"] += log.permissions_asked
        agg["permissions_approved"] += log.permissions_approved
        try:
            last_h = _dt.datetime.fromisoformat(log.last_active).hour
            if last_h >= 23 or last_h < 4:
                agg["late_nights"] += 1
        except Exception:
            pass
    return agg


def _love_score(agg: dict) -> int:
    return agg["pokes"] * 2 + agg["messages_from_partner"] * 3 + agg["peeks"] + agg["permissions_approved"] * 2


def _stats_text(agg: dict, missing: int = 0) -> str:
    parts = [
        f"active this week: {_hms(agg['active'])} across {agg['days_active']} days",
        f"late nights: {agg['late_nights']}",
    ]
    if missing:
        parts.append(f"note: {missing} day(s) have no recorded data at all — the "
                     f"totals below cover only the days that were logged, so don't "
                     f"describe the week as quiet or lazy")
    if _love_score(agg):
        parts.append(f"they reached out {agg['pokes'] + agg['messages_from_partner'] + agg['peeks']} times this week")
    apps = _top(agg["by_app"], 3)
    if apps:
        parts.append("top apps: " + ", ".join(f"{k} {_hms(v)}" for k, v in apps))
    if agg["youtube"]:
        parts.append("most-watched: " + ", ".join(k for k, _ in _top(agg["youtube"], 2)))
    if agg["tracks"]:
        parts.append(f"{len(agg['tracks'])} different tracks")
    return "\n".join(parts)


def build_message(logs: list[DailyLog], missing: int = 0,
                  end: _dt.date | None = None) -> tuple[str, dict]:
    agg = _aggregate(logs)
    intro = summarizer.recap_intro(_stats_text(agg, missing), period="week")

    end = end or _dt.date.today()
    start = end - _dt.timedelta(days=6)
    span = f"{timefmt.day(start)} – {timefmt.day(end)}"

    def _lines(items, fmt):
        return "\n".join(fmt(k, v) for k, v in items) or "—"

    fields = [
        {"name": "⏱ total", "value": _hms(agg["active"]), "inline": True},
        {"name": "📅 days on", "value": str(agg["days_active"]), "inline": True},
        {"name": "🌙 late nights", "value": str(agg["late_nights"]), "inline": True},
    ]
    if missing:
        fields.append({"name": "⚠️ not recorded",
                       "value": f"{missing} day(s) had no saved data", "inline": True})
    if _love_score(agg):
        love_bits = []
        if agg["messages_from_partner"]:
            love_bits.append(f"{agg['messages_from_partner']} messages")
        if agg["pokes"]:
            love_bits.append(f"{agg['pokes']} pokes")
        if agg["peeks"]:
            love_bits.append(f"{agg['peeks']} peeks")
        if agg["permissions_asked"]:
            love_bits.append(f"{agg['permissions_approved']}/{agg['permissions_asked']} asks approved")
        fields.append({"name": "💛 love-o-meter", "value": f"{', '.join(love_bits)} · score {_love_score(agg)}", "inline": True})
    fields.append({"name": "🖥️ most time in", "value": _lines(_top(agg["by_app"], 5), lambda k, v: f"**{k}** · {_hms(v)}"), "inline": False})
    if agg["youtube"]:
        fields.append({"name": "📺 top watches", "value": _lines(
            _top(agg["youtube"], 4),
            lambda k, v: f"**{(k[:46] + '…') if len(k) > 46 else k}** · {_hms(v)}"), "inline": False})
    if agg["sites"]:
        fields.append({"name": "🌐 top sites", "value": _lines(
            _top(agg["sites"], 4), lambda k, v: f"{sites.label(k)} · {_hms(v)}"), "inline": False})
    if agg["tracks"]:
        fields.append({"name": "🎧 on repeat", "value": _lines(
            _top(agg["tracks"], 3), lambda k, v: f"**{k}** · {_hms(v)}"), "inline": False})

    embed = {
        "title": f"🗓️ my week — {span}",
        "description": intro,
        "color": 0xEC4899,
        "fields": fields,
        "footer": {"text": "in detail · weekly wrapped"},
        "timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(),
    }
    return "", embed


def last_occurrence(now: _dt.datetime | None = None) -> _dt.datetime:
    """The most recent moment the wrap was supposed to go out, at or before now."""
    now = now or _dt.datetime.now()
    target = _WEEKDAYS.get(config.WEEKLY_DAY, 6)
    try:
        hh, mm = (int(x) for x in config.WEEKLY_TIME.split(":"))
    except Exception:
        hh, mm = 20, 0
    back = (now.weekday() - target) % 7
    when = now.replace(hour=hh, minute=mm, second=0, microsecond=0) \
              - _dt.timedelta(days=back)
    if when > now:                      # today is the day but the hour hasn't come
        when -= _dt.timedelta(days=7)
    return when


# Set by post(), read by due(), so a failing send retries on a sane cadence
# instead of every tick.
_last_attempt: _dt.datetime | None = None
_RETRY_AFTER = _dt.timedelta(minutes=15)


def due() -> bool:
    """Has a scheduled wrap gone unsent?

    Deliberately *not* "is it Sunday evening right now" — that only ever fired
    if the machine happened to be awake in that minute. A Windows box that's off
    all Sunday would skip the week entirely, and a Mac asleep at the time would
    too. Asking whether the last scheduled moment has passed unposted survives
    any amount of downtime.
    """
    if not config.WEEKLY_ENABLED:
        return False
    now = _dt.datetime.now()
    if _week_id(last_occurrence(now).date()) == _last_posted_week():
        return False
    if _last_attempt and now - _last_attempt < _RETRY_AFTER:
        return False
    return True


def post(force: bool = False, end: _dt.date | None = None) -> bool:
    global _last_attempt
    _last_attempt = _dt.datetime.now()
    # A scheduled catch-up reports the week that ended at its own due date, not
    # the week ending whenever the machine came back.
    end = end or (_dt.date.today() if force else last_occurrence().date())
    logs, missing = _last_7_logs(end)
    if not force and not any(l.active_seconds >= config.RECAP_MIN_MINUTES * 60 for l in logs):
        _mark_posted(_week_id(end))   # genuinely nothing to say; don't retry all week
        return False
    _content, embed = build_message(logs, missing, end)
    ok = notifier.post_embed(embed)
    if ok:
        # Only on success. Marking a failed send as posted used to lose the
        # week to a single flaky request.
        _mark_posted(_week_id(end))
    return ok
