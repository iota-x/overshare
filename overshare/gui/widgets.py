"""Reusable building blocks — cards, labelled rows, and the controls in them.

Every page is assembled from these, which is where the visual consistency comes
from. Each row binds to a *store* (see :mod:`.stores`) and applies instantly:
toggles on click, text fields on a short debounce. There is no Save button on
purpose — the running app watches the config file and picks changes up live, so
an explicit save would only add a step that can be forgotten.
"""

from __future__ import annotations

from PySide6.QtCore import (
    Property, QEasingCurve, QPropertyAnimation, QSize, Qt, QTimer, Signal
)
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QSizePolicy, QSlider, QVBoxLayout, QWidget,
)

from . import theme

# How long after the last keystroke a text field commits.
_DEBOUNCE_MS = 450


# --- Switch ------------------------------------------------------------------
class Switch(QWidget):
    """An iOS-style toggle.

    Qt stylesheets can recolor a checkbox indicator but can't move a knob inside
    it, so this is painted directly. `_pos` (0 → 1) is animated and drives both
    the knob position and the track color.
    """

    toggled = Signal(bool)

    def __init__(self, checked: bool = False, dark: bool = False):
        super().__init__()
        self._checked = checked
        self._pos = 1.0 if checked else 0.0
        self._dark = dark
        self._anim = QPropertyAnimation(self, b"pos_", self)
        self._anim.setDuration(150)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setFixedSize(40, 23)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self) -> QSize:
        return QSize(40, 23)

    def isChecked(self) -> bool:
        return self._checked

    def setChecked(self, value: bool, *, animate: bool = True) -> None:
        value = bool(value)
        if value == self._checked:
            return
        self._checked = value
        if animate:
            self._anim.stop()
            self._anim.setStartValue(self._pos)
            self._anim.setEndValue(1.0 if value else 0.0)
            self._anim.start()
        else:
            self._set_pos(1.0 if value else 0.0)

    def _get_pos(self) -> float:
        return self._pos

    def _set_pos(self, value: float) -> None:
        self._pos = value
        self.update()

    pos_ = Property(float, _get_pos, _set_pos)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.isEnabled():
            self.setChecked(not self._checked)
            self.toggled.emit(self._checked)

    def paintEvent(self, _event) -> None:
        c = theme.tokens(self._dark)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        off = QColor(c["border_hard"])
        on = QColor(c["accent"])
        if not self.isEnabled():
            off, on = QColor(c["border"]), QColor(c["border"])
        # Blend track color along the same curve the knob travels.
        track = QColor(
            int(off.red()   + (on.red()   - off.red())   * self._pos),
            int(off.green() + (on.green() - off.green()) * self._pos),
            int(off.blue()  + (on.blue()  - off.blue())  * self._pos),
        )

        radius = self.height() / 2
        path = QPainterPath()
        path.addRoundedRect(0, 0, self.width(), self.height(), radius, radius)
        p.fillPath(path, track)

        margin = 2.5
        knob = self.height() - margin * 2
        travel = self.width() - knob - margin * 2
        p.setBrush(QColor("#FFFFFF"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(int(margin + travel * self._pos), int(margin), int(knob), int(knob))
        p.end()


# --- Small pieces -------------------------------------------------------------
class StatusDot(QLabel):
    """A coloured bullet + message: connection state at a glance."""

    def __init__(self, dark: bool = False):
        super().__init__()
        self._dark = dark
        self.setWordWrap(True)
        self.set_state("idle", "")

    def set_state(self, state: str, message: str) -> None:
        """state: 'idle' | 'busy' | 'good' | 'bad' | 'warn'."""
        c = theme.tokens(self._dark)
        colour, glyph = {
            "good": (c["good"], "●"),
            "bad":  (c["bad"], "●"),
            "warn": (c["warn"], "●"),
            "busy": (c["muted"], "◌"),
            "idle": (c["muted"], "○"),
        }.get(state, (c["muted"], "○"))
        if not message:
            self.setText("")
            return
        self.setText(
            f'<span style="color:{colour}">{glyph}</span> '
            f'<span style="color:{c["muted"]}">{message}</span>'
        )


def divider() -> QFrame:
    line = QFrame()
    line.setObjectName("Divider")
    line.setFrameShape(QFrame.Shape.HLine)
    line.setFixedHeight(1)
    return line


class Card(QFrame):
    """A titled panel. Rows are appended with `add_row` / `add_widget`."""

    def __init__(self, title: str = "", blurb: str = ""):
        super().__init__()
        self.setObjectName("Card")
        self._v = QVBoxLayout(self)
        self._v.setContentsMargins(16, 14, 16, 14)
        self._v.setSpacing(0)
        self._first = True

        if title:
            label = QLabel(title)
            label.setObjectName("CardTitle")
            self._v.addWidget(label)
        if blurb:
            sub = QLabel(blurb)
            sub.setObjectName("RowHelp")
            sub.setWordWrap(True)
            self._v.addWidget(sub)
        if title or blurb:
            self._v.addSpacing(6)

    def add_widget(self, widget: QWidget, *, separated: bool = True) -> QWidget:
        if separated and not self._first:
            self._v.addSpacing(9)
            self._v.addWidget(divider())
            self._v.addSpacing(9)
        self._v.addWidget(widget)
        self._first = False
        return widget

    def add_row(self, row: QWidget) -> QWidget:
        return self.add_widget(row)

    def add_raw(self, widget: QWidget) -> QWidget:
        """Append without a separator — for notes tucked under a row."""
        self._v.addWidget(widget)
        return widget


class Group(QWidget):
    """Rows that switch on and off together, nested inside a card.

    Used for settings that only apply when the toggle above them is on — they
    stay in the same card so the dependency reads visually, rather than floating
    off as a card of their own.
    """

    def __init__(self):
        super().__init__()
        self.setObjectName("Bare")
        self._v = QVBoxLayout(self)
        self._v.setContentsMargins(0, 0, 0, 0)
        self._v.setSpacing(0)
        self._first = True

    def add_row(self, row: QWidget) -> QWidget:
        if not self._first:
            self._v.addSpacing(9)
            self._v.addWidget(divider())
            self._v.addSpacing(9)
        self._v.addWidget(row)
        self._first = False
        return row


class Row(QWidget):
    """Label (+ help text) on the left, a control on the right."""

    def __init__(self, label: str, help_text: str = "", control: QWidget | None = None,
                 *, stack: bool = False):
        super().__init__()
        self.setObjectName("Bare")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        line = QHBoxLayout()
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(12)
        self._line = line

        text = QVBoxLayout()
        text.setContentsMargins(0, 0, 0, 0)
        text.setSpacing(2)
        title = QLabel(label)
        title.setObjectName("RowLabel")
        text.addWidget(title)
        if help_text:
            hint = QLabel(help_text)
            hint.setObjectName("RowHelp")
            hint.setWordWrap(True)
            text.addWidget(hint)
        line.addLayout(text, 1)

        self.control = control
        if control is not None and not stack:
            line.addWidget(control, 0, Qt.AlignmentFlag.AlignVCenter)
        outer.addLayout(line)
        # `stack` puts a wide control (a long URL field) on its own line below.
        if control is not None and stack:
            outer.addWidget(control)

        self._outer = outer

    def add_below(self, widget: QWidget) -> QWidget:
        self._outer.addWidget(widget)
        return widget

    def add_action(self, widget: QWidget) -> QWidget:
        """Put a small control at the right of the label line (e.g. Show/Hide)."""
        self._line.addWidget(widget, 0, Qt.AlignmentFlag.AlignTop)
        return widget


# --- Bound rows ---------------------------------------------------------------
# Each takes a store, reads its current value, and writes back on change.
def toggle_row(store, key: str, label: str, help_text: str = "", *,
               dark: bool = False, on_change=None) -> tuple[Row, Switch]:
    sw = Switch(bool(store.get(key)), dark=dark)

    def changed(value: bool) -> None:
        store.set(key, value)
        if on_change:
            on_change(value)

    sw.toggled.connect(changed)
    return Row(label, help_text, sw), sw


def text_row(store, key: str, label: str, help_text: str = "", *,
             placeholder: str = "", secret: bool = False, width: int = 240,
             stack: bool = False, on_change=None) -> tuple[Row, QLineEdit]:
    field = QLineEdit(str(store.get(key) or ""))
    field.setPlaceholderText(placeholder)
    if stack:
        field.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    else:
        field.setFixedWidth(width)
    if secret:
        field.setEchoMode(QLineEdit.EchoMode.Password)

    # Commit on a pause in typing rather than every keystroke, so we aren't
    # rewriting the config file (and re-probing the network) mid-paste.
    timer = QTimer(field)
    timer.setSingleShot(True)
    timer.setInterval(_DEBOUNCE_MS)

    def commit() -> None:
        value = field.text().strip()
        store.set(key, value)
        if on_change:
            on_change(value)

    timer.timeout.connect(commit)
    field.textEdited.connect(lambda _: timer.start())
    field.editingFinished.connect(lambda: (timer.stop(), commit()))

    row = Row(label, help_text, field, stack=stack)
    if secret:
        # A reveal button, so a mistyped key can actually be spotted.
        eye = QPushButton("Show")
        eye.setProperty("flat", True)
        eye.setCursor(Qt.CursorShape.PointingHandCursor)

        def flip() -> None:
            hidden = field.echoMode() == QLineEdit.EchoMode.Password
            field.setEchoMode(
                QLineEdit.EchoMode.Normal if hidden else QLineEdit.EchoMode.Password)
            eye.setText("Hide" if hidden else "Show")

        eye.clicked.connect(flip)
        row.add_action(eye)
    return row, field


def choice_row(store, key: str, label: str, options: list[tuple[str, str]],
               help_text: str = "", *, width: int = 200,
               on_change=None) -> tuple[Row, QComboBox]:
    """`options` is a list of (value, display) pairs."""
    box = QComboBox()
    box.setFixedWidth(width)
    for value, display in options:
        box.addItem(display, value)
    current = str(store.get(key) or "")
    index = box.findData(current)
    if index >= 0:
        box.setCurrentIndex(index)

    def changed(i: int) -> None:
        value = box.itemData(i)
        store.set(key, value)
        if on_change:
            on_change(value)

    box.currentIndexChanged.connect(changed)
    return Row(label, help_text, box), box


def slider_row(store, key: str, label: str, low: float, high: float,
               help_text: str = "", *, step: float = 1.0, suffix: str = "",
               fmt=None, on_change=None) -> tuple[Row, QSlider]:
    """A slider with a live readout. Values are stored as floats."""
    steps = max(1, int(round((high - low) / step)))
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setRange(0, steps)
    slider.setFixedWidth(170)

    def to_value(tick: int) -> float:
        return round(low + tick * step, 4)

    def to_tick(value: float) -> int:
        return max(0, min(steps, int(round((float(value) - low) / step))))

    readout = QLabel()
    readout.setObjectName("RowHelp")
    readout.setMinimumWidth(74)
    readout.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def render(value: float) -> str:
        if fmt:
            return fmt(value)
        text = f"{value:g}"
        return f"{text}{suffix}"

    slider.setValue(to_tick(store.get(key) or low))
    readout.setText(render(to_value(slider.value())))

    def moved(tick: int) -> None:
        readout.setText(render(to_value(tick)))

    def released() -> None:
        value = to_value(slider.value())
        store.set(key, value)
        if on_change:
            on_change(value)

    slider.valueChanged.connect(moved)
    slider.sliderReleased.connect(released)
    # Keyboard/arrow changes never fire sliderReleased, so catch those too.
    slider.actionTriggered.connect(lambda _: QTimer.singleShot(0, released))

    holder = QWidget()

    holder.setObjectName("Bare")
    line = QHBoxLayout(holder)
    line.setContentsMargins(0, 0, 0, 0)
    line.setSpacing(10)
    line.addWidget(slider)
    line.addWidget(readout)
    return Row(label, help_text, holder), slider


def time_row(store, key: str, label: str, help_text: str = "",
             on_change=None) -> tuple[Row, QLineEdit]:
    """HH:MM stored as a plain string, matching the existing config format."""
    field = QLineEdit(str(store.get(key) or ""))
    field.setFixedWidth(88)
    field.setPlaceholderText("HH:MM")
    field.setAlignment(Qt.AlignmentFlag.AlignCenter)
    field.setInputMask("99:99")

    def commit() -> None:
        value = field.text().strip()
        hours, _, minutes = value.partition(":")
        if hours.isdigit() and minutes.isdigit() and int(hours) < 24 and int(minutes) < 60:
            store.set(key, f"{int(hours):02d}:{int(minutes):02d}")
            field.setProperty("state", "good")
            if on_change:
                on_change(value)
        else:
            field.setProperty("state", "bad")
        field.style().unpolish(field)
        field.style().polish(field)

    field.editingFinished.connect(commit)
    return Row(label, help_text, field), field


def button(text: str, *, accent: bool = False, flat: bool = False) -> QPushButton:
    btn = QPushButton(text)
    if accent:
        btn.setProperty("accent", True)
    if flat:
        btn.setProperty("flat", True)
    btn.setCursor(Qt.CursorShape.PointingHandCursor)
    return btn
