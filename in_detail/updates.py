"""Checking for, and fetching, a newer build.

Downloading something and then running it is the most dangerous thing this app
does, so the rules are narrow and not negotiable:

  * one repository, over HTTPS, and the asset has to be hosted on github.com —
    a redirect anywhere else is refused rather than followed;
  * the release metadata carries a sha256 per asset, and a file whose hash
    doesn't match it is deleted, not run;
  * nothing is ever launched on its own. The download is verified and then
    handed to whoever pressed the button.

That last one is deliberate. The build is ad-hoc signed, so macOS can't tell
one version from another — an updater that silently swapped the binary would
be trusting the network with code execution, and on macOS it would also revoke
Accessibility every time without anyone watching (see app._watch_permission).
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import ssl
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass

from . import log
from .version import VERSION, is_newer

REPO = "iota-x/overshare"
_API = f"https://api.github.com/repos/{REPO}/releases/latest"
_ALLOWED_HOSTS = ("github.com", "objects.githubusercontent.com",
                  "release-assets.githubusercontent.com")
_TIMEOUT = 20


@dataclass
class Release:
    version: str
    url: str          # the asset for this platform
    name: str
    size: int
    sha256: str
    notes: str = ""

    @property
    def newer(self) -> bool:
        return is_newer(self.version)


def _asset_for_this_machine(assets: list[dict]) -> dict | None:
    """The stable-named asset, so the choice doesn't depend on the version."""
    want = "Overshare-Windows.exe" if sys.platform.startswith("win") \
        else "Overshare-macOS.dmg"
    for a in assets:
        if a.get("name") == want:
            return a
    return None


