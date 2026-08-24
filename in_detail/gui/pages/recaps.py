"""Recaps — the scheduled sends: nightly summary, weekly wrap, daily bookends."""

from __future__ import annotations

from ..stores import CFG, RUNTIME
from ..widgets import Group, choice_row, slider_row, time_row, toggle_row
from .base import Page

_DAYS = [("mon", "Monday"), ("tue", "Tuesday"), ("wed", "Wednesday"),
         ("thu", "Thursday"), ("fri", "Friday"), ("sat", "Saturday"),
         ("sun", "Sunday")]


class RecapsPage(Page):
    title = "Recaps & rituals"
    blurb = "The messages that go out on a clock rather than because you moved."
    nav = "Recaps"
    icon = "calendar"

    def build(self) -> None:
        dark = self.ctx.dark

        # Each section is one card: the switch, then the settings it governs,
        # greyed out until it's on.
        # --- Nightly -------------------------------------------------------------
        daily = self.add_card(
            "Nightly recap",
            "One card at the end of the day: active time, where it went, what you "
            "watched, the soundtrack.")
        body = Group()
        row, _ = toggle_row(
            CFG, "RECAP_ENABLED", "Send a nightly recap", "",
            dark=dark, on_change=body.setEnabled)
        daily.add_row(row)

        row, _ = time_row(CFG, "RECAP_TIME", "Send at", "Your local time.")
        body.add_row(row)
        row, _ = slider_row(
            CFG, "RECAP_MIN_MINUTES", "Skip days under", 0.0, 60.0,
            "A day with barely any activity isn't worth a card.",
            step=5.0, suffix=" min")
        body.add_row(row)
        daily.add_widget(body)
        body.setEnabled(bool(CFG.get("RECAP_ENABLED")))

        # --- Weekly ----------------------------------------------------------------
        weekly = self.add_card(
            "Weekly wrapped",
            "Top apps, what you watched, the week's soundtrack, streaks, late nights.")
        body = Group()
        row, _ = toggle_row(
            CFG, "WEEKLY_ENABLED", "Send a weekly wrap", "",
            dark=dark, on_change=body.setEnabled)
        weekly.add_row(row)

        row, _ = choice_row(CFG, "WEEKLY_DAY", "On", _DAYS, width=150)
        body.add_row(row)
        row, _ = time_row(CFG, "WEEKLY_TIME", "At", "")
        body.add_row(row)
        weekly.add_widget(body)
        body.setEnabled(bool(CFG.get("WEEKLY_ENABLED")))

        # --- Bookends ----------------------------------------------------------------
        morning = self.add_card(
            "Good morning",
            "Goes out on schedule whether or not you're awake for it.")
        body = Group()
        row, _ = toggle_row(
            CFG, "GM_ENABLED", "Send a good-morning message", "",
            dark=dark, on_change=body.setEnabled)
        morning.add_row(row)
        row, _ = time_row(CFG, "GM_TIME", "Send at", "")
        body.add_row(row)
        morning.add_widget(body)
        body.setEnabled(bool(CFG.get("GM_ENABLED")))

        # --- Daily extras ---------------------------------------------------------------
        extras = self.add_card(
            "Daily extras", "Both are off until you turn them on.")

        selfie_body = Group()
        row, _ = toggle_row(
            RUNTIME, "selfie_enabled", "Automatic check-in selfie",
            "One webcam photo a day, sent without them having to ask.",
            dark=dark, on_change=selfie_body.setEnabled)
        extras.add_row(row)
        row, _ = time_row(RUNTIME, "selfie_time", "Selfie at", "")
        selfie_body.add_row(row)
        extras.add_widget(selfie_body)
        selfie_body.setEnabled(bool(RUNTIME.get("selfie_enabled")))

        question_body = Group()
        row, _ = toggle_row(
            RUNTIME, "daily_question_enabled", "Question of the day",
            "A small prompt for them to answer, once a day.",
            dark=dark, on_change=question_body.setEnabled)
        extras.add_row(row)
        row, _ = time_row(RUNTIME, "daily_question_time", "Question at", "")
        question_body.add_row(row)
        extras.add_widget(question_body)
        question_body.setEnabled(bool(RUNTIME.get("daily_question_enabled")))
