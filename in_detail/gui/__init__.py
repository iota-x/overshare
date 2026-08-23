"""The settings GUI — a Qt app that runs in its own process.

Entry point is :func:`in_detail.gui.main.main`; the menu-bar app launches it via
``in_detail.launcher.open_settings()`` rather than importing it, because Qt and
rumps/pystray can't share an event loop.
"""
