"""The menubar app — the thing you actually run.

Shows a little 👀 in your menu bar. Click it to Pause (go dark instantly),
Send an update now, or Quit. In the background it checks what you're doing
every few seconds and posts to Discord per the rules in state.py.
"""

from __future__ import annotations

import datetime as _dt
import threading

import rumps

import random

from . import config
from . import collectors
from . import companion
from . import history
from . import notifier
from . import recap
from . import sites
from . import weekly
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

_ACTIVE_ICON = "👀"
_PAUSED_ICON = "😴"


class InDetailApp(rumps.App):
    def __init__(self) -> None:
        super().__init__(_ACTIVE_ICON, quit_button=None)
        self.paused = config.START_PAUSED
        self.tracker = Tracker()
        self.day = history.load()
        self._ticks = 0
        self._worked_today = False
        self._all_yours_date = ""
        self._weekly_posting = False
        self._flash_ticks = 0  # menu-bar 💛 flash countdown
        self._gm_date = ""
        # Latest activity snapshot, produced by a background thread so slow
        # osascript reads can never stall the menu bar.
        try:
            self._latest = collectors.collect()
        except Exception:
            self._latest = collectors.Snapshot()

        self.status_item = rumps.MenuItem("Starting…")
        self.status_item.set_callback(None)  # display-only
        self.pause_item = rumps.MenuItem("Pause", callback=self.toggle_pause)
        self.send_item = rumps.MenuItem("Send update now", callback=self.send_now)
        self.reply_item = rumps.MenuItem("Reply to her…", callback=self.reply_to_her)
        self.mood_item = rumps.MenuItem("Set mood…", callback=self.set_mood)
        self.recap_item = rumps.MenuItem("Send daily recap now", callback=self.recap_now)
        self.weekly_item = rumps.MenuItem("Send weekly wrap now", callback=self.weekly_now)

        self.menu = [
            self.status_item,
            None,
            self.reply_item,
            self.mood_item,
            self.pause_item,
            self.send_item,
            self.recap_item,
            self.weekly_item,
            None,
            rumps.MenuItem("Quit", callback=self.quit_app),
        ]

        self._apply_paused_ui()

        # Warn up front if something's misconfigured.
        problems = config.missing_requirements()
        if problems:
            self.status_item.title = "⚠️ " + problems[0]
        if not collectors.accessibility_ok():
            try:
                rumps.notification(
                    "in-detail needs Accessibility",
                    "System Settings → Privacy & Security → Accessibility",
                    "so it can read window titles & tabs. Then restart it.",
                )
            except Exception:
                # Notifications need a bundled app; harmless if unavailable
                # (e.g. when launched headless via launchd).
                pass

        # Optional two-way: start the Discord listener if a bot token is set.
        companion.start()

        # Background collector keeps self._latest fresh without blocking the UI.
        threading.Thread(target=self._collect_loop, daemon=True).start()

        self.timer = rumps.Timer(self.tick, config.POLL_INTERVAL)
        self.timer.start()

    # --- UI helpers ---------------------------------------------------------
    def _refresh_icon(self) -> None:
        if self._flash_ticks > 0:
            self.title = "💛"
            self._flash_ticks -= 1
        elif self.paused:
            self.title = _PAUSED_ICON
        elif not self._healthy():
            self.title = "⚠️"
        else:
            self.title = _ACTIVE_ICON

    def _healthy(self) -> bool:
        if not notifier.healthy():
            return False
        if companion.enabled() and companion.dropped():
            return False
        return True

    def _collect_loop(self) -> None:
        import time
        while True:
            try:
                self._latest = collectors.collect()
            except Exception:
                pass
            time.sleep(config.POLL_INTERVAL)

    def _apply_paused_ui(self) -> None:
        self.pause_item.title = "Resume" if self.paused else "Pause"
        if self.paused:
            self.status_item.title = "⏸ Paused"
        self._refresh_icon()

    def _notify(self, title: str, subtitle: str, message: str) -> None:
        try:
            rumps.notification(title, subtitle, message)
        except Exception:
            pass

    def _flash(self, ticks: int = 3) -> None:
        self._flash_ticks = max(self._flash_ticks, ticks)

    def _set_status(self, snap, decision: Decision) -> None:
        label = snap.tab_title or snap.window_title or snap.app
        prefix = "📤 " if decision.should_send else ""
        self.status_item.title = f"{prefix}{snap.app}: {label}"[:60]

    # --- menu callbacks -----------------------------------------------------
    def toggle_pause(self, _sender) -> None:
        self.paused = not self.paused
        self._apply_paused_ui()

    def send_now(self, _sender) -> None:
        decision = self.tracker.force(self._latest)
        self._dispatch(decision)

    def recap_now(self, _sender) -> None:
        threading.Thread(target=self._post_recap, kwargs={"force": True},
                         daemon=True).start()

    def weekly_now(self, _sender) -> None:
        threading.Thread(target=weekly.post, kwargs={"force": True},
                         daemon=True).start()

    def reply_to_her(self, _sender) -> None:
        if not companion.enabled() or not config.DISCORD_HOME_CHANNEL_ID:
            self._notify("Two-way not set up", "", "Add DISCORD_BOT_TOKEN in .env.")
            return
        try:  # bring the app forward so the dialog is visible (menubar-only app)
            from AppKit import NSApplication
            NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        except Exception:
            pass
        win = rumps.Window(message="Send a message to her:", title="Reply",
                           ok="Send", cancel="Cancel", dimensions=(320, 90))
        resp = win.run()
        if resp.clicked and resp.text.strip():
            companion.reply_text(config.DISCORD_HOME_CHANNEL_ID, resp.text.strip())

    def set_mood(self, _sender) -> None:
        from . import settings
        try:
            from AppKit import NSApplication
            NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        except Exception:
            pass
        win = rumps.Window(message="Your mood / status (blank to clear):", title="Mood",
                           ok="Set", cancel="Cancel",
                           default_text=settings.get("mood") or "", dimensions=(300, 80))
        resp = win.run()
        if resp.clicked:
            settings.set("mood", resp.text.strip())

    def quit_app(self, _sender) -> None:
        history.save(self.day)
        rumps.quit_application()

    # --- bot answers & presence ---------------------------------------------
    def _presence_label(self, snap) -> str:
        if snap.url:
            site = sites.lookup(snap.url)
            if site:
                return site.name
        if snap.category == "coding":
            return "code"
        return snap.app

    def _answer_activity(self, channel_id) -> None:
        snap = collectors.collect()
        text = summarize(snap, 0, "change")
        embed = notifier._build_embed(snap, 0)
        companion.reply_embed(channel_id, embed, content=f"👀 {text}")

    def _answer_recap(self, channel_id) -> None:
        _c, embed = recap.build_message(self.day)
        companion.reply_embed(channel_id, embed)

    def _answer_song(self, channel_id) -> None:
        snap = collectors.collect()
        if snap.music:
            t = f"🎧 i'm listening to **{snap.music}**"
            if snap.music_url:
                t += f"\n{snap.music_url}"
        else:
            t = "not listening to anything right now 🤍"
        companion.reply_text(channel_id, t)

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

    # --- daily recap --------------------------------------------------------
    def _rollover_if_new_day(self) -> None:
        today = _dt.date.today().isoformat()
        if self.day.date == today:
            return
        prev = self.day
        if recap.worth_finalizing(prev):
            prev.recap_posted = True  # mark before the (threaded) send
            threading.Thread(target=recap.post, args=(prev,), daemon=True).start()
        history.save(prev)
        self.day = history.load(today)
        self._worked_today = False  # fresh day

    def _post_recap(self, force: bool = False) -> None:
        if not force:
            self.day.recap_posted = True
            history.save(self.day)
        recap.post(self.day)

    def _post_weekly(self) -> None:
        try:
            weekly.post()
        finally:
            self._weekly_posting = False

    def _maybe_all_yours(self, snap, decision: Decision) -> None:
        """Turn the first evening switch away from work into an 'all yours' note."""
        active = snap.idle_seconds < config.IDLE_THRESHOLD
        if active and snap.category in _WORK_CATEGORIES:
            self._worked_today = True
        today = _dt.date.today().isoformat()
        if (
            decision.should_send
            and decision.kind == "change"
            and self._worked_today
            and snap.category not in _WORK_CATEGORIES
            and self._all_yours_date != today
            and _dt.datetime.now().hour >= 18
        ):
            decision.kind = "all_yours"
            self._all_yours_date = today

    def _drain_companion(self) -> None:
        """Handle her incoming messages/reactions (runs even while paused)."""
        while True:
            try:
                kind, payload = companion.events.get_nowait()
            except Exception:
                break
            if kind == "message":
                name, text = payload
                self._notify(f"💌 {name}", "", text)
                self._flash()
            elif kind == "reaction":
                self._notify("💛 she reacted", "", str(payload))
                self._flash()
            elif kind == "poke":
                self._notify("👉 poke!", "", f"{payload} is thinking of you")
                self._flash()
            elif kind == "miss":
                self._notify("🥺 she misses you", "", f"{payload} misses you")
                self._flash()
            elif kind == "callme":
                self._notify("📞 call me", "", f"{payload} wants you to call")
                self._flash()
            elif kind == "break":
                self._notify("☕ take a break", "", f"{payload} says step away for a bit")
                self._flash()
            elif kind == "food":
                self._notify("🍜 did you eat?", "", f"{payload} is checking you ate")
                self._flash()
            elif kind == "greet":
                which, nm = payload
                title = "☀️ good morning" if which == "gm" else "🌙 goodnight"
                self._notify(title, "", f"from {nm}")
                self._flash()
            elif kind == "cmd_activity":
                threading.Thread(target=self._answer_activity, args=(payload,), daemon=True).start()
            elif kind == "cmd_recap":
                threading.Thread(target=self._answer_recap, args=(payload,), daemon=True).start()
            elif kind == "cmd_song":
                threading.Thread(target=self._answer_song, args=(payload,), daemon=True).start()
            elif kind == "request_update" and not self.paused:
                self.send_now(None)

    # --- background loop ----------------------------------------------------
    def tick(self, _timer) -> None:
        self._drain_companion()
        self._refresh_icon()
        if self.paused:
            return
        self._rollover_if_new_day()

        snap = self._latest  # produced by the background collector thread
        decision = self.tracker.evaluate(snap)
        self._set_status(snap, decision)

        # Accumulate the day's tally (only while you're actually at the desk).
        if snap.idle_seconds < config.IDLE_THRESHOLD:
            self.day.record(snap, config.POLL_INTERVAL)
        self._ticks += 1
        if self._ticks % 15 == 0:  # persist ~every 30s
            history.save(self.day)

        # Bot presence (throttled) + scheduled good-morning to her.
        if companion.enabled():
            if self._ticks % 10 == 0 and snap.idle_seconds < config.IDLE_THRESHOLD:
                companion.set_presence(self._presence_label(snap))
            self._maybe_good_morning()

        if recap.due(self.day):
            self._post_recap()
        if not self._weekly_posting and weekly.due():
            self._weekly_posting = True
            threading.Thread(target=self._post_weekly, daemon=True).start()

        self._maybe_all_yours(snap, decision)

        if decision.should_send:
            self._dispatch(decision)

    def _dispatch(self, decision: Decision) -> None:
        """Do the (slow) summarize + network send off the UI thread."""
        if decision.snapshot is None:
            return
        threading.Thread(target=self._send_worker, args=(decision,), daemon=True).start()

    def _send_worker(self, decision: Decision) -> None:
        message = summarize(decision.snapshot, decision.minutes, decision.kind)
        notifier.send_update(
            message, decision.snapshot, decision.minutes, decision.kind
        )


def main() -> None:
    InDetailApp().run()


if __name__ == "__main__":
    main()
