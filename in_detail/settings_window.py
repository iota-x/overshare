"""A real settings panel — a native AppKit window, not just menu-bar toggles.

The menu bar stays (quick privacy flips), but this gives one place to see and
change everything she experiences: where updates land, the tone, your prefix,
mood, and the camera/screen/mirror switches. Wired straight to `settings` so the
menu bar and this window always agree.

rumps is already PyObjC under the hood, so we can raise a normal Cocoa window
inside the same app with no extra dependency.
"""

from __future__ import annotations

import objc
from AppKit import (
    NSObject,
    NSWindow,
    NSButton,
    NSPopUpButton,
    NSTextField,
    NSMakeRect,
    NSBackingStoreBuffered,
    NSApp,
    NSColor,
    NSFont,
)

from . import settings

# Window style bits (titled + closable) and the checkbox button type — spelled as
# ints so we don't depend on symbol names that drift across PyObjC versions.
_STYLE_TITLED_CLOSABLE = 1 | 2
_BUTTON_TYPE_SWITCH = 3

_W, _MARGIN = 440, 24
_LABEL_W, _CTRL_X, _CTRL_W = 150, 180, 236
_ROW_H, _GAP = 24, 14


class SettingsController(NSObject):
    """Owns the window and mirrors every control back into `settings`."""

    # --- lifecycle ----------------------------------------------------------
    def init(self):
        self = objc.super(SettingsController, self).init()
        if self is None:
            return None
        self._window = None
        self._sync = None            # callback to refresh menu-bar item states
        self._prefix_field = None
        self._mood_field = None
        self._voice_field = None
        self._y = 0                  # layout cursor (top-down)
        return self

    @objc.python_method
    def show(self, sync=None):
        self._sync = sync
        if self._window is None:
            self._build()
        self._window.makeKeyAndOrderFront_(None)
        NSApp.activateIgnoringOtherApps_(True)

    # --- construction -------------------------------------------------------
    @objc.python_method
    def _build(self):
        # Height is derived from the rows we add, so it's easy to extend later.
        rows = 5 + 1 + 3      # 5 delivery + 1 status + 3 camera switches
        headers = 3
        height = _MARGIN * 2 + 40 + rows * (_ROW_H + _GAP) + headers * 30
        win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, _W, height),
            _STYLE_TITLED_CLOSABLE,
            NSBackingStoreBuffered,
            False,
        )
        win.setTitle_("overshare — settings")
        win.center()
        win.setReleasedWhenClosed_(False)   # so it can be reopened
        win.setDelegate_(self)
        self._window = win
        self._y = height - _MARGIN - 26

        self._header("Delivery 💌")
        self._popup("Send updates to", "card_destination", ["channel", "dm", "both"], "changeDest:")
        self._popup("Tone she picks", "tone", ["default", "cutesy", "chill", "detailed"], "changeTone:")
        self._prefix_field = self._text("Command prefix", "prefix", placeholder="! (default)")
        self._mood_field = self._text("Your mood / status", "mood", placeholder="blank = none")
        self._voice_field = self._text("Voice for !say", "say_voice", placeholder="blank = system default")

        self._header("Status accuracy 📡")
        self._check("Exact mode — send what's detected, no AI wording", "exact_status", "toggleExact:")

        self._header("Camera & screen 🔒")
        self._check("Allow camera peeks", "camera_enabled", "toggleCamera:")
        self._check("Allow screen peeks", "screen_enabled", "toggleScreen:")
        self._check("Mirror camera photos (selfie view)", "mirror_capture", "toggleMirror:")

    # --- layout helpers -----------------------------------------------------
    @objc.python_method
    def _header(self, title):
        self._y -= 30
        lbl = self._label(NSMakeRect(_MARGIN, self._y, _W - 2 * _MARGIN, 22), title, bold=True)
        lbl.setTextColor_(NSColor.secondaryLabelColor())

    @objc.python_method
    def _label(self, rect, text, bold=False):
        f = NSTextField.alloc().initWithFrame_(rect)
        f.setStringValue_(text)
        f.setBezeled_(False)
        f.setDrawsBackground_(False)
        f.setEditable_(False)
        f.setSelectable_(False)
        f.setFont_(NSFont.boldSystemFontOfSize_(12) if bold else NSFont.systemFontOfSize_(13))
        self._window.contentView().addSubview_(f)
        return f

    @objc.python_method
    def _row_rects(self):
        self._y -= _ROW_H + _GAP
        label_rect = NSMakeRect(_MARGIN, self._y - 2, _LABEL_W, _ROW_H)
        ctrl_rect = NSMakeRect(_CTRL_X, self._y - 4, _CTRL_W, _ROW_H)
        return label_rect, ctrl_rect

    @objc.python_method
    def _popup(self, title, key, options, action):
        label_rect, ctrl_rect = self._row_rects()
        self._label(label_rect, title)
        pop = NSPopUpButton.alloc().initWithFrame_pullsDown_(ctrl_rect, False)
        pop.addItemsWithTitles_(options)
        current = str(settings.get(key) or options[0])
        if current in options:
            pop.selectItemWithTitle_(current)
        pop.setTarget_(self)
        pop.setAction_(action)
        self._window.contentView().addSubview_(pop)

    @objc.python_method
    def _text(self, title, key, placeholder=""):
        label_rect, ctrl_rect = self._row_rects()
        self._label(label_rect, title)
        tf = NSTextField.alloc().initWithFrame_(ctrl_rect)
        tf.setStringValue_(str(settings.get(key) or ""))
        if placeholder:
            tf.setPlaceholderString_(placeholder)
        self._window.contentView().addSubview_(tf)
        return tf   # persisted on window close

    @objc.python_method
    def _check(self, title, key, action):
        self._y -= _ROW_H + _GAP
        rect = NSMakeRect(_MARGIN, self._y, _W - 2 * _MARGIN, _ROW_H)
        btn = NSButton.alloc().initWithFrame_(rect)
        btn.setButtonType_(_BUTTON_TYPE_SWITCH)
        btn.setTitle_(title)
        btn.setState_(1 if settings.get(key) else 0)
        btn.setTarget_(self)
        btn.setAction_(action)
        self._window.contentView().addSubview_(btn)

    @objc.python_method
    def _notify(self):
        if self._sync:
            try:
                self._sync()
            except Exception:
                pass

    # --- control actions (ObjC selectors) -----------------------------------
    def changeDest_(self, sender):
        settings.set("card_destination", sender.titleOfSelectedItem())

    def changeTone_(self, sender):
        settings.set("tone", sender.titleOfSelectedItem())

    def toggleExact_(self, sender):
        settings.set("exact_status", bool(sender.state()))

    def toggleCamera_(self, sender):
        settings.set("camera_enabled", bool(sender.state()))
        self._notify()

    def toggleScreen_(self, sender):
        settings.set("screen_enabled", bool(sender.state()))
        self._notify()

    def toggleMirror_(self, sender):
        settings.set("mirror_capture", bool(sender.state()))
        self._notify()

    # Text fields commit when the window closes (covers edits without Enter).
    def windowWillClose_(self, _notification):
        if self._prefix_field is not None:
            settings.set("prefix", self._prefix_field.stringValue().strip())
        if self._mood_field is not None:
            settings.set("mood", self._mood_field.stringValue().strip())
        if self._voice_field is not None:
            settings.set("say_voice", self._voice_field.stringValue().strip())
        self._notify()
