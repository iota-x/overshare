"""Advanced — appearance of the webhook, where files live, and the reset button."""

from __future__ import annotations

import subprocess
import sys

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QWidget

from ... import config, settings
from ..stores import CFG
from ..widgets import button, text_row, toggle_row
from .base import Page


class AdvancedPage(Page):
    title = "Advanced"
    blurb = "Things you'll probably only touch once."
    nav = "⚙️  Advanced"

    def build(self) -> None:
        dark = self.ctx.dark

        # --- Appearance ---------------------------------------------------------
        look = self.add_card(
            "How the messages look in Discord",
            "The name and avatar the webhook posts under.")
        row, _ = text_row(
            CFG, "WEBHOOK_USERNAME", "Posts as", "",
            placeholder="in detail 💬", width=220)
        look.add_row(row)
        row, _ = text_row(
            CFG, "WEBHOOK_AVATAR_URL", "Avatar image",
            "A direct link to an image. Blank uses the webhook's own avatar.",
            placeholder="https://…", stack=True)
        look.add_row(row)

        # --- Startup -------------------------------------------------------------
        startup = self.add_card("Startup")
        row, _ = toggle_row(
            CFG, "START_PAUSED", "Start paused",
            "Launches asleep (😴 in the menu bar) until you un-pause it yourself.",
            dark=dark)
        startup.add_row(row)

        # --- Files ---------------------------------------------------------------
        files = self.add_card(
            "Your data",
            "Settings, daily tallies and history all live in one folder. Nothing "
            "is sent anywhere except your own Discord channel.")

        path = QLabel(str(config.DATA_DIR))
        path.setObjectName("RowHelp")
        path.setWordWrap(True)
        path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        files.add_widget(path, separated=False)

        actions = QWidget()

        actions.setObjectName("Bare")
        line = QHBoxLayout(actions)
        line.setContentsMargins(0, 10, 0, 0)
        line.setSpacing(8)
        open_btn = button("Open folder")
        open_btn.clicked.connect(self._open_folder)
        line.addWidget(open_btn)
        line.addStretch(1)
        files.add_raw(actions)

        # --- Reset ----------------------------------------------------------------
        danger = self.add_card(
            "Start over",
            "Clears every setting on every page and returns the app to a fresh "
            "install. Your daily history is kept.")
        reset = QWidget()
        reset.setObjectName("Bare")
        line = QHBoxLayout(reset)
        line.setContentsMargins(0, 4, 0, 0)
        reset_btn = button("Reset all settings")
        reset_btn.clicked.connect(self._reset)
        line.addWidget(reset_btn)
        line.addStretch(1)
        danger.add_widget(reset, separated=False)

    # --- actions ----------------------------------------------------------------
    def _open_folder(self) -> None:
        config.DATA_DIR.mkdir(parents=True, exist_ok=True)
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(config.DATA_DIR)])
        elif sys.platform.startswith("win"):
            subprocess.Popen(["explorer", str(config.DATA_DIR)])
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(config.DATA_DIR)))

    def _reset(self) -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Reset all settings?")
        box.setText("Reset every setting to its default?")
        box.setInformativeText(
            "Your webhook link, keys and preferences are cleared. The daily "
            "history in your data folder is kept. This can't be undone.")
        box.setStandardButtons(
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Reset)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if box.exec() != QMessageBox.StandardButton.Reset:
            return

        for target in (config.CONFIG_PATH, config.DATA_DIR / "settings.json"):
            try:
                target.unlink()
            except OSError:
                pass
        config.reload()
        settings._cache = None   # drop the in-process copy of what we just deleted
        self.ctx.say("Settings reset — reopen this window to see the defaults")
