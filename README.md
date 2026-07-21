# overshare 💌

**the clingy-girlfriend starter pack 💅** — a tiny menu-bar / tray app that keeps
your partner *lovingly over-informed* about everything you do on your computer,
automatically, in real time, in detail. For the girlfriends who need to know
where their man is at all times, and the boyfriends who have *nothing to hide* 😇

> **Origin story:** my girlfriend said I don't give her enough *detail* about my
> day. So instead of just... texting more like a normal person, I built an app
> that broadcasts my entire screen life to her. This is that app. 💛

Works on **macOS** and **Windows**. Whenever you switch apps or tabs (and every
few minutes as a heartbeat), it posts a warm, AI-written one-liner + a rich card
to a Discord channel (or her DMs):

- **VS Code / terminal** → `coding in Cursor — app.py 💻`
- **YouTube / Twitch / Netflix** → the video/stream (+ thumbnail & "▶️ watch along" on macOS)
- **Spotify** (even in the background) → the track (+ "🎧 play along" link on macOS)
- **Discord** → which channel you're in
- **Games / any app** → caught by the generic layer
- **Idle** → "stepped away 🙂"; late night → "goodnight 🌙"

## What it does

- **Sees everything** — frontmost app, window/file titles, browser tab, background
  music, idle time.
- **Per-site smarts** — 📺 YouTube, 🟣 Twitch, 👽 Reddit, 🐙 GitHub, 🤖 ChatGPT… own
  emoji + brand color + phrasing.
