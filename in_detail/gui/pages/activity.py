"""Activity — what gets noticed, and how eagerly it gets sent."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QHBoxLayout, QWidget

from ... import config
from ..stores import CFG, RUNTIME
from ..widgets import button, slider_row, toggle_row
from .base import Page

# Whole-feel presets, so the five sliders below stay optional.
_PRESETS = {
    "Relaxed": {"POLL_INTERVAL": 5.0, "STABILIZE": 6.0, "MIN_GAP": 20.0,
                "HEARTBEAT": 900.0},
    "Balanced": {"POLL_INTERVAL": 2.0, "STABILIZE": 2.0, "MIN_GAP": 4.0,
                 "HEARTBEAT": 300.0},
    "Clingy": {"POLL_INTERVAL": 1.0, "STABILIZE": 1.0, "MIN_GAP": 2.0,
               "HEARTBEAT": 120.0},
}


def _minutes(value: float) -> str:
    return f"{value / 60:g} min"


class ActivityPage(Page):
    title = "Activity"
    blurb = "What she finds out about, and how quickly."
    nav = "Activity"
    icon = "eye"

    def build(self) -> None:
        dark = self.ctx.dark

        # --- The master switch ----------------------------------------------
        # Pausing used to be menu-bar-only and lived in memory, so it couldn't
        # be reached from here and quietly resumed after a restart.
        master = self.add_card(
            "Sharing",
            "The one switch that stops everything. She's told the updates "
            "stopped, never what you were doing when they did.")
        row, _ = toggle_row(
            RUNTIME, "paused", "Pause sharing",
            "Nothing goes out while this is on \u2014 no activity, no recaps, no "
            "good-mornings. It stays paused until you turn it off, even if you "
            "quit and reopen.",
            dark=dark)
        master.add_row(row)

        # --- What ---------------------------------------------------------------
        what = self.add_card("What gets shared")
        row, _ = toggle_row(
            CFG, "REPORT_TITLES", "Window and document titles",
            "The difference between “on Notion” and “on Notion — Q3 planning”. "
            "This is what reads the channel you're in on Discord, the document "
            "you have open, the video you're watching. Turn it off and she gets "
            "the app name and nothing else.",
            dark=dark)
        what.add_row(row)

        row, _ = toggle_row(
            CFG, "REPORT_MEDIA", "Background music",
            "Lets a message read “watching X while Y plays”. A song change counts "
            "as an update on its own.", dark=dark)
        what.add_row(row)

        row, _ = toggle_row(
            CFG, "READ_BROWSER_URL", "Read the browser address bar",
            "Windows only. It's what unlocks per-site cards, links and video "
            "thumbnails there — but it's slow, so it can be turned off."
            + ("" if sys.platform.startswith("win") else "  Has no effect on this Mac."),
            dark=dark)
        what.add_row(row)
        if not sys.platform.startswith("win"):
            row.setEnabled(False)

        # --- Pace -----------------------------------------------------------------
        pace = self.add_card(
            "Pace", "Start with a preset. The sliders are there if you want them.")

        presets = QWidget()

        presets.setObjectName("Bare")
        line = QHBoxLayout(presets)
        line.setContentsMargins(0, 0, 0, 4)
        line.setSpacing(8)
        for name in _PRESETS:
            btn = button(name)
            btn.clicked.connect(lambda _=False, n=name: self._apply_preset(n))
            line.addWidget(btn)
        line.addStretch(1)
        pace.add_widget(presets, separated=False)

        self._sliders = {}
        row, self._sliders["POLL_INTERVAL"] = slider_row(
            CFG, "POLL_INTERVAL", "Check every", 0.5, 10.0,
            "How often we look at what you're doing. Lower feels instant on a "
            "tab switch and costs a little more battery.",
            step=0.5, suffix="s")
        pace.add_row(row)

        row, self._sliders["STABILIZE"] = slider_row(
            CFG, "STABILIZE", "Settle for", 0.0, 15.0,
            "How long you have to stay on something before it's announced — "
            "enough to skip a quick flick through tabs.",
            step=0.5, suffix="s")
        pace.add_row(row)

        row, self._sliders["MIN_GAP"] = slider_row(
            CFG, "MIN_GAP", "Wait between updates", 0.0, 60.0,
            "A floor between messages, so a burst of switching doesn't flood her.",
            step=1.0, suffix="s")
        pace.add_row(row)

        row, self._sliders["HEARTBEAT"] = slider_row(
            CFG, "HEARTBEAT", "Nudge again after", 60.0, 1800.0,
            "If you stay on one thing, re-send with the running time "
            "(“still on X, ~12 min”).",
            step=60.0, fmt=_minutes)
        pace.add_row(row)

        row, self._sliders["IDLE_THRESHOLD"] = slider_row(
            CFG, "IDLE_THRESHOLD", "Counts as away after", 60.0, 1800.0,
            "No keyboard or mouse for this long and you've “stepped away”.",
            step=60.0, fmt=_minutes)
        pace.add_row(row)

    def _apply_preset(self, name: str) -> None:
        config.save(_PRESETS[name])
        self._refresh_sliders()
        self.ctx.say(f"Switched to the {name.lower()} pace")

    def _refresh_sliders(self) -> None:
        """Rebuild slider positions from config after a bulk change."""
        for key, slider in self._sliders.items():
            value = float(getattr(config, key, 0) or 0)
            low, step = _RANGES[key]
            slider.setValue(max(0, min(slider.maximum(), int(round((value - low) / step)))))


# Mirrors the (low, step) pairs passed to slider_row above, so a preset can map
# a stored value back onto the right tick.
_RANGES = {
    "POLL_INTERVAL": (0.5, 0.5),
    "STABILIZE": (0.0, 0.5),
    "MIN_GAP": (0.0, 1.0),
    "HEARTBEAT": (60.0, 60.0),
    "IDLE_THRESHOLD": (60.0, 60.0),
}
