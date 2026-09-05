"""Turns a raw activity Snapshot into a warm, casual one-liner.

Uses Claude when configured; falls back to a plain template if the API is off,
unkeyed, or unreachable — so the app never goes silent because of the network.
"""

from __future__ import annotations

import random
import re

from . import config
from . import sites
from .collectors import Snapshot

# Curated, warm "moment" lines. These are greetings, not activity reports, so we
# don't let a small model near them — we pick from these for variety instead.
_MOMENTS = {
    "morning": [
        "just woke up, good morning love ☀️",
        "morning! just got on my mac 🌅",
        "up and at it — morning babe ☀️",
        "just started my day, thinking of you 💛",
    ],
    "night": [
        "heading to bed — goodnight, miss you 💤",
        "calling it a night 🌙 sweet dreams love",
        "off to sleep now, night night 💤",
        "winding down for bed — goodnight babe 🌙",
    ],
    "all_yours": [
        "work's done — all yours now 💕",
        "finished for the day, i'm all yours 💛",
        "done working! yours for the rest of the night 🥰",
        "clocking off — all yours now 💕",
    ],
    "away": [
        "stepped away from the desk for a bit 🙂",
        "afk for a little while",
        "away from my desk for a sec",
    ],
}

_SYSTEM = (
    "You write short, warm, casual status updates that someone sends to their "
    "partner, so their partner always knows what they're up to on their computer. "
    "Voice: first person, texting-casual, lowercase is fine, affectionate but "
    "not over the top. At most one emoji, often zero. ONE short line only. "
    "No preamble, no quotes, no explanation — output only the message itself.\n"
    "ACCURACY MATTERS MORE THAN ANYTHING. They trust this to be literally true. "
    "Use ONLY the facts in the context below. Never infer, upgrade, embellish, or "
    "guess an activity. Do NOT say the writer is watching, streaming, playing, "
    "calling, on "
    "a call, or with anyone — unless the context explicitly states it. Do not name "
    "a video, stream, game, or person that isn't given. Be specific only with "
    "details actually provided (a video title, a file, a site name). "
    "For a chat or voice app like Discord: when the context gives a 'discord "
    "channel/dm', SAY IT — the channel is the interesting part, so 'in #general' "
    "beats 'on discord', and name the server too when one is given. Those are "
    "facts you were handed, not guesses. Only when no channel is given do you fall "
    "back to saying just that they're on it (e.g. 'on discord'). Either way never "
    "invent a stream, a topic, or who they're with. When details are thin, stay "
    "general ('on my mac') rather than guessing. If background music is listed you "
    "may weave it in. When in doubt, under-describe — say less, never more than "
    "the facts. "
    "If the context marks this as lingering on the SAME thing for a while (a "
    "dwell), you may say so warmly — 'still deep in this', 'been on this a "
    "while' — using only the detail given, never inventing why they're lingering."
)

_TONES = {
    "cutesy": "Lean extra cute and affectionate — playful, warm, a pet name is "
              "welcome, an emoji or two is fine.",
    "chill": "Keep it super laid-back and minimal — lowercase, casual, few words.",
    "detailed": "Include a little more specific detail about exactly what you're doing.",
}


def _system() -> str:
    from . import settings
    extra = _TONES.get(settings.get("tone"), "")
    return _SYSTEM + ((" " + extra) if extra else "")


def _conversation(snap: Snapshot) -> tuple[str, str]:
    """The Discord channel/DM and server they'd actually care about, if any."""
    from .notifier import _discord_channel
    if snap.category == "discord":
        return _discord_channel(snap.window_title)
    site = sites.lookup(snap.url) or sites.lookup_title(snap.tab_title)
    if site and site.name == "Discord":
        return _discord_channel(snap.tab_title)
    return "", ""


