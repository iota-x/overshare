"""Grab a still frame — webcam or screen — for her to peek at.

macOS uses tiny external tools (no Python deps): `imagesnap` for the webcam,
`screencapture` for the screen, `sips` to mirror a shot. Windows has no
equivalent tiny CLI tools, so it uses `opencv-python-headless` for the webcam
and Pillow's `ImageGrab` for the screen (Pillow is already a Windows dep here).

Every function returns a path to a fresh JPEG on success, or None if the
capture failed (tool/lib missing, permission denied, no camera, etc.). Callers
are expected to delete the file once it's been uploaded.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
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


def _rm(path: str) -> None:
    try:
        os.remove(path)
    except Exception:
        pass
    return None


def _cv2_available() -> bool:
    try:
        import cv2  # noqa: F401
        return True
    except Exception:
        return False


def webcam_available() -> bool:
    if sys.platform == "darwin":
        return _resolve("imagesnap") is not None
    if sys.platform.startswith("win"):
        return _cv2_available()
    return False


def snap_webcam(warmup: float = 0.6, mirror: bool = False) -> str | None:
    """One photo from the default camera. `warmup` lets the sensor expose.

    `mirror` flips the shot left-to-right so it reads like a mirror/selfie —
    the view we're used to seeing of ourselves — instead of the raw sensor
    frame, which feels reversed (text backwards, part in the "wrong" place).
    """
    if sys.platform == "darwin":
        return _snap_webcam_mac(warmup, mirror)
    if sys.platform.startswith("win"):
        return _snap_webcam_win(warmup, mirror)
    return None


def snap_screen() -> str | None:
    """The whole screen. JPEG so retina/high-DPI shots stay small (a full PNG
    can be ~5MB — too heavy for the rapid-fire live view)."""
    if sys.platform == "darwin":
        return _snap_screen_mac()
    if sys.platform.startswith("win"):
        return _snap_screen_win()
    return None


# --- macOS --------------------------------------------------------------


def _snap_webcam_mac(warmup: float, mirror: bool) -> str | None:
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
    if os.path.getsize(path) <= 0:
        return _rm(path)
    if mirror:
        _flip_horizontal_mac(path)  # best-effort; keep the un-flipped shot if it fails
    return path


def _flip_horizontal_mac(path: str) -> bool:
    """Mirror a still in place. Uses `sips` (built into macOS — no extra deps)."""
    sips = _resolve("sips")
    if not sips:
        return False
    try:
        subprocess.run(
            [sips, "--flip", "horizontal", path],
            check=True, capture_output=True, timeout=20,
        )
        return True
    except Exception:
        return False


def _snap_screen_mac() -> str | None:
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


# --- Windows --------------------------------------------------------------


def _snap_webcam_win(warmup: float, mirror: bool) -> str | None:
    try:
        import cv2
    except Exception:
        return None
    cap = cv2.VideoCapture(0)
    try:
        if not cap.isOpened():
            return None
        # No `-w` flag equivalent here — read (and discard) frames for `warmup`
        # seconds so auto-exposure settles, keeping the last good frame. Mirrors
        # imagesnap's warmup behavior on macOS.
        deadline = time.time() + max(warmup, 0.3)
        frame = None
        while time.time() < deadline:
            ok, f = cap.read()
            if ok:
                frame = f
        if frame is None:
            ok, frame = cap.read()
            if not ok:
                return None
        if mirror:
            frame = cv2.flip(frame, 1)
        path = _fresh(".jpg")
        ok = cv2.imwrite(path, frame, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not ok or not os.path.exists(path) or os.path.getsize(path) <= 0:
            return _rm(path)
        return path
    except Exception:
        return None
    finally:
        cap.release()


def _snap_screen_win() -> str | None:
    try:
        from PIL import ImageGrab
    except Exception:
        return None
    try:
        img = ImageGrab.grab()
        path = _fresh(".jpg")
        img.convert("RGB").save(path, "JPEG", quality=85)
        return path if os.path.exists(path) and os.path.getsize(path) > 0 else _rm(path)
    except Exception:
        return None
