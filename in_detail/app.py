"""The menubar app — the thing you actually run.

Shows a little 💌 in your menu bar. Click it to Pause (go dark instantly),
Send an update now, or Quit. In the background it checks what you're doing
every few seconds and posts to Discord per the rules in state.py.
"""

from __future__ import annotations

import datetime as _dt
import threading

import rumps

import random

from . import config
from . import capture
from . import collectors
from . import companion
from . import history
from . import notifier
from . import questions
from . import recap
from . import settings
from . import sites
from . import sound
from . import weekly
from .state import Tracker, Decision
from .summarizer import summarize

_WORK_CATEGORIES = {"coding", "terminal"}


def _good_morning_line() -> str:
    from . import settings
    her = settings.get("pet_name") or config.HER_NAME or "love"
    return random.choice([
        f"good morning {her} ☀️ hope you slept well",
        f"morning {her} 🌅 thinking of you already",
        f"gm my love ☀️ have the best day",
        f"good morning {her} 💛 miss you",
    ])

_ACTIVE_ICON = "💌"
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
        self._selfie_date = ""    # last date the daily auto-selfie was sent
        self._question_date = ""  # last date the daily couple question was sent
        # Latest activity snapshot, produced by a background thread so slow
        # osascript reads can never stall the menu bar.
        try:
            self._latest = collectors.collect()
        except Exception:
            self._latest = collectors.Snapshot()

        self.status_item = rumps.MenuItem("Starting…")
        self.status_item.set_callback(None)  # display-only
        self.screentime_item = rumps.MenuItem("📊 Today: —")
        self.screentime_item.set_callback(None)
        self.hertime_item = rumps.MenuItem("🕐 Her time: —")
        self.hertime_item.set_callback(None)
        self.pause_item = rumps.MenuItem("Pause", callback=self.toggle_pause)
        self.send_item = rumps.MenuItem("Send update now", callback=self.send_now)
        self.reply_item = rumps.MenuItem("Reply to her…", callback=self.reply_to_her)
        self.mood_item = rumps.MenuItem("Set mood…", callback=self.set_mood)
        self.ask_item = rumps.MenuItem("Ask permission…", callback=self.ask_her_permission)
        self.recap_item = rumps.MenuItem("Send daily recap now", callback=self.recap_now)
        self.weekly_item = rumps.MenuItem("Send weekly wrap now", callback=self.weekly_now)
        # Live privacy switches: whether she can pull a camera / screen view.
        # Checkmark = allowed. config.PEEK_ENABLED is the master off-switch.
        from . import settings
        self.camera_item = rumps.MenuItem("Allow camera peeks", callback=self.toggle_camera)
        self.screen_item = rumps.MenuItem("Allow screen peeks", callback=self.toggle_screen)
        # Mirror webcam photos so they look like a selfie rather than reversed.
        self.mirror_item = rumps.MenuItem("Mirror camera photos", callback=self.toggle_mirror)
        self.camera_item.state = 1 if settings.get("camera_enabled") else 0
        self.screen_item.state = 1 if settings.get("screen_enabled") else 0
        self.mirror_item.state = 1 if settings.get("mirror_capture") else 0
        # Full settings panel (everything the menu bar covers, in one window).
        self.settings_item = rumps.MenuItem("Settings…", callback=self.open_settings)
        # Last-seen config.json timestamp, so tick() can spot edits made in the
        # settings window and reload without a restart.
        self._config_stamp = config.config_mtime()
        self._reminders = set()   # live rumps.Timers for pending !remind nudges

        self.menu = [
            self.status_item,
            self.screentime_item,
            self.hertime_item,
            None,
            self.reply_item,
            self.mood_item,
            self.ask_item,
            self.pause_item,
            self.send_item,
            self.recap_item,
            self.weekly_item,
            None,
            self.settings_item,
            self.camera_item,
            self.screen_item,
            self.mirror_item,
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
        # Anything that came due while the app was closed — see recap.catch_up.
        threading.Thread(target=self._catch_up, daemon=True).start()

        self.timer = rumps.Timer(self.tick, config.POLL_INTERVAL)
        self.timer.start()

    # --- UI helpers ---------------------------------------------------------
    def _refresh_icon(self) -> None:
        from . import settings
        active_icon = settings.get("mood_emoji") or _ACTIVE_ICON
        if self._flash_ticks > 0:
            self.title = "💛"
            self._flash_ticks -= 1
        elif self.paused:
            self.title = _PAUSED_ICON
        elif not self._healthy():
            self.title = "⚠️"
        else:
            self.title = active_icon

    def _healthy(self) -> bool:
        if not notifier.healthy():
            return False
        if companion.enabled() and companion.dropped():
            return False
        if history.save_error:
            return False  # the day's tally isn't persisting — recaps will lie
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

    def toggle_camera(self, _sender) -> None:
        from . import settings
        new = not bool(settings.get("camera_enabled"))
        settings.set("camera_enabled", new)
        self.camera_item.state = 1 if new else 0

    def toggle_screen(self, _sender) -> None:
        from . import settings
        new = not bool(settings.get("screen_enabled"))
        settings.set("screen_enabled", new)
        self.screen_item.state = 1 if new else 0

    def toggle_mirror(self, _sender) -> None:
        from . import settings
        new = not bool(settings.get("mirror_capture"))
        settings.set("mirror_capture", new)
        self.mirror_item.state = 1 if new else 0

    def open_settings(self, _sender) -> None:
        # The settings window is a Qt app in its own process — rumps already
        # owns this one's event loop. It writes config.json; _poll_config picks
        # the changes up from there.
        try:
            from . import launcher
            launcher.open_settings()
        except Exception as e:
            rumps.notification("overshare", "Settings", f"couldn’t open settings ({e})")

    def _sync_menu_states(self) -> None:
        # Keep the menu-bar checkmarks in step with edits made in the panel.
        from . import settings
        self.camera_item.state = 1 if settings.get("camera_enabled") else 0
        self.screen_item.state = 1 if settings.get("screen_enabled") else 0
        self.mirror_item.state = 1 if settings.get("mirror_capture") else 0

    def _say_aloud(self, text: str) -> None:
        from . import voice, settings
        voice.speak(text, settings.get("say_voice") or None)

    def _schedule_reminder(self, seconds: int, message: str) -> None:
        # rumps.Timer fires on the main run loop, so the notification is safe.
        def fire(timer) -> None:
            timer.stop()
            self._reminders.discard(timer)
            self._notify("💛 from her", "", message)
            self._flash()

        timer = rumps.Timer(fire, seconds)
        self._reminders.add(timer)
        timer.start()

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

    def ask_her_permission(self, _sender) -> None:
        if not companion.enabled() or not config.DISCORD_HOME_CHANNEL_ID:
            self._notify("Two-way not set up", "", "Add DISCORD_BOT_TOKEN in .env.")
            return
        try:  # bring the app forward so the dialog is visible (menubar-only app)
            from AppKit import NSApplication
            NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        except Exception:
            pass
        win = rumps.Window(message="What do you want to ask her permission for?",
                           title="Ask permission", ok="Ask", cancel="Cancel",
                           dimensions=(320, 90))
        resp = win.run()
        if resp.clicked and resp.text.strip():
            asked = resp.text.strip()
            companion.ask_permission(config.DISCORD_HOME_CHANNEL_ID, asked)
            self.day.permissions_asked += 1
            self._notify("🙏 asked her", "", asked)
            self._flash()

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
        return notifier.presence_label(snap)

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

    def _peek_ping(self, what: str) -> None:
        """Let him know she's looking (unless he turned notices off)."""
        if config.PEEK_NOTIFY:
            self._notify("📸 she's peeking", "", what)
            self._flash()

    def _answer_peek(self, channel_id, source: str) -> None:
        from . import settings
        if not config.PEEK_ENABLED:
            companion.reply_text(channel_id, "peeking is turned off right now 🤍")
            return
        if not settings.peek_source_enabled(source):
            off = "his camera is" if source == "cam" else "screen sharing is"
            companion.reply_text(channel_id, f"{off} turned off right now 🤍")
            return
        if source == "cam":
            if not capture.webcam_available():
                companion.reply_text(channel_id, "no camera tool set up on his end 😔")
                return
            self._peek_ping("she asked for a webcam photo")
            path = capture.snap_webcam(mirror=bool(settings.get("mirror_capture")))
            caption = "📸 caught him 🤳"
        else:
            self._peek_ping("she asked for a screenshot")
            path = capture.snap_screen()
            caption = "🖥️ his screen right now"
        if path:
            companion.reply_file(channel_id, path, content=caption)
        else:
            companion.reply_text(
                channel_id,
                "couldn’t grab that 😔 (needs Camera / Screen Recording permission for the app)",
            )

    def _answer_live(self, channel_id, source: str) -> None:
        from . import settings
        if not config.PEEK_ENABLED:
            companion.reply_text(channel_id, "peeking is turned off right now 🤍")
            return
        if not settings.peek_source_enabled(source):
            off = "his camera is" if source == "cam" else "screen sharing is"
            companion.reply_text(channel_id, f"{off} turned off right now 🤍")
            return
        if source == "cam" and not capture.webcam_available():
            companion.reply_text(channel_id, "no camera tool set up on his end 😔")
            return
        if source == "cam":
            _mirror = bool(settings.get("mirror_capture"))
            grab = lambda: capture.snap_webcam(mirror=_mirror)
        else:
            grab = capture.snap_screen
        self._peek_ping(f"she started a live {'camera' if source == 'cam' else 'screen'} view")
        companion.live_feed(channel_id, grab, config.LIVE_SECONDS, config.LIVE_INTERVAL)

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

    def _due_at(self, hhmm: str, default: tuple[int, int]) -> bool:
        """Has today passed HH:MM yet? Used for the once-daily extras below."""
        try:
            hh, mm = (int(x) for x in str(hhmm).split(":"))
        except Exception:
            hh, mm = default
        now = _dt.datetime.now()
        return (now.hour, now.minute) >= (hh, mm)

    def _maybe_auto_selfie(self) -> None:
        from . import settings
        if not (settings.get("selfie_enabled") and companion.enabled() and config.DISCORD_HOME_CHANNEL_ID):
            return
        today = _dt.date.today().isoformat()
        if self._selfie_date == today:
            return
        if self._due_at(settings.get("selfie_time"), (9, 0)):
            self._selfie_date = today
            threading.Thread(target=self._send_auto_selfie, daemon=True).start()

    def _send_auto_selfie(self) -> None:
        from . import settings
        if not (config.PEEK_ENABLED and settings.peek_source_enabled("cam") and capture.webcam_available()):
            return
        path = capture.snap_webcam(mirror=bool(settings.get("mirror_capture")))
        if path:
            companion.reply_file(
                config.DISCORD_HOME_CHANNEL_ID, path,
                content="📸 good morning check-in — thinking of you 💛",
            )

    def _maybe_daily_question(self) -> None:
        from . import settings
        if not (settings.get("daily_question_enabled") and companion.enabled() and config.DISCORD_HOME_CHANNEL_ID):
            return
        today = _dt.date.today().isoformat()
        if self._question_date == today:
            return
        if self._due_at(settings.get("daily_question_time"), (12, 0)):
            self._question_date = today
            companion.reply_text(
                config.DISCORD_HOME_CHANNEL_ID, f"❓ question of the day: {questions.pick()}"
            )

    def _update_screentime(self) -> None:
        apps = recap._top(self.day.by_app, 3)
        if not apps:
            self.screentime_item.title = "📊 Today: just getting started"
            return
        parts = [f"{k} {recap._hms(v)}" for k, v in apps]
        self.screentime_item.title = ("📊 Today: " + " · ".join(parts))[:80]

    def _update_her_time(self) -> None:
        from . import settings
        tz = settings.get("her_timezone")
        if not tz:
            self.hertime_item.title = "🕐 Her time: not set"
            return
        try:
            from zoneinfo import ZoneInfo
            now = _dt.datetime.now(ZoneInfo(tz))
            self.hertime_item.title = f"🕐 Her time: {now.strftime('%-I:%M %p').lower()}"
        except Exception:
            self.hertime_item.title = "🕐 Her time: invalid timezone"

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

    def _catch_up(self) -> None:
        """Send what the schedule missed while we weren't running."""
        try:
            recap.catch_up()
        except Exception:
            pass
        try:
            if weekly.due():
                weekly.post()
        except Exception:
            pass

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
                self.day.messages_from_her += 1
                self._notify(f"💌 {name}", "", text)
                self._flash()
            elif kind == "reaction":
                self._notify("💛 she reacted", "", str(payload))
                self._flash()
            elif kind == "poke":
                self.day.pokes += 1
                self._notify("👉 poke!", "", f"{payload} is thinking of you")
                self._flash()
            elif kind == "miss":
                self.day.pokes += 1
                self._notify("🥺 she misses you", "", f"{payload} misses you")
                self._flash()
            elif kind == "callme":
                self.day.pokes += 1
                self._notify("📞 call me", "", f"{payload} wants you to call")
                self._flash()
            elif kind == "break":
                self.day.pokes += 1
                self._notify("☕ take a break", "", f"{payload} says step away for a bit")
                self._flash()
            elif kind == "food":
                self.day.pokes += 1
                self._notify("🍜 did you eat?", "", f"{payload} is checking you ate")
                self._flash()
            elif kind == "kiss":
                self.day.pokes += 1
                self._notify("😘 kiss!", "", f"{payload} sent you a kiss")
                self._flash()
            elif kind == "hug":
                self.day.pokes += 1
                self._notify("🫂 hug!", "", f"{payload} is hugging you")
                self._flash()
            elif kind == "boop":
                self.day.pokes += 1
                self._notify("👉 boop!", "", f"{payload} booped you")
                self._flash()
            elif kind == "sound":
                threading.Thread(target=sound.play, args=(payload,), daemon=True).start()
            elif kind == "greet":
                which, nm = payload
                title = "☀️ good morning" if which == "gm" else "🌙 goodnight"
                self._notify(title, "", f"from {nm}")
                self._flash()
            elif kind == "say":
                _cid, spoken = payload
                self._notify("🔊 she said", "", spoken)
                self._flash()
                # Speaking blocks until done, so keep it off the main loop.
                threading.Thread(target=self._say_aloud, args=(spoken,), daemon=True).start()
            elif kind == "remind":
                _cid, secs, message = payload
                self._schedule_reminder(secs, message)
            elif kind == "permission_result":
                approved, asked = payload
                if approved:
                    self.day.permissions_approved += 1
                title = "✅ she said yes" if approved else "❌ she said no"
                self._notify(title, "", asked)
                self._flash()
            elif kind == "cmd_activity":
                threading.Thread(target=self._answer_activity, args=(payload,), daemon=True).start()
            elif kind == "cmd_recap":
                threading.Thread(target=self._answer_recap, args=(payload,), daemon=True).start()
            elif kind == "cmd_song":
                threading.Thread(target=self._answer_song, args=(payload,), daemon=True).start()
            elif kind == "cmd_peek":
                self.day.peeks += 1
                threading.Thread(target=self._answer_peek, args=(payload, "cam"), daemon=True).start()
            elif kind == "cmd_screen":
                self.day.peeks += 1
                threading.Thread(target=self._answer_peek, args=(payload, "screen"), daemon=True).start()
            elif kind == "cmd_live":
                self.day.peeks += 1
                cid, src = payload
                self._answer_live(cid, src)
            elif kind == "request_update" and not self.paused:
                self.send_now(None)

    # --- background loop ----------------------------------------------------
    def _poll_config(self) -> None:
        """Adopt edits made in the settings window, without a restart.

        Every module reads its values as `config.<NAME>` at the point of use, so
        a reload is enough — nothing has stale copies. The one exception is our
        own poll timer, whose interval was fixed when it was created.
        """
        stamp = config.config_mtime()
        if stamp == self._config_stamp:
            return
        self._config_stamp = stamp
        config.reload()
        settings._cache = None       # her preferences may have changed too
        self._sync_menu_states()
        if abs(self.timer.interval - config.POLL_INTERVAL) > 0.01:
            self.timer.interval = config.POLL_INTERVAL

    def tick(self, _timer) -> None:
        self._poll_config()
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
            self._update_screentime()
            self._update_her_time()

        # Bot presence (throttled) + scheduled good-morning to her.
        if companion.enabled():
            if self._ticks % 10 == 0 and snap.idle_seconds < config.IDLE_THRESHOLD:
                companion.set_presence(self._presence_label(snap))
            self._maybe_good_morning()
            self._maybe_auto_selfie()
            self._maybe_daily_question()

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