def _context_block(snap: Snapshot, minutes: int, kind: str) -> str:
    from . import settings
    lines = [
        f"app: {snap.app}",
        f"category: {snap.category}",
    ]
    mood = settings.get("mood")
    if mood:
        lines.append(f"their current mood/status: {mood}")
    # Where possible hand the model the *parsed* pieces and withhold the raw
    # title: given the raw string it echoes it verbatim ("on discord #general |
    # gooner hideout"), which reads like a log line, not something you'd text.
    channel, server = _conversation(snap)
    if channel:
        lines.append(f"discord channel/dm: {channel}")
        if server:
            lines.append(f"discord server: {server}")
    else:
        if snap.window_title:
            lines.append(f"window/title: {snap.window_title}")
        if snap.tab_title:
            lines.append(f"browser tab: {snap.tab_title}")
    if snap.url:
        lines.append(f"url: {snap.url}")
        site = sites.lookup(snap.url)
        if site:
            lines.append(f"site: {site.name} (you're {site.verb} it)")
    if snap.music:
        lines.append(f"background music playing: {snap.music}")
    if minutes >= 1:
        lines.append(f"time on this so far: ~{minutes} min")
    if kind == "dwell":
        lines.append("note: they've been on this SAME thing a while — lingering on it, "
                     "not just still around. say so warmly, with the detail given.")
    elif kind == "heartbeat":
        lines.append("note: still doing this — a gentle 'still at it' check-in")
    elif kind == "back":
        lines.append("note: just came back to the desk after being away")
    elif kind == "morning":
        lines.append("note: just started the day at the computer — a warm good-morning to them")
    elif kind == "night":
        lines.append("note: winding down for the night — a soft goodnight to them")
    elif kind == "all_yours":
        lines.append("note: just finished work for the day — tell them you're all theirs now, affectionately")
    return "\n".join(lines)


def _template(snap: Snapshot, minutes: int, kind: str) -> str:
    """Plain fallback message — no AI needed."""
    if kind in _MOMENTS:
        return random.choice(_MOMENTS[kind])
    if kind == "back":
        return "back at my desk 👋"

    detail = snap.tab_title or snap.window_title
    where = snap.app
    if detail.strip().lower() == where.strip().lower():
        detail = ""  # "on Discord — Discord" tells them nothing
    channel, server = _conversation(snap)
    if channel:
        base = f"on {where} in {channel}"
        if server:
            base += f" ({server})"
    elif snap.category == "browsing" and detail:
        base = f"on {where}: {detail}"
    elif snap.category == "coding" and detail:
        base = f"coding in {where} — {detail}"
    elif detail:
        base = f"on {where} — {detail}"
    else:
        base = f"on {where}"

    if kind == "dwell":
        # Lingering on one thing — warmer and more specific than the heartbeat:
        # "still on this exact post", not "still around".
        # `base` already opens with "on …"/"coding in …", so just prefix "still".
        base = f"still {base}" + (f" — {minutes} min in 👀" if minutes >= 1 else " 👀")
    elif kind == "heartbeat" and minutes >= 1:
        base = f"still {base} (~{minutes} min)"
    if snap.music:
        base = f"{base} 🎧 {snap.music}"
    return base


def _clean(text: str) -> str:
    """Strip quotes / extra lines the model might wrap around the message.

    Reasoning models (gpt-oss, qwen3, deepseek-r1) narrate inside <think> blocks
    before answering. Taking the first line blindly would send them the model's
    scratchpad, so drop those blocks before picking the line."""
    text = re.sub(r"(?is)<(think|reasoning)>.*?</\1>", " ", text or "")
    text = re.sub(r"(?is)^\s*<(think|reasoning)>.*$", " ", text)  # unclosed block
    text = text.strip().strip('"').strip()
    for line in text.splitlines():
        line = line.strip().strip('"').strip()
        if line:
            return line
    return ""


def _user_prompt(snap: Snapshot, minutes: int, kind: str) -> str:
    return (
        "Write the update. Here's what I'm doing right now:\n\n"
        + _context_block(snap, minutes, kind)
    )


