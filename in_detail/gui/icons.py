"""The sidebar icons, drawn as vectors.

Emoji were the quick version and they looked it: seven multicolour glyphs at
seven different visual weights, none of them agreeing with the palette. These
are plain stroked paths instead, so they take the theme's colour, sit at one
consistent weight, and stay sharp on any display.

Each path is drawn on a 24×24 grid and scaled at paint time. `icon()` returns a
QIcon carrying both a muted and an accent version, which is what lets the
selected row light up without any extra wiring.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

from . import theme

_GRID = 24.0          # the coordinate space every path below is drawn in
_STROKE = 1.7         # matches the weight of the sidebar text


# --- The paths ---------------------------------------------------------------
# Each returns (stroked_path, filled_path | None).
def _envelope() -> tuple[QPainterPath, QPainterPath | None]:
    p = QPainterPath()
    p.addRoundedRect(QRectF(3, 5.5, 18, 13), 2.5, 2.5)
    p.moveTo(3.6, 6.6)          # the flap, as a shallow V into the body
    p.lineTo(12, 13.2)
    p.lineTo(20.4, 6.6)
    return p, None


def _eye() -> tuple[QPainterPath, QPainterPath | None]:
    p = QPainterPath()
    p.moveTo(2.2, 12)
    p.quadTo(12, 4.2, 21.8, 12)
    p.quadTo(12, 19.8, 2.2, 12)
    p.addEllipse(QPointF(12, 12), 2.9, 2.9)
    return p, None


def _sparkle() -> tuple[QPainterPath, QPainterPath | None]:
    # A four-point star with concave sides — reads as "generated" without the
    # cartoon weight of ✨.
    big = QPainterPath()
    big.moveTo(11, 2.6)
    big.quadTo(12, 9.2, 18.6, 10.4)
    big.quadTo(12, 11.6, 11, 18.2)
    big.quadTo(10, 11.6, 3.4, 10.4)
    big.quadTo(10, 9.2, 11, 2.6)
    small = QPainterPath()
    small.moveTo(18, 14.4)
    small.quadTo(18.4, 17.2, 21.2, 17.6)
    small.quadTo(18.4, 18, 18, 20.8)
    small.quadTo(17.6, 18, 14.8, 17.6)
    small.quadTo(17.6, 17.2, 18, 14.4)
    return big, small       # the little one is filled, for a bit of sparkle


def _lock() -> tuple[QPainterPath, QPainterPath | None]:
    p = QPainterPath()
    p.addRoundedRect(QRectF(4.5, 10.5, 15, 10), 2.5, 2.5)
    # Shackle: a half-circle sitting on the body.
    p.arcMoveTo(QRectF(7.75, 3.5, 8.5, 8.5), 0)
    p.arcTo(QRectF(7.75, 3.5, 8.5, 8.5), 0, 180)
    return p, None


def _calendar() -> tuple[QPainterPath, QPainterPath | None]:
    p = QPainterPath()
    p.addRoundedRect(QRectF(3.5, 5, 17, 15.5), 2.5, 2.5)
    p.moveTo(3.5, 10)           # header rule
    p.lineTo(20.5, 10)
    p.moveTo(8.5, 3)            # the two hangers
    p.lineTo(8.5, 7)
    p.moveTo(15.5, 3)
    p.lineTo(15.5, 7)
    return p, None


def _heart() -> tuple[QPainterPath, QPainterPath | None]:
    p = QPainterPath()
    p.moveTo(12, 20.4)
    p.cubicTo(4.2, 14.6, 3.2, 9.4, 6.6, 6.9)
    p.cubicTo(9.1, 5.1, 11.1, 6.5, 12, 8.3)
    p.cubicTo(12.9, 6.5, 14.9, 5.1, 17.4, 6.9)
    p.cubicTo(20.8, 9.4, 19.8, 14.6, 12, 20.4)
    return p, None


def _sliders() -> tuple[QPainterPath, QPainterPath | None]:
    p = QPainterPath()
    for y, knob in ((7.0, 9.0), (12.0, 15.0), (17.0, 8.0)):
        p.moveTo(4, y)
        p.lineTo(20, y)
        p.addEllipse(QPointF(knob, y), 2.4, 2.4)
    return p, None


_PATHS = {
    "envelope": _envelope,
    "eye": _eye,
    "sparkle": _sparkle,
    "lock": _lock,
    "calendar": _calendar,
    "heart": _heart,
    "sliders": _sliders,
}


# --- Rendering ----------------------------------------------------------------
def pixmap(name: str, colour: str, size: int = 19, ratio: float = 2.0) -> QPixmap:
    """One icon, stroked in `colour`. Rendered at `ratio`× for retina."""
    build = _PATHS.get(name)
    px = QPixmap(int(size * ratio), int(size * ratio))
    px.fill(Qt.GlobalColor.transparent)
    if build is None:
        px.setDevicePixelRatio(ratio)
        return px

    stroked, filled = build()
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size * ratio / _GRID, size * ratio / _GRID)

    pen = QPen(QColor(colour))
    pen.setWidthF(_STROKE)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(stroked)

    if filled is not None:
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(colour))
        p.drawPath(filled)
    p.end()
    # Tag the ratio only once painting is done: setting it first would put the
    # painter into logical coordinates and scale the path a second time.
    px.setDevicePixelRatio(ratio)
    return px


def icon(name: str, dark: bool, size: int = 19) -> QIcon:
    """A themed icon that brightens to the accent colour when its row is selected.

    Qt's item delegate asks a QIcon for its Selected pixmap on a selected row,
    so supplying both modes here is all the highlight needs.
    """
    c = theme.tokens(dark)
    result = QIcon()
    result.addPixmap(pixmap(name, c["muted"], size), QIcon.Mode.Normal)
    result.addPixmap(pixmap(name, c["accent"], size), QIcon.Mode.Selected)
    result.addPixmap(pixmap(name, c["accent"], size), QIcon.Mode.Active)
    return result
