"""The blocklist — what never gets broadcast.

This app reads your screen and sends what it finds to someone else. Some of
what's on screen is nobody's business: your bank, your password manager, the
incognito window you opened for a reason. Without this, all of it goes out with
everything else.

Redaction happens inside `collectors.collect()`, which is the one place every
consumer reads from. That matters more than it looks: the state machine, the
card, the bot's presence *and the day's tally* all take the redacted snapshot,
so a hidden app can't reappear hours later inside a recap's "top apps".

Nothing here is sent anywhere to be checked — the lists are local strings
matched against local strings.
"""

from __future__ import annotations

from . import config
from .collectors import Snapshot

# How browsers title a private window. Checked against the window title, which
# is the only signal available on both platforms — there's no API that says
# "this window is incognito".
_INCOGNITO_MARKERS = (
    "incognito",          # Chrome, Brave, Edge (older), Opera
    "inprivate",          # Edge
    "private browsing",   # Firefox, Safari
    "private window",     # Safari
    "(private)",          # Firefox on some locales
)


def _terms(raw: str) -> list[str]:
    return [t.strip().lower() for t in (raw or "").split(",") if t.strip()]


def _hit(haystacks: tuple[str, ...], needles: list[str]) -> bool:
    if not needles:
        return False
    blob = " ".join(h for h in haystacks if h).lower()
    return any(n in blob for n in needles)


def is_private(snap: Snapshot) -> bool:
    """Should this activity be hidden?"""
    if not config.PRIVACY_ENABLED:
        return False

    if config.PRIVACY_HIDE_INCOGNITO:
        title = f"{snap.window_title} {snap.tab_title}".lower()
        if any(m in title for m in _INCOGNITO_MARKERS):
            return True

    # An app is matched on its name *and* its bundle id / exe, so "1password"
    # catches both "1Password 7" and "com.1password.1password".
    if _hit((snap.app, snap.bundle_id), _terms(config.PRIVACY_APPS)):
        return True
    if _hit((snap.url,), _terms(config.PRIVACY_SITES)):
        return True
    if _hit((snap.window_title, snap.tab_title, snap.url),
            _terms(config.PRIVACY_WORDS)):
        return True
    return False


def redact(snap: Snapshot) -> Snapshot:
    """Replace a private activity with a vague stand-in.

    Music survives on purpose: what's playing isn't the secret, and keeping it
    means the message still reads like a person ("something private, while X
    plays") rather than a gap in the day.

    The bundle id is pinned to one value so every hidden app shares a signature
    — otherwise switching between two blocked apps would fire an update each
    time and quietly announce, by rhythm alone, that something is being hidden.
    """
    if not is_private(snap):
        return snap
    label = config.PRIVACY_LABEL or "something private 🔒"
    return Snapshot(
        app=label,
        bundle_id="private",
        window_title="",
        tab_title="",
        url="",
        category="private",
        music=snap.music,
        music_url=snap.music_url,
        idle_seconds=snap.idle_seconds,
    )
