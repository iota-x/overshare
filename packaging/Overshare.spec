# PyInstaller spec — builds Overshare.app on macOS and Overshare.exe on Windows.
#
#   pyinstaller packaging/Overshare.spec --noconfirm
#
# One spec covers both because the platform branches are small: what differs is
# the icon format, which optional dependencies exist, and whether we wrap the
# result in a .app bundle at the end.
#
# Unlike the old `py2app -A` build, this is fully self-contained — it embeds the
# interpreter and every dependency, so it runs on a machine with no Python.

import os
import sys

ROOT = os.path.dirname(os.path.abspath(SPECPATH))

# The release workflow rewrites in_detail/version.py from the tag before it
# builds. Read it back rather than hardcoding, so the bundle, the plist and the
# update check can never disagree about what this build is.
def _version():
    ns = {}
    exec((open(os.path.join(ROOT, "in_detail", "version.py")).read()), ns)
    return ns.get("VERSION", "0.0.0")

APP_VERSION = _version()
MACOS = sys.platform == "darwin"
WINDOWS = sys.platform.startswith("win")

datas = [(os.path.join(ROOT, "assets", "icon.png"), "assets")]
if MACOS and os.path.exists(os.path.join(ROOT, "assets", "icon.icns")):
    datas.append((os.path.join(ROOT, "assets", "icon.icns"), "assets"))

# Things imported lazily or by name, which static analysis misses.
hiddenimports = [
    "in_detail.gui.main",
    "in_detail.app",
    "in_detail.app_win",
    "discord",
    "dotenv",
]
if MACOS:
    # cv2 is the camera fallback when imagesnap isn't installed (see capture.py),
    # and it's imported lazily, so name it explicitly.
    hiddenimports += ["rumps", "AppKit", "Foundation", "Quartz", "cv2"]
if WINDOWS:
    hiddenimports += [
        "pystray._win32", "PIL.ImageGrab", "win32api", "win32gui",
        "win32process", "psutil", "uiautomation", "cv2", "tzdata",
        # Writing the Startup-folder shortcut for the "start when I sign in"
        # toggle. Imported inside a function, so nothing static finds it.
        "win32com", "win32com.client", "pythoncom",
    ]

# PySide6 ships far more than a settings window needs. Dropping these takes the
# bundle from ~450MB to well under 150MB, and none of it is referenced.
qt_excludes = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebEngineQuick", "PySide6.QtWebChannel", "PySide6.QtWebSockets",
    "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQuickWidgets",
    "PySide6.QtQml", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
    "PySide6.QtNetworkAuth", "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtPositioning",
    "PySide6.QtLocation", "PySide6.QtSensors", "PySide6.QtSerialPort",
    "PySide6.QtSql", "PySide6.QtTest", "PySide6.QtDesigner", "PySide6.QtHelp",
    "PySide6.QtUiTools", "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets",
    "PySide6.QtRemoteObjects", "PySide6.QtScxml", "PySide6.QtSpatialAudio",
    "PySide6.QtStateMachine", "PySide6.QtTextToSpeech", "PySide6.Qt3DCore",
    "PySide6.Qt3DRender", "PySide6.Qt3DInput", "PySide6.Qt3DAnimation",
    "PySide6.QtXml", "PySide6.QtConcurrent", "PySide6.QtHttpServer",
]
# Note: shiboken6 must NOT be excluded — it's the binding layer every PySide6
# import goes through, not an optional module.

excludes = qt_excludes + [
    "matplotlib", "numpy.f2py", "pytest", "setuptools", "pip", "wheel",
    "IPython", "notebook", "sphinx", "PyQt5", "PyQt6", "PySide2",
]
# tkinter still backs the small prompt dialogs in app_win.py, so it stays on
# Windows — but a Mac build has no use for it.
if MACOS:
    excludes.append("tkinter")

a = Analysis(
    [os.path.join(ROOT, "run_app.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Overshare",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # no terminal window on either platform
    disable_windowed_traceback=False,
    argv_emulation=False,   # must stay off: it would eat our --settings flag
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # Windows wants a real .ico here; macOS wants .icns.
    icon=os.path.join(ROOT, "assets", "icon.icns" if MACOS else "icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Overshare",
)

if MACOS:
    app = BUNDLE(
        coll,
        name="Overshare.app",
        icon=os.path.join(ROOT, "assets", "icon.icns"),
        bundle_identifier="com.iota.overshare",
        info_plist={
            "CFBundleName": "Overshare",
            "CFBundleDisplayName": "Overshare",
            "CFBundleShortVersionString": APP_VERSION,
            "CFBundleVersion": APP_VERSION,
            "NSHighResolutionCapable": True,
            # Menu-bar app — no Dock icon. The settings window flips this
            # process back to a normal app while it's open (see gui/main.py).
            "LSUIElement": True,
            "NSAppleEventsUsageDescription": (
                "Overshare reads your active browser tab and now-playing media "
                "so it can describe what you're doing."
            ),
            # Required for the webcam peek — macOS hard-denies camera access to
            # a bundle without this key. Screen Recording has no plist key;
            # macOS prompts for it on first use.
            "NSCameraUsageDescription": (
                "Overshare can send a webcam photo to your partner when they ask."
            ),
        },
    )
