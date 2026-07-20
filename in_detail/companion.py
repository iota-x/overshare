"""The two-way half: a Discord bot that listens AND talks.

Incoming (her → your Mac): messages, reactions, and commands become events the
menubar app drains on the main thread.
Outgoing (your Mac → Discord): the app calls reply_text/reply_embed/set_presence,
which are scheduled onto the bot's asyncio loop from any thread.
"""

from __future__ import annotations

import queue
import threading

from . import config

# (kind, payload) events for the app to drain on the main thread.
events: "queue.Queue[tuple[str, object]]" = queue.Queue()

_thread: threading.Thread | None = None
_client = None   # discord.Client, set once connected
_loop = None     # its asyncio event loop
_connected = False
_ever_connected = False


def is_connected() -> bool:
    return _connected


def dropped() -> bool:
    """True only if it connected once and is now down (no startup false alarm)."""
    return _ever_connected and not _connected

_LOVE_PHRASES = ("i love you", "love you", "love u", "ily", "luv u", "luv you")

_HELP_EMBED = {
    "title": "💬 in-detail — what you can do",
    "color": 0x8B5CF6,
    "description": "type any of these in the channel (or just talk to me 💛)",
    "fields": [
        {"name": "👀 check on him", "value": "`!wyd` — what he's doing right now\n`!song` — what he's listening to\n`!recap` — his day so far", "inline": False},
        {"name": "💌 poke him", "value": "`!poke` — poke 👉\n`!miss` — tell him you miss him 🥺\n`!callme` — ask him to call 📞\n`!break` — tell him to rest\n`!food` — remind him to eat 🍜", "inline": False},
        {"name": "🌙 sweet", "value": "`gm` / `gn` — good morning / goodnight\nsay **i love you** → he gets a ❤️\nreact ❤️ to any card → 💛 flashes on his Mac", "inline": False},
        {"name": "📍 where your updates go", "value": "`!dm` — send them to your DMs\n`!channel` (or `!dm off`) — stop DMs, send here instead\n`!both` — both · `!where` — check current", "inline": False},
        {"name": "🎨 style", "value": "`!tone cutesy` · `chill` · `detailed` · `default` — pick how he writes to you", "inline": False},
        {"name": "✍️ just talk", "value": "anything else you type pops up on his screen 💛", "inline": False},
    ],
    "footer": {"text": "in detail · !help"},
}


def enabled() -> bool:
    return bool(config.DISCORD_BOT_TOKEN)


def start() -> None:
    global _thread
    if not enabled() or _thread is not None:
        return
    _thread = threading.Thread(target=_run, daemon=True, name="companion")
    _thread.start()


def _in_channel(channel_id) -> bool:
    if not config.DISCORD_CHANNEL_IDS:
        return True
    return str(channel_id) in config.DISCORD_CHANNEL_IDS


def _is_her(user_id) -> bool:
    if not config.HER_USER_IDS:
        return True
    return str(user_id) in config.HER_USER_IDS


# --- Outgoing (called from the app, any thread) -----------------------------
def _schedule(coro) -> None:
    if _loop is None or _client is None:
        return
    try:
        import asyncio
        asyncio.run_coroutine_threadsafe(coro, _loop)
    except Exception:
        pass


async def _send(channel_id, content=None, embed=None) -> None:
    import discord
    try:
        ch = _client.get_channel(int(channel_id)) or await _client.fetch_channel(int(channel_id))
        e = discord.Embed.from_dict(embed) if embed else None
        await ch.send(content=content or None, embed=e)
    except Exception:
        pass


async def _dm(user_id, content=None, embed=None) -> None:
    import discord
    try:
        user = _client.get_user(int(user_id)) or await _client.fetch_user(int(user_id))
        e = discord.Embed.from_dict(embed) if embed else None
        await user.send(content=content or None, embed=e)
    except Exception:
        pass


async def _presence(label) -> None:
    import discord
    try:
        await _client.change_presence(
            activity=discord.Activity(type=discord.ActivityType.watching, name=label[:120])
        )
    except Exception:
        pass


def reply_text(channel_id, text: str) -> None:
    if channel_id and text:
        _schedule(_send(channel_id, content=text))


def reply_embed(channel_id, embed: dict, content: str = "") -> None:
    if channel_id and embed:
        _schedule(_send(channel_id, content=content or None, embed=embed))


def dm_user(user_id, content: str = "", embed: dict | None = None) -> None:
    if user_id and (content or embed):
        _schedule(_dm(user_id, content or None, embed))


def set_presence(label: str) -> None:
    if label:
        _schedule(_presence(label))


