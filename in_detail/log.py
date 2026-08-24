"""A log file, because a packaged app has nowhere else to speak.

Both builds are windowed — `console=False` in the spec — so on Windows there is
no stdout and no stderr at all, and on macOS anything printed disappears into
the launch services log. When someone says "I double-clicked it and nothing
happened", there has to be a file to look at; otherwise the report can't be
acted on.

Lives beside config.json in the app's data dir, so it's where someone already
has to go to find their settings.
"""

from __future__ import annotations

import datetime as _dt
import os
import threading
import traceback

_lock = threading.Lock()
_path: str | None = None
_MAX_BYTES = 512 * 1024          # a couple of days of chatter; then it rolls


def path() -> str:
    global _path
    if _path is None:
        from . import config
        d = config.DATA_DIR
        os.makedirs(d, exist_ok=True)
        _path = os.path.join(d, "overshare.log")
    return _path


def write(event: str, detail: str = "") -> None:
    """Append one line. Never raises — logging must not become the failure."""
    try:
        p = path()
        stamp = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{stamp}  {event}"
        if detail:
            line += f"  |  {detail}"
        with _lock:
            # Roll rather than truncate, so the tail of the previous run
            # survives the one that replaced it.
            try:
                if os.path.getsize(p) > _MAX_BYTES:
                    os.replace(p, p + ".1")
            except OSError:
                pass
            with open(p, "a", encoding="utf-8", errors="replace") as fh:
                fh.write(line + "\n")
    except Exception:
        pass


def exception(event: str, exc: BaseException) -> None:
    write(event, "".join(traceback.format_exception_only(type(exc), exc)).strip())
    write(event + " (traceback)", traceback.format_exc().replace("\n", " ⏎ "))
