"""Guard the path a brand-new user takes, on both platforms.

v1.2.x shipped an app that installed, started, and then sat in the tray with no
window and no way to reach one — `is_configured()` was only ever consulted from
*inside* the settings window, and on Windows a fresh tray icon hides in the
overflow. Nothing constructed the app far enough to notice.

Run by CI on macOS and Windows. Imports only; nothing is sent and no window
opens.
"""

import os
import pathlib
import sys
import types
from unittest import mock

# Python puts *this* file's directory on sys.path, not the working directory,
# so the repo root has to be added by hand or `overshare` won't import.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))


def check_first_run(cls, name):
    """Unconfigured must open settings; configured must not."""
    calls = []
    fake = types.ModuleType("overshare.launcher")
    fake.open_settings = lambda on_fail=None: calls.append("opened")
    fake.is_open = lambda: False
    fake.close_settings = lambda: None
    # _first_run imports the launcher by name, so the stub has to go in
    # sys.modules — and has to come back out, or the next check gets the stub.
    real = sys.modules.get("overshare.launcher")
    sys.modules["overshare.launcher"] = fake

    from overshare import config

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
        sys.modules["overshare.launcher"] = real
    else:
        del sys.modules["overshare.launcher"]
    print(f"{name}: first run opens settings, and only when unconfigured")


def check_tray_default():
    """pystray dispatches an icon click to the item marked default — or nowhere."""
    # Imported here, not at the top: pystray is a Windows-only requirement and
    # isn't installed on the macOS runner.
    import pystray

    from overshare import app_win

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
    from overshare import launcher

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
    from overshare.gui.main import SettingsWindow, _come_to_the_front
    from overshare.gui import theme

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
    from overshare.gui.main import SettingsWindow
    from overshare.gui import theme

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
    from overshare import companion, config, settings

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


def check_permission_watcher():
    """Losing Accessibility must be announced once, and regaining it once.

    Updating the app replaces the bundle and macOS revokes the grant with it,
    so this fires on exactly the upgrade path everyone takes.
    """
    from overshare import app, collectors

    notes = []
    probe = app.OvershareApp.__new__(app.OvershareApp)
    seq = iter([False, True, True])
    ticks = [1, 2, 3]

    with mock.patch.object(app.rumps, "notification",
                           lambda *a, **k: notes.append(a[1])), \
         mock.patch.object(collectors, "accessibility_ok", lambda: next(seq)), \
         mock.patch.object(app.time, "sleep", lambda s: ticks.pop() and None):
        try:
            probe._watch_permission()
        except (StopIteration, IndexError):
            pass

    assert notes == ["Missing Accessibility", "Accessibility is back"], notes
    print("accessibility: announced once when lost, once when back")


def check_loop_failures_are_recorded():
    """A throwing tick must leave a real traceback, not silence."""
    import os

    from overshare import log

    try:
        raise ValueError("a tick that throws")
    except Exception as e:
        saved = e

    # Tagged, so this reads only the lines this call wrote. Scanning the whole
    # tail picks up older runs and fails on their content instead of ours.
    tag = f"ci-probe-{os.getpid()}"
    log.exception(tag, saved)
    mine = [l for l in log.tail(500) if tag in l]
    assert mine, "nothing was recorded"
    joined = " ".join(mine)
    assert "a tick that throws" in joined, "the reason wasn't recorded"
    assert "NoneType: None" not in joined, \
        "traceback taken from the ambient exception, not the one passed in"
    assert "check_first_run.py" in joined, "no traceback captured"
    print("log: a failed tick records its traceback")


def check_no_duplicate_checks():
    """Each check appears once. An if/elif/else got mis-nested and Health
    showed both "Titles — good" and "Titles — nothing readable" at once."""
    from collections import Counter

    from overshare import checkup

    counts = Counter(c.name for c in checkup.run())
    dupes = {n: k for n, k in counts.items() if k > 1}
    assert not dupes, f"a check is reported more than once: {dupes}"
    print(f"health: {len(counts)} checks, each reported once")


