# Contributing

PRs welcome. This is a small, silly project — the bar is "does it work and does
it read like the rest of the code", not ceremony.

## Getting it running

```bash
git clone https://github.com/iota-x/overshare.git
cd overshare
./run.sh          # macOS — makes a venv, installs deps, creates .env
run.bat           # Windows — same
```

Open the settings window on its own with:

```bash
python run_app.py --settings
```

Then check nothing's broken:

```bash
python -m overshare.selftest      # renders every card shape, sends nothing
```

`selftest` leads with a health check (platform, AI provider, webhook,
Accessibility, whether the day's tally is saving) and then prints all ten card
shapes. It's the fastest way to see a formatting change without waiting for the
activity to happen naturally.

## How it fits together

The tray app and the settings window are **two processes**. Qt owns an event
loop and so do rumps (macOS) and pystray (Windows), so they can't share one —
`launcher.py` re-invokes the same binary with `--settings`, and they talk
through the config file.

```
run_app.py ──┬─► overshare/app.py       menu bar (macOS, rumps)
             ├─► overshare/app_win.py   tray (Windows, pystray)
             └─► overshare/gui/         settings window (PySide6) — own process

collectors.py → state.py → summarizer.py → notifier.py → Discord
   what you're    is it     write the       build the
   doing          new?      sentence        card
```

**Config is layered**, highest priority first:

1. `config.json` in the data folder — what the settings window writes
2. `.env` / the environment — still fully supported
3. defaults in `config.py`

Everything reads its values as `config.<NAME>` **at the point of use**, never
`from .config import NAME`. That's what lets `config.reload()` swap values under
a running app, which is why settings apply without a restart. Please keep it
that way — a module-level `from ... import` will silently freeze at startup.

## Adding a setting

1. Add it to `_apply()` in `config.py` (or `_DEFAULTS` in `settings.py` if it's
   one of *her* live preferences rather than install config).
2. Add a row to the matching page in `overshare/gui/pages/`, using the helpers
   in `gui/widgets.py` — `toggle_row`, `text_row`, `slider_row`, `choice_row`,
   `time_row`. They bind to a store and save on change; don't write your own
   save button.
3. If it needs a connection check, add a probe to `gui/probes.py` and run it
   through `Prober` so it stays off the UI thread.

## What CI checks

Every PR builds on macOS and Windows: byte-compiles everything, runs `selftest`,
and brings the settings window up offscreen walking all seven pages in both
light and dark. Installers are only built on a `v*` tag.

## Style

Match what's around you. Comments explain *why*, not what — if a line needs a
comment to say what it does, the line is usually the problem. Commit messages
say what changed and why it mattered, not "fix bug".

## A note on scope

Some obvious features are left out **on purpose** — there's a list at the bottom
of the README. The privacy blocklist is the big one, and a good first PR if you
want somewhere to start.
