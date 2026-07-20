"""Accumulates what you did today so we can post a daily recap.

Time is added in small increments as the app polls. It's persisted to
data/day-YYYY-MM-DD.json so the tally survives restarts/logins.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
from dataclasses import asdict, dataclass, field, fields

from . import config
from .collectors import Snapshot


def _today() -> str:
    return _dt.date.today().isoformat()


def _now_iso() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _add(d: dict, key: str, seconds: float) -> None:
    if key:
        d[key] = d.get(key, 0.0) + seconds


def _domain(url: str) -> str:
    m = re.search(r"https?://(?:www\.)?([^/]+)", url or "")
    return m.group(1) if m else ""


def _is_youtube(url: str) -> bool:
    return "youtube.com" in (url or "") or "youtu.be" in (url or "")


def _clean_yt_title(title: str) -> str:
    return re.sub(r"\s*-\s*YouTube\s*$", "", title or "").strip()


@dataclass
class DailyLog:
    date: str
    active_seconds: float = 0.0
    by_app: dict = field(default_factory=dict)
    by_category: dict = field(default_factory=dict)
    youtube: dict = field(default_factory=dict)   # video title -> seconds
    sites: dict = field(default_factory=dict)     # domain -> seconds
    tracks: dict = field(default_factory=dict)    # "song — artist (app)" -> seconds
    first_active: str = ""
    last_active: str = ""
    recap_posted: bool = False

    def record(self, snap: Snapshot, seconds: float) -> None:
        self.active_seconds += seconds
        _add(self.by_app, snap.app, seconds)
        _add(self.by_category, snap.category, seconds)

        if snap.category == "browsing":
            if _is_youtube(snap.url):
                title = _clean_yt_title(snap.tab_title)
                _add(self.youtube, title or "a video", seconds)
            elif snap.url:
                _add(self.sites, _domain(snap.url), seconds)

        if snap.music:
            _add(self.tracks, snap.music, seconds)

        if not self.first_active:
            self.first_active = _now_iso()
        self.last_active = _now_iso()

    def active_minutes(self) -> float:
        return self.active_seconds / 60.0


def _path(date: str):
    return config.DATA_DIR / f"day-{date}.json"


def load(date: str | None = None) -> DailyLog:
    date = date or _today()
    p = _path(date)
    if p.exists():
        try:
            data = json.loads(p.read_text())
            valid = {f.name for f in fields(DailyLog)}
            return DailyLog(**{k: v for k, v in data.items() if k in valid})
        except Exception:
            pass
    return DailyLog(date=date)


def save(log: DailyLog) -> None:
    # Write to a sibling temp file then atomically rename over the real one. A
    # plain write_text truncates in place, so a crash/kill mid-write (e.g. during
    # a live burst or the midnight rollover) leaves a 0-byte file that load()
    # then silently reads as an empty day — losing everything. os.replace is
    # atomic on the same filesystem, so the day file is always whole or untouched.
    try:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        dest = _path(log.date)
        tmp = dest.with_name(dest.name + f".tmp-{os.getpid()}")
        tmp.write_text(json.dumps(asdict(log), ensure_ascii=False, indent=2))
        os.replace(tmp, dest)
    except Exception:
        try:
            tmp.unlink()
        except Exception:
            pass
