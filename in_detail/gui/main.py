"""The settings window — sidebar on the left, one page at a time on the right.

Runs as its own process (``Overshare --settings``). The menu-bar/tray app owns
an event loop of its own — rumps on macOS, pystray on Windows — and Qt insists
on owning one too, so the two can't share a process. Keeping them apart also
means a crash in here can't take the broadcaster down with it; they communicate
only through the config file, which the app re-reads when it changes.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import (
    QApplication, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QMainWindow, QStackedWidget, QVBoxLayout, QWidget,
)

from .. import config
from . import theme
from .pages import PAGES, Context

_WINDOW_MIN = (940, 660)


def _prefers_dark() -> bool:
    """Follow the OS appearance. Qt 6.5+ reports it; older ones fall back light."""
    try:
        scheme = QGuiApplication.styleHints().colorScheme()
        return scheme == Qt.ColorScheme.Dark
    except Exception:
        return False


def _icon() -> QIcon:
    """The app icon, from the bundle when frozen and the repo when not."""
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    for name in ("assets/icon.png", "assets/icon.icns"):
        candidate = root / name
        if candidate.exists():
            return QIcon(str(candidate))
    return QIcon()


class SettingsWindow(QMainWindow):
    def __init__(self, dark: bool):
        super().__init__()
        self.setWindowTitle("Overshare")
        self.setMinimumSize(*_WINDOW_MIN)
        self.setWindowIcon(_icon())

        self.ctx = Context(dark=dark, status=self._say)

        root = QWidget()
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        body = QWidget()
        columns = QHBoxLayout(body)
        columns.setContentsMargins(0, 0, 0, 0)
        columns.setSpacing(0)
        columns.addWidget(self._build_sidebar())
        self._stack = QStackedWidget()
        columns.addWidget(self._stack, 1)
        outer.addWidget(body, 1)
        outer.addWidget(self._build_status_bar())

        for page_class in PAGES:
            page = page_class(self.ctx)
            self._stack.addWidget(page)
            item = QListWidgetItem(page_class.nav or page_class.title)
            self._nav.addItem(item)

        self._nav.currentRowChanged.connect(self._switch_page)
        self._nav.setCurrentRow(0)

        # A fresh install lands on Setup with a nudge rather than in silence.
        if not config.is_configured():
            self._say("Paste your Discord webhook link below to get started 💌")

    # --- chrome ---------------------------------------------------------------
    def _build_sidebar(self) -> QWidget:
        side = QWidget()
        side.setObjectName("Sidebar")
        side.setFixedWidth(216)
        column = QVBoxLayout(side)
        column.setContentsMargins(0, 20, 0, 12)
        column.setSpacing(0)

        mark = QLabel("Overshare 💌")
        mark.setObjectName("WordMark")
        mark.setContentsMargins(18, 0, 18, 0)
        column.addWidget(mark)

        tag = QLabel("lovingly over-informed")
        tag.setObjectName("Tagline")
        tag.setContentsMargins(18, 0, 18, 0)
        column.addWidget(tag)
        column.addSpacing(18)

        self._nav = QListWidget()
        self._nav.setObjectName("NavList")
        self._nav.setFrameShape(QListWidget.Shape.NoFrame)
        self._nav.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        column.addWidget(self._nav, 1)
        return side

    def _build_status_bar(self) -> QWidget:
        bar = QWidget()
        bar.setObjectName("StatusBar")
        bar.setFixedHeight(34)
        line = QHBoxLayout(bar)
        line.setContentsMargins(16, 0, 16, 0)

        self._status = QLabel("")
        line.addWidget(self._status, 1)

        hint = QLabel("Changes save as you make them")
        line.addWidget(hint, 0, Qt.AlignmentFlag.AlignRight)
        return bar

    # --- behaviour --------------------------------------------------------------
    def _switch_page(self, index: int) -> None:
        self._stack.setCurrentIndex(index)
        page = self._stack.currentWidget()
        if hasattr(page, "on_show"):
            page.on_show()

    def _say(self, message: str) -> None:
        self._status.setText(message)
        # Transient — clear it so a stale line doesn't read as current state.
        QTimer.singleShot(6000, lambda: self._status.setText("")
                          if self._status.text() == message else None)


def _become_a_normal_app() -> None:
    """macOS: leave LSUIElement mode so this window can take focus.

    The bundle is marked LSUIElement so the *tray* app has no Dock icon. That
    flag is per-bundle, and this process inherits it — which would leave the
    settings window unfocusable behind other apps. Switching the activation
    policy to Regular applies to this process only, and only while it's open.
    """
    if sys.platform != "darwin":
        return
    try:
        from AppKit import NSApplication, NSApplicationActivationPolicyRegular
        NSApplication.sharedApplication().setActivationPolicy_(
            NSApplicationActivationPolicyRegular)
    except Exception:
        pass


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Overshare")
    app.setApplicationDisplayName("Overshare")
    app.setWindowIcon(_icon())
    _become_a_normal_app()

    dark = _prefers_dark()
    app.setStyleSheet(theme.qss(dark))

    window = SettingsWindow(dark)
    window.show()
    window.raise_()
    window.activateWindow()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
