"""Starting when you sign in.

The two platforms disagreed, and neither was a decision anyone made: the
Windows installer ticks "Start Overshare when I sign in" by default, and the
macOS .dmg has no login item at all. So the same app was always-on on one and
manual on the other, and the only way to change it on Windows was to reinstall.

One toggle, one mechanism per platform:

  * macOS   — a LaunchAgent in ~/Library/LaunchAgents. Per-user, no admin.
  * Windows — the same Startup-folder shortcut the installer creates, so this
    and the installer can't both fire and start the app twice.

RunAtLoad only, never KeepAlive: quitting from the menu bar has to mean quit,
not "restart in a second".
"""

from __future__ import annotations

import os
import plistlib
import sys
from pathlib import Path

from . import log

LABEL = "com.iota.overshare"
_NAME = "Overshare"


def _app_path() -> str:
    """What to launch. Empty from a source checkout — nothing to install there."""
    if not getattr(sys, "frozen", False):
        return ""
    if sys.platform == "darwin":
        bundle = Path(sys.executable).resolve().parents[2]
        return str(bundle) if bundle.suffix == ".app" else ""
    return sys.executable


def available() -> bool:
    return bool(_app_path())


# --- macOS -------------------------------------------------------------------
def _agent() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def _mac_enabled() -> bool:
    return _agent().exists()


def _mac_set(on: bool) -> None:
    path = _agent()
    if not on:
        path.unlink(missing_ok=True)
        return
    app = _app_path()
    # `open -a` rather than the inner binary: it goes through Launch Services,
    # which is what gives the process the bundle's identity — and therefore the
    # Accessibility grant that was given to the bundle.
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        plistlib.dump({
            "Label": LABEL,
            "ProgramArguments": ["/usr/bin/open", "-a", app],
            "RunAtLoad": True,
        }, fh)


# --- Windows -----------------------------------------------------------------
def _shortcut() -> Path:
    base = os.environ.get("APPDATA") or str(Path.home())
    return (Path(base) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
            / "Startup" / f"{_NAME}.lnk")


def _win_enabled() -> bool:
    return _shortcut().exists()


def _win_set(on: bool) -> None:
    link = _shortcut()
    if not on:
        link.unlink(missing_ok=True)
        return
    link.parent.mkdir(parents=True, exist_ok=True)
    from win32com.client import Dispatch          # pywin32, Windows-only

    shell = Dispatch("WScript.Shell")
    sc = shell.CreateShortCut(str(link))
    sc.Targetpath = _app_path()
    sc.WorkingDirectory = str(Path(_app_path()).parent)
    sc.Description = "Overshare"
    sc.save()


# --- the two anyone calls ----------------------------------------------------
def enabled() -> bool:
    if not available():
        return False
    try:
        return _win_enabled() if sys.platform.startswith("win") else _mac_enabled()
    except Exception:
        return False


def set_enabled(on: bool) -> bool:
    """Returns whether it ended up the way you asked."""
    if not available():
        return False
    try:
        if sys.platform.startswith("win"):
            _win_set(on)
        else:
            _mac_set(on)
        log.write(f"startup: {'on' if on else 'off'}", _app_path())
        return enabled() == on
    except Exception as e:
        log.exception("startup: could not change the login item", e)
        return False
