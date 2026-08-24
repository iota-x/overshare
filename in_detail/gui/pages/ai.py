"""AI — who writes the one-liners, and proof that the key actually works."""

from __future__ import annotations

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QRadioButton, QStackedWidget, QVBoxLayout, QWidget,
)

from ... import config
from .. import probes
from ..stores import CFG
from ..widgets import Row, StatusDot, text_row, toggle_row
from .base import Page

# value, title, one-line pitch
_PROVIDERS = [
    ("none",      "Off — plain templates",  "No AI at all. Still works, just less charming."),
    ("groq",      "Groq — free",            "A free cloud key. Nothing runs on your machine."),
    ("ollama",    "Ollama — free, local",   "Runs a small model on this computer. Nothing leaves it."),
    ("anthropic", "Claude — paid",          "The best writing, billed per message."),
]


class AIPage(Page):
    title = "AI"
    blurb = "How your activity gets turned into a sentence they'd actually enjoy reading."
    nav = "AI"
    icon = "sparkle"

    def build(self) -> None:
        dark = self.ctx.dark

        # --- Provider choice ---------------------------------------------------
        card = self.add_card("Who writes the messages")
        self._group = QButtonGroup(self)
        current = config.active_provider()

        holder = QWidget()

        holder.setObjectName("Bare")
        column = QVBoxLayout(holder)
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(2)
        for value, title, pitch in _PROVIDERS:
            radio = QRadioButton(title)
            radio.setChecked(value == current)
            self._group.addButton(radio)
            radio.setProperty("value", value)
            column.addWidget(radio)
            column.addWidget(_hint(pitch))
        card.add_widget(holder, separated=False)
        self._group.buttonClicked.connect(self._provider_picked)

        # --- Per-provider detail ------------------------------------------------
        self._detail = QStackedWidget()
        self._detail.setObjectName("Bare")
        self._pages: dict[str, int] = {}
        self._status: dict[str, StatusDot] = {}
        self._models: dict[str, QComboBox] = {}

        self._pages["none"] = self._detail.addWidget(
            _hint("Messages will use the built-in templates — still descriptive, "
                  "just not written fresh each time."))
        self._pages["groq"] = self._detail.addWidget(self._groq_panel(dark))
        self._pages["ollama"] = self._detail.addWidget(self._ollama_panel(dark))
        self._pages["anthropic"] = self._detail.addWidget(self._anthropic_panel(dark))

        detail_card = self.add_card("Connection")
        detail_card.add_widget(self._detail, separated=False)

        # --- Phrasing ------------------------------------------------------------
        from ..stores import RUNTIME
        phrasing = self.add_card("Phrasing")
        row, _ = toggle_row(
            RUNTIME, "exact_status", "Send exactly what's detected",
            "Skips the AI phrasing and sends the raw app + window title. Blunter, "
            "and completely predictable.",
            dark=dark,
        )
        phrasing.add_row(row)

        self._probe = probes.Prober(self)
        self._probe.finished.connect(self._probe_result)

        self._show_detail(current)
        QTimer.singleShot(200, self.on_show)

    # --- panels ----------------------------------------------------------------
    def _groq_panel(self, dark: bool) -> QWidget:
        panel, column = _panel()
        row, self._groq_key = text_row(
            CFG, "GROQ_API_KEY", "API key",
            "Free at console.groq.com — sign in, then API Keys → Create.",
            placeholder="gsk_…", secret=True, stack=True,
            on_change=lambda _: self._check("groq"),
        )
        column.addWidget(row)
        self._status["groq"] = StatusDot(dark)
        column.addWidget(self._status["groq"])
        self._models["groq"] = self._model_box("GROQ_MODEL")
        column.addWidget(Row("Model", "Populated from your account once the key checks out.",
                             self._models["groq"]))
        row, _ = text_row(
            CFG, "GROQ_BASE_URL", "API endpoint",
            "Any OpenAI-compatible host works here — Cerebras, OpenRouter, and so on.",
            placeholder="https://api.groq.com/openai/v1", stack=True,
            on_change=lambda _: self._check("groq"),
        )
        column.addWidget(row)
        return panel

    def _ollama_panel(self, dark: bool) -> QWidget:
        panel, column = _panel()
        row, self._ollama_host = text_row(
            CFG, "OLLAMA_HOST", "Server address",
            "Where Ollama is listening. The default is right for a local install.",
            placeholder="http://localhost:11434", stack=True,
            on_change=lambda _: self._check("ollama"),
        )
        column.addWidget(row)
        self._status["ollama"] = StatusDot(dark)
        column.addWidget(self._status["ollama"])
        self._models["ollama"] = self._model_box("OLLAMA_MODEL")
        column.addWidget(Row("Model", "Whatever you've pulled. A small one is plenty here.",
                             self._models["ollama"]))
        return panel

    def _anthropic_panel(self, dark: bool) -> QWidget:
        panel, column = _panel()
        row, self._anthropic_key = text_row(
            CFG, "ANTHROPIC_API_KEY", "API key",
            "From console.anthropic.com. This one bills per message — a cheaper "
            "model is more than good enough for one-liners.",
            placeholder="sk-ant-…", secret=True, stack=True,
            on_change=lambda _: self._check("anthropic"),
        )
        column.addWidget(row)
        self._status["anthropic"] = StatusDot(dark)
        column.addWidget(self._status["anthropic"])
        self._models["anthropic"] = self._model_box("AI_MODEL")
        column.addWidget(Row("Model", "Listed live from your account.",
                             self._models["anthropic"]))
        return panel

    def _model_box(self, key: str) -> QComboBox:
        """Editable, so a model the API doesn't list can still be typed in."""
        box = QComboBox()
        box.setEditable(True)
        box.setFixedWidth(230)
        box.setCurrentText(str(getattr(config, key, "") or ""))
        box.currentTextChanged.connect(lambda text: CFG.set(key, text.strip()))
        return box

    # --- behaviour ---------------------------------------------------------------
    def _provider_picked(self, radio) -> None:
        value = radio.property("value")
        if value == "none":
            CFG.set("AI_ENABLED", False)
        else:
            config.save({"AI_ENABLED": True, "AI_PROVIDER": value})
        self._show_detail(value)

    def _show_detail(self, provider: str) -> None:
        self._detail.setCurrentIndex(self._pages.get(provider, 0))
        if provider != "none":
            self._check(provider)

    def _check(self, provider: str) -> None:
        self._pending = provider
        dot = self._status.get(provider)
        if dot:
            dot.set_state("busy", "Checking…")
        if provider == "groq":
            base = str(CFG.get("GROQ_BASE_URL") or "https://api.groq.com/openai/v1")
            self._probe.run(probes.check_groq, self._groq_key.text().strip(), base)
        elif provider == "ollama":
            self._probe.run(probes.check_ollama, self._ollama_host.text().strip())
        elif provider == "anthropic":
            self._probe.run(probes.check_anthropic, self._anthropic_key.text().strip())

    def _probe_result(self, result: probes.Result) -> None:
        provider = getattr(self, "_pending", "")
        dot = self._status.get(provider)
        if dot:
            dot.set_state("good" if result.ok else "bad", result.message)

        box = self._models.get(provider)
        if box and result.options:
            # Keep whatever is selected; just refresh what's on offer.
            chosen = box.currentText()
            box.blockSignals(True)
            box.clear()
            box.addItems(result.options)
            box.setCurrentText(chosen or (result.options[0] if result.options else ""))
            box.blockSignals(False)

    def on_show(self) -> None:
        provider = config.active_provider()
        if provider != "none":
            self._check(provider)


# --- small helpers ---------------------------------------------------------------
def _hint(text: str):
    from PySide6.QtWidgets import QLabel
    label = QLabel(text)
    label.setObjectName("RowHelp")
    label.setWordWrap(True)
    label.setContentsMargins(24, 0, 0, 6)
    return label


def _panel() -> tuple[QWidget, QVBoxLayout]:
    panel = QWidget()
    panel.setObjectName("Bare")
    column = QVBoxLayout(panel)
    column.setContentsMargins(0, 0, 0, 0)
    column.setSpacing(10)
    return panel, column
