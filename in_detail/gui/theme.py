"""The look — one palette, rendered to Qt stylesheets for light and dark.

Qt's defaults read as "a tool someone built in 2009", which is the opposite of
what this app is. So everything is styled from a single token set: a warm
off-white ground, soft rose accent, and generous spacing. Both palettes define
the same keys, so `qss()` builds either from the same template.
"""

from __future__ import annotations

LIGHT = {
    "bg":          "#FDF8F7",  # window ground, faintly warm
    "surface":     "#FFFFFF",  # cards sitting on the ground
    "surface_alt": "#F7EFEE",  # hover / inset fills
    "border":      "#ECDFDD",
    "border_hard": "#DCC9C6",  # inputs, which need to read as editable
    "text":        "#2B2226",
    "muted":       "#8A7B80",
    "accent":      "#DB4F86",
    "accent_hov":  "#C83F75",
    "accent_soft": "#FCEDF3",  # selected nav row, accent-tinted fills
    "on_accent":   "#FFFFFF",
    "good":        "#1F9D6B",
    "warn":        "#C98A22",
    "bad":         "#D2453F",
    "sidebar":     "#F6EDEC",
}

DARK = {
    "bg":          "#17131A",
    "surface":     "#211C26",
    "surface_alt": "#2A2430",
    "border":      "#332B39",
    "border_hard": "#463B4D",
    "text":        "#F2EBEF",
    "muted":       "#A2939F",
    "accent":      "#FF7AAE",
    "accent_hov":  "#FF95BF",
    "accent_soft": "#33212C",
    "on_accent":   "#2B0F1C",
    "good":        "#4ED9A0",
    "warn":        "#E8B45C",
    "bad":         "#FF7A72",
    "sidebar":     "#1C1720",
}

# System font stacks — Qt resolves the first that exists on the box.
# macOS registers its UI font as ".AppleSystemUIFont"; "SF Pro Text" is not a
# family Qt can look up, and asking for it silently lands on a generic fallback.
FONT_UI = ('".AppleSystemUIFont", "Segoe UI Variable Text", "Segoe UI", '
           '"Helvetica Neue", sans-serif')
FONT_DISPLAY = ('".AppleSystemUIFont", "Segoe UI Variable Display", "Segoe UI", '
                '"Helvetica Neue", sans-serif')
FONT_MONO = '"SF Mono", "Cascadia Mono", "Consolas", monospace'


def tokens(dark: bool) -> dict:
    return DARK if dark else LIGHT


