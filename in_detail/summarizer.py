"""Turns a raw activity Snapshot into a warm, casual one-liner.

Uses Claude when configured; falls back to a plain template if the API is off,
unkeyed, or unreachable — so the app never goes silent because of the network.
"""

from __future__ import annotations

import random

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
    "You write short, warm, casual status updates that a guy sends to his "
    "girlfriend so she always knows what he's up to on his computer. "
    "Voice: first person, texting-casual, lowercase is fine, affectionate but "
    "not over the top. At most one emoji, often zero. ONE short line only. "
    "No preamble, no quotes, no explanation — output only the message itself. "
    "Be specific using the details given (the video, the file, the channel, "
    "the app). If you're coding, say what file/project. If watching something, "
    "name it. If a game, name the game. If music is playing in the background, "
    "weave it in naturally too (e.g. 'watching X while Y plays 🎧'). "
    "Never invent details you weren't given."
)

_TONES = {
    "cutesy": "Lean extra cute and affectionate — playful, warm, a pet name is "
              "welcome, an emoji or two is fine.",
    "chill": "Keep it super laid-back and minimal — lowercase, casual, few words.",
    "detailed": "Include a little more specific detail about exactly what he's doing.",
}


def _system() -> str:
    from . import settings
    extra = _TONES.get(settings.get("tone"), "")
    return _SYSTEM + ((" " + extra) if extra else "")


def _context_block(snap: Snapshot, minutes: int, kind: str) -> str:
    from . import settings
    lines = [
        f"app: {snap.app}",
        f"category: {snap.category}",
    ]
    mood = settings.get("mood")
    if mood:
        lines.append(f"his current mood/status: {mood}")
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
    if kind == "heartbeat":
        lines.append("note: still doing this — a gentle 'still at it' check-in")
    elif kind == "back":
        lines.append("note: just came back to the desk after being away")
    elif kind == "morning":
        lines.append("note: just started the day at the computer — a warm good-morning to her")
    elif kind == "night":
        lines.append("note: winding down for the night — a soft goodnight to her")
    elif kind == "all_yours":
        lines.append("note: just finished work for the day — tell her you're all hers now, affectionately")
    return "\n".join(lines)


def _template(snap: Snapshot, minutes: int, kind: str) -> str:
    """Plain fallback message — no AI needed."""
    if kind in _MOMENTS:
        return random.choice(_MOMENTS[kind])
    if kind == "back":
        return "back at my desk 👋"

    detail = snap.tab_title or snap.window_title
    where = snap.app
    if snap.category == "browsing" and detail:
        base = f"on {where}: {detail}"
    elif snap.category == "coding" and detail:
        base = f"coding in {where} — {detail}"
    elif detail:
        base = f"on {where} — {detail}"
    else:
        base = f"on {where}"

    if kind == "heartbeat" and minutes >= 1:
        base = f"still {base} (~{minutes} min)"
    if snap.music:
        base = f"{base} 🎧 {snap.music}"
    return base


def _clean(text: str) -> str:
    """Strip quotes / extra lines the model might wrap around the message."""
    text = (text or "").strip().strip('"').strip()
    return text.splitlines()[0] if text else ""


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
            "options": {"temperature": 0.7, "num_predict": num_predict},
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
                 max_tokens: int = 80) -> str:
    """OpenAI-compatible chat — works with Groq, Cerebras, OpenRouter, etc."""
    import requests

    resp = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.7,
            "max_tokens": max_tokens,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return _clean(resp.json()["choices"][0]["message"]["content"])


def _chat_groq(system: str, user: str, max_tokens: int = 80) -> str:
    return _chat_openai(config.GROQ_BASE_URL, config.GROQ_API_KEY, config.GROQ_MODEL,
                        system, user, max_tokens)


def _via_groq(snap: Snapshot, minutes: int, kind: str) -> str:
    return _chat_groq(_system(), _user_prompt(snap, minutes, kind))


_RECAP_SYSTEM = (
    "You write ONE warm, casual sentence for your girlfriend, summarizing how "
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
            text = _chat_groq(_RECAP_SYSTEM, user, max_tokens=120)
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
