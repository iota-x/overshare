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
        "CFBundleName": "In Detail",
        "CFBundleDisplayName": "In Detail",
        "CFBundleIdentifier": "com.iota.in-detail",
        "CFBundleShortVersionString": "0.1.0",
        "CFBundleVersion": "0.1.0",
        # Menubar app — no Dock icon.
        "LSUIElement": True,
        "NSAppleEventsUsageDescription": (
            "in-detail reads your active browser tab and now-playing media so it "
            "can describe what you're doing."
        ),
    },
}

setup(
    app=APP,
    name="In Detail",
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
