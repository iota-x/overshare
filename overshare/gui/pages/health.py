"""Health — is everything this needs actually working?

Exists because a Windows install sent a successful test message and then never
sent an update, and there was no way to tell from the outside whether the
webhook was wrong, sharing was paused, or the activity backend hadn't loaded at
all. Every one of those looks identical from the sofa: nothing arrives.

The checks live in `overshare.checkup` so they can run without Qt — CI walks
them, and the tray app can log them on startup.
"""

from __future__ import annotations

import subprocess
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from ... import checkup, collectors, config, log
from ..widgets import button
from .base import Page


class _Line(QWidget):
    """One check: a coloured dot, what it is, what it found, what to do."""

    def __init__(self, check: checkup.Check, dark: bool):
        super().__init__()
        from .. import theme

        c = theme.tokens(dark)
        colour = {"good": c["good"], "bad": c["bad"], "warn": c["warn"]}.get(
            check.state, c["muted"])
        glyph = {"good": "●", "bad": "●", "warn": "●"}.get(check.state, "○")

        self.setObjectName("Bare")
        v = QVBoxLayout(self)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(2)

        top = QLabel(
            f'<span style="color:{colour}">{glyph}</span> '
            f'<b>{check.name}</b> '
            f'<span style="color:{c["muted"]}">— {check.detail}</span>')
        top.setTextFormat(Qt.TextFormat.RichText)
        top.setWordWrap(True)
        v.addWidget(top)

        if check.fix:
            fix = QLabel(check.fix)
            fix.setObjectName("RowHelp")
            fix.setWordWrap(True)
            fix.setContentsMargins(18, 0, 0, 0)
            v.addWidget(fix)


class HealthPage(Page):
    title = "Health"
    blurb = "Everything that has to be true for an update to reach your partner."
    nav = "Health"
    icon = "sliders"

    def build(self) -> None:
        self._results = self.add_card(
            "Checks",
            "Re-run each time you open this page. Nothing here sends a message.")

        # The lines live in their own container that gets emptied and refilled.
        # Adding them straight to the Card would leave a divider behind for every
        # row removed — Card draws one per row and doesn't know they've gone.
        self._list = QWidget()
        self._list.setObjectName("Bare")
        self._list_v = QVBoxLayout(self._list)
        self._list_v.setContentsMargins(0, 0, 0, 0)
        self._list_v.setSpacing(9)

        bar = QWidget()
        bar.setObjectName("Bare")
        line = QHBoxLayout(bar)
        line.setContentsMargins(0, 4, 0, 0)
        line.setSpacing(8)
        again = button("Run again", accent=True)
        again.clicked.connect(self._refresh)
        line.addWidget(again)
        copy = button("Copy report")
        copy.clicked.connect(self._copy)
        line.addWidget(copy)
        if sys.platform == "darwin":
            # Updating the app revokes this every time, so it's the one thing
            # here worth a button rather than a sentence.
            grant = button("Fix Accessibility")
            grant.clicked.connect(self._grant)
            line.addWidget(grant)
        line.addStretch(1)
        self._results.add_widget(bar)
        self._results.add_widget(self._list)

        # --- inviting the bot -------------------------------------------------
        self._invite_card = self.add_card(
            "Invite the bot",
            "A bot has to be invited to the server before it can reply to "
            "anything. The link is built from your token.")
        self._invite_label = QLabel()
        self._invite_label.setObjectName("RowHelp")
        self._invite_label.setWordWrap(True)
        self._invite_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction)
        self._invite_label.setOpenExternalLinks(True)
        self._invite_card.add_widget(self._invite_label)

        self._invite_btn = button("Copy invite link")
        self._invite_btn.clicked.connect(self._copy_invite)
        self._invite_card.add_widget(self._invite_btn)

        # --- what the sender has actually been doing --------------------------
        # The tray app is a different process; this file is the only window onto
        # it. Showing it here beats telling someone to go and open a log.
        self._recent_card = self.add_card(
            "Recent activity",
            "The last few things the app recorded, newest at the bottom.")
        self._recent = QLabel()
        self._recent.setObjectName("RowHelp")
        self._recent.setWordWrap(True)
        self._recent.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        self._recent_card.add_widget(self._recent)

        # --- where to look when it goes wrong ---------------------------------
        where = self.add_card("Files", "Where this app keeps things.")
        for label, path in (("Settings", str(config.CONFIG_PATH)),
                            ("Log", log.path())):
            row = QLabel(f"<b>{label}</b><br>{path}")
            row.setObjectName("RowHelp")
            row.setWordWrap(True)
            row.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse)
            where.add_widget(row)

        self._refresh()

    # --- live ----------------------------------------------------------------
    def on_show(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        config.reload()          # the reader may have just changed something
        while self._list_v.count():
            item = self._list_v.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

        self._checks = checkup.run()
        for check in self._checks:
            self._list_v.addWidget(_Line(check, self.ctx.dark))

        url = checkup.bot_invite_url()
        if url:
            self._invite_label.setText(
                f'<a href="{url}" style="color:#FF6FA5">Open the invite page</a>'
                "<br>Pick your server, then Authorise. "
                "The link already asks for exactly what the bot uses — nothing more.")
            self._invite_btn.setEnabled(True)
        else:
            self._invite_label.setText(
                "Paste a bot token on the Partner page and this fills itself in.")
            self._invite_btn.setEnabled(False)

        lines = log.tail(10)
        self._recent.setText(
            "<br>".join(l.replace("&", "&amp;").replace("<", "&lt;") for l in lines)
            or "Nothing recorded yet.")

        bad = [c for c in self._checks if c.state == "bad"]
        if bad:
            self.ctx.say(f"{len(bad)} thing{'s' if len(bad) > 1 else ''} "
                         "stopping updates — see below")
        else:
            self.ctx.say("everything needed is in place")

    def _copy(self) -> None:
        """A report worth pasting into a bug report."""
        import platform

        lines = [f"Overshare health — {platform.system()} {platform.release()}"]
        for c in getattr(self, "_checks", []):
            lines.append(f"[{c.state}] {c.name}: {c.detail}")
        QApplication.clipboard().setText("\n".join(lines))
        self.ctx.say("report copied")

    def _copy_invite(self) -> None:
        url = checkup.bot_invite_url()
        if url:
            QApplication.clipboard().setText(url)
            self.ctx.say("invite link copied")

    def _grant(self) -> None:
        """Ask macOS for the permission, and open the pane either way.

        The prompt only appears if the app isn't already trusted, and macOS
        shows it once per launch — so the pane is opened as well, which is what
        actually helps when the entry is there but stale after an update.
        """
        collectors.ask_for_permission()
        subprocess.Popen([
            "open",
            "x-apple.systempreferences:com.apple.preference.security"
            "?Privacy_Accessibility"])
        self.ctx.say("re-grant Overshare, then quit and reopen it")
