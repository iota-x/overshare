# Overshare — browser

The companion to the Overshare desktop app. The desktop app sees *what app and
what page* you're on (window titles, the browser's address bar). It cannot see
**inside** a page — a like, a Not Interested, an upvote, which reel you're on.
Those live in the page's DOM, and only something running *in* the page can read
them. That's this.

It posts to the **same Discord webhook** your desktop app uses, as cards in the
same style, so both streams land in one channel.

## Everything is off until you turn it on

A fresh install captures nothing: no webhook, master switch off, every site off,
every action off. You opt in to each thing. There are three levels of switch:

- **the master switch** — off means nothing leaves the browser, whatever else is ticked
- **per site** — X, Instagram, YouTube, Reddit, each on/off on its own
- **per action** — under each site: liked, Not Interested, reel, upvote, lingering, …

It also never touches DM / message screens, skips incognito windows unless you
opt in, and reads only *public actions* — a like, a vote, what you're watching —
never the contents of your messages.

## Install (unpacked)

It's not on any store — load it from disk:

1. **Chrome / Brave / Edge / Arc / Opera** → `chrome://extensions`
2. Turn on **Developer mode**
3. **Load unpacked** → pick this `extension/` folder
4. Click the extension → **Options** → paste your Discord webhook URL, hit
   **Send a test card** to confirm it reaches the channel, then switch on the
   sites and actions you want.

One extension covers every Chromium browser, on both macOS and Windows. Firefox
and Safari need small manifest changes — not done yet.

## What it can detect today

| Site | Actions |
|---|---|
| X / Twitter | like, unlike, repost, reply, follow, **Not Interested**, lingering on a post |
| Instagram | like, unlike, save, follow, lingering on a post or **reel** |
| YouTube | **watching** a video/short, like, unlike, lingering |
| Reddit | upvote, downvote, save, lingering on a post |
| TikTok | like, unlike, follow, save, lingering on a video |
| Spotify | save a track, lingering on music |
| Netflix | what you're watching, lingering on a title |
| Amazon | add to cart, save, lingering on a product |
| LinkedIn | like, unlike, lingering on a post |

The four below TikTok haven't had a real event through them yet, so their
selectors may need a first-run tune — the same pass X and Instagram got.

## Adding a site

Everything site-specific is in two places:

- `src/registry.js` — one row: the site's hosts and which actions it can emit.
  The options page and the toggle gate build themselves from this.
- `src/adapters/<site>.js` — the detectors. An adapter watches the page and
  calls `Overshare.emit(site, action, detail)`; the shared `base.js` handles
  sending, dwell timing, click delegation, and de-duping.

Then add a `content_scripts` entry in `manifest.json` for the new host.

## A caveat worth knowing

These sites rewrite their HTML often, and the detectors key on `data-testid`s and
`aria-label`s that the sites can change without warning. When a site ships a
redesign, its adapter may go quiet until its selectors are updated — that's the
one file to fix, and it fails silent (stops sending) rather than sending wrong
things.

## Architecture

```
manifest.json            hosts, permissions, which adapter loads where
src/
  registry.js            the sites + the action vocabulary (single source)
  config.js              stored settings + allowed() — the one toggle gate
  background.js          receives events, checks the gate, posts to the webhook
  content.js             starts the matched adapter
  adapters/
    base.js              emit(), dwell, click delegation, de-dupe — shared
    x.js instagram.js youtube.js reddit.js
  options.html/js/css    the switches (built from the registry)
```

The rule that matters: content scripts only **detect**. Whether anything is
actually *sent* is decided in exactly one place — `allowed()` in `config.js`,
called by the background — so no detector, and no future adapter, can slip past
a switch that's off.
