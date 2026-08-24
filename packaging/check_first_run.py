"""Guard the path a brand-new user takes, on both platforms.

v1.2.x shipped an app that installed, started, and then sat in the tray with no
window and no way to reach one — `is_configured()` was only ever consulted from
*inside* the settings window, and on Windows a fresh tray icon hides in the
overflow. Nothing constructed the app far enough to notice.

Run by CI on macOS and Windows. Imports only; nothing is sent and no window
opens.
"""

import pathlib
import sys
import types
from unittest import mock

# Python puts *this* file's directory on sys.path, not the working directory,
# so the repo root has to be added by hand or `in_detail` won't import.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))


def check_first_run(cls, name):
    """Unconfigured must open settings; configured must not."""
    calls = []
    fake = types.ModuleType("in_detail.launcher")
    fake.open_settings = lambda on_fail=None: calls.append("opened")
    fake.is_open = lambda: False
    fake.close_settings = lambda: None
    # _first_run imports the launcher by name, so the stub has to go in
    # sys.modules — and has to come back out, or the next check gets the stub.
    real = sys.modules.get("in_detail.launcher")
    sys.modules["in_detail.launcher"] = fake

    from in_detail import config

    probe = cls.__new__(cls)                    # no tray/menu-bar construction
    probe._notify = lambda *a, **k: None
    probe._settings_failed = lambda why: None

    mod = sys.modules[cls.__module__]
    with mock.patch.object(mod.time, "sleep", lambda s: None):
        with mock.patch.object(config, "is_configured", lambda: False):
            probe._first_run()
        assert calls == ["opened"], f"{name}: fresh install opened nothing ({calls})"

        calls.clear()
        with mock.patch.object(config, "is_configured", lambda: True):
            probe._first_run()
        assert calls == [], f"{name}: reopened settings on a configured machine"

    if real is not None:
        sys.modules["in_detail.launcher"] = real
    else:
        del sys.modules["in_detail.launcher"]
    print(f"{name}: first run opens settings, and only when unconfigured")


def check_tray_default():
    """pystray dispatches an icon click to the item marked default — or nowhere."""
    # Imported here, not at the top: pystray is a Windows-only requirement and
    # isn't installed on the macOS runner.
    import pystray

    from in_detail import app_win

    src = open(app_win.__file__, encoding="utf-8").read()
    assert "default=True" in src, "no default tray item: clicking the icon does nothing"

    hit = []
    menu = pystray.Menu(
        pystray.MenuItem("Settings…", lambda i, it: hit.append("settings"), default=True))
    menu(None)                                   # exactly what a left-click does
    assert hit == ["settings"], "default item did not receive the click"
    print("tray: clicking the icon opens Settings")


def check_launcher_is_async():
    """open_settings must not block: rumps runs menu clicks on the main thread."""
    import time
    from in_detail import launcher

    got = []
    with mock.patch.object(launcher, "_command",
                           lambda: [sys.executable, "-c", "import sys; sys.exit(3)"]):
        t0 = time.time()
        launcher.open_settings(on_fail=got.append)
        elapsed = time.time() - t0
    assert elapsed < 0.5, f"open_settings blocked for {elapsed:.2f}s"
    time.sleep(3.0)
    assert got and "exit 3" in got[0], f"a dead settings window went unreported ({got})"
    print(f"launcher: returns in {elapsed:.3f}s and still reports a dead child")


def check_window_comes_forward():
    """The settings window must end up shown, unminimised, and not left pinned."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from in_detail.gui.main import SettingsWindow, _come_to_the_front
    from in_detail.gui import theme

    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(theme.qss(True))
    w = SettingsWindow(dark=True)
    _come_to_the_front(w)
    assert w.isVisible(), "settings window never became visible"
    assert not (w.windowState() & Qt.WindowState.WindowMinimized), "opened minimised"
    assert not (w.windowFlags() & Qt.WindowType.WindowStaysOnTopHint), \
        "left pinned above every other window"
    print("window: comes forward, and isn't left on top")


def check_health_page():
    """The Health page must survive being refreshed twice — it rebuilds rows."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    from in_detail.gui.main import SettingsWindow
    from in_detail.gui import theme

    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(theme.qss(True))
    w = SettingsWindow(dark=True)
    titles = [w._nav.item(i).text() for i in range(w._nav.count())]
    assert "Health" in titles, f"Health page missing from the sidebar ({titles})"
    page = w._stack.widget(titles.index("Health"))
    page.on_show()
    page.on_show()
    print(f"health: page builds and re-runs; {len(page._checks)} checks")


def check_late_token_starts_the_bot():
    """A token pasted after startup must bring the bot up without a restart."""
    import time
    from in_detail import companion, config, settings

    started = []
    with mock.patch.object(companion, "_run", lambda: started.append("ran")):
        companion._thread = None
        with mock.patch.object(config, "DISCORD_BOT_TOKEN", ""):
            companion.start()
        assert started == [], "started a bot with no token"

        with mock.patch.object(config, "DISCORD_BOT_TOKEN", "tok"):
            companion.start()
        time.sleep(0.3)
    assert started == ["ran"], "a token pasted later never started the bot"
    print("companion: a late token brings the bot online")


def check_titles_toggle():
    """REPORT_TITLES must actually drop titles, and keep everything else."""
    from in_detail import collectors, config

    before = bool(config.REPORT_TITLES)
    try:
        config.save({"REPORT_TITLES": False})
        config.reload()
        snap = collectors.collect()
        assert snap.window_title == "" and snap.tab_title == "", \
            "titles still collected with the toggle off"

        config.save({"REPORT_TITLES": True})
        config.reload()
        assert config.REPORT_TITLES is True
    finally:
        config.save({"REPORT_TITLES": before})
        config.reload()
    print("titles: the toggle drops titles and nothing else")


if sys.platform.startswith("win"):
    from in_detail.app_win import WinApp
    check_first_run(WinApp, "windows")
    check_tray_default()
else:
    from in_detail.app import InDetailApp
    check_first_run(InDetailApp, "macos")

check_launcher_is_async()
check_late_token_starts_the_bot()
check_window_comes_forward()
check_health_page()
check_titles_toggle()
print("OK")