def qss(dark: bool) -> str:
    """The full application stylesheet for the given mode."""
    c = tokens(dark)
    return f"""
    QWidget {{
        background: {c['bg']};
        color: {c['text']};
        font-family: {FONT_UI};
        font-size: 13px;
    }}

    /* --- Sidebar navigation ------------------------------------------- */
    #Sidebar {{
        background: {c['sidebar']};
        border-right: 1px solid {c['border']};
    }}
    #Sidebar QLabel {{ background: transparent; }}
    #NavList {{
        background: transparent;
        border: none;
        outline: none;
        font-size: 13.5px;
    }}
    #NavList::item {{
        padding: 9px 12px;
        margin: 2px 8px;
        border-radius: 8px;
        color: {c['text']};
    }}
    #NavList::item:hover {{ background: {c['surface_alt']}; }}
    #NavList::item:selected {{
        background: {c['accent_soft']};
        color: {c['accent']};
        font-weight: 600;
    }}

    #WordMark {{
        font-family: {FONT_DISPLAY};
        font-size: 17px;
        font-weight: 700;
        color: {c['text']};
    }}
    #Tagline {{ color: {c['muted']}; font-size: 11.5px; }}

    /* --- Page furniture ------------------------------------------------ */
    #PageTitle {{
        font-family: {FONT_DISPLAY};
        font-size: 22px;
        font-weight: 700;
        padding-bottom: 2px;
    }}
    #PageBlurb {{ color: {c['muted']}; font-size: 13px; }}

    #Card {{
        background: {c['surface']};
        border: 1px solid {c['border']};
        border-radius: 12px;
    }}
    #Card QLabel {{ background: transparent; }}
    #CardTitle {{ font-size: 13px; font-weight: 700; }}
    #RowLabel {{ font-size: 13px; }}
    #RowHelp  {{ color: {c['muted']}; font-size: 11.5px; }}
    #Divider  {{ background: {c['border']}; max-height: 1px; border: none; }}
    /* Plain layout containers: without this they paint the window ground and
       show up as a tinted band inside a card. */
    #Bare {{ background: transparent; }}

    /* --- Inputs --------------------------------------------------------- */
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTimeEdit, QPlainTextEdit {{
        background: {c['surface']};
        border: 1px solid {c['border_hard']};
        border-radius: 8px;
        padding: 6px 9px;
        selection-background-color: {c['accent']};
        selection-color: {c['on_accent']};
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus,
    QDoubleSpinBox:focus, QTimeEdit:focus, QPlainTextEdit:focus {{
        border: 1px solid {c['accent']};
    }}
    QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled,
    QDoubleSpinBox:disabled, QTimeEdit:disabled {{
        background: {c['surface_alt']};
        color: {c['muted']};
    }}
    QLineEdit[state="good"] {{ border: 1px solid {c['good']}; }}
    QLineEdit[state="bad"]  {{ border: 1px solid {c['bad']}; }}

    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox QAbstractItemView {{
        background: {c['surface']};
        border: 1px solid {c['border_hard']};
        border-radius: 8px;
        padding: 4px;
        selection-background-color: {c['accent_soft']};
        selection-color: {c['accent']};
        outline: none;
    }}

    /* --- Buttons -------------------------------------------------------- */
    QPushButton {{
        background: {c['surface']};
        border: 1px solid {c['border_hard']};
        border-radius: 8px;
        padding: 6px 14px;
        font-weight: 600;
    }}
    QPushButton:hover  {{ background: {c['surface_alt']}; }}
    QPushButton:disabled {{ color: {c['muted']}; background: {c['surface_alt']}; }}
    QPushButton[accent="true"] {{
        background: {c['accent']};
        color: {c['on_accent']};
        border: 1px solid {c['accent']};
    }}
    QPushButton[accent="true"]:hover {{
        background: {c['accent_hov']};
        border-color: {c['accent_hov']};
    }}
    QPushButton[accent="true"]:disabled {{
        background: {c['surface_alt']};
        border-color: {c['border']};
        color: {c['muted']};
    }}
    QPushButton[flat="true"] {{
        background: transparent;
        border: none;
        color: {c['accent']};
        padding: 4px 6px;
        font-weight: 600;
    }}
    QPushButton[flat="true"]:hover {{ color: {c['accent_hov']}; }}

    /* --- Switch (a QCheckBox drawn as a pill) ---------------------------- */
    QCheckBox {{ spacing: 0px; background: transparent; }}
    QCheckBox::indicator {{
        width: 38px; height: 22px;
        border-radius: 11px;
        background: {c['border_hard']};
        border: none;
    }}
    QCheckBox::indicator:checked {{ background: {c['accent']}; }}
    QCheckBox::indicator:disabled {{ background: {c['border']}; }}

    QRadioButton {{ background: transparent; spacing: 8px; padding: 3px 0; }}
    QRadioButton::indicator {{
        width: 16px; height: 16px;
        border-radius: 9px;
        border: 1.5px solid {c['border_hard']};
        background: {c['surface']};
    }}
    /* The inner dot is painted as a radial gradient rather than a fat border —
       Qt drops the border-radius once the border gets thick, which renders the
       indicator as a square. */
    QRadioButton::indicator:checked {{
        border: 1.5px solid {c['accent']};
        background: qradialgradient(cx:0.5, cy:0.5, radius:0.5,
                                    fx:0.5, fy:0.5,
                                    stop:0 {c['accent']},
                                    stop:0.55 {c['accent']},
                                    stop:0.6 {c['surface']});
    }}

    /* --- Slider --------------------------------------------------------- */
    QSlider::groove:horizontal {{
        height: 4px; border-radius: 2px; background: {c['border_hard']};
    }}
    QSlider::sub-page:horizontal {{
        height: 4px; border-radius: 2px; background: {c['accent']};
    }}
    QSlider::handle:horizontal {{
        width: 16px; height: 16px; margin: -6px 0;
        border-radius: 8px;
        background: {c['surface']};
        border: 1.5px solid {c['accent']};
    }}
    QSlider::handle:horizontal:hover {{ background: {c['accent_soft']}; }}

    /* --- Scrollbars ------------------------------------------------------ */
    QScrollArea {{ border: none; background: transparent; }}
    QScrollArea > QWidget > QWidget {{ background: transparent; }}
    QScrollBar:vertical {{
        background: transparent; width: 10px; margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {c['border_hard']}; border-radius: 4px; min-height: 28px;
    }}
    QScrollBar::handle:vertical:hover {{ background: {c['muted']}; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

    /* --- Status strip along the bottom ----------------------------------- */
    #StatusBar {{
        background: {c['surface']};
        border-top: 1px solid {c['border']};
    }}
    #StatusBar QLabel {{ background: transparent; color: {c['muted']}; }}

    QToolTip {{
        background: {c['surface']};
        color: {c['text']};
        border: 1px solid {c['border_hard']};
        border-radius: 6px;
        padding: 5px 8px;
    }}
    """
