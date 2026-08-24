"""Peek — the camera and screen switches, and the warning that goes with them."""

from __future__ import annotations

from ..stores import CFG, RUNTIME
from ..widgets import slider_row, text_row, toggle_row
from .base import Page


class PeekPage(Page):
    title = "Camera & screen"
    blurb = ("She can ask for a webcam photo or a screenshot on demand. These are "
             "the switches that decide whether that's possible at all.")
    nav = "Privacy"
    icon = "lock"

    def build(self) -> None:
        dark = self.ctx.dark

        master = self.add_card(
            "Master switch",
            "Off means no camera or screen request works, whatever the switches "
            "below say.")
        row, self._master = toggle_row(
            CFG, "PEEK_ENABLED", "Allow peeking at all", "",
            dark=dark, on_change=lambda value: self._sources.setEnabled(value))
        master.add_row(row)

        # --- Per-source ----------------------------------------------------------
        self._sources = self.add_card(
            "What she can look at",
            "These two are also on the menu-bar menu, for a quick flip mid-call.")
        row, _ = toggle_row(
            RUNTIME, "camera_enabled", "Webcam photos",
            "The green camera light always comes on, whatever else is set.",
            dark=dark)
        self._sources.add_row(row)

        row, _ = toggle_row(
            RUNTIME, "screen_enabled", "Screenshots",
            "Sends whatever is on screen at that moment — including anything you'd "
            "rather she didn't see.", dark=dark)
        self._sources.add_row(row)

        row, _ = toggle_row(
            RUNTIME, "mirror_capture", "Mirror the webcam",
            "Flips photos left-to-right so they look like a mirror rather than the "
            "reversed-feeling raw frame.", dark=dark)
        self._sources.add_row(row)

        row, _ = text_row(
            RUNTIME, "camera_device", "Pin a camera",
            "Match part of a camera's name (“FaceTime”) so a virtual cam like OBS "
            "can't stand in for it. Blank picks the first real camera.",
            placeholder="auto", width=200)
        self._sources.add_row(row)
        self._sources.setEnabled(bool(self._master.isChecked()))

        # --- Being told ------------------------------------------------------------
        told = self.add_card("Being told about it")
        row, _ = toggle_row(
            CFG, "PEEK_NOTIFY", "Ping me every time she looks",
            "Off means she can look without you being notified. The camera light "
            "still comes on regardless.", dark=dark)
        told.add_row(row)

        live = self.add_card(
            "Live view",
            "`!live` sends a frame that keeps refreshing for a short burst.")
        row, _ = slider_row(
            CFG, "LIVE_SECONDS", "Burst lasts", 5.0, 120.0, "", step=5.0, suffix="s")
        live.add_row(row)
        row, _ = slider_row(
            CFG, "LIVE_INTERVAL", "New frame every", 1.0, 10.0, "",
            step=0.5, suffix="s")
        live.add_row(row)
