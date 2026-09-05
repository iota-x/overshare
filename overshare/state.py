"""The little state machine that decides *when* to send an update.

Rules, in plain english:
  - When you switch to something new, wait until it's stuck around for
    STABILIZE seconds (so flicking between windows doesn't spam them).
  - Don't send change-updates closer together than MIN_GAP.
  - If nothing changes, send a "still doing X" heartbeat every HEARTBEAT.
  - When you go idle for IDLE_THRESHOLD, say you stepped away — once — and say
    "back" when you return.
"""

from __future__ import annotations

import datetime as _dt
import time
from dataclasses import dataclass

from . import config
from .collectors import Snapshot


@dataclass
class Decision:
    should_send: bool = False
    kind: str = "change"          # change | heartbeat | away | back
    minutes: int = 0
    snapshot: Snapshot | None = None


def _lingerable(snap: Snapshot) -> bool:
    """Is this the kind of thing it makes sense to say someone lingered ON?

    A specific piece of content you sit with — a post, an article, a reel, a
    video — always has a URL, and that URL is also the link worth sending. An
    app with no URL (your editor, a terminal) is where you *live*, not something
    you linger on, so dwelling there would just nag.
    """
    return bool(snap.url)


def _scrollable(snap: Snapshot) -> bool:
    """A feed you scroll, where lots of quick changes mean a rabbit hole rather
    than deliberate reading. Any browsing counts; a code editor or a document
    never does."""
    return snap.category == "browsing"


class Tracker:
    def __init__(self) -> None:
        now = time.monotonic()
        self.last_sig: str = ""
        self.last_sent_at: float = 0.0
        self.pending_sig: str = ""
        self.pending_since: float = now
        self.away_announced: bool = False
        self.away_since: float = 0.0
        self.last_snapshot: Snapshot | None = None
        # Dwell escalates in tiers on the SAME thing: the item we're timing,
        # and the deepest tier already announced for it (0 none, 1 lingering,
        # 2 properly deep). Reset when the item changes.
        self.dwell_sig: str = ""
        self.dwell_level: int = 0
        # Rabbit hole: timestamps of recent browsing *changes*. Many in a short
        # window is scrolling, not lingering. `_last_rabbit` throttles it.
        self._churn: list[float] = []
        self._last_rabbit: float = 0.0

    def evaluate(self, snap: Snapshot) -> Decision:
        now = time.monotonic()
        self.last_snapshot = snap
        idle = snap.idle_seconds >= config.IDLE_THRESHOLD

        # --- away / back handling -------------------------------------------
        if idle:
            if not self.away_announced:
                self.away_announced = True
                self.away_since = now
                self.last_sent_at = now
                hour = _dt.datetime.now().hour
                kind = "night" if (hour >= 22 or hour < 5) else "away"
                return Decision(True, kind, 0, snap)
            return Decision(False)  # already told them, stay quiet

        just_back = False
        back_kind = "back"
        if self.away_announced:
            # Coming back from idle — reset so the current activity is "new".
            away_dur = now - self.away_since if self.away_since else 0.0
            hour = _dt.datetime.now().hour
            # A long gap (overnight) or an early-morning return reads as waking up.
            if away_dur >= config.LONG_AWAY_SECONDS or (4 <= hour <= 11 and away_dur >= 3600):
                back_kind = "morning"
            self.away_announced = False
            just_back = True
            self.pending_sig = ""

        # --- track the current activity -------------------------------------
        sig = snap.signature()
        if sig != self.pending_sig:
            self.pending_sig = sig
            self.pending_since = now

        minutes = int((now - self.pending_since) // 60)

        if just_back:
            self.last_sig = sig
            self.last_sent_at = now
            return Decision(True, back_kind, 0, snap)

        changed = sig != self.last_sig
        stable = (now - self.pending_since) >= config.STABILIZE
        gap_ok = (now - self.last_sent_at) >= config.MIN_GAP
        heartbeat_due = (now - self.last_sent_at) >= config.HEARTBEAT

        if changed and stable and gap_ok:
            self.last_sig = sig
            self.last_sent_at = now
            self.dwell_sig = sig            # a fresh thing to (maybe) linger on
            self.dwell_level = 0
            # Rabbit hole: count distinct browsing changes in a rolling window.
            # Sitting on one thing produces no changes, so lingering never trips
            # this — only churn does.
            if config.RABBIT_ENABLED and _scrollable(snap):
                self._churn = [t for t in self._churn if now - t <= config.RABBIT_WINDOW]
                self._churn.append(now)
                if (len(self._churn) >= config.RABBIT_COUNT
                        and now - self._last_rabbit >= config.RABBIT_COOLDOWN):
                    self._last_rabbit = now
                    self._churn = []
                    return Decision(True, "rabbit_hole", minutes, snap)
            else:
                self._churn = []            # left the feed — the count resets
            return Decision(True, "change", minutes, snap)

        # Lingering on one specific thing (a post, a page, a reel), in tiers:
        # a first "still on this" at DWELL_SECONDS, a stronger "properly deep in
        # this" at DWELL_DEEP_SECONDS. Gated to things with a URL so it never
        # nags on your editor, and each tier fires at most once per thing.
        if (config.DWELL_ENABLED and not changed and sig == self.last_sig
                and _lingerable(snap) and gap_ok):
            if sig != self.dwell_sig:
                self.dwell_sig = sig
                self.dwell_level = 0
            elapsed = now - self.pending_since
            target = 2 if elapsed >= config.DWELL_DEEP_SECONDS else (
                1 if elapsed >= config.DWELL_SECONDS else 0)
            if target > self.dwell_level:
                self.dwell_level = target
                self.last_sent_at = now
                return Decision(True, "dwell_deep" if target == 2 else "dwell", minutes, snap)

        if heartbeat_due:
            self.last_sig = sig
            self.last_sent_at = now
            return Decision(True, "heartbeat", minutes, snap)

        return Decision(False)

    def force(self, snap: Snapshot) -> Decision:
        """Send-now: always emit an update for the current activity."""
        now = time.monotonic()
        self.last_sig = snap.signature()
        self.last_sent_at = now
        minutes = int((now - self.pending_since) // 60)
        return Decision(True, "change", minutes, snap)
