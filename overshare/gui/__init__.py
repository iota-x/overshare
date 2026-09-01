"""The settings GUI — a Qt app that runs in its own process.

Entry point is :func:`overshare.gui.main.main`; the menu-bar app launches it via
``overshare.launcher.open_settings()`` rather than importing it, because Qt and
rumps/pystray can't share an event loop.
"""