def _chat_anthropic(system: str, user: str, max_tokens: int = 120) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)
    resp = client.messages.create(
        model=config.AI_MODEL,
        max_tokens=max_tokens,
        system=system,
        # Simple task: no thinking, low effort keeps it fast + cheap and avoids
        # reasoning leaking into the visible text.
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": user}],
    )
    if resp.stop_reason == "refusal":
        return ""
    return _clean(
        "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    )


def _chat_ollama(system: str, user: str, num_predict: int = 60) -> str:
    """Free, local. Talks to the Ollama server over plain HTTP (no SDK)."""
    import requests

    resp = requests.post(
        f"{config.OLLAMA_HOST}/api/chat",
        json={
            "model": config.OLLAMA_MODEL,
            "stream": False,
            # Low temperature: we want faithful, not creative — fewer invented details.
            "options": {"temperature": 0.4, "num_predict": num_predict},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        },
        timeout=30,
    )
    resp.raise_for_status()
    return _clean(resp.json().get("message", {}).get("content", ""))


def _via_anthropic(snap: Snapshot, minutes: int, kind: str) -> str:
    return _chat_anthropic(_system(), _user_prompt(snap, minutes, kind))


def _via_ollama(snap: Snapshot, minutes: int, kind: str) -> str:
    return _chat_ollama(_system(), _user_prompt(snap, minutes, kind))


def _chat_openai(base_url: str, api_key: str, model: str, system: str, user: str,
                 max_tokens: int = 300, extra: dict | None = None) -> str:
    """OpenAI-compatible chat — works with Groq, Cerebras, OpenRouter, etc.

    The budget is deliberately generous: the reasoning models these free hosts
    now serve spend most of their tokens thinking, and a tight cap means the
    visible answer never gets written and they get an empty card."""
    import requests

    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.4,
        "max_tokens": max_tokens,
    }
    body.update(extra or {})
    resp = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json=body,
        timeout=30,
    )
    if resp.status_code == 400 and extra:
        # Host doesn't know the reasoning knobs — retry plain rather than go silent.
        return _chat_openai(base_url, api_key, model, system, user, max_tokens)
    resp.raise_for_status()
    return _clean(resp.json()["choices"][0]["message"].get("content") or "")


# Keep the thinking short and out of the reply — we want the one line, not the
# reasoning that produced it. Ignored by hosts that don't serve reasoning models.
_REASONING_OPTS = {"reasoning_effort": "low", "reasoning_format": "hidden"}


def _chat_groq(system: str, user: str, max_tokens: int = 300) -> str:
    return _chat_openai(config.GROQ_BASE_URL, config.GROQ_API_KEY, config.GROQ_MODEL,
                        system, user, max_tokens, _REASONING_OPTS)


def _via_groq(snap: Snapshot, minutes: int, kind: str) -> str:
    return _chat_groq(_system(), _user_prompt(snap, minutes, kind))


_RECAP_SYSTEM = (
    "You write ONE warm, casual sentence for your partner, summarizing how "
    "your time on the computer went based on the stats you're given. First "
    "person, affectionate, relaxed. At most one emoji. Output only the sentence."
)


def recap_intro(stats: str, period: str = "day") -> str:
    """A one-line warm intro for a recap card (period = 'day' or 'week')."""
    provider = config.active_provider()
    user = f"Here are the stats for my {period}:\n\n{stats}\n\nWrite the one-sentence recap."
    try:
        if provider == "ollama":
            text = _chat_ollama(_RECAP_SYSTEM, user, num_predict=90)
        elif provider == "groq" and config.GROQ_API_KEY:
            text = _chat_groq(_RECAP_SYSTEM, user, max_tokens=400)
        elif provider == "anthropic" and config.ANTHROPIC_API_KEY:
            text = _chat_anthropic(_RECAP_SYSTEM, user, max_tokens=150)
        else:
            text = ""
    except Exception:
        text = ""
    return text or "here's how my day went 💙"


def summarize(snap: Snapshot, minutes: int = 0, kind: str = "change") -> str:
    """kind: 'change' | 'heartbeat' | 'away' | 'back'."""
    # Moment greetings are curated (reliable + sweet), not model-written.
    if kind in _MOMENTS:
        return _template(snap, minutes, kind)

    # Exact mode: send only what's literally detected, no AI phrasing at all.
    # For when they need the status to be beyond-doubt accurate.
    from . import settings
    if settings.get("exact_status"):
        return _template(snap, minutes, kind)

    provider = config.active_provider()
    try:
        if provider == "ollama":
            text = _via_ollama(snap, minutes, kind)
        elif provider == "groq" and config.GROQ_API_KEY:
            text = _via_groq(snap, minutes, kind)
        elif provider == "anthropic" and config.ANTHROPIC_API_KEY:
            text = _via_anthropic(snap, minutes, kind)
        else:
            text = ""
    except Exception:
        text = ""

    # Whatever the reason (AI off, unreachable, empty), never go silent.
    return text or _template(snap, minutes, kind)
