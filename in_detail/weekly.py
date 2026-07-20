"""Weekly "Wrapped" — a Sunday summary of the whole week, Spotify-Wrapped style."""

from __future__ import annotations

import datetime as _dt
import json

from . import config, notifier, sites, summarizer
from .history import DailyLog, load as _load_day
from .recap import _hms, _top

_WEEKDAYS = {
    "mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6,
}


def _marker_path():
    return config.DATA_DIR / "weekly.json"


def _last_posted_week() -> str:
    try:
        return json.loads(_marker_path().read_text()).get("last_week", "")
    except Exception:
        return ""


def _mark_posted(week_id: str) -> None:
    try:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        _marker_path().write_text(json.dumps({"last_week": week_id}))
    except Exception:
        pass


def _week_id(d: _dt.date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def _last_7_logs() -> list[DailyLog]:
    today = _dt.date.today()
    logs = []
    for i in range(7):
        day = (today - _dt.timedelta(days=i)).isoformat()
        p = config.DATA_DIR / f"day-{day}.json"
        if p.exists():
            logs.append(_load_day(day))
    return logs


def _merge(target: dict, src: dict) -> None:
    for k, v in src.items():
        target[k] = target.get(k, 0.0) + v


def _aggregate(logs: list[DailyLog]) -> dict:
    agg = {
        "active": 0.0, "by_app": {}, "youtube": {}, "sites": {}, "tracks": {},
        "days_active": 0, "late_nights": 0,
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
        try:
            last_h = _dt.datetime.fromisoformat(log.last_active).hour
            if last_h >= 23 or last_h < 4:
                agg["late_nights"] += 1
        except Exception:
            pass
    return agg


def _stats_text(agg: dict) -> str:
    parts = [
        f"active this week: {_hms(agg['active'])} across {agg['days_active']} days",
        f"late nights: {agg['late_nights']}",
    ]
    apps = _top(agg["by_app"], 3)
    if apps:
        parts.append("top apps: " + ", ".join(f"{k} {_hms(v)}" for k, v in apps))
    if agg["youtube"]:
        parts.append("most-watched: " + ", ".join(k for k, _ in _top(agg["youtube"], 2)))
    if agg["tracks"]:
        parts.append(f"{len(agg['tracks'])} different tracks")
    return "\n".join(parts)


def build_message(logs: list[DailyLog]) -> tuple[str, dict]:
    agg = _aggregate(logs)
    intro = summarizer.recap_intro(_stats_text(agg), period="week")

    end = _dt.date.today()
    start = end - _dt.timedelta(days=6)
    span = f"{start.strftime('%b %-d')} – {end.strftime('%b %-d')}".lower()

    def _lines(items, fmt):
        return "\n".join(fmt(k, v) for k, v in items) or "—"

    fields = [
        {"name": "⏱ total", "value": _hms(agg["active"]), "inline": True},
        {"name": "📅 days on", "value": str(agg["days_active"]), "inline": True},
        {"name": "🌙 late nights", "value": str(agg["late_nights"]), "inline": True},
        {"name": "🖥️ most time in", "value": _lines(_top(agg["by_app"], 5), lambda k, v: f"**{k}** · {_hms(v)}"), "inline": False},
    ]
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


def due() -> bool:
    if not config.WEEKLY_ENABLED:
        return False
    now = _dt.datetime.now()
    if now.weekday() != _WEEKDAYS.get(config.WEEKLY_DAY, 6):
        return False
    try:
        hh, mm = (int(x) for x in config.WEEKLY_TIME.split(":"))
    except Exception:
        hh, mm = 20, 0
    if (now.hour, now.minute) < (hh, mm):
        return False
    return _week_id(now.date()) != _last_posted_week()


def post(force: bool = False) -> bool:
    logs = _last_7_logs()
    if not force and not any(l.active_seconds >= config.RECAP_MIN_MINUTES * 60 for l in logs):
        return False
    _content, embed = build_message(logs)
    ok = notifier.post_embed(embed)
    if ok or not force:
        _mark_posted(_week_id(_dt.date.today()))
    return ok
