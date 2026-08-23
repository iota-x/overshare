"""Opening the settings window from the menu-bar/tray app.

The GUI is a separate process (see :mod:`in_detail.gui.main` for why), so this
is the seam between them: work out how to re-invoke ourselves with
``--settings``, and don't start a second one if a window is already up.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

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


def open_settings() -> None:
    """Show the settings window, reusing the one already open if there is one."""
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
    _child = subprocess.Popen(_command(), env=env)


def close_settings() -> None:
    """Used on quit, so the settings window doesn't outlive the app."""
    global _child
    if is_open():
        try:
            _child.terminate()
        except OSError:
            pass
    _child = None
