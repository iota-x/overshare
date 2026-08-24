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
    """Hand the verified file over. The installer is started by a person."""
    if sys.platform == "darwin":
        subprocess.Popen(["open", path])          # mounts the .dmg
    elif sys.platform.startswith("win"):
        os.startfile(path)                        # noqa: S606 - runs the installer
    log.write("update: handed over to the installer", path)


def report() -> str:
    """One line for the settings window."""
    rel = latest()
    if rel is None:
        return "couldn't check right now"
    if rel.newer:
        return f"{rel.version} is out — you're on {VERSION}"
    return f"up to date ({VERSION})"
