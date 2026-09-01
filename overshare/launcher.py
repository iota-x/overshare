"""Opening the settings window from the menu-bar/tray app.

The GUI is a separate process (see :mod:`overshare.gui.main` for why), so this
is the seam between them: work out how to re-invoke ourselves with
``--settings``, and don't start a second one if a window is already up.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

from . import log

_child: subprocess.Popen | None = None


def _command() -> list[str]:
    """How to launch this same program again in settings mode."""
    if getattr(sys, "frozen", False):
        # PyInstaller: sys.executable *is* the app binary.
        return [sys.executable, "--settings"]
    # From a source checkout, go back through run_app.py with the same
    # interpreter, so the virtualenv comes along.
    entry = Path(__file__).resolve().parent.parent / "run_app.py"
    return [sys.executable, str(entry), "--settings"]


def is_open() -> bool:
    return _child is not None and _child.poll() is None


def _let_child_take_focus(pid: int) -> None:
    """Windows: hand the settings process our right to come to the front.

    Windows refuses SetForegroundWindow to a process that isn't already the
    foreground one — it's the anti-focus-stealing rule, and it applies to a
    child we just spawned. So the window opened *behind* whatever the reader was
    looking at, which on a settings window you opened deliberately reads as not
    opening at all.

    The tray process does hold the foreground right at this moment (the shell
    grants it when its icon is clicked), and this passes that right along.
    """
    if not sys.platform.startswith("win"):
        return
    try:
        import ctypes
        ctypes.windll.user32.AllowSetForegroundWindow(pid)
    except Exception as e:
        log.exception("settings: could not hand over focus", e)


def _watch(child: subprocess.Popen, on_fail) -> None:
    """Notice a child that dies on startup, and say so somewhere.

    A frozen Windows build is a GUI-subsystem binary: if the settings process
    fails on import there is no console for the traceback and no window to show
    it in, so the only symptom is that nothing opens. This turns that into a log
    line and a notification.

    It runs on its own thread because the callers don't have 2.5s to spare —
    rumps dispatches menu clicks on the AppKit main thread, and blocking that
    freezes the whole menu bar.
    """
    try:
        code = child.wait(timeout=2.5)
    except subprocess.TimeoutExpired:
        log.write("settings: window is up")        # still running == it worked
        return
    log.write("settings: child exited immediately", f"returncode={code}")
    if on_fail is not None:
        try:
            on_fail(f"the settings window quit straight away (exit {code})")
        except Exception:
            pass


def open_settings(on_fail=None) -> None:
    """Show the settings window, reusing the one already open if there is one.

    `on_fail` is called with a message if the window dies on startup instead of
    appearing. It fires from a background thread, well after this returns.
    """
    global _child
    if is_open():
        # Qt won't raise a window from another process for us; on macOS `open`
        # can, and elsewhere the user can click the taskbar entry.
        if sys.platform == "darwin" and getattr(sys, "frozen", False):
            bundle = Path(sys.executable).resolve().parents[2]
            if bundle.suffix == ".app":
                subprocess.Popen(["open", str(bundle)])
        return

    env = dict(os.environ)
    # A frozen macOS bundle is LSUIElement (no Dock icon); the GUI process flips
    # itself back to a normal app so its window can take focus. Flagged through
    # the environment so only the settings process does it.
    env["OVERSHARE_GUI"] = "1"

    cmd = _command()
    log.write("settings: launching", " ".join(cmd))
    _child = subprocess.Popen(cmd, env=env)
    _let_child_take_focus(_child.pid)
    threading.Thread(target=_watch, args=(_child, on_fail), daemon=True).start()


def close_settings() -> None:
    """Used on quit, so the settings window doesn't outlive the app."""
    global _child
    if is_open():
        try:
            _child.terminate()
        except OSError:
            pass
    _child = None
