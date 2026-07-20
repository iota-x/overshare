"""Configuration — loaded from environment / a local .env file.

Nothing secret is hard-coded here. Copy .env.example to .env and fill it in.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env sitting next to the project root (in-detail/.env)
_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_PATH)


def _get_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _get_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


# --- Delivery ---------------------------------------------------------------
# The Discord webhook she'll receive updates through.
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
# Display name / avatar the webhook posts as.
WEBHOOK_USERNAME = os.environ.get("WEBHOOK_USERNAME", "in detail 💬")
WEBHOOK_AVATAR_URL = os.environ.get("WEBHOOK_AVATAR_URL", "").strip()

# --- Two-way (optional Discord bot) -----------------------------------------
# A bot token lets her replies + reactions reach your Mac as notifications.
# Leave blank to stay send-only. Setup steps are in the README.
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
# Restrict listening to specific channel(s) — comma-separated IDs. Best to set
# this to the channel your update cards post to (so her reactions are caught).
# Blank = listen everywhere the bot can see.
DISCORD_CHANNEL_ID = os.environ.get("DISCORD_CHANNEL_ID", "").strip()
DISCORD_CHANNEL_IDS = {c.strip() for c in DISCORD_CHANNEL_ID.split(",") if c.strip()}
# Where the bot posts outbound messages (quick-reply, good-morning). Defaults to
# the first channel above — set this to your main chat channel.
DISCORD_HOME_CHANNEL_ID = os.environ.get("DISCORD_HOME_CHANNEL_ID", "").strip()
if not DISCORD_HOME_CHANNEL_ID and DISCORD_CHANNEL_ID:
    DISCORD_HOME_CHANNEL_ID = DISCORD_CHANNEL_ID.split(",")[0].strip()

# Only react to HER (so other server members — or your own actions — don't
# trigger anything). Comma-separated to allow more than one (e.g. add your own
# id for testing). Blank = respond to anyone in the listened channels.
HER_USER_ID = os.environ.get("HER_USER_ID", "").strip()
HER_USER_IDS = {u.strip() for u in HER_USER_ID.split(",") if u.strip()}
# The one to DM the cards to (first id above), when she picks DM delivery.
HER_PRIMARY_ID = HER_USER_ID.split(",")[0].strip() if HER_USER_ID else ""

# Scheduled "good morning <her>" to the channel (even while you sleep).
GM_ENABLED = _get_bool("GM_ENABLED", True)
GM_TIME = os.environ.get("GM_TIME", "08:30").strip()  # HH:MM local
HER_NAME = os.environ.get("HER_NAME", "").strip()     # for the good-morning line

# --- AI ---------------------------------------------------------------------
# Set AI_ENABLED=false to fall back to plain templated messages (no AI at all).
AI_ENABLED = _get_bool("AI_ENABLED", True)

# Which brain writes the one-liners:
#   "ollama"    -> FREE, runs a small model locally on your Mac (install Ollama)
#   "anthropic" -> Claude (best writing, costs money — needs an API key)
AI_PROVIDER = os.environ.get("AI_PROVIDER", "ollama").strip().lower()

# --- Anthropic (only used if AI_PROVIDER=anthropic) ---
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
#   claude-opus-4-8   -> best writing, ~5x pricier for an always-on tool
#   claude-haiku-4-5  -> plenty good for one-liners, far cheaper
AI_MODEL = os.environ.get("AI_MODEL", "claude-opus-4-8")

# --- Ollama (only used if AI_PROVIDER=ollama) — free & local ---
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
# A small, fast model is plenty for one-liners. Pull it first: `ollama pull llama3.2`
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")

# --- Groq (only if AI_PROVIDER=groq) — FREE cloud, nothing runs on your Mac ---
# Get a free key at https://console.groq.com. OpenAI-compatible, so GROQ_BASE_URL
# can also point at Cerebras / OpenRouter / any compatible free host.
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_BASE_URL = os.environ.get("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")


def active_provider() -> str:
    """Which AI backend is in effect: 'ollama' | 'groq' | 'anthropic' | 'none'."""
    if not AI_ENABLED:
        return "none"
    if AI_PROVIDER in {"ollama", "groq", "anthropic"}:
        return AI_PROVIDER
    return "none"

# --- Timing (all seconds) ---------------------------------------------------
# How often we look at what you're doing (lower = snappier tab-switch updates).
POLL_INTERVAL = _get_float("POLL_INTERVAL", 2.0)
# A new activity must persist this long before we announce it — just enough to
# skip quick flick-throughs, but still feels near-instant when you land on a tab.
STABILIZE = _get_float("STABILIZE", 2.0)
# Light throttle so a burst of switches doesn't flood; genuine switches still
# update within a few seconds.
MIN_GAP = _get_float("MIN_GAP", 4.0)
# Heartbeat: if you stay on the same thing, re-send with the running time
# ("still on X, ~12 min") every so often.
HEARTBEAT = _get_float("HEARTBEAT", 300.0)  # 5 min
# Consider you "away" after this much no keyboard/mouse activity.
IDLE_THRESHOLD = _get_float("IDLE_THRESHOLD", 300.0)  # 5 min

# --- Daily recap ------------------------------------------------------------
# An end-of-day summary card: total active time, where it went, what you
# watched, the soundtrack.
RECAP_ENABLED = _get_bool("RECAP_ENABLED", True)
RECAP_TIME = os.environ.get("RECAP_TIME", "23:00").strip()  # HH:MM, local
RECAP_MIN_MINUTES = _get_float("RECAP_MIN_MINUTES", 5.0)     # skip near-empty days

# --- Weekly "Wrapped" --------------------------------------------------------
WEEKLY_ENABLED = _get_bool("WEEKLY_ENABLED", True)
WEEKLY_DAY = os.environ.get("WEEKLY_DAY", "sun").strip().lower()  # weekday name
WEEKLY_TIME = os.environ.get("WEEKLY_TIME", "20:00").strip()      # HH:MM, local

# --- Sweet bookends ----------------------------------------------------------
# A gap this long before returning reads as "just woke up" (good-morning).
LONG_AWAY_SECONDS = _get_float("LONG_AWAY_SECONDS", 4 * 3600)

# Where the per-day tallies are stored.
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# --- Behaviour --------------------------------------------------------------
# Also report what's playing in the background (Spotify / Apple Music), so a
# message can be "watching X while Y plays". A song change counts as an update.
REPORT_MEDIA = _get_bool("REPORT_MEDIA", True)

# Start paused (menubar shows 😴 until you un-pause).
START_PAUSED = _get_bool("START_PAUSED", False)


def missing_requirements() -> list[str]:
    """Return a list of human-readable problems that would stop us working."""
    problems: list[str] = []
    if not DISCORD_WEBHOOK_URL:
        problems.append("DISCORD_WEBHOOK_URL is not set (she won't get anything)")
    if active_provider() == "anthropic" and not ANTHROPIC_API_KEY:
        problems.append(
            "AI_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set "
            "(add the key, switch to AI_PROVIDER=ollama, or AI_ENABLED=false)"
        )
    if active_provider() == "groq" and not GROQ_API_KEY:
        problems.append(
            "AI_PROVIDER=groq but GROQ_API_KEY is not set "
            "(get a free key at console.groq.com)"
        )
    return problems
