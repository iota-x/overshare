"""Grab a still frame — webcam or screen — for her to peek at.

Both use tiny external tools rather than heavy Python deps:
  • webcam → `imagesnap`  (brew install imagesnap)
  • screen → `screencapture`  (built into macOS)

Every function returns a path to a fresh JPEG/PNG on success, or None if the
capture failed (tool missing, permission denied, no camera, etc.). Callers are
expected to delete the file once it's been uploaded.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time

# Reused across peeks so the temp dir doesn't fill up with orphans if a caller
# ever forgets to clean one up (we still delete after upload as the happy path).
_TMP = os.path.join(tempfile.gettempdir(), "in_detail_peek")

# A bundled .app launched from Finder/launchd inherits a minimal PATH
# (/usr/bin:/bin:/usr/sbin:/sbin) that omits Homebrew, so shutil.which can't see
# imagesnap even when it's installed — which reads as "no camera tool" to the
# user. Search Homebrew's bins (Apple Silicon + Intel) too, and call the tool by
# absolute path so the subprocess doesn't depend on PATH either.
_EXTRA_BINS = ("/opt/homebrew/bin", "/usr/local/bin")


def _resolve(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for d in _EXTRA_BINS:
        cand = os.path.join(d, name)
        if os.path.isfile(cand) and os.access(cand, os.X_OK):
            return cand
    return None


def _fresh(suffix: str) -> str:
    os.makedirs(_TMP, exist_ok=True)
    return os.path.join(_TMP, f"{int(time.time() * 1000)}{suffix}")


def webcam_available() -> bool:
    return _resolve("imagesnap") is not None


def snap_webcam(warmup: float = 0.6) -> str | None:
    """One photo from the default camera. `warmup` lets the sensor expose."""
    imagesnap = _resolve("imagesnap")
    if not imagesnap:
        return None
    path = _fresh(".jpg")
    try:
        # -q quiet, -w warmup seconds (helps avoid a black/greenish first frame)
        subprocess.run(
            [imagesnap, "-q", "-w", str(warmup), path],
            check=True, capture_output=True, timeout=20,
        )
    except Exception:
        _rm(path)
        return None
    return path if os.path.getsize(path) > 0 else _rm(path)


def snap_screen() -> str | None:
    """The whole screen, no shutter sound. JPEG so retina shots stay small
    (a full PNG can be ~5MB — too heavy for the rapid-fire live view)."""
    path = _fresh(".jpg")
    try:
        # -x no sound, -t jpg to keep the file light
        subprocess.run(
            ["screencapture", "-x", "-t", "jpg", path],
            check=True, capture_output=True, timeout=20,
        )
    except Exception:
        _rm(path)
        return None
    return path if os.path.exists(path) and os.path.getsize(path) > 0 else _rm(path)


def _rm(path: str) -> None:
    try:
        os.remove(path)
    except Exception:
        pass
    return None
