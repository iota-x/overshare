"""Advanced — appearance of the webhook, where files live, and the reset button."""

from __future__ import annotations

import subprocess
import sys

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QHBoxLayout, QLabel, QMessageBox,
                               QWidget)

from ... import config, settings, uninstall, updates, version
from ..stores import CFG
from ..probes import Prober
from ..widgets import (Row, Switch, button, choice_row, text_row,
                       toggle_row)
from .base import Page


class AdvancedPage(Page):
    title = "Advanced"
    blurb = "Things you'll probably only touch once."
    nav = "Advanced"
    icon = "sliders"

    def build(self) -> None:
        dark = self.ctx.dark

        # --- Theme ----------------------------------------------------------------
        appearance = self.add_card(
            "Appearance",
            "Applies to this window. The menu-bar icon always follows the system.")
        row, _ = choice_row(
            CFG, "UI_THEME", "Theme",
            [("system", "Match my system"), ("light", "Light"), ("dark", "Dark")],
            "", width=180, on_change=lambda _: self.ctx.restyle())
        appearance.add_row(row)

        # --- How it looks in Discord ----------------------------------------------
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

        # --- Updates ----------------------------------------------------------
        up = self.add_card(
            "Updates",
            f"You're on {version.VERSION}. Checked against the releases page — "
            "nothing is downloaded until you ask.")
        self._up_status = QLabel("Checking…")
        self._up_status.setObjectName("RowHelp")
        self._up_status.setWordWrap(True)
        up.add_widget(self._up_status, separated=False)

        row = QWidget()
        row.setObjectName("Bare")
        line = QHBoxLayout(row)
        line.setContentsMargins(0, 8, 0, 0)
        line.setSpacing(8)
        self._up_check = button("Check again")
        self._up_check.clicked.connect(self._check_updates)
        line.addWidget(self._up_check)
        self._up_get = button("Download and install", accent=True)
        self._up_get.setVisible(False)
        self._up_get.clicked.connect(self._get_update)
        line.addWidget(self._up_get)
        line.addStretch(1)
        up.add_widget(row, separated=False)

        self._release = None
        self._up_worker = Prober(self)
        self._up_worker.finished.connect(self._show_update)
        self._check_updates()

        # --- Uninstall --------------------------------------------------------
        # Windows gets the worst of this: a per-user Inno install isn't in
        # Program Files, "Overshare" is easy to miss in Installed apps, and the
        # usual outcome is deleting the shortcut while the tray app keeps
        # running. The uninstaller sits next to the binary; this runs it.
        if uninstall.available():
            gone = self.add_card(
                "Uninstall",
                "Removes Overshare from this computer. They stop hearing "
                "anything the moment it closes.")
            # A Row + Switch, like every other toggle here. A bare QCheckBox
            # renders as a featureless pill: the stylesheet draws its indicator
            # as a track with no knob and no tick, left from before the switch
            # was painted by hand.
            self._wipe = Switch(False, dark=dark)
            gone.add_widget(
                Row("Also delete my settings and history",
                    "Off keeps them, so reinstalling picks up where you left off.",
                    self._wipe),
                separated=False)

            row = QWidget()
            row.setObjectName("Bare")
            line = QHBoxLayout(row)
            line.setContentsMargins(0, 8, 0, 0)
            btn = button("Uninstall Overshare")
            btn.clicked.connect(self._uninstall)
            line.addWidget(btn)
            line.addStretch(1)
            gone.add_widget(row, separated=False)

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

    def _uninstall(self) -> None:
        wipe = self._wipe.isChecked()
        where = "moved to the Trash" if sys.platform == "darwin" \
            else "removed by the Windows uninstaller"

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Uninstall Overshare?")
        box.setText("Uninstall Overshare from this computer?")
        box.setInformativeText(
            f"The app is {where}, and it stops sending straight away.\n\n"
            + ("Your settings and history are deleted too — that can't be undone."
               if wipe else
               "Your settings and history are kept, so reinstalling picks up "
               "where you left off."))
        box.setStandardButtons(
            QMessageBox.StandardButton.Cancel | QMessageBox.StandardButton.Yes)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        if box.exec() != QMessageBox.StandardButton.Yes:
            return

        problem = uninstall.run(also_data=wipe)
        if problem:
            self.ctx.say(problem)
            return
        # Nothing left worth showing: the app this window belongs to is going.
        QApplication.quit()

    # --- updates -----------------------------------------------------------
    def _check_updates(self) -> None:
        self._up_status.setText("Checking…")
        self._up_check.setEnabled(False)
        self._up_get.setVisible(False)
        # Prober wraps this on a worker thread — a network call on the UI
        # thread would freeze the window for as long as GitHub takes.
        self._up_worker.run(updates.latest)

    def _show_update(self, rel) -> None:
        self._up_check.setEnabled(True)
        self._release = rel if getattr(rel, "newer", False) else None

        if rel is None or not hasattr(rel, "version"):
            self._up_status.setText(
                "Couldn't reach GitHub just now. You're still on "
                f"{version.VERSION}.")
            return
        if not rel.newer:
            self._up_status.setText(f"Up to date — {version.VERSION} is the latest.")
            return

        mb = rel.size / 1048576 if rel.size else 0
        note = (f"<b>{rel.version} is out</b> — you're on {version.VERSION}. "
                f"{mb:.0f} MB.")
        if sys.platform == "darwin":
            note += ("<br>macOS drops the Accessibility grant when the app is "
                     "replaced, so re-grant it afterwards or updates stop "
                     "naming what you're in.")
        self._up_status.setText(note)
        self._up_get.setVisible(True)

    def _get_update(self) -> None:
        rel = self._release
        if rel is None:
            return
        self._up_get.setEnabled(False)
        self._up_status.setText("Downloading…")

        def fetch():
            return updates.download(rel)

        worker = Prober(self)
        worker.finished.connect(self._downloaded)
        self._up_fetch = worker            # keep it alive until it reports
        worker.run(fetch)

    def _downloaded(self, path) -> None:
        self._up_get.setEnabled(True)
        if not isinstance(path, str):
            # Prober turns an exception into a Result; either way it didn't work.
            self._up_status.setText(
                "That download didn't verify, so it was thrown away. "
                "Try again, or grab it from the releases page.")
            return
        self._up_status.setText(
            "Downloaded and checksum verified. The installer is opening — "
            "quit Overshare before running it.")
        updates.reveal(path)