- **Rich Discord cards** — links, thumbnails, channel names, now-playing, duration.
- **Peek on demand** — she can ask for a 📸 webcam photo, a 🖥️ screenshot, or a
  live-ish auto-refreshing frame — and you get pinged every time (see [Peek](#peek--camera--screen-on-demand)).
- **Free AI** — [Groq](https://console.groq.com) (free cloud) / Ollama (free local)
  / Claude, or plain templates.
- **Two-way** — with a Discord bot she can reply, react, and run commands.
- **Recaps** — a daily summary + a weekly "Wrapped" (top apps, watches, soundtrack,
  streaks, late nights).
- **Sweet touches** — listen/watch-along, morning/night bookends, "all yours now",
  mood/status, tone presets she picks.
- **Featherweight & resilient** — tiny footprint, auto-reconnects, ⚠️ if anything breaks.
- **An off-switch** — one click to Pause. Because *sometimes* you want privacy. (Or not. 😏)

---

## Requirements

- **macOS** (Apple Silicon/Intel) **or Windows 10/11**
- **Python 3.10+** — [python.org](https://www.python.org/downloads/) (on Windows,
  tick **"Add Python to PATH"** during install)
- A **Discord** account + a server you control
- *(only for local AI on macOS)* Homebrew
- *(only for the webcam peek on macOS)* `imagesnap` — `brew install imagesnap`

```bash
git clone https://github.com/iota-x/overshare.git
cd overshare
```

Then follow **[macOS](#-macos-setup)** or **[Windows](#-windows-setup)** below.

---

## 🍎 macOS setup

**1. First run** (makes a virtualenv, installs deps, creates `.env`):
```bash
./run.sh
```
**2. Edit `.env`** — set `DISCORD_WEBHOOK_URL` and pick an AI provider (see
[AI providers](#ai-providers)).

**3. Test:** `./run.sh` again → a 👀 appears in your menu bar. `Ctrl-C` to stop.

**4. Build the app:**
```bash
./.venv/bin/python setup.py py2app -A
mv "dist/Overshare.app" /Applications/
open "/Applications/Overshare.app"
```

**5. Grant permissions** (System Settings → Privacy & Security):
- **Accessibility** → turn on **Overshare** (window/file titles + Discord channel)
- **Automation** → allow **Overshare** to control your **browser** + **Spotify**
  (browser tab URLs + background music)
- *(only if you use `!peek` / `!live`)* **Camera**, and **Screen Recording** for
  `!screen` — macOS prompts the first time each is used.

After granting Accessibility, quit Overshare (menu bar → Quit) and reopen it.

**6. Auto-start:** System Settings → General → Login Items → **+** → add Overshare.

> **Note:** the app is built with `py2app -A` (alias mode), so it runs your live
> source. After you edit the code, **quit and reopen** the app to pick up changes.

---

## 🪟 Windows setup

**1. First run** — double-click **`run.bat`** (or run it in a terminal). It makes a
virtualenv, installs deps, and creates `.env`, then exits.

**2. Edit `.env`** — set `DISCORD_WEBHOOK_URL` and pick an AI provider (see
[AI providers](#ai-providers)). `AI_PROVIDER=groq` with a free key is ideal.

**3. Test:** run **`run.bat`** again → a 👀 tray icon appears near the clock
(click the ▲ if it's hidden). Right-click it for the menu.

**4. Build a standalone `.exe`** (optional, so you don't need a terminal):
```bat
.venv\Scripts\pip install pyinstaller
.venv\Scripts\pyinstaller --noconsole --name Overshare --add-data "assets\icon.png;assets" run_app.py
```
The app is then `dist\Overshare\Overshare.exe`.

**5. Permissions:** none needed — Windows doesn't gate this like macOS does. 🎉

**6. Auto-start:** press `Win+R`, type `shell:startup`, Enter, and drop a shortcut
to `run.bat` (or `Overshare.exe`) in that folder.

> **Windows notes:** it reads the active window title (which for browsers already
> includes the page title, e.g. *"FIFA - YouTube"*) and reads background Spotify
> from its window title. Clickable URLs / thumbnails / per-site colors and the
> `!peek` / `!screen` / `!live` peek commands are macOS-only for now (Windows has
> no clean cross-browser URL API) — everything else works.

---

## AI providers

Set `AI_PROVIDER` in `.env`:

| Provider | Cost | Setup |
|---|---|---|
| **`groq`** ⭐ | free | free key at [console.groq.com](https://console.groq.com) → `GROQ_API_KEY=gsk_...`. Cloud, fast, no card, nothing runs on your machine. |
| **`ollama`** | free | `brew install ollama && ollama pull llama3.2` (macOS) → `AI_PROVIDER=ollama`. Local, ~2 GB RAM. |
| **`anthropic`** | paid | key at [console.anthropic.com](https://console.anthropic.com) → `ANTHROPIC_API_KEY=sk-ant-...`. Best writing. |
| *(none)* | free | `AI_ENABLED=false` — plain templates. |

---

## Two-way bot (optional) 💌

Lets her reply, react, and run commands — you get it all as notifications.

1. [discord.com/developers](https://discord.com/developers/applications) → **New
   Application** → **Bot** → **Reset Token** → copy → `.env`: `DISCORD_BOT_TOKEN=...`
2. Enable **MESSAGE CONTENT INTENT** on the Bot page → Save.
3. **OAuth2 → URL Generator** → scopes `bot`; permissions: View Channels, Read
   Message History, Add Reactions, Attach Files → open the URL → add to your server.
4. Optional in `.env`: `DISCORD_CHANNEL_ID` (comma-sep), `DISCORD_HOME_CHANNEL_ID`,
   `HER_USER_ID` (respond only to her), `HER_NAME`, `BOT_PREFIX`.
5. Restart the app.

### Commands she types

The prefix defaults to `!` and is **changeable** — she can run `!prefix >` to switch
to any symbol, or set `BOT_PREFIX` in `.env`.

| Command | Does |
|---|---|
| `!help` | posts the full command list |
| `!wyd` | bot replies with your live activity |
| `!song` · `!recap` | now-playing · today's recap |
| `!peek` · `!screen` | a webcam photo · a screenshot |
| `!live` · `!live screen` | live-ish view (auto-refreshing frame) |
| `!poke` `!miss` `!callme` `!break` `!food` | pings you |
| `!gm` / `!gn` · say **i love you** | greetings · auto ❤️ react |
| `!dm` / `!channel` / `!both` | where her updates go |
| `!tone cutesy` / `chill` / `detailed` | how you write to her |
| `!prefix <x>` | change the command prefix |
| react ❤️ to any card | 💛 flashes your tray/menu bar |

### Peek — camera & screen on demand

`!peek` sends a **webcam photo**, `!screen` a **screenshot**, and `!live` an
auto-refreshing frame that feels live (add `screen` for the desktop). A bot can't
open a real live *stream*, so this is fast snapshot-on-demand.

- **Webcam** needs `brew install imagesnap`. The screen uses the built-in
  `screencapture` — no install. (The app finds `imagesnap` even when launched as a
  bundled `.app` with a minimal `PATH`.)
- First use, macOS asks for **Camera** and **Screen Recording** permission for the app (System Settings → Privacy). The green camera light shows whenever the webcam fires.
- Only allowed users (`HER_USER_IDS`) can trigger it, and **you get a card + flash every time she peeks** (`PEEK_NOTIFY=false` to silence, `PEEK_ENABLED=false` to disable the whole feature).
- **Per-source toggles in the menu bar** — **Allow camera peeks** and **Allow screen peeks** flip camera and screen independently, live (checkmark = allowed). Turn the camera off and `!peek` politely bounces while `!screen` still works — no restart, and it sticks across launches.

---

## Config reference (`.env`)

| Key | What |
|---|---|
| `DISCORD_WEBHOOK_URL` | **required** — where cards are posted |
| `AI_PROVIDER` / `AI_ENABLED` | `groq` / `ollama` / `anthropic`; `false` = templates |
| `GROQ_API_KEY`, `OLLAMA_MODEL`, `ANTHROPIC_API_KEY` | provider keys/models |
| `DISCORD_BOT_TOKEN`, `BOT_PREFIX` | two-way bot + command prefix |
| `DISCORD_CHANNEL_ID`, `DISCORD_HOME_CHANNEL_ID`, `HER_USER_ID`, `HER_NAME` | bot scoping |
| `PEEK_ENABLED`, `PEEK_NOTIFY`, `LIVE_SECONDS`, `LIVE_INTERVAL` | camera/screen peek |
| `POLL_INTERVAL`, `STABILIZE`, `MIN_GAP`, `HEARTBEAT`, `IDLE_THRESHOLD` | timing (s) |
| `REPORT_MEDIA`, `RECAP_TIME`, `WEEKLY_DAY/TIME`, `GM_TIME`, `START_PAUSED` | features |

Every key has an inline comment in `.env.example`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| macOS: only app names (no file/tab detail) | Grant **Accessibility**, then Quit + reopen |
| macOS: no browser URL / background Spotify | Grant **Automation** (browser + Spotify) |
| `!peek` says "no camera tool set up" | `brew install imagesnap`, then Quit + reopen the app |
| `!peek` says "couldn't grab that" | Grant **Camera** (and **Screen Recording** for `!screen`) to the app, then retry |
| ⚠️ indicator | Bot disconnected or webhook failing — check token/webhook/internet |
| Her DM updates don't arrive | Her Discord DMs must be open to the bot |
| Bot shows offline | Check token, Message Content Intent, and that it's invited |
| Messages are plain/templated | AI provider/key not set — it falls back to templates |

## Stack

Python · [`rumps`](https://github.com/jaredks/rumps) (macOS menu bar) /
[`pystray`](https://github.com/moses-palmer/pystray) (Windows tray) · `pyobjc` +
`osascript` (macOS) / `pywin32` + `psutil` (Windows) ·
[`discord.py`](https://github.com/Rapptz/discord.py) for the bot ·
`imagesnap` + `screencapture` (macOS peeks). Pluggable AI:
Groq / Ollama / Anthropic / templates.

## Privacy

With Groq or Ollama your activity text stays private. Nothing is stored or sent
anywhere except the Discord channel you configure. The camera/screen peek is off
unless you enable it, limited to allowed users, and pings you every time. There's
a Pause button for the moments that shouldn't be a live feed.

---

## Potential improvements (intentionally *not* added 😅)

Real, useful features I skipped — because **I share everything with my girl. Like,
everything.** If you're more private, you'll want some of these:

- **🔒 Privacy blocklist / incognito guard** — the big one. Auto-hide banking,
  passwords, 1Password, and *private/incognito windows* behind a vague "busy 🔒".
  I left this out on purpose (she can see my banking, my passwords, my incognito
  tabs — no secrets here). **Most people should add this before going live.**
- **🌙 Quiet hours** — auto-pause overnight so it isn't broadcasting while you sleep.
- **😴 Snooze** — "pause 1 hour / till tomorrow" instead of only an indefinite pause.
- **🔗 Windows browser URLs** — thumbnails / clickable links / per-site colors on
  Windows (needs UI-Automation address-bar reading).
- **👥 Multiple recipients** · **📊 web dashboard** · **🎚️ a real settings window**
  instead of editing `.env`.

PRs welcome. Or just trust your partner completely and skip half of these like I did. 💛

---

*Built with a lot of love (and slightly concerning transparency). MIT — do
whatever you want with it.*
