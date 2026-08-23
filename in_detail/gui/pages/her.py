"""Her — the day-to-day preferences, the same ones she can change from Discord."""

from __future__ import annotations

import sys

from ..stores import RUNTIME
from ..widgets import choice_row, text_row
from .base import Page

_DESTINATIONS = [
    ("channel", "The channel"),
    ("dm", "Her DMs"),
    ("both", "Both"),
]

_TONES = [
    ("default", "Default — warm and plain"),
    ("cutesy", "Cutesy — emoji and pet names"),
    ("chill", "Chill — short and low-key"),
    ("detailed", "Detailed — tells her everything"),
]


class HerPage(Page):
    title = "Her preferences"
    blurb = ("Everything on this page she can also change herself from Discord — "
             "this is just the same set of dials, in one place.")
    nav = "💞  Her"

    def build(self) -> None:
        delivery = self.add_card("Delivery")
        row, _ = choice_row(
            RUNTIME, "card_destination", "Send cards to", _DESTINATIONS,
            "DMs need the bot set up on the Setup page.")
        delivery.add_row(row)

        row, _ = choice_row(RUNTIME, "tone", "Tone", _TONES,
                            "How the one-liners are written.", width=240)
        delivery.add_row(row)

        # --- Names ------------------------------------------------------------
        names = self.add_card("Names & status")
        row, _ = text_row(
            RUNTIME, "pet_name", "What the bot calls her",
            "Overrides her name in the good-morning and goodnight lines.",
            placeholder="babe", width=200)
        names.add_row(row)

        row, _ = text_row(
            RUNTIME, "mood", "Your status",
            "A short line shown alongside your activity. Blank for none.",
            placeholder="e.g. deep in it, back at 6", stack=True)
        names.add_row(row)

        row, _ = text_row(
            RUNTIME, "mood_emoji", "Menu-bar icon",
            "Replaces the 💌 glyph up top. One emoji.",
            placeholder="💌", width=70)
        names.add_row(row)

        row, _ = text_row(
            RUNTIME, "her_timezone", "Her timezone",
            "An IANA name like America/New_York, so the menu can show her local "
            "time. Blank to hide it.",
            placeholder="America/New_York", width=220)
        names.add_row(row)

        if sys.platform == "darwin":
            voice = self.add_card("Voice")
            row, _ = text_row(
                RUNTIME, "say_voice", "Voice for !say",
                "A macOS voice name — whatever is installed under System Settings → "
                "Accessibility → Spoken Content. Blank uses the system default.",
                placeholder="system default", width=220)
            voice.add_row(row)
