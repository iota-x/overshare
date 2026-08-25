"""Windows tray app — the same engine as the macOS app, driven by pystray.

Everything platform-specific (reading activity, notifications, the tray UI) is
here or in `_win.py`; the state machine, sender, recaps, and Discord bot are the
shared modules used on both OSes. Camera/screen peeks (`!peek`/`!screen`/`!live`)
and the daily auto-selfie are macOS-only (no Windows capture backend yet) — your
partner gets a clear message instead of silence if they ask for one. Everything else
introduced alongside the macOS app (reactions, sound board, !say, !remind, pet
names, permission requests, the love-o-meter, screen-time/their-time in the tray,
and Settings) has a Windows equivalent here.
"""

from __future__ import annotations

import os
import threading
import time
import datetime as _dt
import random

import pystray
from PIL import Image

from . import capture, config, collectors, companion, history, log, notifier, questions, recap, settings, sites, sound, weekly, timefmt
from .state import Tracker, Decision
from .summarizer import summarize

_WORK_CATEGORIES = {"coding", "terminal"}


def _good_morning_line() -> str:
    name = settings.get("pet_name") or config.PARTNER_NAME or "love"
    return random.choice([
        f"good morning {name} ☀️ hope you slept well",
        f"morning {name} 🌅 thinking of you already",
        f"gm my love ☀️ have the best day",
        f"good morning {name} 💛 miss you",
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
        self.paused = config.START_PAUSED or bool(settings.get("paused"))
        self.tracker = Tracker()
        self.day = history.load()
        self._ticks = 0
        self._worked_today = False
        self._all_yours_date = ""
        self._weekly_posting = False
        self._gm_date = ""
        self._selfie_date = ""    # last date the daily auto-selfie was sent
        self._question_date = ""  # last date the daily couple question was sent
        self._running = True
        # Last-seen config.json timestamp, so the loop can spot edits made
        # in the settings window and reload without a restart.
        self._config_stamp = config.config_mtime()
        self._screentime_text = "just getting started"
        self._hertime_text = "not set"
        self._reminders: set = set()  # live threading.Timers for pending !remind nudges
        self._loop_errors: dict[str, int] = {}   # what's failing, and how often
        try:
            self._latest = collectors.collect()
        except Exception:
            self._latest = collectors.Snapshot()

        menu = pystray.Menu(
            pystray.MenuItem(lambda i: f"📊 Today: {self._screentime_text}", None, enabled=False),
            pystray.MenuItem(lambda i: f"🕐 Their time: {self._hertime_text}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(lambda i: "Resume" if self.paused else "Pause", self._toggle_pause),
            pystray.MenuItem("Set mood…", self._set_mood),
            pystray.MenuItem("Reply to them…", self._reply),
            pystray.MenuItem("Ask permission…", self._ask_permission),
            # default=True is what makes a left-click on the tray icon do
            # anything at all: pystray dispatches an icon click to the item
            # marked default, and silently does nothing when none is.
            pystray.MenuItem("Settings…", self._open_settings, default=True),
            pystray.MenuItem("Send daily recap now", self._recap_now),
            pystray.MenuItem("Send weekly wrap now", self._weekly_now),
            pystray.MenuItem("Quit", self._quit),
        )
        self.icon = pystray.Icon("overshare", _load_icon(), self._tooltip(), menu)

        companion.start()
        threading.Thread(target=self._first_run, daemon=True).start()
        threading.Thread(target=self._loop, daemon=True).start()
        # Windows machines get shut down for the night, so the in-process day
        # rollover never runs — see recap.catch_up.
        threading.Thread(target=self._catch_up, daemon=True).start()

    # --- UI helpers ---------------------------------------------------------
    def _tooltip(self) -> str:
        accent = settings.get("mood_emoji") or "💌"
        if self.paused:
            return f"overshare — paused ({accent})"
        if not self._healthy():
            return "overshare — ⚠️ check connection"
        return f"overshare {accent}"

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
        if history.save_error:
            return False  # the day's tally isn't persisting — recaps will lie
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
        settings.set("paused", self.paused)
        self._refresh()

    def _set_mood(self, _icon, _item) -> None:
        val = self._ask("Mood", "Your mood / status (blank to clear):", settings.get("mood") or "")
        if val is not None:
            settings.set("mood", val.strip())

    def _reply(self, _icon, _item) -> None:
        if not companion.enabled() or not config.DISCORD_HOME_CHANNEL_ID:
            self._notify("Two-way not set up", "Add DISCORD_BOT_TOKEN in .env.")
            return
        val = self._ask("Reply", "Send a message to them:")
        if val and val.strip():
            companion.reply_text(config.DISCORD_HOME_CHANNEL_ID, val.strip())

    def _ask_permission(self, _icon, _item) -> None:
        if not companion.enabled() or not config.DISCORD_HOME_CHANNEL_ID:
            self._notify("Two-way not set up", "Add DISCORD_BOT_TOKEN in .env.")
            return
        val = self._ask("Ask permission", "What do you want to ask permission for?")
        if val and val.strip():
            asked = val.strip()
            companion.ask_permission(config.DISCORD_HOME_CHANNEL_ID, asked)
            self.day.permissions_asked += 1
            self._notify("🙏 asked them", asked)

    def _open_settings(self, _icon, _item) -> None:
        # The settings window is a Qt app in its own process — pystray already
        # owns this one's loop. It writes config.json; _poll_config picks the
        # changes up from there.
        try:
            from . import launcher
            launcher.open_settings(on_fail=self._settings_failed)
        except Exception as e:
            log.exception("settings: could not launch", e)
            self._notify("Settings", f"couldn't open settings ({e})")

    def _settings_failed(self, why: str) -> None:
        """The window started and died. Point at the log, which now has the why."""
        from . import log as _log
        self._notify("Settings didn't open", f"{why} — details in {_log.path()}")

    def _recap_now(self, _icon, _item) -> None:
        threading.Thread(target=recap.post, args=(self.day,), daemon=True).start()

    def _weekly_now(self, _icon, _item) -> None:
        threading.Thread(target=weekly.post, kwargs={"force": True}, daemon=True).start()

    def _quit(self, _icon, _item) -> None:
        self._running = False
        for t in list(self._reminders):
            try:
                t.cancel()
            except Exception:
                pass
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

    def _due_at(self, hhmm: str, default: tuple[int, int]) -> bool:
        try:
            hh, mm = (int(x) for x in str(hhmm).split(":"))
        except Exception:
            hh, mm = default
        now = _dt.datetime.now()
        return (now.hour, now.minute) >= (hh, mm)

    def _maybe_daily_question(self) -> None:
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
            self._screentime_text = "just getting started"
            return
        self._screentime_text = (" · ".join(f"{k} {recap._hms(v)}" for k, v in apps))[:70]

    def _update_her_time(self) -> None:
        tz = settings.get("her_timezone")
        if not tz:
            self._hertime_text = "not set"
            return
        try:
            from zoneinfo import ZoneInfo
            now = _dt.datetime.now(ZoneInfo(tz))
            self._hertime_text = timefmt.clock(now)
        except Exception:
            self._hertime_text = "invalid timezone"

    def _presence_label(self, snap) -> str:
        return notifier.presence_label(snap)

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

    def _peek_ping(self, what: str) -> None:
        """Say that they're looking, unless the notices were turned off."""
        if config.PEEK_NOTIFY:
            self._notify("📸 they're peeking", what)

    def _answer_peek(self, channel_id, source: str) -> None:
        if not config.PEEK_ENABLED:
            companion.reply_text(channel_id, "peeking is turned off right now 🤍")
            return
        if not settings.peek_source_enabled(source):
            off = "their camera is" if source == "cam" else "screen sharing is"
            companion.reply_text(channel_id, f"{off} turned off right now 🤍")
            return
        if source == "cam":
            if not capture.webcam_available():
                companion.reply_text(channel_id, "no camera set up on their end 😔")
                return
            self._peek_ping("they asked for a webcam photo")
            path = capture.snap_webcam(mirror=bool(settings.get("mirror_capture")))
            caption = "📸 caught them 🤳"
        else:
            self._peek_ping("they asked for a screenshot")
            path = capture.snap_screen()
            caption = "🖥️ their screen right now"
        if path:
            companion.reply_file(channel_id, path, content=caption)
        else:
            companion.reply_text(
                channel_id,
                "couldn't grab that 😔 (camera might be in use, or blocked by Windows camera privacy settings)",
            )

    def _answer_live(self, channel_id, source: str) -> None:
        if not config.PEEK_ENABLED:
            companion.reply_text(channel_id, "peeking is turned off right now 🤍")
            return
        if not settings.peek_source_enabled(source):
            off = "their camera is" if source == "cam" else "screen sharing is"
            companion.reply_text(channel_id, f"{off} turned off right now 🤍")
            return
        if source == "cam" and not capture.webcam_available():
            companion.reply_text(channel_id, "no camera set up on their end 😔")
            return
        if source == "cam":
            _mirror = bool(settings.get("mirror_capture"))
            grab = lambda: capture.snap_webcam(mirror=_mirror)
        else:
            grab = capture.snap_screen
        self._peek_ping(f"they started a live {'camera' if source == 'cam' else 'screen'} view")
        companion.live_feed(channel_id, grab, config.LIVE_SECONDS, config.LIVE_INTERVAL)

    def _maybe_auto_selfie(self) -> None:
        if not (settings.get("selfie_enabled") and companion.enabled() and config.DISCORD_HOME_CHANNEL_ID):
            return
        today = _dt.date.today().isoformat()
        if self._selfie_date == today:
            return
        if self._due_at(settings.get("selfie_time"), (9, 0)):
            self._selfie_date = today
            threading.Thread(target=self._send_auto_selfie, daemon=True).start()

    def _send_auto_selfie(self) -> None:
        if not (config.PEEK_ENABLED and settings.peek_source_enabled("cam") and capture.webcam_available()):
            return
        path = capture.snap_webcam(mirror=bool(settings.get("mirror_capture")))
        if path:
            companion.reply_file(
                config.DISCORD_HOME_CHANNEL_ID, path,
                content="📸 good morning check-in — thinking of you 💛",
            )

    def _speak(self, text: str) -> None:
        from . import settings, voice
        voice.speak(text, settings.get("say_voice") or None)

    def _schedule_reminder(self, seconds: int, message: str) -> None:
        def fire():
            self._reminders.discard(timer)
            self._notify("💛 from them", message)

        timer = threading.Timer(seconds, fire)
        timer.daemon = True
        self._reminders.add(timer)
        timer.start()

    def _drain_companion(self) -> None:
        while True:
            try:
                kind, payload = companion.events.get_nowait()
            except Exception:
                break
            if kind == "message":
                name, text = payload
                self.day.messages_from_partner += 1
                self._notify(f"💌 {name}", text)
            elif kind == "reaction":
                self._notify("💛 they reacted", str(payload))
            elif kind == "poke":
                self.day.pokes += 1
                self._notify("👉 poke!", f"{payload} is thinking of you")
            elif kind == "miss":
                self.day.pokes += 1
                self._notify("🥺 they miss you", f"{payload} misses you")
            elif kind == "callme":
                self.day.pokes += 1
                self._notify("📞 call me", f"{payload} wants you to call")
            elif kind == "break":
                self.day.pokes += 1
                self._notify("☕ take a break", f"{payload} says step away")
            elif kind == "food":
                self.day.pokes += 1
                self._notify("🍜 did you eat?", f"{payload} is checking you ate")
            elif kind == "kiss":
                self.day.pokes += 1
                self._notify("😘 kiss!", f"{payload} sent you a kiss")
            elif kind == "hug":
                self.day.pokes += 1
                self._notify("🫂 hug!", f"{payload} is hugging you")
            elif kind == "boop":
                self.day.pokes += 1
                self._notify("👉 boop!", f"{payload} booped you")
            elif kind == "sound":
                threading.Thread(target=sound.play, args=(payload,), daemon=True).start()
            elif kind == "say":
                _cid, spoken = payload
                self._notify("🔊 they said", spoken)
                threading.Thread(target=self._speak, args=(spoken,), daemon=True).start()
            elif kind == "remind":
                _cid, secs, message = payload
                self._schedule_reminder(secs, message)
            elif kind == "permission_result":
                approved, asked = payload
                if approved:
                    self.day.permissions_approved += 1
                self._notify("✅ they said yes" if approved else "❌ they said no", asked)
            elif kind == "greet":
                which, nm = payload
                self._notify("☀️ good morning" if which == "gm" else "🌙 goodnight", f"from {nm}")
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
                self._dispatch(self.tracker.force(self._latest))

    def _dispatch(self, decision: Decision) -> None:
        if decision.snapshot is None:
            return
        threading.Thread(target=self._send_worker, args=(decision,), daemon=True).start()

    def _send_worker(self, decision: Decision) -> None:
        # Runs on its own thread, in a windowed build with no stderr. Without
        # this, a summarizer or network failure took the whole update with it
        # and left no trace anywhere — the app looked healthy and your partner got
        # nothing.
        try:
            msg = summarize(decision.snapshot, decision.minutes, decision.kind)
        except Exception as e:
            log.exception("send: could not write the message", e)
            return
        try:
            ok = notifier.send_update(
                msg, decision.snapshot, decision.minutes, decision.kind)
        except Exception as e:
            log.exception("send: delivery raised", e)
            return
        log.write("send: sent" if ok else "send: every channel refused it", msg[:120])

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
            self._update_screentime()
            self._update_her_time()
        if companion.enabled():
            if self._ticks % 10 == 0 and snap.idle_seconds < config.IDLE_THRESHOLD:
                companion.set_presence(self._presence_label(snap))
            self._maybe_good_morning()
            self._maybe_daily_question()
            self._maybe_auto_selfie()
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

    def _first_run(self) -> None:
        """Show the settings window when there's nothing configured yet.

        Without this, installing the app and double-clicking it appears to do
        nothing: there's no window, and on Windows 11 a new tray icon goes
        straight into the hidden overflow, so there isn't even an icon to find.
        The app was running the whole time with no way to reach it.
        """
        if config.is_configured():
            return
        # Let the tray icon finish registering first, so the notification below
        # has somewhere to point.
        time.sleep(1.5)
        try:
            from . import launcher
            launcher.open_settings(on_fail=self._settings_failed)
            log.write("first run: opened settings")
        except Exception as e:
            log.exception("first run: could not open settings", e)
            self._notify(
                "Overshare is running",
                "Open the tray (the ^ next to the clock) and click Overshare to set it up.")

    def _catch_up(self) -> None:
        """Send what the schedule missed while the machine was off."""
        try:
            recap.catch_up()
        except Exception:
            pass
        try:
            if weekly.due():
                weekly.post()
        except Exception:
            pass

    def _poll_config(self) -> None:
        """Adopt edits made in the settings window, without a restart.

        Every module reads its values as `config.<NAME>` at the point of use, so
        reloading here is enough — nothing is holding a stale copy.
        """
        stamp = config.config_mtime()
        if stamp == self._config_stamp:
            return
        self._config_stamp = stamp
        config.reload()
        settings._cache = None       # their preferences may have changed too
        # A bot token pasted into the settings window arrives long after
        # companion.start() ran and found nothing. Without this the bot stays
        # offline until the app is restarted, with no hint as to why.
        try:
            companion.start()
        except Exception as e:
            log.exception("companion: could not start after a config change", e)
        # The settings window can pause too, so adopt whatever it decided.
        if bool(settings.get("paused")) != self.paused:
            self.paused = bool(settings.get("paused"))
        self._refresh()

    def _loop(self) -> None:
        while self._running:
            # Each stage is isolated so one bad poll can't kill the loop — but
            # they used to be `except: pass`, which meant a _tick() that threw
            # on every pass sent nothing, for ever, in complete silence. That is
            # exactly the shape of "it's running and they get nothing".
            for name, step in (("poll_config", self._poll_config),
                               ("collect", self._collect_into_latest),
                               ("tick", self._tick)):
                try:
                    step()
                except Exception as e:
                    self._complain(name, e)
            time.sleep(config.POLL_INTERVAL)

    def _collect_into_latest(self) -> None:
        self._latest = collectors.collect()

    def _complain(self, where: str, exc: BaseException) -> None:
        """Log a loop failure, but don't write the same one 30 times a minute."""
        key = f"{where}:{type(exc).__name__}"
        seen = self._loop_errors.get(key, 0) + 1
        self._loop_errors[key] = seen
        if seen == 1 or seen % 100 == 0:
            log.exception(f"loop: {where} failed (x{seen})", exc)

    def run(self) -> None:
        self.icon.run()


_MUTEX = None


def _claim_mutex() -> None:
    """Publish a named mutex so the installer can see us running.

    installer.iss sets AppMutex to this name. That's what lets an upgrade shut
    the app down and start it again by itself, instead of failing partway
    through with files in use — which is the difference between "update" and
    "quit it first, then remember to reopen it".
    """
    global _MUTEX
    try:
        import win32event
        _MUTEX = win32event.CreateMutex(None, False, "Overshare.SingleInstance")
    except Exception as e:
        log.exception("mutex: could not publish one", e)


def main() -> None:
    _claim_mutex()
    WinApp().run()


if __name__ == "__main__":
    main()
