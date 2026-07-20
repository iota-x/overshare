"""Reads what you're currently doing — dispatches to the right OS backend.

Defines the shared Snapshot; the actual reading lives in `_mac.py` (macOS) or
`_win.py` (Windows). Everything downstream (state machine, summarizer, notifier,
recaps, the bot) is platform-agnostic and works off a Snapshot.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field


@dataclass
class Snapshot:
    app: str = "Unknown"
    bundle_id: str = ""       # bundle id (mac) / exe name (windows)
    window_title: str = ""
    tab_title: str = ""
    url: str = ""
    category: str = "other"
    music: str = ""           # what's playing in the background
    music_url: str = ""       # shareable track link (so she can listen along)
    idle_seconds: float = 0.0
    extras: dict = field(default_factory=dict)

    def signature(self) -> str:
        """Fingerprint of the activity — changes when you switch app, tab, file,
        page, or the background song. That's exactly when we want to update."""
        detail = self.url or self.tab_title or self.window_title
        sig = f"{self.bundle_id}|{detail}"
        if self.music:
            sig += f"|♪{self.music}"
        return sig.strip("|")


# Pick the backend for this OS.
_backend = None
try:
    if sys.platform == "darwin":
        from . import _mac as _backend
    elif sys.platform.startswith("win"):
        from . import _win as _backend
except Exception:
    _backend = None


def accessibility_ok() -> bool:
    """Whether we have the OS permission we need (Accessibility on macOS)."""
    try:
        return _backend.permission_ok() if _backend else True
    except Exception:
        return True


def collect() -> Snapshot:
    """Take one read of the current activity (never raises)."""
    if _backend is None:
        return Snapshot()
    try:
        return _backend.collect()
    except Exception:
        return Snapshot()


if __name__ == "__main__":
    import json
    print("platform:", sys.platform, "| permission:",
          "OK" if accessibility_ok() else "MISSING")
    s = collect()
    print(json.dumps({
        "app": s.app, "id": s.bundle_id, "window_title": s.window_title,
        "tab_title": s.tab_title, "url": s.url, "category": s.category,
        "music": s.music, "idle_seconds": round(s.idle_seconds, 1),
        "signature": s.signature(),
    }, indent=2))
