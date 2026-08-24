"""Setup — the only page that has to be filled in for the app to do anything."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from ... import config
from .. import probes
from ..stores import CFG
from ..widgets import Row, StatusDot, button, text_row
from .base import Page

_WEBHOOK_HELP = (
    "In Discord: right-click the channel → Edit Channel → Integrations → "
    "Webhooks → New Webhook → Copy Webhook URL."
)


class SetupPage(Page):
    title = "Setup"
    blurb = "One link is all it takes to start. Everything else is optional."
    nav = "Setup"
    icon = "envelope"

    def build(self) -> None:
        dark = self.ctx.dark

        # --- Where the updates land ------------------------------------------
        card = self.add_card(
            "Where updates go",
            "The Discord channel that receives your activity cards.",
        )

        self._hook_status = StatusDot(dark)
        row, self._hook_field = text_row(
            CFG, "DISCORD_WEBHOOK_URL", "Webhook link", _WEBHOOK_HELP,
            placeholder="https://discord.com/api/webhooks/…",
            stack=True, on_change=lambda _: self._check_webhook(),
        )
        card.add_row(row)
        card.add_raw(self._hook_status)

        actions = QWidget()

        actions.setObjectName("Bare")
        line = QHBoxLayout(actions)
        line.setContentsMargins(0, 8, 0, 0)
        line.setSpacing(8)
        self._test_btn = button("Send a test message", accent=True)
        self._test_btn.clicked.connect(self._send_test)
        line.addWidget(self._test_btn)
        guide = button("How do I get this?", flat=True)
        guide.clicked.connect(lambda: QDesktopServices.openUrl(
            "https://support.discord.com/hc/en-us/articles/228383668"))
        line.addWidget(guide)
        line.addStretch(1)
        card.add_raw(actions)

        # --- Telegram ------------------------------------------------------------
        tg = self.add_card(
            "Telegram  ·  optional",
            "Not everyone is on Discord. Fill this in and the same cards go to "
            "Telegram too — having both on at once is fine.")

        self._tg_status = StatusDot(dark)
        row, self._tg_token = text_row(
            CFG, "TELEGRAM_BOT_TOKEN", "Bot token",
            "In Telegram, message @BotFather → /newbot → copy the token it gives you.",
            placeholder="123456:ABC-DEF…", secret=True, stack=True,
            on_change=lambda _: self._check_telegram(),
        )
        tg.add_row(row)
        tg.add_raw(self._tg_status)

        row, self._tg_chat = text_row(
            CFG, "TELEGRAM_CHAT_ID", "Chat",
            "Which conversation to post into. Send your new bot any message, "
            "then press Find my chat.",
            placeholder="press Find my chat", width=220,
            on_change=lambda _: self._check_telegram(),
        )
        tg.add_row(row)

        tg_actions = QWidget()
        tg_actions.setObjectName("Bare")
        line = QHBoxLayout(tg_actions)
        line.setContentsMargins(0, 8, 0, 0)
        line.setSpacing(8)
        self._tg_find = button("Find my chat")
        self._tg_find.clicked.connect(self._find_chat)
        line.addWidget(self._tg_find)
        self._tg_test = button("Send a test message", accent=True)
        self._tg_test.clicked.connect(self._send_tg_test)
        line.addWidget(self._tg_test)
        line.addStretch(1)
        tg.add_raw(tg_actions)

        # --- Two-way -----------------------------------------------------------
        two_way = self.add_card(
            "Let them reply  ·  optional",
            "With a bot token their replies, reactions and commands reach you back. "
            "Leave this blank to stay send-only.",
        )

        self._bot_status = StatusDot(dark)
        row, self._bot_field = text_row(
            CFG, "DISCORD_BOT_TOKEN", "Bot token", "",
            placeholder="Paste the token from your bot's page",
            secret=True, stack=True, on_change=lambda _: self._check_bot(),
        )
        two_way.add_row(row)
        two_way.add_raw(self._bot_status)

        row, _ = text_row(
            CFG, "PARTNER_USER_ID", "Their Discord user ID",
            "So only they can trigger anything. Turn on Developer Mode in Discord, "
            "then right-click their name → Copy User ID.",
            placeholder="e.g. 41234567890123456", width=220,
        )
        two_way.add_row(row)

        row, self._channel_field = text_row(
            CFG, "DISCORD_CHANNEL_ID", "Channel ID",
            "Which channel the bot listens in. Filled in automatically when the "
            "webhook above checks out.",
            placeholder="auto", width=220,
        )
        two_way.add_row(row)

        row, _ = text_row(
            CFG, "BOT_PREFIX", "Command prefix",
            "What they type before a command — !peek, !screen, !say.",
            placeholder="!", width=70,
        )
        two_way.add_row(row)

        # --- Your partner ----------------------------------------------------------------
        partner = self.add_card("Your partner", "Used in the good-morning and goodnight lines.")
        row, _ = text_row(
            CFG, "PARTNER_NAME", "What to call them", "",
            placeholder="their name", width=220,
        )
        partner.add_row(row)

        # Probes are created once and reused, so a superseded check is dropped
        # rather than racing the one after it.
        self._hook_probe = probes.Prober(self)
        self._hook_probe.started_.connect(
            lambda: self._hook_status.set_state("busy", "Checking…"))
        self._hook_probe.finished.connect(self._hook_result)

        self._bot_probe = probes.Prober(self)
        self._bot_probe.started_.connect(
            lambda: self._bot_status.set_state("busy", "Checking…"))
        self._bot_probe.finished.connect(self._bot_result)

        self._test_probe = probes.Prober(self)
        self._test_probe.started_.connect(lambda: self._test_btn.setEnabled(False))
        self._test_probe.finished.connect(self._test_result)

        self._tg_probe = probes.Prober(self)
        self._tg_probe.started_.connect(
            lambda: self._tg_status.set_state("busy", "Checking…"))
        self._tg_probe.finished.connect(self._tg_result)

        self._tg_find_probe = probes.Prober(self)
        self._tg_find_probe.started_.connect(
            lambda: (self._tg_find.setEnabled(False),
                     self._tg_status.set_state("busy", "Looking for your chat…")))
        self._tg_find_probe.finished.connect(self._found_chat)

        self._tg_test_probe = probes.Prober(self)
        self._tg_test_probe.started_.connect(lambda: self._tg_test.setEnabled(False))
        self._tg_test_probe.finished.connect(self._tg_test_result)

        QTimer.singleShot(150, self.on_show)

    # --- checks ---------------------------------------------------------------
    def on_show(self) -> None:
        self._check_webhook()
        self._check_bot()
        self._check_telegram()

    # --- telegram --------------------------------------------------------------
    def _check_telegram(self) -> None:
        if not self._tg_token.text().strip():
            self._tg_status.set_state("idle", "Not set — Discord only")
            self._tg_test.setEnabled(False)
            return
        self._tg_probe.run(probes.check_telegram,
                           self._tg_token.text().strip(), self._tg_chat.text().strip())

    def _tg_result(self, result: probes.Result) -> None:
        self._tg_status.set_state("good" if result.ok else "bad", result.message)
        self._tg_test.setEnabled(result.ok)

    def _find_chat(self) -> None:
        self._tg_find_probe.run(probes.find_telegram_chat, self._tg_token.text().strip())

    def _found_chat(self, result: probes.Result) -> None:
        self._tg_find.setEnabled(True)
        if not result.ok:
            self._tg_status.set_state("warn", result.message)
            return
        chat_id = result.detail.get("chat_id", "")
        if chat_id:
            self._tg_chat.setText(chat_id)
            CFG.set("TELEGRAM_CHAT_ID", chat_id)
            self.ctx.say(result.message)
            self._check_telegram()

    def _send_tg_test(self) -> None:
        self.ctx.say("Sending a test message…")
        self._tg_test_probe.run(probes.send_telegram_test,
                                self._tg_token.text().strip(), self._tg_chat.text().strip())

    def _tg_test_result(self, result: probes.Result) -> None:
        self._tg_test.setEnabled(True)
        self._tg_status.set_state("good" if result.ok else "bad", result.message)
        self.ctx.say(result.message)

    def _check_webhook(self) -> None:
        self._hook_probe.run(probes.check_webhook, self._hook_field.text().strip())

    def _check_bot(self) -> None:
        self._bot_probe.run(probes.check_bot_token, self._bot_field.text().strip())

    def _hook_result(self, result: probes.Result) -> None:
        self._hook_status.set_state("good" if result.ok else "bad", result.message)
        self._hook_field.setProperty("state", "good" if result.ok else "bad")
        self._hook_field.style().unpolish(self._hook_field)
        self._hook_field.style().polish(self._hook_field)
        self._test_btn.setEnabled(result.ok)

        # The webhook already knows its channel — save the user hunting for the
        # ID in Discord's developer mode.
        channel = result.detail.get("channel_id", "")
        if result.ok and channel and not self._channel_field.text().strip():
            self._channel_field.setText(channel)
            CFG.set("DISCORD_CHANNEL_ID", channel)
            self.ctx.say("Picked up the channel ID from your webhook")

    def _bot_result(self, result: probes.Result) -> None:
        has_token = bool(self._bot_field.text().strip())
        state = "good" if result.ok and has_token else ("idle" if result.ok else "bad")
        self._bot_status.set_state(state, result.message)

    def _send_test(self) -> None:
        self.ctx.say("Sending a test message…")
        self._test_probe.run(
            probes.send_test_message,
            self._hook_field.text().strip(),
            config.WEBHOOK_USERNAME,
        )

    def _test_result(self, result: probes.Result) -> None:
        self._test_btn.setEnabled(True)
        self._hook_status.set_state("good" if result.ok else "bad", result.message)
        self.ctx.say(result.message)