def check_update_guardrails():
    """The updater downloads and hands over an installer, so its refusals are
    the security boundary. They get tested, not assumed."""
    import hashlib

    from overshare import updates

    for bad in ("http://github.com/x.dmg",          # not https
                "https://github.com.evil.tld/x.dmg",  # lookalike host
                "https://evil.example/x.dmg"):
        try:
            updates._check_host(bad)
            raise AssertionError(f"allowed a download from {bad}")
        except ValueError:
            pass
    for good in ("https://github.com/iota-x/overshare/releases/download/v1/x.dmg",
                 "https://objects.githubusercontent.com/a/b"):
        updates._check_host(good)

    # No checksum published -> refuse outright rather than trust it.
    try:
        updates.download(updates.Release("9.9.9", good, "x.dmg", 10, ""))
        raise AssertionError("downloaded an asset with no checksum")
    except ValueError:
        pass

    # A hash that doesn't match must delete the file.
    body = b"pretend installer"
    class R:
        def __init__(self): self._b = [body]
        def read(self, n=-1): return self._b.pop() if self._b else b""
        def geturl(self): return good
        def __enter__(self): return self
        def __exit__(self, *a): return False

    rel = updates.Release("9.9.9", good, "x.dmg", len(body), "0" * 64)
    with mock.patch.object(updates.urllib.request, "urlopen", lambda *a, **k: R()):
        try:
            updates.download(rel)
            raise AssertionError("kept a file whose checksum didn't match")
        except ValueError:
            pass
        rel.sha256 = hashlib.sha256(body).hexdigest()
        path = updates.download(rel)
    assert os.path.exists(path), "a verified download was thrown away"
    os.remove(path)

    # And version comparison, where a string compare would be wrong.
    from overshare.version import parts
    assert parts("1.3.10") > parts("1.3.9"), "1.3.10 must be newer than 1.3.9"
    print("updates: refuses bad hosts and bad checksums, keeps verified ones")


def check_swap_script():
    """The in-place install must refuse from a checkout, and the macOS swap
    script must wait for the whole bundle — the settings window is its own
    process, so waiting on one pid would replace the app under the tray."""
    from overshare import updates

    assert not updates.can_install(), "a source checkout offered to replace itself"
    assert updates.install("/tmp/nothing.dmg") is False, "install() didn't refuse"

    if sys.platform == "darwin":
        s = updates._SWAP
        assert 'pgrep -f "$TARGET/Contents/MacOS/"' in s, \
            "the swap waits on a single pid, not on the bundle"
        assert 'mv "$OLD" "$TARGET"' in s, \
            "a failed copy must put the old version back"
        assert "KeepAlive" not in s
    print("updates: in-place install refuses in a checkout; swap waits for the bundle")


def check_login_item():
    """The login item must go on and off, and never resurrect a quit app."""
    import tempfile
    from pathlib import Path

    from overshare import startup

    assert not startup.available(), "a source checkout offered a login item"

    tmp = Path(tempfile.mkdtemp())
    if sys.platform.startswith("win"):
        exe = tmp / "Overshare.exe"
        exe.write_text("stub")
        env = {"APPDATA": str(tmp / "roaming")}
    else:
        exe = tmp / "Overshare.app" / "Contents" / "MacOS" / "Overshare"
        exe.parent.mkdir(parents=True)
        exe.write_text("stub")
        env = {}

    with mock.patch.object(sys, "frozen", True, create=True), \
         mock.patch.object(sys, "executable", str(exe)), \
         mock.patch.dict(os.environ, env):
        assert startup.available(), "an installed build had no login item to offer"
        if sys.platform.startswith("win"):
            print("login item: offered on Windows (shortcut not written in CI)")
            return

        import plistlib
        agent = startup._agent()
        was = agent.exists()
        backup = agent.read_bytes() if was else None
        try:
            assert startup.set_enabled(True) and startup.enabled()
            data = plistlib.loads(agent.read_bytes())
            assert data["RunAtLoad"] is True
            assert "KeepAlive" not in data, \
                "KeepAlive would restart the app after someone quits it"
            assert startup.set_enabled(False) and not startup.enabled()
        finally:
            if backup is not None:
                agent.write_bytes(backup)
    print("login item: goes on and off, and won't resurrect a quit app")


