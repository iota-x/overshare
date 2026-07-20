"""Windows tray app — the same engine as the macOS app, driven by pystray.

Everything platform-specific (reading activity, notifications, the tray UI) is
here or in `_win.py`; the state machine, sender, recaps, and Discord bot are the
shared modules used on both OSes.
"""

from __future__ import annotations

import os
import threading
import time
import datetime as _dt
import random

import pystray
from PIL import Image

from . import config, collectors, companion, history, notifier, recap, sites, weekly
from .state import Tracker, Decision
from .summarizer import summarize

_WORK_CATEGORIES = {"coding", "terminal"}


def _good_morning_line() -> str:
    her = config.HER_NAME or "love"
    return random.choice([
        f"good morning {her} ☀️ hope you slept well",
        f"morning {her} 🌅 thinking of you already",
        f"gm my love ☀️ have the best day",
        f"good morning {her} 💛 miss you",
    ])


def _load_icon() -> Image.Image:
    here = os.path.dirname(os.path.abspath(__file__))
    for p in (os.path.join(here, "..", "assets", "icon.png"),
              os.path.join(here, "assets", "icon.png")):
        try:
            return Image.open(p)
        except Exception:
            pass
    img = Image.new("RGB", (64, 64), (0x6D, 0x5F, 0xF6))  # fallback: solid tile
    return img


