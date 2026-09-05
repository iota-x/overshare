"""Configuration — a JSON overlay written by the settings app, layered over .env.

Three sources, highest priority first:

  1. ``<data>/config.json``  — what the settings GUI writes. Typed (real bools
     and floats), and the only thing the GUI ever touches.
  2. ``.env`` / the environment — how this app was configured before there was
     a GUI. Still fully supported, so an existing checkout keeps working.
  3. The defaults spelled out below.

Every consumer reads these as attributes (``config.POLL_INTERVAL``), never via
``from .config import POLL_INTERVAL`` — which is what lets :func:`reload` swap
the whole module's values at runtime and have the running app pick them up on
its next poll. Keep it that way.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


# --- Where user data lives ---------------------------------------------------
# Running from a source checkout we keep the repo's data/ folder (so a dev's
# history and settings survive). Frozen into an .app/.exe, the bundle is the
# wrong place to write — go to the OS's per-user application data directory.
def _default_data_dir() -> Path:
    if getattr(sys, "frozen", False):
        if sys.platform == "darwin":
            return Path.home() / "Library" / "Application Support" / "Overshare"
        if sys.platform.startswith("win"):
            base = os.environ.get("APPDATA") or str(Path.home())
            return Path(base) / "Overshare"
        return Path.home() / ".overshare"
    return Path(__file__).resolve().parent.parent / "data"


DATA_DIR = _default_data_dir()

# The overlay the settings GUI writes. Lives beside the day tallies so backing
# up one folder keeps everything.
CONFIG_PATH = DATA_DIR / "config.json"

_overlay: dict = {}


def _load_overlay() -> None:
    global _overlay
    try:
        loaded = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        _overlay = loaded if isinstance(loaded, dict) else {}
    except Exception:
        _overlay = {}


def _load_env() -> None:
    """Load .env from the checkout, and (when frozen) from the data dir too."""
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
    if getattr(sys, "frozen", False):
        load_dotenv(DATA_DIR / ".env")


# --- Typed lookups across overlay → env → default ----------------------------
# The overlay holds real types; the environment only ever holds strings. Each
# helper accepts both, so a value reads the same whichever layer supplied it.
def _get_str(name: str, default: str = "", *, was: str = "") -> str:
    """`was` is the key's previous name, still honoured so an existing .env or
    config.json written before a rename keeps working."""
    val = _overlay.get(name)
    if val is None and was:
        val = _overlay.get(was)
    if val is None:
        val = os.environ.get(name)
    if val is None and was:
        val = os.environ.get(was)
    if val is None:
        val = default
    return str(val).strip()


def _get_float(name: str, default: float) -> float:
    val = _overlay.get(name)
    if val is None:
        val = os.environ.get(name, default)
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _get_int(name: str, default: int) -> int:
    return int(_get_float(name, default))


def _get_bool(name: str, default: bool) -> bool:
    val = _overlay.get(name)
    if isinstance(val, bool):
        return val
    if val is None:
        val = os.environ.get(name)
    if val is None:
        return default
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


def _apply() -> None:
    """(Re)compute every setting from the current overlay + environment."""
    g = globals()

    # --- Delivery ------------------------------------------------------------
    # Cards go to every destination that's switched on *and* filled in, so more
    # than one can run at once — see overshare/channels/.
    g["DISCORD_ENABLED"] = _get_bool("DISCORD_ENABLED", True)
    g["TELEGRAM_ENABLED"] = _get_bool("TELEGRAM_ENABLED", True)

    # Telegram: talk to @BotFather for a token, and the chat id is whichever
    # conversation the bot should post into.
    g["TELEGRAM_BOT_TOKEN"] = _get_str("TELEGRAM_BOT_TOKEN")
    g["TELEGRAM_CHAT_ID"] = _get_str("TELEGRAM_CHAT_ID")

    # The Discord webhook your partner receives updates through.
    g["DISCORD_WEBHOOK_URL"] = _get_str("DISCORD_WEBHOOK_URL")
    # Display name / avatar the webhook posts as.
    g["WEBHOOK_USERNAME"] = _get_str("WEBHOOK_USERNAME", "in detail 💬")
    g["WEBHOOK_AVATAR_URL"] = _get_str("WEBHOOK_AVATAR_URL")

    # --- Two-way (optional Discord bot) --------------------------------------
    # A bot token lets their replies + reactions reach your machine as
    # notifications. Leave blank to stay send-only.
    g["DISCORD_BOT_TOKEN"] = _get_str("DISCORD_BOT_TOKEN")
    # Command prefix for the bot (they can also change it live with "<prefix>prefix >").
    g["BOT_PREFIX"] = _get_str("BOT_PREFIX", "!")
    # Restrict listening to specific channel(s) — comma-separated IDs. Best set
    # to the channel your update cards post to (so their reactions are caught).
    # Blank = listen everywhere the bot can see.
    channel_id = _get_str("DISCORD_CHANNEL_ID")
    g["DISCORD_CHANNEL_ID"] = channel_id
    g["DISCORD_CHANNEL_IDS"] = {c.strip() for c in channel_id.split(",") if c.strip()}
    # Where the bot posts outbound messages (quick-reply, good-morning).
    # Defaults to the first channel above.
    home = _get_str("DISCORD_HOME_CHANNEL_ID")
    if not home and channel_id:
        home = channel_id.split(",")[0].strip()
    g["DISCORD_HOME_CHANNEL_ID"] = home

    # Only react to your partner (so other server members — or your own actions — don't
    # trigger anything). Comma-separated to allow more than one.
    # Named HER_* until v1.3.3. The old names are still read, so nobody's .env
    # or config.json breaks over a wording change.
    ids = _get_str("PARTNER_USER_ID", was="HER_USER_ID")
    g["PARTNER_USER_ID"] = ids
    g["PARTNER_USER_IDS"] = {u.strip() for u in ids.split(",") if u.strip()}
    # The one to DM the cards to (first id above), when they pick DM delivery.
    g["PARTNER_PRIMARY_ID"] = ids.split(",")[0].strip() if ids else ""

    # Scheduled "good morning <name>" to the channel (even while you sleep).
    g["GM_ENABLED"] = _get_bool("GM_ENABLED", True)
    g["GM_TIME"] = _get_str("GM_TIME", "08:30")   # HH:MM local
    g["PARTNER_NAME"] = _get_str("PARTNER_NAME", was="HER_NAME")   # good-morning line

    # --- Peek (camera / screen on demand) ------------------------------------
    # Let them grab a webcam photo (`!peek`), a screenshot (`!screen`), or a
    # live-ish view (`!live`). Set false to disable all of it.
    g["PEEK_ENABLED"] = _get_bool("PEEK_ENABLED", True)
    # Notify you every time they peek, so it's never silent.
    g["PEEK_NOTIFY"] = _get_bool("PEEK_NOTIFY", True)
    # Live-view (`!live`) burst length and how often the frame refreshes.
    g["LIVE_SECONDS"] = _get_int("LIVE_SECONDS", 20)
    g["LIVE_INTERVAL"] = _get_float("LIVE_INTERVAL", 2.5)

    # --- AI ------------------------------------------------------------------
    # Set AI_ENABLED=false to fall back to plain templated messages.
    g["AI_ENABLED"] = _get_bool("AI_ENABLED", True)
    #   "groq"      -> FREE cloud, nothing runs locally
    #   "ollama"    -> FREE, runs a small model on your own machine
    #   "anthropic" -> Claude (best writing, costs money — needs an API key)
    g["AI_PROVIDER"] = _get_str("AI_PROVIDER", "ollama").lower()

    g["ANTHROPIC_API_KEY"] = _get_str("ANTHROPIC_API_KEY")
    g["AI_MODEL"] = _get_str("AI_MODEL", "claude-opus-4-8")

    g["OLLAMA_HOST"] = _get_str("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    g["OLLAMA_MODEL"] = _get_str("OLLAMA_MODEL", "llama3.2")

    g["GROQ_API_KEY"] = _get_str("GROQ_API_KEY")
    g["GROQ_MODEL"] = _get_str("GROQ_MODEL", "openai/gpt-oss-20b")
    g["GROQ_BASE_URL"] = _get_str(
        "GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")

    # --- Windows: read the browser's address bar via UI Automation -----------
    # It's the only way to get per-site cards, links and YouTube thumbnails
    # there — but it's slow, so this can be turned off.
    g["READ_BROWSER_URL"] = _get_bool("READ_BROWSER_URL", True)

    # --- Timing (all seconds) ------------------------------------------------
    # How often we look at what you're doing.
    g["POLL_INTERVAL"] = _get_float("POLL_INTERVAL", 2.0)
    # A new activity must persist this long before we announce it.
    g["STABILIZE"] = _get_float("STABILIZE", 2.0)
    # Light throttle so a burst of switches doesn't flood.
    g["MIN_GAP"] = _get_float("MIN_GAP", 4.0)
    # Heartbeat: re-send with the running time if you stay on the same thing.
    g["HEARTBEAT"] = _get_float("HEARTBEAT", 300.0)
    # Consider you "away" after this much no keyboard/mouse activity.
    g["IDLE_THRESHOLD"] = _get_float("IDLE_THRESHOLD", 300.0)
    # Dwell: when you stay on the *same* post/page/reel this long, send a "still
    # lingering on this" nudge with the link — a stronger signal than the plain
    # heartbeat, and only for something worth lingering on (a thing with a URL),
    # never "still in your editor". Fires once per thing. Kept under HEARTBEAT so
    # it lands first; a longer value means only real lingering trips it.
    g["DWELL_ENABLED"] = _get_bool("DWELL_ENABLED", True)
    g["DWELL_SECONDS"] = _get_float("DWELL_SECONDS", 180.0)

    # --- Daily recap ---------------------------------------------------------
    g["RECAP_ENABLED"] = _get_bool("RECAP_ENABLED", True)
    g["RECAP_TIME"] = _get_str("RECAP_TIME", "23:00")           # HH:MM, local
    g["RECAP_MIN_MINUTES"] = _get_float("RECAP_MIN_MINUTES", 5.0)

    # --- Weekly "Wrapped" ----------------------------------------------------
    g["WEEKLY_ENABLED"] = _get_bool("WEEKLY_ENABLED", True)
    g["WEEKLY_DAY"] = _get_str("WEEKLY_DAY", "sun").lower()     # weekday name
    g["WEEKLY_TIME"] = _get_str("WEEKLY_TIME", "20:00")         # HH:MM, local

    # --- Sweet bookends ------------------------------------------------------
    # A gap this long before returning reads as "just woke up".
    g["LONG_AWAY_SECONDS"] = _get_float("LONG_AWAY_SECONDS", 4 * 3600)

    # --- Privacy blocklist ---------------------------------------------------
    # What never gets broadcast, however much else does. On by default: this
    # app reads your screen, and a password manager showing up in someone
    # else's chat is not a thing anyone should have to opt out of.
    g["PRIVACY_ENABLED"] = _get_bool("PRIVACY_ENABLED", True)
    # Built-in categories. These are switches rather than lists you have to
    # type, because the common cases shouldn't depend on anyone thinking of
    # them — the lists in privacy.py hold what each one covers.
    g["PRIVACY_HIDE_INCOGNITO"] = _get_bool("PRIVACY_HIDE_INCOGNITO", True)
    g["PRIVACY_HIDE_PASSWORDS"] = _get_bool("PRIVACY_HIDE_PASSWORDS", True)
    g["PRIVACY_HIDE_FINANCE"] = _get_bool("PRIVACY_HIDE_FINANCE", True)

    # Anything the categories above miss. All comma-separated and matched
    # case-insensitively: apps against name and bundle id / exe, sites against
    # the address, words against titles and the address.
    g["PRIVACY_APPS"] = _get_str("PRIVACY_APPS", "")
    g["PRIVACY_SITES"] = _get_str("PRIVACY_SITES", "")
    g["PRIVACY_WORDS"] = _get_str("PRIVACY_WORDS", "")
    # What they see instead.
    g["PRIVACY_LABEL"] = _get_str("PRIVACY_LABEL", "something private 🔒")

    # --- Appearance ----------------------------------------------------------
    # Settings-window theme: "system" follows the OS, or force "light"/"dark".
    g["UI_THEME"] = _get_str("UI_THEME", "system").lower()

    # --- Behaviour -----------------------------------------------------------
    # Also report background music, so a message can be "watching X while Y plays".
    # The difference between "on Notion" and "on Notion — Q3 planning". Titles
    # are where nearly all the texture lives: the Discord channel, the document
    # you have open, the video you're watching. On by default because without it
    # the messages read like a process list.
    g["REPORT_TITLES"] = _get_bool("REPORT_TITLES", True)
    g["REPORT_MEDIA"] = _get_bool("REPORT_MEDIA", True)
    # Start paused (menubar shows 😴 until you un-pause).
    g["START_PAUSED"] = _get_bool("START_PAUSED", False)


def reload() -> None:
    """Re-read .env and the overlay, and republish every value.

    The running app calls this when it notices config.json changed on disk, so
    edits made in the settings window take effect without a restart.
    """
    _load_env()
    _load_overlay()
    _apply()


def save(values: dict) -> None:
    """Merge `values` into the overlay, persist it, and apply immediately."""
    _load_overlay()
    merged = {**_overlay, **values}
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    tmp.replace(CONFIG_PATH)  # atomic, so a reader never sees a half-written file
    reload()


def overlay() -> dict:
    """The raw overlay dict — what the GUI has explicitly set."""
    _load_overlay()
    return dict(_overlay)


def config_mtime() -> float:
    """Modification time of the overlay, or 0.0 if it doesn't exist yet."""
    try:
        return CONFIG_PATH.stat().st_mtime
    except OSError:
        return 0.0


def is_configured() -> bool:
    """Has this install been set up at all? Drives the first-run experience."""
    return bool(DISCORD_WEBHOOK_URL)


def active_provider() -> str:
    """Which AI backend is in effect: 'ollama' | 'groq' | 'anthropic' | 'none'."""
    if not AI_ENABLED:
        return "none"
    if AI_PROVIDER in {"ollama", "groq", "anthropic"}:
        return AI_PROVIDER
    return "none"


def missing_requirements() -> list[str]:
    """Return a list of human-readable problems that would stop us working."""
    problems: list[str] = []
    if not DISCORD_WEBHOOK_URL:
        problems.append("DISCORD_WEBHOOK_URL is not set (nothing can be sent)")
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


reload()
