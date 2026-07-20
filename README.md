# overshare 👀

A tiny macOS menu-bar app that keeps your partner **lovingly over-informed** about
everything you're doing on your Mac — automatically, in real time, in detail.

> **Origin story:** my girlfriend said I don't give her enough *detail* about my
> day. So instead of just... texting more like a normal person, I built an app
> that broadcasts my entire screen life to her. This is that app. 💛

Whenever you switch apps or tabs (and every few minutes as a heartbeat), it posts
a warm, AI-written one-liner + a rich card to a Discord channel (or her DMs):

- **VS Code / terminal** → `coding in Cursor — app.py 💻`
- **YouTube / Twitch / Netflix** → the actual video/stream, with a thumbnail + "▶️ watch along"
- **Spotify** (even in the background) → the track, with a "🎧 play along" link
- **Discord** → which channel you're in
- **Genshin, any game, any app** → caught by the generic layer
- **Idle** → "stepped away 🙂"; late at night → "goodnight 🌙"

## What it does

- **Sees everything** — frontmost app, window/file titles, browser tab + URL,
  background music, idle time. Works for *every* app on your Mac.
- **Per-site smarts** — known sites get their own emoji + brand color + phrasing
  (📺 YouTube, 🟣 Twitch, 👽 Reddit, 🐙 GitHub, 🤖 ChatGPT, and ~20 more).
- **Rich Discord cards** — clickable links, thumbnails, channel names, now-playing,
  duration, color-coded by activity.
- **Free AI** — writes the one-liners via **Groq** (free cloud) or **Ollama**
  (free local), or **Claude** if you want. Or plain templates (no AI).
- **Two-way** — with a Discord bot, she can reply, react, and run commands; you
  get it all as Mac notifications.
- **Recaps** — a daily summary card + a weekly "Wrapped" (hours, top apps, most
  watched, soundtrack, late nights, streaks).
- **Sweet touches** — listen/watch-along, morning/night bookends, "all yours now"
  when you finish work, mood/status, tone presets she picks.
- **Featherweight & resilient** — ~84 MB RAM, near-0% CPU, auto-reconnects, and a
  menu-bar ⚠️ if anything ever breaks.
- **An off-switch** — one click to Pause (😴). Because *sometimes* you want privacy.
  (Or not — see below. 😏)

## Two-way commands (she types these in Discord)

| Command | Does |
|---|---|
| `!help` | posts the full command list |
| `!wyd` | bot replies with your live activity |
| `!song` · `!recap` | now-playing / today's recap |
| `!poke` `!miss` `!callme` `!break` `!food` | pings your Mac |
| `gm` / `gn` · say **i love you** | greetings · auto ❤️ react |
| `!dm` / `!channel` / `!both` | where her updates go |
| `!tone cutesy` / `chill` / `detailed` | how you write to her |
| react ❤️ to any card | 💛 flashes your menu bar |

## Setup

1. **Discord webhook** — make a channel, `Edit Channel → Integrations → Webhooks
   → New Webhook → Copy URL`.
2. **Configure** — `cp .env.example .env`, set `DISCORD_WEBHOOK_URL`, pick an AI
   provider (`AI_PROVIDER=groq` + a free key from console.groq.com is the sweet
   spot — free *and* nothing runs on your Mac).
3. **Build the app** — `./run.sh` once, then `python setup.py py2app -A` and move
   `dist/In Detail.app` to `/Applications`. It auto-starts on login.
4. **Grant permissions** — Accessibility (window titles) + Automation (browser
   tabs & Spotify) for **In Detail** in System Settings → Privacy & Security.
5. *(Optional)* **Two-way bot** — create a bot at discord.com/developers, enable
   Message Content Intent, invite it, and set `DISCORD_BOT_TOKEN` in `.env`.

Full details for each step live in the comments of `.env.example`.

## Stack

Python + [`rumps`](https://github.com/jaredks/rumps) menu-bar app · `pyobjc`
(AppKit/Quartz/Accessibility) for macOS reads · `osascript` for browser/Spotify ·
[`discord.py`](https://github.com/Rapptz/discord.py) for the two-way bot ·
packaged with `py2app`. AI is pluggable: Groq / Ollama / Anthropic / templates.

## Privacy

With Groq or Ollama, your activity text never leaves your control (Ollama is fully
local; Groq is a free cloud call). Nothing is stored or sent anywhere except the
Discord channel you configure. There's a Pause button for the moments that
shouldn't be a live feed.

---

## Potential improvements (intentionally *not* added 😅)

These are real, useful features — I just didn't build them, because **I share
everything with my girl. Like, everything.** But if you're a more private person,
you'll probably want some of these:

- **🔒 Privacy blocklist / incognito guard** — the big one. Auto-hide banking,
  passwords, 1Password, and *private/incognito windows* behind a vague "busy 🔒"
  instead of the real app/site. I left this out on purpose — she can see my
  banking, my passwords, my incognito tabs, all of it. No secrets here. But most
  people should absolutely add this before going live.
- **🌙 Quiet hours** — auto-pause overnight (e.g. 1am–9am) so it isn't broadcasting
  while you sleep. (I don't mind her seeing my 3am doomscrolling.)
- **😴 Snooze options** — "pause 1 hour" / "pause till tomorrow" instead of only an
  indefinite pause.
- **👥 Multiple recipients / group** — post to more than one person or a shared feed.
- **📸 Screenshot / selfie on request** — she asks, and (with a per-request tap to
  approve) gets a screen peek or a webcam wave. Fun but a little much.
- **📊 Web dashboard** — a live private web page of your day instead of / alongside
  Discord.
- **📍 Away context** — "stepped out" vs "at desk" using more than just idle time.
- **🪟 Windows / Linux agents** — right now it's macOS-only (it leans on
  NSWorkspace + AppleScript).
- **🧠 Smarter batching** — coalesce a burst of rapid tab-switches into one update
  instead of several.
- **🎚️ Setup UI** — a real settings window instead of editing `.env`.

PRs welcome. Or, you know, just trust your partner completely and skip half of
these like I did. 💛

---

*Built with a lot of love (and slightly concerning transparency).*