class WinApp:
    def __init__(self) -> None:
        self.paused = config.START_PAUSED
        self.tracker = Tracker()
        self.day = history.load()
        self._ticks = 0
        self._worked_today = False
        self._all_yours_date = ""
        self._weekly_posting = False
        self._gm_date = ""
        self._running = True
        try:
            self._latest = collectors.collect()
        except Exception:
            self._latest = collectors.Snapshot()

        menu = pystray.Menu(
            pystray.MenuItem(lambda i: "Resume" if self.paused else "Pause", self._toggle_pause),
            pystray.MenuItem("Set mood…", self._set_mood),
            pystray.MenuItem("Reply to her…", self._reply),
            pystray.MenuItem("Send daily recap now", self._recap_now),
            pystray.MenuItem("Send weekly wrap now", self._weekly_now),
            pystray.MenuItem("Quit", self._quit),
        )
        self.icon = pystray.Icon("overshare", _load_icon(), self._tooltip(), menu)

        companion.start()
        threading.Thread(target=self._loop, daemon=True).start()

    # --- UI helpers ---------------------------------------------------------
    def _tooltip(self) -> str:
        if self.paused:
            return "overshare — paused"
        if not self._healthy():
            return "overshare — ⚠️ check connection"
        return "overshare 👀"

    def _refresh(self) -> None:
        try:
            self.icon.title = self._tooltip()
            self.icon.update_menu()
        except Exception:
            pass

    def _notify(self, title: str, message: str) -> None:
        try:
            self.icon.notify(message or title, title)
        except Exception:
            pass

    def _healthy(self) -> bool:
        if not notifier.healthy():
            return False
        return not (companion.enabled() and companion.dropped())

    def _ask(self, title: str, prompt: str, default: str = "") -> str | None:
        try:
            import tkinter as tk
            from tkinter import simpledialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            val = simpledialog.askstring(title, prompt, initialvalue=default, parent=root)
            root.destroy()
            return val
        except Exception:
            return None

    # --- menu callbacks -----------------------------------------------------
    def _toggle_pause(self, _icon, _item) -> None:
        self.paused = not self.paused
        self._refresh()

    def _set_mood(self, _icon, _item) -> None:
        from . import settings
        val = self._ask("Mood", "Your mood / status (blank to clear):", settings.get("mood") or "")
        if val is not None:
            settings.set("mood", val.strip())

    def _reply(self, _icon, _item) -> None:
        if not companion.enabled() or not config.DISCORD_HOME_CHANNEL_ID:
            self._notify("Two-way not set up", "Add DISCORD_BOT_TOKEN in .env.")
            return
        val = self._ask("Reply", "Send a message to her:")
        if val and val.strip():
            companion.reply_text(config.DISCORD_HOME_CHANNEL_ID, val.strip())

    def _recap_now(self, _icon, _item) -> None:
        threading.Thread(target=recap.post, args=(self.day,), daemon=True).start()

    def _weekly_now(self, _icon, _item) -> None:
        threading.Thread(target=weekly.post, kwargs={"force": True}, daemon=True).start()

    def _quit(self, _icon, _item) -> None:
        self._running = False
        history.save(self.day)
        try:
            self.icon.stop()
        except Exception:
            pass

    # --- engine (same logic as the macOS app) -------------------------------
    def _rollover_if_new_day(self) -> None:
        today = _dt.date.today().isoformat()
        if self.day.date == today:
            return
        prev = self.day
        if recap.worth_finalizing(prev):
            prev.recap_posted = True
            threading.Thread(target=recap.post, args=(prev,), daemon=True).start()
        history.save(prev)
        self.day = history.load(today)
        self._worked_today = False

    def _maybe_all_yours(self, snap, decision: Decision) -> None:
        active = snap.idle_seconds < config.IDLE_THRESHOLD
        if active and snap.category in _WORK_CATEGORIES:
            self._worked_today = True
        today = _dt.date.today().isoformat()
        if (decision.should_send and decision.kind == "change" and self._worked_today
                and snap.category not in _WORK_CATEGORIES and self._all_yours_date != today
                and _dt.datetime.now().hour >= 18):
            decision.kind = "all_yours"
            self._all_yours_date = today

    def _maybe_good_morning(self) -> None:
        if not (config.GM_ENABLED and companion.enabled() and config.DISCORD_HOME_CHANNEL_ID):
            return
        today = _dt.date.today().isoformat()
        if self._gm_date == today:
            return
        try:
            hh, mm = (int(x) for x in config.GM_TIME.split(":"))
        except Exception:
            hh, mm = 8, 30
        now = _dt.datetime.now()
        if now.hour < 12 and (now.hour, now.minute) >= (hh, mm):
            companion.reply_text(config.DISCORD_HOME_CHANNEL_ID, _good_morning_line())
            self._gm_date = today

    def _presence_label(self, snap) -> str:
        if snap.url:
            site = sites.lookup(snap.url)
            if site:
                return site.name
        return "code" if snap.category == "coding" else snap.app

    def _answer_activity(self, cid) -> None:
        snap = collectors.collect()
        companion.reply_embed(cid, notifier._build_embed(snap, 0),
                              content=f"👀 {summarize(snap, 0, 'change')}")

    def _answer_recap(self, cid) -> None:
        _c, embed = recap.build_message(self.day)
        companion.reply_embed(cid, embed)

    def _answer_song(self, cid) -> None:
        snap = collectors.collect()
        if snap.music:
            t = f"🎧 i'm listening to **{snap.music}**" + (f"\n{snap.music_url}" if snap.music_url else "")
        else:
            t = "not listening to anything right now 🤍"
        companion.reply_text(cid, t)

    def _drain_companion(self) -> None:
        while True:
            try:
                kind, payload = companion.events.get_nowait()
            except Exception:
                break
            if kind == "message":
                name, text = payload
                self._notify(f"💌 {name}", text)
            elif kind == "reaction":
                self._notify("💛 she reacted", str(payload))
            elif kind == "poke":
                self._notify("👉 poke!", f"{payload} is thinking of you")
            elif kind == "miss":
                self._notify("🥺 she misses you", f"{payload} misses you")
            elif kind == "callme":
                self._notify("📞 call me", f"{payload} wants you to call")
            elif kind == "break":
                self._notify("☕ take a break", f"{payload} says step away")
            elif kind == "food":
                self._notify("🍜 did you eat?", f"{payload} is checking you ate")
            elif kind == "greet":
                which, nm = payload
                self._notify("☀️ good morning" if which == "gm" else "🌙 goodnight", f"from {nm}")
            elif kind == "cmd_activity":
                threading.Thread(target=self._answer_activity, args=(payload,), daemon=True).start()
            elif kind == "cmd_recap":
                threading.Thread(target=self._answer_recap, args=(payload,), daemon=True).start()
            elif kind == "cmd_song":
                threading.Thread(target=self._answer_song, args=(payload,), daemon=True).start()
            elif kind == "request_update" and not self.paused:
                self._dispatch(self.tracker.force(self._latest))

    def _dispatch(self, decision: Decision) -> None:
        if decision.snapshot is None:
            return
        threading.Thread(target=self._send_worker, args=(decision,), daemon=True).start()

    def _send_worker(self, decision: Decision) -> None:
        msg = summarize(decision.snapshot, decision.minutes, decision.kind)
        notifier.send_update(msg, decision.snapshot, decision.minutes, decision.kind)

    def _tick(self) -> None:
        self._drain_companion()
        self._refresh()
        if self.paused:
            return
        self._rollover_if_new_day()
        snap = self._latest
        decision = self.tracker.evaluate(snap)
        if snap.idle_seconds < config.IDLE_THRESHOLD:
            self.day.record(snap, config.POLL_INTERVAL)
        self._ticks += 1
        if self._ticks % 15 == 0:
            history.save(self.day)
        if companion.enabled():
            if self._ticks % 10 == 0 and snap.idle_seconds < config.IDLE_THRESHOLD:
                companion.set_presence(self._presence_label(snap))
            self._maybe_good_morning()
        if recap.due(self.day):
            self.day.recap_posted = True
            history.save(self.day)
            threading.Thread(target=recap.post, args=(self.day,), daemon=True).start()
        if not self._weekly_posting and weekly.due():
            self._weekly_posting = True
            threading.Thread(target=self._post_weekly, daemon=True).start()
        self._maybe_all_yours(snap, decision)
        if decision.should_send:
            self._dispatch(decision)

    def _post_weekly(self) -> None:
        try:
            weekly.post()
        finally:
            self._weekly_posting = False

    def _loop(self) -> None:
        while self._running:
            try:
                self._latest = collectors.collect()
            except Exception:
                pass
            try:
                self._tick()
            except Exception:
                pass
            time.sleep(config.POLL_INTERVAL)

    def run(self) -> None:
        self.icon.run()


def main() -> None:
    WinApp().run()


if __name__ == "__main__":
    main()
