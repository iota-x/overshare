"""The scaffold every settings page is built on."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from ..widgets import Card


@dataclass
class Context:
    """Shared state handed to every page."""

    dark: bool = False
    # Write a transient line into the window's status strip.
    status: object = None
    # Rebuild the window under a new theme (set by main.py).
    retheme: object = None

    def say(self, message: str) -> None:
        if callable(self.status):
            self.status(message)

    def restyle(self) -> None:
        """Re-run the window with whatever theme is now configured."""
        if callable(self.retheme):
            self.retheme()


class Page(QScrollArea):
    """A scrollable column of cards with a title block on top.

    Subclasses set `title` / `blurb` / `nav` and fill `build()` with
    `self.add_card(...)` calls.
    """

    title = ""
    blurb = ""
    nav = ""          # label in the sidebar
    icon = ""         # which vector in gui/icons.py sits next to it

    def __init__(self, ctx: Context):
        super().__init__()
        self.ctx = ctx
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        body = QWidget()
        self._v = QVBoxLayout(body)
        self._v.setContentsMargins(30, 26, 30, 30)
        self._v.setSpacing(14)

        if self.title:
            heading = QLabel(self.title)
            heading.setObjectName("PageTitle")
            self._v.addWidget(heading)
        if self.blurb:
            sub = QLabel(self.blurb)
            sub.setObjectName("PageBlurb")
            sub.setWordWrap(True)
            self._v.addWidget(sub)
        if self.title or self.blurb:
            self._v.addSpacing(6)

        self.build()
        self._v.addStretch(1)
        self.setWidget(body)

    def build(self) -> None:      # pragma: no cover - overridden
        raise NotImplementedError

    def add_card(self, title: str = "", blurb: str = "") -> Card:
        card = Card(title, blurb)
        self._v.addWidget(card)
        return card

    def add_widget(self, widget: QWidget) -> QWidget:
        self._v.addWidget(widget)
        return widget

    def on_show(self) -> None:
        """Called each time the page becomes visible — re-run live checks here."""
