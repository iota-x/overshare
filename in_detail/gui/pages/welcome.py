"""Welcome — what this app is, before anyone is asked to configure it.

The window used to open straight onto a form asking for a Discord webhook,
which assumes the reader already knows what they downloaded and why. This says
what it does and what it will and won't share, then hands off to Setup.

It stays in the sidebar afterwards, because it's also where the answer lives
when someone comes back in three months wondering what a "peek" was.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ... import config
from .. import icons
from ..widgets import button
from .base import Page

# icon, heading, body — the whole product in three beats.
_STEPS = [
    ("eye", "It notices",
     "The app you're in, the file you're editing, the tab you're reading, the "
     "song playing behind it — and when you've wandered off."),
    ("sparkle", "It writes",
     "A warm one-liner, not a log entry. Free AI, a model running on this "
     "computer, or plain templates with no AI at all."),
    ("envelope", "They get it",
     "A rich card in Discord or Telegram, with links and thumbnails. They can "
     "reply, react, and ask for a photo — and you're told every time."),
]

_FACTS = [
    ("lock", "You decide what's off-limits",
     "Password managers and private windows are hidden out of the box. Add "
     "your own apps, sites and words on the Privacy page."),
    ("calendar", "It sums up your day",
     "A nightly recap and a weekly wrapped — top apps, what you watched, the "
     "soundtrack, late nights."),
    ("sliders", "It's yours to tune",
     "Every dial is in this window, and changes apply while it's running. "
     "Nothing needs restarting."),
]


class WelcomePage(Page):
    title = ""          # the hero does the titling
    nav = "Welcome"
    icon = "heart"

    def build(self) -> None:
        dark = self.ctx.dark

        self.add_widget(self._hero(dark))
        self._section("How it works")
        self.add_widget(self._cards(_STEPS, dark, numbered=True))
        self._section("Worth knowing")
        self.add_widget(self._cards(_FACTS, dark, numbered=False))
        self.add_widget(self._reassurance(dark))

    # --- pieces -----------------------------------------------------------
    def _hero(self, dark: bool) -> QWidget:
        hero = QWidget()
        hero.setObjectName("Hero")
        outer = QHBoxLayout(hero)
        outer.setContentsMargins(26, 26, 26, 26)
        outer.setSpacing(20)

        from .. import theme
        mark = QLabel()
        mark.setPixmap(icons.pixmap("envelope", theme.tokens(dark)["accent"], 52))
        mark.setFixedWidth(56)
        mark.setAlignment(Qt.AlignmentFlag.AlignTop)
        outer.addWidget(mark)

        column = QVBoxLayout()
        column.setSpacing(4)
        line = QLabel("Tell them everything.")
        line.setObjectName("HeroTitle")
        column.addWidget(line)
        line = QLabel("Without typing a word.")
        line.setObjectName("HeroAccent")
        column.addWidget(line)

        blurb = QLabel(
            "Overshare watches what you're doing on this computer and sends "
            "your partner a warm little update about it — automatically, all "
            "day. It takes one link to set up.")
        blurb.setObjectName("HeroSub")
        blurb.setWordWrap(True)
        column.addSpacing(8)
        column.addWidget(blurb)

        actions = QWidget()
        actions.setObjectName("Bare")
        row = QHBoxLayout(actions)
        row.setContentsMargins(0, 14, 0, 0)
        row.setSpacing(9)
        cta = button(
            "Set it up" if not config.is_configured() else "Open settings",
            accent=True)
        cta.clicked.connect(lambda: self.ctx.goto("Setup"))
        row.addWidget(cta)

        if config.is_configured():
            note = QLabel("Already connected")
            note.setObjectName("StepBody")
            row.addWidget(note)
        row.addStretch(1)
        column.addWidget(actions)

        outer.addLayout(column, 1)
        return hero

    def _section(self, text: str) -> None:
        label = QLabel(text)
        label.setObjectName("CardTitle")
        label.setContentsMargins(2, 10, 0, 0)
        self.add_widget(label)

    def _cards(self, items, dark: bool, *, numbered: bool) -> QWidget:
        from .. import theme
        holder = QWidget()
        holder.setObjectName("Bare")
        grid = QGridLayout(holder)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)

        for i, (icon, heading, body) in enumerate(items):
            card = QWidget()
            card.setObjectName("Step")
            column = QVBoxLayout(card)
            column.setContentsMargins(16, 15, 16, 16)
            column.setSpacing(3)

            top = QHBoxLayout()
            top.setSpacing(8)
            mark = QLabel()
            mark.setPixmap(icons.pixmap(icon, theme.tokens(dark)["accent"], 20))
            top.addWidget(mark, 0, Qt.AlignmentFlag.AlignVCenter)
            if numbered:
                num = QLabel(f"{i + 1:02d}")
                num.setObjectName("StepNum")
                top.addWidget(num, 0, Qt.AlignmentFlag.AlignVCenter)
            top.addStretch(1)
            column.addLayout(top)
            column.addSpacing(6)

            label = QLabel(heading)
            label.setObjectName("StepTitle")
            column.addWidget(label)
            text = QLabel(body)
            text.setObjectName("StepBody")
            text.setWordWrap(True)
            column.addWidget(text)
            column.addStretch(1)

            grid.addWidget(card, 0, i)
            grid.setColumnStretch(i, 1)
        return holder

    def _reassurance(self, dark: bool) -> QWidget:
        from .. import theme
        box = QWidget()
        box.setObjectName("Reassure")
        row = QHBoxLayout(box)
        row.setContentsMargins(18, 16, 18, 16)
        row.setSpacing(14)

        mark = QLabel()
        mark.setPixmap(icons.pixmap("lock", theme.tokens(dark)["muted"], 22))
        mark.setFixedWidth(26)
        mark.setAlignment(Qt.AlignmentFlag.AlignTop)
        row.addWidget(mark)

        text = QLabel(
            "Your activity goes to the one channel you choose and nowhere "
            "else — there's no account here and no server of ours in the "
            "middle. Everything is stored on this computer, and you can pause "
            "the whole thing from the menu bar whenever you like.")
        text.setObjectName("StepBody")
        text.setWordWrap(True)
        row.addWidget(text, 1)
        return box
