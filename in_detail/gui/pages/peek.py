"""Privacy — the blocklist, and the camera/screen switches."""

from __future__ import annotations

from ..stores import CFG, RUNTIME
from ..widgets import Group, slider_row, text_row, toggle_row
from .base import Page


class PeekPage(Page):
    title = "Privacy"
    blurb = ("What never leaves this machine, and what they're allowed to look at "
             "when they ask.")
    nav = "Privacy"
    icon = "lock"

    def build(self) -> None:
        dark = self.ctx.dark

        # --- Blocklist -----------------------------------------------------------
        block = self.add_card(
            "Never share these",
            "Anything matching is replaced with a vague line instead of being "
            "described \u2014 and it's kept out of the daily and weekly recaps too, "
            "so it can't quietly reappear there later.")
        body = Group()
        row, _ = toggle_row(
            CFG, "PRIVACY_ENABLED", "Hide private activity", "",
            dark=dark, on_change=body.setEnabled)
        block.add_row(row)

        row, _ = toggle_row(
            CFG, "PRIVACY_HIDE_INCOGNITO", "Private & incognito windows",
            "Recognised from the window title, which is the only signal either OS "
            "offers \u2014 a browser that words it unusually could slip through.",
            dark=dark)
        body.add_row(row)

        row, _ = toggle_row(
            CFG, "PRIVACY_HIDE_PASSWORDS", "Password managers",
            "1Password, Bitwarden, KeePass, LastPass, Dashlane, Proton Pass, "
            "Keychain Access and friends.",
            dark=dark)
        body.add_row(row)

        row, _ = toggle_row(
            CFG, "PRIVACY_HIDE_FINANCE", "Banking, money & tax",
            "Banks, card issuers, brokers, crypto exchanges, payment apps and tax "
            "sites. It can't know every bank in the world \u2014 add yours below if "
            "it slips through.",
            dark=dark)
        body.add_row(row)

        row, _ = text_row(
            CFG, "PRIVACY_APPS", "Also hide these apps",
            "Comma separated, matched against the app's name and its bundle id.",
            placeholder="Photos, Journal, \u2026", stack=True)
        body.add_row(row)

        row, _ = text_row(
            CFG, "PRIVACY_SITES", "\u2026 and these sites",
            "Matched anywhere in the address \u2014 \u201cmyclinic.org\u201d, or just \u201cclinic\u201d.",
            placeholder="myclinic.org, therapy", stack=True)
        body.add_row(row)

        row, _ = text_row(
            CFG, "PRIVACY_WORDS", "\u2026 and any title containing",
            "Matched against window titles, tab titles and addresses. For a "
            "filename you'd rather wasn't announced.",
            placeholder="salary, diagnosis", stack=True)
        body.add_row(row)

        row, _ = text_row(
            CFG, "PRIVACY_LABEL", "They see instead", "",
            placeholder="something private \U0001F512", width=250)
        body.add_row(row)

        block.add_widget(body)
        body.setEnabled(bool(CFG.get("PRIVACY_ENABLED")))

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
            "What they can look at",
            "These two are also on the menu-bar menu, for a quick flip mid-call.")
        row, _ = toggle_row(
            RUNTIME, "camera_enabled", "Webcam photos",
            "The green camera light always comes on, whatever else is set.",
            dark=dark)
        self._sources.add_row(row)

        row, _ = toggle_row(
            RUNTIME, "screen_enabled", "Screenshots",
            "Sends whatever is on screen at that moment — including anything you'd "
            "rather they didn't see.", dark=dark)
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
            CFG, "PEEK_NOTIFY", "Ping me every time they look",
            "Off means they can look without you being notified. The camera light "
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