def check_startup_default():
    """A fresh install must already be set to open at sign-in — and only once.

    This is the whole bug: Windows asked during setup with the box ticked, the
    .dmg never asked, so the Mac build was the only one that didn't come back
    after a restart. And the half that matters just as much — someone who turns
    it off must not find it back on next launch.
    """
    from overshare import startup

    store, asked, on = {}, [], [False]
    fake = types.SimpleNamespace(get=store.get,
                                 set=lambda k, v: store.__setitem__(k, v))

    def record(v):
        asked.append(v)
        on[0] = v
        return True

    with mock.patch.object(startup, "settings", fake), \
         mock.patch.object(startup, "available", lambda: True), \
         mock.patch.object(startup, "enabled", lambda: on[0]), \
         mock.patch.object(startup, "set_enabled", record):
        startup.apply_default()
        if sys.platform.startswith("win"):
            assert asked == [], "re-ticked the box the installer already asked about"
        else:
            assert asked == [True], \
                f"a fresh install was left not opening at sign-in ({asked})"

        # They turn it off. Launching again must leave it off.
        on[0] = False
        asked.clear()
        startup.apply_default()
        assert asked == [], "switched the login item back on after it was turned off"

    # And a checkout has nothing installed to start, so it must not even mark it.
    store.clear()
    with mock.patch.object(startup, "settings", fake), \
         mock.patch.object(startup, "available", lambda: False):
        startup.apply_default()
    assert store == {}, f"a source checkout recorded a decision ({store})"
    print("startup: on by default once on a fresh install, and off stays off")


def check_discord_variants():
    """Every Discord build is Discord, and the channel survives the title.

    PTB was missing from the bundle map, so it scored as "other": a grey generic
    card, and the raw window title handed to the summarizer, which echoed it
    back as "on Discord PTB — General | Gooner hideout - Discord" rather than
    naming the channel. Someone on PTB got no channel at all.
    """
    if sys.platform != "darwin":
        print("discord: bundle map is macOS-only, skipped")
        return

    from overshare import _mac, notifier

    for bundle in ("com.hnc.Discord", "com.hnc.DiscordPTB",
                   "com.hnc.DiscordCanary", "com.hnc.DiscordDevelopment"):
        got = _mac._CATEGORY_BY_BUNDLE.get(bundle)
        assert got == "discord", f"{bundle} categorised as {got!r}, not discord"

    # The rank of build must not change what is read out of the title.
    forms = {
        "#general | My Server - Discord":       ("#general", "My Server"),
        "#general | My Server - Discord PTB":   ("#general", "My Server"),
        "#general | My Server - Discord Canary": ("#general", "My Server"),
        "(3) #general | My Server":             ("#general", "My Server"),
        "@friend - Discord":                    ("@friend", ""),
        "(1466) Discord | @sam":                ("@sam", ""),
        "Discord":                              ("", ""),      # home / friends
        "Discord PTB":                          ("", ""),
    }
    for title, want in forms.items():
        got = notifier._discord_channel(title)
        assert got == want, f"{title!r} -> {got}, wanted {want}"
    print(f"discord: 4 builds map to discord, {len(forms)} title forms parse")


