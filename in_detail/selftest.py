"""Post one card of every kind, so you can see exactly what she'll see.

    python -m in_detail.selftest              # dry run: print the cards here
    python -m in_detail.selftest --post       # actually send them to her channel
    python -m in_detail.selftest --live       # one card for what you're doing now

Formatting bugs used to only show up when a real activity happened to hit the
broken path — hours or days later, in her channel. This makes every path
reproducible on demand.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

from . import collectors, config, history, notifier
from .collectors import Snapshot
from .summarizer import summarize

# One representative snapshot per code path, including the awkward ones:
# non-ASCII names, unread counters, and titles that carry their own app name.
_CASES: list[tuple[str, Snapshot]] = [
    ("discord · server channel", Snapshot(
        app="Discord", bundle_id="com.hnc.Discord", category="discord",
        window_title="#general | Gooner hideout - Discord")),
    ("discord · dm, non-ascii", Snapshot(
        app="Discord", bundle_id="com.hnc.Discord", category="discord",
        window_title="(1466) Discord | @め michiyo")),
    ("discord · in a browser tab", Snapshot(
        app="Brave Browser", bundle_id="com.brave.Browser", category="browsing",
        tab_title="(1467) Discord | @my soldier 🩷",
        url="https://discord.com/channels/@me/1470856102026547383")),
    ("browsing · youtube + music", Snapshot(
        app="Brave Browser", bundle_id="com.brave.Browser", category="browsing",
        tab_title="Never Gonna Give You Up - YouTube",
        url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        music="粛清 — 米津玄師 (Spotify)",
        music_url="https://open.spotify.com/track/abc")),
    ("browsing · unknown site", Snapshot(
        app="Brave Browser", bundle_id="com.brave.Browser", category="browsing",
        tab_title="Some Obscure Blog — Archive", url="https://example.com/post/1")),
    ("coding · file in project", Snapshot(
        app="Cursor", bundle_id="com.todesktop.230313mzl4w4u92", category="coding",
        window_title="notifier.py — in-detail")),
    ("terminal", Snapshot(
        app="iTerm2", bundle_id="com.googlecode.iterm2", category="terminal",
        window_title="in-detail — -zsh")),
    ("notes", Snapshot(
        app="Obsidian", bundle_id="md.obsidian", category="notes",
        window_title="Daily note - Brain")),
    ("music", Snapshot(
        app="Spotify", bundle_id="com.spotify.client", category="music",
        window_title="Lovely White — Soo Yeony")),
    ("bare app, no title at all", Snapshot(
        app="Preview", bundle_id="com.apple.Preview", category="other")),
]


def _render(label: str, snap: Snapshot, minutes: int, use_ai: bool) -> dict:
    message = summarize(snap, minutes, "change") if use_ai else ""
    embed = notifier._build_embed(snap, minutes)
    emoji, header, title, context, _color = notifier.describe(snap)
    print(f"\n─── {label}")
    print(f"    author   {emoji} {header}")
    print(f"    title    {title}")
    print(f"    context  {context or '—'}")
    print(f"    link     {embed.get('url') or '—'}")
    for field in embed.get("fields", []):
        print(f"    field    {field['name']}: {field['value']}")
    if message:
        print(f"    message  {message}")
    print(f"    presence {notifier.presence_label(snap)}")
    return embed


def _health() -> int:
    """Report anything that would stop her from getting good updates."""
    problems = list(config.missing_requirements())
    if not collectors.accessibility_ok():
        problems.append("no Accessibility permission — window titles will be blank")
    if history.save_error:
        problems.append(f"history isn't saving: {history.save_error}")
    provider = config.active_provider()
    print(f"platform     {sys.platform}")
    print(f"ai provider  {provider}" + (f" ({config.GROQ_MODEL})" if provider == "groq" else ""))
    print(f"webhook      {'set' if config.DISCORD_WEBHOOK_URL else 'MISSING'}")
    for p in problems:
        print(f"  ⚠️  {p}")
    return len(problems)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="in_detail.selftest", description=__doc__)
    ap.add_argument("--post", action="store_true",
                    help="really send the cards to the configured destination")
    ap.add_argument("--live", action="store_true",
                    help="use what you're actually doing right now instead of samples")
    ap.add_argument("--no-ai", action="store_true", help="skip the AI one-liner")
    args = ap.parse_args(argv)

    print("=== health ===")
    problems = _health()

    cases = _CASES
    if args.live:
        snap = collectors.collect()
        cases = [("live · what you're doing now", snap)]

    print("\n=== cards ===")
    embeds = [(label, _render(label, snap, 7, not args.no_ai)) for label, snap in cases]

    if not args.post:
        print(f"\ndry run — nothing sent. {len(embeds)} card(s) rendered.")
        print("re-run with --post to send them to her channel for real.")
        return 1 if problems else 0

    print(f"\nsending {len(embeds)} card(s)…")
    sent = 0
    for i, (label, embed) in enumerate(embeds):
        if i:
            # Webhooks rate-limit at roughly 5 posts / 2s; a burst of cards would
            # get 429'd and silently dropped, which is the opposite of a self-test.
            time.sleep(1.5)
        if notifier.post_embed(embed, f"**self-test** · {label}"):
            sent += 1
            print(f"  sent: {label}")
        else:
            print(f"  FAILED: {label}")
    print(f"sent {sent}/{len(embeds)}")
    return 0 if sent == len(embeds) else 1


if __name__ == "__main__":
    raise SystemExit(main())
