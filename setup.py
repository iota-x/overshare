"""Build the macOS .app bundle:

    ./.venv/bin/python setup.py py2app -A

The -A (alias) build makes a real .app bundle with our icon and identity that
runs against this project's virtualenv — fast to build and perfect for personal
use. (Drop -A for a fully self-contained, distributable bundle.)
"""

from setuptools import setup

APP = ["run_app.py"]

OPTIONS = {
    "iconfile": "assets/icon.icns",
    "plist": {
        "CFBundleName": "Overshare",
        "CFBundleDisplayName": "Overshare",
        "CFBundleIdentifier": "com.iota.overshare",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "0.1.0",
        # Menubar app — no Dock icon.
        "LSUIElement": True,
        "NSAppleEventsUsageDescription": (
            "Overshare reads your active browser tab and now-playing media so it "
            "can describe what you're doing."
        ),
        # Required for the webcam peek (!peek / !live) — macOS hard-denies camera
        # access to an app bundle without this key. Screen Recording (!screen)
        # has no plist key; macOS prompts for it on first use.
        "NSCameraUsageDescription": (
            "Overshare can send a webcam photo to your partner when they ask."
        ),
    },
}

setup(
    app=APP,
    name="Overshare",
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