# --- The bot itself (runs in its own thread) --------------------------------
def _register(client, discord) -> None:
    @client.event
    async def on_ready():
        global _connected, _ever_connected
        _connected = True
        _ever_connected = True

    @client.event
    async def on_resumed():
        global _connected
        _connected = True

    @client.event
    async def on_disconnect():
        global _connected
        _connected = False

    @client.event
    async def on_message(msg):
        if msg.author.bot or msg.webhook_id or (client.user and msg.author.id == client.user.id):
            return
        if msg.guild is not None and not _in_channel(msg.channel.id):
            return
        if not _is_her(msg.author.id):
            return
        text = (msg.content or "").strip()
        low = text.lower()
        name = msg.author.display_name
        cid = msg.channel.id

        if low in ("!help", "help", "!commands", "commands"):
            try:
                await msg.channel.send(embed=discord.Embed.from_dict(_HELP_EMBED))
            except Exception:
                pass
            return
        if low in ("!dm", "!dms", "!channel", "!chan", "!both", "!where",
                   "!nodm", "!stopdm") or low.startswith("!dm "):
            from . import settings
            if low in ("!channel", "!chan", "!nodm", "!stopdm", "!dm off", "!dms off"):
                settings.set("card_destination", "channel")
            elif low == "!both":
                settings.set("card_destination", "both")
            elif low in ("!dm", "!dms", "!dm on", "!dms on"):
                settings.set("card_destination", "dm")
            cur = settings.get("card_destination")
            label = {"dm": "your DMs 💌", "channel": "the channel", "both": "both DMs + the channel"}[cur]
            lead = "here's where" if low == "!where" else "done —"
            try:
                await msg.channel.send(f"{lead} i send your updates: **{label}**")
            except Exception:
                pass
            return
        if low.startswith("!tone"):
            from . import settings
            opts = ("default", "cutesy", "chill", "detailed")
            parts = low.split()
            if len(parts) >= 2 and parts[1] in opts:
                settings.set("tone", parts[1])
                reply = f"done — i'll write in a **{parts[1]}** tone 💛"
            else:
                reply = (f"my tone is **{settings.get('tone')}**. "
                         "try `!tone cutesy` · `chill` · `detailed` · `default`")
            try:
                await msg.channel.send(reply)
            except Exception:
                pass
            return
        if low in ("!wyd", "!doing", "!status", "!what"):
            events.put(("cmd_activity", cid))
        elif low in ("!recap", "recap"):
            events.put(("cmd_recap", cid))
        elif low in ("!song", "!music", "!listening", "!np"):
            events.put(("cmd_song", cid))
        elif low in ("!poke", "!wave", "poke"):
            events.put(("poke", name))
        elif low in ("!miss", "!missu"):
            events.put(("miss", name))
        elif low in ("!callme", "!call", "call me"):
            events.put(("callme", name))
        elif low in ("!break",):
            events.put(("break", name))
        elif low in ("!food", "!eat"):
            events.put(("food", name))
        elif low in ("!gm", "gm", "good morning"):
            events.put(("greet", ("gm", name)))
        elif low in ("!gn", "gn", "goodnight", "good night"):
            events.put(("greet", ("gn", name)))
        elif text:
            events.put(("message", (name, text)))

        if any(p in low for p in _LOVE_PHRASES):
            try:
                await msg.add_reaction("❤️")   # auto love-back
            except Exception:
                pass

    @client.event
    async def on_raw_reaction_add(payload):
        if payload.guild_id is not None and not _in_channel(payload.channel_id):
            return
        if not _is_her(payload.user_id):
            return
        events.put(("reaction", str(payload.emoji)))


def _run() -> None:
    global _client, _loop, _connected
    try:
        import asyncio
        import time
        import discord
    except Exception:
        return

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    _loop = loop

    intents = discord.Intents.none()
    intents.guilds = True
    intents.messages = True
    intents.guild_messages = True
    intents.dm_messages = True
    intents.message_content = True       # privileged — enable in the portal
    intents.guild_reactions = True
    intents.dm_reactions = True

    # Supervisor loop: discord.py auto-reconnects internally, but if the whole
    # session dies we recreate a fresh client and reconnect after a short wait.
    while True:
        client = discord.Client(intents=intents)
        _client = client
        _register(client, discord)
        try:
            loop.run_until_complete(client.start(config.DISCORD_BOT_TOKEN))
        except discord.LoginFailure:
            break  # bad token — retrying won't help
        except Exception:
            pass
        _connected = False
        try:
            loop.run_until_complete(client.close())
        except Exception:
            pass
        time.sleep(15)