def check_discord_channel_reaches_the_model():
    """The channel is useless if the summarizer is told to ignore it.

    The prompt used to offer "on discord" as the example output twice and never
    said to use the channel, so every Discord update read "on Discord" even with
    the channel sitting in the context. No model call here — this asserts the
    context block carries the parsed pieces, and that the prompt asks for them.
    """
    from overshare import summarizer

    assert "discord channel/dm" in summarizer._SYSTEM or \
           "channel/dm" in summarizer._SYSTEM, \
        "the prompt never mentions the channel it is given"
    lowered = summarizer._SYSTEM.lower()
    say_it = lowered.index("say it")
    fallback = lowered.index("only when no channel is given")
    assert say_it < fallback, \
        "the fallback is stated before the instruction to name the channel"
    print("discord: the prompt asks for the channel before offering the fallback")


def check_relaunch_on_regrant():
    """Getting the permission back must reopen the app, exactly once.

    A grant that returns mid-run does not reach apps this process already tried
    to read while it was blocked. On 2026-09-03 that left Discord reporting a
    bare "on Discord" for seven minutes after Accessibility came back, while
    Code and Brave — first read after the grant — were fine immediately. Nobody
    can tell those apart from the outside, so the app restarts itself.
    """
    # overshare.app imports rumps, which is a macOS-only requirement — the same
    # reason check_permission_watcher is skipped on the Windows runner.
    if sys.platform != "darwin":
        print("accessibility: relaunch is macOS-only, skipped")
        return

    from overshare import app, collectors

    calls = []
    probe = app.OvershareApp.__new__(app.OvershareApp)
    probe._relaunched = False
    probe._relaunch_for_permission = lambda: calls.append("reopened")

    # missing -> back -> still back: one restart, on the edge only.
    seq = iter([False, True, True])
    ticks = [1, 2, 3]
    with mock.patch.object(app.rumps, "notification", lambda *a, **k: None), \
         mock.patch.object(collectors, "accessibility_ok", lambda: next(seq)), \
         mock.patch.object(collectors, "ask_for_permission", lambda: True), \
         mock.patch.object(app.time, "sleep", lambda s: ticks.pop() and None):
        try:
            probe._watch_permission()
        except (StopIteration, IndexError):
            pass
    assert calls == ["reopened"], f"expected exactly one reopen, got {calls}"

    # A checkout has no bundle to reopen, and must not try.
    real = app.OvershareApp.__new__(app.OvershareApp)
    real._relaunched = False
    real._relaunch_for_permission()          # sys.frozen is False here
    assert real._relaunched is False, "a source checkout armed a relaunch"

    # The helper waits for the whole bundle, like the updater's swap does —
    # the settings window is its own process out of the same bundle.
    assert 'pgrep -f "$TARGET/Contents/MacOS/"' in app._RELAUNCH, \
        "the relaunch waits on one pid instead of the bundle"
    assert 'open -a "$TARGET"' in app._RELAUNCH, \
        "reopens the inner binary, which loses the bundle identity the grant is on"
    print("accessibility: a returning grant reopens the app, once, and never in a checkout")


def check_regrant_says_remove_and_readd():
    """Every place that tells someone how to re-grant must say −/+, not toggle.

    Toggling re-approves the build that was replaced, which is the one thing
    that looks like it should work and doesn't.
    """
    import re
    root = pathlib.Path(__file__).resolve().parent.parent
    targets = [
        root / "README.md",
        root / "docs" / "install.html",
        root / "overshare" / "app.py",
        root / "overshare" / "checkup.py",
        root / "overshare" / "gui" / "pages" / "health.py",
        root / "packaging" / "make_dmg.sh",
    ]
    for f in targets:
        text = f.read_text(encoding="utf-8")
        if "Accessibility" not in text:
            continue
        assert "−" in text or '"-"' in text, f"{f.name} never mentions removing the entry"
    # And nothing may still claim a plain toggle is the fix.
    for f in targets:
        text = f.read_text(encoding="utf-8").lower()
        for claim in ("switch overshare off and on in that list",
                      "turn on overshare, then quit"):
            assert claim not in text, f"{f.name} still tells people to toggle"
    print(f"regrant: {len(targets)} places say remove-and-re-add, none say toggle")


