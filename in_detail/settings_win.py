"""A real settings panel for Windows — a tkinter window, not just tray dialogs.

Mirrors settings_window.py (the macOS AppKit panel) field-for-field, including
the camera/screen/mirror/selfie controls — `!peek`/`!screen`/`!live` and the
daily auto-selfie both work on Windows too (see capture.py).
"""

from __future__ import annotations

from . import settings

_DEST_OPTS = ["channel", "dm", "both"]
_TONE_OPTS = ["default", "cutesy", "chill", "detailed"]


def open_settings_window(on_change=None) -> None:
    """Blocks until the window is closed (call from a background thread, same
    as the existing `_ask()` dialogs already do for Reply/Mood)."""
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("overshare — settings")
    root.attributes("-topmost", True)
    root.resizable(False, False)

    pad = {"padx": 10, "pady": 6}
    row = 0

    def header(text):
        nonlocal row
        ttk.Label(root, text=text, font=("", 10, "bold")).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=10, pady=(14, 2))
        row += 1

    def combo_row(label, key, options):
        nonlocal row
        ttk.Label(root, text=label).grid(row=row, column=0, sticky="w", **pad)
        var = tk.StringVar(value=str(settings.get(key) or options[0]))
        cb = ttk.Combobox(root, textvariable=var, values=options, state="readonly", width=22)
        cb.grid(row=row, column=1, sticky="w", **pad)
        row += 1
        return var

    def text_row(label, key, placeholder=""):
        nonlocal row
        ttk.Label(root, text=label).grid(row=row, column=0, sticky="w", **pad)
        var = tk.StringVar(value=str(settings.get(key) or ""))
        entry = ttk.Entry(root, textvariable=var, width=24)
        entry.grid(row=row, column=1, sticky="w", **pad)
        if placeholder and not var.get():
            entry.insert(0, "")  # tk has no native placeholder; label carries the hint instead
        row += 1
        return var

    def check_row(label, key):
        nonlocal row
        var = tk.BooleanVar(value=bool(settings.get(key)))
        ttk.Checkbutton(root, text=label, variable=var).grid(
            row=row, column=0, columnspan=2, sticky="w", padx=10, pady=6)
        row += 1
        return var

    header("Delivery 💌")
    dest_var = combo_row("Send updates to", "card_destination", _DEST_OPTS)
    tone_var = combo_row("Tone she picks", "tone", _TONE_OPTS)
    prefix_var = text_row("Command prefix (blank = !)", "prefix")
    mood_var = text_row("Your mood / status", "mood")
    voice_var = text_row("Voice for !say (blank = default)", "say_voice")
    petname_var = text_row("Pet name (what he calls her)", "pet_name")
    emoji_var = text_row("Tray icon accent (blank = default)", "mood_emoji")

    header("Status accuracy 📡")
    exact_var = check_row("Exact mode — send what's detected, no AI wording", "exact_status")

    header("Camera & screen 🔒")
    camera_var = check_row("Allow camera peeks", "camera_enabled")
    screen_var = check_row("Allow screen peeks", "screen_enabled")
    mirror_var = check_row("Mirror camera photos (selfie view)", "mirror_capture")

    header("Fun 🎉")
    selfie_var = check_row("Daily auto-selfie check-in", "selfie_enabled")
    selfie_time_var = text_row("  ↳ at (HH:MM, 24h)", "selfie_time")
    question_var = check_row("Daily couple question", "daily_question_enabled")
    question_time_var = text_row("  ↳ at (HH:MM, 24h)", "daily_question_time")

    header("Long distance 🌍")
    tz_var = text_row("Her timezone (e.g. America/New_York)", "her_timezone")

    def save_and_close():
        settings.set("card_destination", dest_var.get())
        settings.set("tone", tone_var.get())
        settings.set("prefix", prefix_var.get().strip())
        settings.set("mood", mood_var.get().strip())
        settings.set("say_voice", voice_var.get().strip())
        settings.set("pet_name", petname_var.get().strip())
        settings.set("mood_emoji", emoji_var.get().strip())
        settings.set("exact_status", bool(exact_var.get()))
        settings.set("camera_enabled", bool(camera_var.get()))
        settings.set("screen_enabled", bool(screen_var.get()))
        settings.set("mirror_capture", bool(mirror_var.get()))
        settings.set("selfie_enabled", bool(selfie_var.get()))
        settings.set("selfie_time", selfie_time_var.get().strip() or "09:00")
        settings.set("daily_question_enabled", bool(question_var.get()))
        settings.set("daily_question_time", question_time_var.get().strip() or "12:00")
        settings.set("her_timezone", tz_var.get().strip())
        if on_change:
            try:
                on_change()
            except Exception:
                pass
        root.destroy()

    ttk.Button(root, text="Save & Close", command=save_and_close).grid(
        row=row, column=0, columnspan=2, pady=14)
    root.protocol("WM_DELETE_WINDOW", save_and_close)  # closing the window also saves

    root.eval("tk::PlaceWindow . center")
    root.mainloop()
