"""Entry point — the menu-bar/tray app, or the settings window with --settings.

Both modes sit behind one entry point so the packaged app stays a single binary:
the tray app re-invokes itself as `Overshare --settings` to raise the GUI in its
own process (see in_detail/launcher.py for why they can't share one).
"""

import sys


def main() -> None:
    if "--settings" in sys.argv:
        from in_detail.gui.main import main as settings_main
        raise SystemExit(settings_main())

    if sys.platform.startswith("win"):
        from in_detail.app_win import main as app_main
    else:
        from in_detail.app import main as app_main
    app_main()


if __name__ == "__main__":
    main()