def check_dwell():
    """Lingering on one thing fires once, only for things with a link, and obeys
    the toggle. It's the whole 'still on this post' feature — cheap to get wrong
    silently (fire every tick, or nag on the editor), so it's pinned here."""
    from unittest import mock
    from overshare import config, state
    from overshare.collectors import Snapshot

    clock = [1000.0]
    with mock.patch.object(state.time, "monotonic", lambda: clock[0]):
        post = Snapshot(app="Brave", bundle_id="com.brave.Browser",
                        category="browsing", tab_title="a post",
                        url="https://x.com/a/status/1")
        editor = Snapshot(app="Code", bundle_id="com.microsoft.VSCode",
                          category="coding", window_title="app.py")

        with mock.patch.object(config, "DWELL_ENABLED", True), \
             mock.patch.object(config, "DWELL_SECONDS", 180.0):
            t = state.Tracker()
            kinds = []
            for _ in range(90):
                clock[0] += 3
                d = t.evaluate(post)
                if d.should_send:
                    kinds.append(d.kind)
            dwell = [k for k in kinds if k == "dwell"]
            assert len(dwell) == 1, f"dwell should fire once, got {dwell} in {kinds}"

            # A URL-less activity must never dwell — you live in your editor.
            t2 = state.Tracker()
            for _ in range(90):
                clock[0] += 3
                d = t2.evaluate(editor)
                assert d.kind != "dwell", "the editor should never trigger a dwell"

        # Toggle off = never fires.
        with mock.patch.object(config, "DWELL_ENABLED", False), \
             mock.patch.object(config, "DWELL_SECONDS", 180.0):
            t3 = state.Tracker()
            for _ in range(90):
                clock[0] += 3
                d = t3.evaluate(post)
                assert d.kind != "dwell", "dwell fired with the toggle off"

    print("dwell: fires once on a linked page, never on the editor, off when disabled")


def check_uninstall():
    """Offered only by an installed build, and never against a checkout."""
    import os
    import tempfile
    from pathlib import Path

    from overshare import uninstall

    assert not uninstall.available(), "a source checkout offered to uninstall itself"
    assert uninstall.run(also_data=False), "run() must refuse in a checkout"

    tmp = Path(tempfile.mkdtemp())
    if sys.platform.startswith("win"):
        (tmp / "unins000.exe").write_text("stub")
        exe, plat = tmp / "Overshare.exe", "win32"
    else:
        exe = tmp / "Overshare.app" / "Contents" / "MacOS" / "Overshare"
        exe.parent.mkdir(parents=True)
        plat = "darwin"
    exe.write_text("stub")

    with mock.patch.object(sys, "frozen", True, create=True), \
         mock.patch.object(sys, "executable", str(exe)), \
         mock.patch.object(sys, "platform", plat):
        assert uninstall.available(), "an installed build could not find its uninstaller"
    print("uninstall: offered by an installed build, refused in a checkout")


def check_titles_toggle():
    """REPORT_TITLES must actually drop titles, and keep everything else."""
    from overshare import collectors, config

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
    from overshare.app_win import WinApp
    check_first_run(WinApp, "windows")
    check_tray_default()
else:
    from overshare.app import OvershareApp
    check_first_run(OvershareApp, "macos")

check_launcher_is_async()
check_late_token_starts_the_bot()
check_window_comes_forward()
check_health_page()
check_titles_toggle()
check_no_duplicate_checks()
check_update_guardrails()
check_swap_script()
check_login_item()
check_startup_default()
check_discord_variants()
check_discord_channel_reaches_the_model()
check_relaunch_on_regrant()
check_regrant_says_remove_and_readd()
check_dwell()
check_uninstall()
check_loop_failures_are_recorded()
if not sys.platform.startswith("win"):
    check_permission_watcher()
print("OK")
