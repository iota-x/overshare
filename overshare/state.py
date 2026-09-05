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
        # The activity we've already sent a "still lingering" nudge for, so
        # it fires once per post/page, not on every tick past the threshold.
        self.dwelt_sig: str = ""

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
            return Decision(True, "change", minutes, snap)

        # Lingering on one specific thing (a post, a page, a reel) for a while
        # is worth saying on its own — warmer and more specific than the plain
        # heartbeat. Gated to activities with a URL so it never fires "still in
        # your editor", and to once per thing via dwelt_sig.
        dwell_due = (
            config.DWELL_ENABLED
            and not changed                     # same thing we last announced
            and sig == self.last_sig
            and sig != self.dwelt_sig           # not already dwelt on this one
            and _lingerable(snap)
            and (now - self.pending_since) >= config.DWELL_SECONDS
            and gap_ok
        )
        if dwell_due:
            self.dwelt_sig = sig
            self.last_sent_at = now
            return Decision(True, "dwell", minutes, snap)

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
