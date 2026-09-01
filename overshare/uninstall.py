"""Removing the app, from inside the app.

Windows users get the worst of this: a per-user Inno install doesn't sit in
Program Files, and "Overshare" in Installed apps is easy to miss, so the usual
outcome is deleting the shortcut and leaving a tray app running forever. The
uninstaller is right there next to the binary — this just finds it and runs it.

Nothing here deletes anything directly. macOS goes through Finder so the app
lands in the Trash and can be put back; Windows hands over to the uninstaller
that the installer already wrote.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from . import config, log

# Written by packaging/installer.iss. Inno appends _is1 to the AppId.
_INNO_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall" \
            r"\{8F3A6C21-9E4D-4B77-A1E5-2C6D0B9F4A18}_is1"


def available() -> bool:
    """Can this build uninstall itself?"""
    return bool(_target())


def _target() -> str:
    """The uninstaller to run (Windows) or the bundle to trash (macOS)."""
    if not getattr(sys, "frozen", False):
        return ""            # a source checkout is a git clone; deleting it is not ours to do
    if sys.platform == "darwin":
        bundle = Path(sys.executable).resolve().parents[2]
        return str(bundle) if bundle.suffix == ".app" else ""
    if sys.platform.startswith("win"):
        # Inno drops unins000.exe beside the app; fall back to the registry,
        # which is authoritative if the layout ever changes.
        here = Path(sys.executable).resolve().parent
        for cand in (here / "unins000.exe", here.parent / "unins000.exe"):
            if cand.exists():
                return str(cand)
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _INNO_KEY) as k:
                path = winreg.QueryValueEx(k, "UninstallString")[0].strip('"')
            return path if os.path.exists(path) else ""
        except Exception:
            return ""
    return ""


def data_paths() -> list[str]:
    """Settings, history and the log — everything the app wrote about you."""
    d = Path(config.DATA_DIR)
    return [str(d)] if d.exists() else []


def stop_the_tray_app() -> None:
    """Quit the other process, so the uninstaller isn't deleting files in use."""
    try:
        import psutil
    except Exception:
        return
    me = os.getpid()
    for proc in psutil.process_iter(["pid", "name", "exe"]):
        try:
            if proc.info["pid"] == me:
                continue
            exe = (proc.info.get("exe") or "")
            if exe and Path(exe).name.lower().startswith("overshare"):
                proc.terminate()
                log.write("uninstall: stopped the tray app", f"pid={proc.info['pid']}")
        except Exception:
            continue


def remove_data() -> bool:
    """Delete the data directory. Only ever called when asked for explicitly."""
    import shutil

    ok = True
    for path in data_paths():
        try:
            shutil.rmtree(path)
            log.write("uninstall: removed data", path)
        except Exception as e:
            log.exception("uninstall: could not remove data", e)
            ok = False
    return ok


def run(*, also_data: bool) -> str:
    """Start the uninstall. Returns "" on success, or why it couldn't.

    Returning rather than raising because the caller is a button, and the only
    useful thing it can do with a failure is print it next to itself.
    """
    target = _target()
    if not target:
        return ("This build can't uninstall itself — it's running from a "
                "checkout, not an installed copy.")

    log.write("uninstall: starting", f"target={target} data={also_data}")
    if also_data:
        remove_data()

    stop_the_tray_app()

    try:
        if sys.platform == "darwin":
            # Finder, so it goes to the Trash and can be put back. rm -rf on the
            # bundle you are currently executing from is not a thing to do.
            script = (f'tell application "Finder" to delete POSIX file "{target}"')
            subprocess.run(["osascript", "-e", script], check=True,
                           capture_output=True, timeout=30)
        else:
            subprocess.Popen([target])
    except Exception as e:
        log.exception("uninstall: failed", e)
        return f"Couldn't start the uninstaller: {e}"
    return ""
