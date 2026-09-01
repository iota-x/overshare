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
    """Log an exception and its traceback.

    Formatted from the exception object, not from `format_exc()` — that reads
    the *ambient* exception, so calling this with one caught earlier (which the
    poll loop does, by design) recorded a cheerful "NoneType: None".
    """
    write(event, "".join(traceback.format_exception_only(type(exc), exc)).strip())
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    write(event + " (traceback)", tb.strip().replace("\n", " ⏎ "))


def tail(limit: int = 12) -> list[str]:
    """The last few lines, newest last.

    The settings window is a separate process from the tray app, so this file is
    the only way it can see what the part that actually sends is doing.
    """
    try:
        with open(path(), encoding="utf-8", errors="replace") as fh:
            return [l.rstrip("\n") for l in fh.readlines()[-limit:]]
    except Exception:
        return []


def last_send() -> str:
    """The most recent line about sending, whichever way it went."""
    for line in reversed(tail(400)):
        if "send:" in line or "loop:" in line:
            return line
    return ""
