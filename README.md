# in-detail 💬

A tiny macOS menubar app that keeps your girlfriend posted — automatically — on
what you're doing on your Mac. Whenever you switch apps/tabs (and every 5 min
as a heartbeat), it posts a warm, casual one-liner to a Discord channel you
share with her.

> Built because "I don't give enough detail" deserved an over-engineered fix. 😄

## What she sees

- **VS Code / terminal** → `coding in Cursor — App.tsx (wallet-chat)`
- **YouTube** → `watching some genshin 5.3 stream 📺`
- **X / Reddit / any site** → `scrolling X for a sec`
- **Discord** → whatever channel your Discord window title shows
- **Genshin, any game, Spotify, Notes, literally any app** → caught by the
  generic "frontmost app + window title" layer
- **Background music** → what you're doing *plus* what's playing on Spotify /
  Apple Music, even when it's not in focus: `watching the FIFA final while
  Bambi Baker plays 🎧`

Every message is time-stamped: `**8:42 pm** · watching some genshin 📺`

## How it works

- Reads the **frontmost app** (works for *every* app on your Mac) + its window
  title. Browsers additionally give the active **tab title + URL**.
- A small state machine decides *when* to send: on a real change (after it's
  stuck around ~12s so quick alt-tabbing doesn't spam), a 5-min heartbeat, and
  an "away / back" when you go idle.
- An **AI** writes the actual one-liner — free & local via **Ollama** by
  default, or **Claude** if you prefer (or plain templates with AI off).
- Posts to Discord via a **webhook**.
- Menubar **Pause** button (😴) instantly stops broadcasting — your off-switch.

## Two-way (optional bot)
With a bot token set, she can talk back. Commands she can type in the channel:

| Command | Does |
|---|---|
| `!help` | posts the full command list |
| `!wyd` | bot replies in-channel with your live activity card |
| `!song` | what you're listening to (+ play link) |
| `!recap` | today's recap so far |
| `!poke` · `!miss` · `!callme` · `!break` · `!food` | pings your Mac |
| `gm` / `gn` | good morning / goodnight |
| say **i love you** | bot auto-reacts ❤️ |
| react ❤️ to any card | 💛 flashes your menu bar + a notification |

Anything else she types pops up on your Mac. You can reply back from the menu
bar → **Reply to her…**. The bot
also auto-sends a **good morning** to the channel at `GM_TIME`, and its Discord
status shows what you're doing. See the README `.env` section for setup.

## Sweet touches
- **Listen-along / watch-along** — the "also playing" track is a tappable
  Spotify link, and video cards get a "▶️ watch along" button so she can join.
- **Bookends** — auto "good morning ☀️" (first activity after a long/overnight
  gap), "goodnight 🌙" (going idle late), and "work's done — all yours 💕" when
  you leave work apps in the evening. These are curated, warm lines (not AI).
- **Daily recap** — end-of-day summary card (time, top apps, watches, soundtrack).
  Preview via menu → *Send daily recap now*.
- **Weekly Wrapped** — a Sunday "your week" card (hours, days on, late nights,
  top apps/watches/sites/tracks). Menu → *Send weekly wrap now*.
- **Per-site smarts** — known sites get their own emoji, brand colour, and
  phrasing (📺 YouTube, 🟣 Twitch, 👽 Reddit, 🐙 GitHub, 🤖 ChatGPT…).

## Setup

### 1. Discord webhook (where she gets updates)
Make a private server/channel with her, then:
`Channel → Edit Channel → Integrations → Webhooks → New Webhook → Copy URL`

### 2. Configure
```bash
cd ~/Desktop/projects/in-detail
cp .env.example .env
```
Set `DISCORD_WEBHOOK_URL` in `.env`. Then pick who writes the messages:

- **Free & local (default)** — Ollama on your Mac, nothing leaves your machine:
  ```bash
  brew install ollama
  ollama pull llama3.2      # ~2 GB, one time
  ```
  Leave `AI_PROVIDER=ollama` in `.env`. That's it — no key, no cost.
- **Claude** — better writing, costs money: set `AI_PROVIDER=anthropic` and
  `ANTHROPIC_API_KEY=sk-ant-...` (get a key at https://console.anthropic.com).
- **No AI** — set `AI_ENABLED=false` for plain templated messages.

### 3. Run
First-time setup (makes the virtualenv + installs deps, then builds the app):
```bash
./run.sh                              # Ctrl-C once the 👀 appears
./.venv/bin/python setup.py py2app -A # build In Detail.app
mv "dist/In Detail.app" /Applications/
```
After that it's just a normal Mac app:
- **Run it** — double-click **In Detail** in `/Applications` (or ⌘Space → "In Detail").
- **Auto-start on login** — it's added to System Settings → General → Login Items.
- **Quit / restart** — click the menu-bar icon → **Quit**, then reopen it.

A 👀 (or 😴 when paused) appears in your menu bar. No terminal needed for daily use.

> `service.sh` (a `launchd` background service) is an optional alternative to
> the app + Login Items — it also adds crash auto-restart. The `_legacy/` plist
> is there if you want it. Most people can ignore it.

### 4. Grant two permissions (one-time macOS prompts)
- **Accessibility** — System Settings → Privacy & Security → **Accessibility** →
  turn on **In Detail** (add it from `/Applications` if it's not listed).
  Needed to read window titles, VS Code file names & the Discord channel.
- **Automation** — macOS asks "In Detail wants to control Chrome/Safari/Spotify…"
  the first time it reads a browser tab or now-playing track. Click **OK**.

After granting Accessibility, restart it: menu-bar icon → **Quit**, then reopen
**In Detail** from `/Applications`.

## Test the pieces individually
```bash
./.venv/bin/python -m in_detail.collectors   # prints what it currently sees
./.venv/bin/python -m in_detail.notifier     # sends a test message to Discord
```

## AI options & cost
- **Ollama (default, free):** runs `llama3.2` locally — no cost, and the
  activity text never leaves your Mac. Want snappier? Try a tinier model:
  `ollama pull qwen2.5:3b` then set `OLLAMA_MODEL=qwen2.5:3b`.
- **Claude:** each update is a short API call. For an all-day tool that adds up
  — `AI_MODEL=claude-haiku-4-5` is much cheaper than opus and still great.
- **Templates:** `AI_ENABLED=false` — zero AI, zero cost.

## Privacy / the off-switch
- **Pause** in the menubar = instant silence. Use it for banking, surprises,
  job hunting, anything you don't want on the live feed.
- With Ollama (default), the activity text never leaves your Mac. Nothing is
  stored or sent anywhere except your Discord channel — and, only if you switch
  to Claude, the short activity text sent to Anthropic to write the line.
- Want auto-hiding of sensitive apps (a blocklist) or quiet hours? Easy to add —
  it was scoped out of v1, ping me.

## Tuning
All timing lives in `.env` (`POLL_INTERVAL`, `STABILIZE`, `MIN_GAP`,
`HEARTBEAT`, `IDLE_THRESHOLD`). Defaults: look every 2s, announce after 2s
(so tab switches update in ~2–4s), ≥4s between updates, heartbeat every 5 min
(re-sends with the running time), "away" after 5 min idle. Want it calmer /
chattier? Raise/lower `STABILIZE` and `MIN_GAP`.

## Notes & limits
- **Discord channel detail** is best-effort: it comes from the Discord window
  title, which usually shows `#channel | Server`. If Discord only exposes
  "Discord", you'll just get "on Discord".
- **Firefox** tab reading isn't supported (no AppleScript hook); it still shows
  as "on Firefox" via the generic layer. Chrome, Brave, Arc, Edge, Safari,
  Vivaldi, Opera all give full tab detail.

## The app bundle
It's packaged as **In Detail.app** (menubar-only, custom icon, signed identity
so macOS permissions stick). Auto-start on login is handled by the `launchd`
service (`service.sh`) — no Login Items needed.

Rebuild the app after code changes:
```bash
./.venv/bin/python setup.py py2app -A
rm -rf "/Applications/In Detail.app"
mv "dist/In Detail.app" "/Applications/In Detail.app"
./service.sh start
```
Regenerate the icon: `cd assets && ../.venv/bin/python make_icon.py`.
(Because the ad-hoc signature changes on rebuild, you may need to re-tick
Accessibility for the new build.)