def latest() -> Release | None:
    """What's published now, or None if the check couldn't be made."""
    try:
        req = urllib.request.Request(
            _API, headers={"Accept": "application/vnd.github+json",
                           "User-Agent": f"Overshare/{VERSION}"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT,
                                    context=ssl.create_default_context()) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        log.exception("update: could not reach GitHub", e)
        return None

    asset = _asset_for_this_machine(data.get("assets") or [])
    if asset is None:
        log.write("update: no build for this platform in the latest release")
        return None

    digest = (asset.get("digest") or "")
    return Release(
        version=(data.get("tag_name") or "").lstrip("vV"),
        url=asset.get("browser_download_url", ""),
        name=asset.get("name", ""),
        size=int(asset.get("size") or 0),
        sha256=digest.split("sha256:")[-1] if digest.startswith("sha256:") else "",
        notes=(data.get("body") or "").strip(),
    )


def _check_host(url: str) -> None:
    host = urllib.request.urlparse(url).hostname or ""
    if not url.startswith("https://") or not any(
            host == h or host.endswith("." + h) for h in _ALLOWED_HOSTS):
        raise ValueError(f"refusing to download from {host or url!r}")


def download(rel: Release, progress=None) -> str:
    """Fetch the installer and verify it. Returns the path, or raises.

    The hash is the whole point: without a paid certificate the file itself
    carries no proof of where it came from, so this is the only thing standing
    between a tampered download and an installer being run.
    """
    if not rel.url:
        raise ValueError("that release has no download for this machine")
    if not rel.sha256:
        raise ValueError("that release published no checksum — refusing to fetch")
    _check_host(rel.url)

    out = os.path.join(tempfile.mkdtemp(prefix="overshare-update-"), rel.name)
    digest = hashlib.sha256()
    got = 0

    req = urllib.request.Request(url=rel.url,
                                 headers={"User-Agent": f"Overshare/{VERSION}"})
    with urllib.request.urlopen(req, timeout=_TIMEOUT,
                                context=ssl.create_default_context()) as r:
        _check_host(r.geturl())          # again, in case a redirect moved hosts
        with open(out, "wb") as fh:
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                fh.write(chunk)
                digest.update(chunk)
                got += len(chunk)
                if progress and rel.size:
                    progress(got / rel.size)

    if rel.size and got != rel.size:
        os.remove(out)
        raise ValueError(f"download was {got} bytes, expected {rel.size}")
    if digest.hexdigest() != rel.sha256:
        os.remove(out)
        log.write("update: checksum did not match — file deleted", rel.name)
        raise ValueError("the download didn't match its checksum, so it was deleted")

    log.write("update: downloaded and verified", f"{rel.name} ({got} bytes)")
    return out


def reveal(path: str) -> None:
    """Open the download the manual way — mount the .dmg, run the installer."""
    if sys.platform == "darwin":
        subprocess.Popen(["open", path])
    elif sys.platform.startswith("win"):
        os.startfile(path)                        # noqa: S606 - runs the installer
    log.write("update: handed over to the installer", path)


def can_install() -> bool:
    """Can we replace this build in place, or does it have to be done by hand?"""
    if not getattr(sys, "frozen", False):
        return False
    if sys.platform == "darwin":
        bundle = _bundle()
        return bool(bundle) and os.access(os.path.dirname(bundle), os.W_OK) \
            and os.access(bundle, os.W_OK)
    return sys.platform.startswith("win")


def _bundle() -> str:
    if sys.platform != "darwin":
        return ""
    from pathlib import Path
    b = Path(sys.executable).resolve().parents[2]
    return str(b) if b.suffix == ".app" else ""


# The swap can't run inside the app it's replacing, so it's a script that
# outlives it: wait for us to go, move the old bundle aside, copy the new one
# in, put the old one back if anything failed, then reopen.
_SWAP = r"""#!/bin/sh
set -u
DMG="$1"; TARGET="$2"; PID="$3"; LOG="$4"
say() { printf '%s  swap: %s
' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" >> "$LOG"; }

# Wait for *every* process running out of this bundle, not just the one that
# asked. The settings window is its own process, so waiting on that pid alone
# would swap the bundle out from under the tray app still running from it.
n=0
while pgrep -f "$TARGET/Contents/MacOS/" >/dev/null 2>&1 || kill -0 "$PID" 2>/dev/null; do
  n=$((n+1)); [ "$n" -gt 200 ] && { say "app never quit — nothing changed"; exit 1; }
  sleep 0.2
done

MP=$(mktemp -d /tmp/overshare-mnt.XXXXXX)
hdiutil attach -nobrowse -readonly -mountpoint "$MP" "$DMG" >/dev/null 2>&1 || {
  say "could not mount the download — nothing changed"; exit 1; }

NEW="$MP/Overshare.app"
[ -d "$NEW" ] || { say "no app inside the download — nothing changed"
                   hdiutil detach "$MP" >/dev/null 2>&1; exit 1; }

OLD="$TARGET.replacing"
rm -rf "$OLD"
mv "$TARGET" "$OLD" 2>/dev/null || { say "could not move the old app aside"
                                     hdiutil detach "$MP" >/dev/null 2>&1; exit 1; }

if ditto "$NEW" "$TARGET" 2>/dev/null; then
  rm -rf "$OLD"
  xattr -dr com.apple.quarantine "$TARGET" 2>/dev/null
  say "replaced"
else
  rm -rf "$TARGET"; mv "$OLD" "$TARGET"          # put it back exactly as it was
  say "copy failed — the old version was restored"
  hdiutil detach "$MP" >/dev/null 2>&1; exit 1
fi

hdiutil detach "$MP" >/dev/null 2>&1
open "$TARGET"
say "reopened"
"""


def install(path: str) -> bool:
    """Replace this build with the verified download and reopen.

    Windows hands over to the installer, which knows how to upgrade over a
    running copy — CloseApplications shuts the app down and RestartApplications
    starts it again. macOS has no such thing, so it gets the script above.

    Returns False if it couldn't start, so the caller can fall back to opening
    the download and letting someone do it by hand.
    """
    if not can_install():
        return False
    try:
        if sys.platform.startswith("win"):
            log.write("update: running the installer over this copy")
            subprocess.Popen([path, "/SILENT", "/CLOSEAPPLICATIONS",
                              "/RESTARTAPPLICATIONS", "/NORESTART"])
            return True

        # The tray app is a different process holding the same bundle; the
        # settings window quitting is not enough on its own.
        from . import uninstall
        uninstall.stop_the_tray_app()

        script = os.path.join(tempfile.mkdtemp(prefix="overshare-swap-"), "swap.sh")
        with open(script, "w") as fh:
            fh.write(_SWAP)
        os.chmod(script, 0o755)
        log.write("update: swapping the app bundle", _bundle())
        subprocess.Popen(
            ["/bin/sh", script, path, _bundle(), str(os.getpid()), log.path()],
            start_new_session=True,          # outlives the app it's replacing
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as e:
        log.exception("update: could not start the install", e)
        return False


def report() -> str:
    """One line for the settings window."""
    rel = latest()
    if rel is None:
        return "couldn't check right now"
    if rel.newer:
        return f"{rel.version} is out — you're on {VERSION}"
    return f"up to date ({VERSION})"
