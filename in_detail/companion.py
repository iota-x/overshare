"""The two-way half: a Discord bot that listens AND talks.

Incoming (her → your Mac): messages, reactions, and commands become events the
menubar app drains on the main thread.
Outgoing (your Mac → Discord): the app calls reply_text/reply_embed/set_presence,
which are scheduled onto the bot's asyncio loop from any thread.
"""

from __future__ import annotations

import queue
import re
import threading

from . import config

# (kind, payload) events for the app to drain on the main thread.
events: "queue.Queue[tuple[str, object]]" = queue.Queue()

# Open permission requests: her-facing card message_id -> what he asked for. She
# resolves one by reacting ✅/❌ on the card (or `!yes` / `!no` for the latest).
_pending_perms: "dict[int, str]" = {}

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

def _prefix() -> str:
    from . import settings
    return settings.get("prefix") or config.BOT_PREFIX or "!"


def _help_embed(p: str) -> dict:
    return {
        "title": "💬 overshare — what you can do",
        "color": 0x8B5CF6,
        "description": f"type these in the channel · prefix is `{p}` (change it with `{p}prefix >`)",
        "fields": [
            {"name": "👀 check on him", "value": f"`{p}wyd` — what he's doing now\n`{p}song` — what he's listening to\n`{p}recap` — his day so far", "inline": False},
            {"name": "📸 see him", "value": f"`{p}peek` — a webcam photo 🤳\n`{p}screen` — his screen right now 🖥️\n`{p}live` — live-ish view (📷 or `{p}live screen`)", "inline": False},
            {"name": "💌 poke him", "value": f"`{p}poke` 👉 · `{p}miss` 🥺 · `{p}callme` 📞 · `{p}break` · `{p}food` 🍜", "inline": False},
            {"name": "🔊 reach him", "value": f"`{p}say <text>` — speak it aloud on his Mac\n`{p}remind 30m <text>` — nudge him later (s/m/h)", "inline": False},
            {"name": "🙏 permission", "value": f"when he asks to do something, a card pops up — react ✅ / ❌ on it, or `{p}yes` / `{p}no`", "inline": False},
            {"name": "🌙 sweet", "value": f"`{p}gm` / `{p}gn` — good morning / goodnight\nsay **i love you** → he gets a ❤️\nreact ❤️ to any card → 💛 flashes on his Mac", "inline": False},
            {"name": "📍 where your updates go", "value": f"`{p}dm` — your DMs\n`{p}channel` (or `{p}dm off`) — here instead\n`{p}both` · `{p}where` — check", "inline": False},
            {"name": "🎨 style", "value": f"`{p}tone cutesy` · `chill` · `detailed` · `default`", "inline": False},
            {"name": "✍️ just talk", "value": "anything else you type pops up on his screen 💛", "inline": False},
        ],
        "footer": {"text": f"overshare · {p}help"},
    }


def _parse_duration(tok: str) -> int | None:
    """'30m' '1h' '45s' '1h30m' '90'(=minutes) -> seconds, capped at 24h."""
    tok = (tok or "").strip().lower()
    if not tok:
        return None
    if tok.isdigit():
        secs = int(tok) * 60
    else:
        m = re.fullmatch(r"(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?", tok)
        if not m or not any(m.groups()):
            return None
        h, mi, s = (int(x) if x else 0 for x in m.groups())
        secs = h * 3600 + mi * 60 + s
    return min(secs, 24 * 3600) if secs > 0 else None


def _fmt_duration(secs: int) -> str:
    h, r = divmod(secs, 3600)
    mi, s = divmod(r, 60)
    parts = [f"{h}h" for _ in (1,) if h] + [f"{mi}m" for _ in (1,) if mi] + [f"{s}s" for _ in (1,) if s]
    return " ".join(parts) or "0s"


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


async def _send_file(channel_id, path, content=None, filename=None) -> None:
    import os
    import discord
    try:
        ch = _client.get_channel(int(channel_id)) or await _client.fetch_channel(int(channel_id))
        await ch.send(content=content or None,
                      file=discord.File(path, filename=filename or os.path.basename(path)))
    finally:
        try:
            os.remove(path)
        except Exception:
            pass


async def _live_feed(channel_id, source, seconds, interval) -> None:
    """Post one message and keep swapping its image — feels like a live view.

    `source` is a zero-arg callable returning a fresh file path (or None). It's
    run in a thread so the capture subprocess never blocks the bot's loop.
    """
    import os
    import asyncio
    import discord
    loop = asyncio.get_event_loop()

    async def grab():
        return await loop.run_in_executor(None, source)

    def cleanup(p):
        if p:
            try:
                os.remove(p)
            except Exception:
                pass

    first = await grab()
    if not first:
        try:
            ch = _client.get_channel(int(channel_id)) or await _client.fetch_channel(int(channel_id))
            await ch.send("couldn’t open the feed 😔 (permission or camera busy)")
        except Exception:
            pass
        return
    try:
        ch = _client.get_channel(int(channel_id)) or await _client.fetch_channel(int(channel_id))
        msg = await ch.send(content="🔴 live · updating…",
                            file=discord.File(first, filename="live.jpg"))
    except Exception:
        cleanup(first)
        return
    cleanup(first)

    deadline = loop.time() + seconds
    while loop.time() < deadline:
        await asyncio.sleep(interval)
        frame = await grab()
        if not frame:
            continue
        try:
            await msg.edit(content="🔴 live · updating…",
                           attachments=[discord.File(frame, filename="live.jpg")])
        except Exception:
            pass
        cleanup(frame)
    try:
        await msg.edit(content="⚫ live ended")
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


async def _ask_permission(channel_id, text: str) -> None:
    """Post a request card she can approve/deny, and remember it for matching."""
    import discord
    try:
        ch = _client.get_channel(int(channel_id)) or await _client.fetch_channel(int(channel_id))
        embed = discord.Embed.from_dict({
            "title": "🙏 permission request",
            "description": (f"he's asking:\n\n**{text}**\n\n"
                            f"react ✅ to allow · ❌ to say no  ·  or `{_prefix()}yes` / `{_prefix()}no`"),
            "color": 0xF5A9C0,
        })
        msg = await ch.send(embed=embed)
        _pending_perms[msg.id] = text
        for e in ("✅", "❌"):
            try:
                await msg.add_reaction(e)
            except Exception:
                pass
    except Exception:
        pass


def ask_permission(channel_id, text: str) -> None:
    """He asks her for permission to do something (from the menu bar)."""
    if channel_id and text:
        _schedule(_ask_permission(channel_id, text))


def _pop_latest_perm() -> "str | None":
    """The most recent unresolved request, for `!yes` / `!no`."""
    if not _pending_perms:
        return None
    mid = next(reversed(_pending_perms))
    return _pending_perms.pop(mid)


def reply_file(channel_id, path: str, content: str = "", filename: str = "") -> None:
    if channel_id and path:
        _schedule(_send_file(channel_id, path, content or None, filename or None))


def live_feed(channel_id, source, seconds: int = 20, interval: float = 2.5) -> None:
    """`source` is a zero-arg callable returning a fresh file path (or None)."""
    if channel_id and callable(source):
        _schedule(_live_feed(channel_id, source, seconds, interval))


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
        prefix = _prefix()

        # Not a command → normal message: notify him, and love-react.
        if not low.startswith(prefix):
            if text:
                events.put(("message", (name, text)))
            if any(p in low for p in _LOVE_PHRASES):
                try:
                    await msg.add_reaction("❤️")
                except Exception:
                    pass
            return

        cmd = low[len(prefix):].strip()          # command, prefix stripped
        raw = text[len(prefix):].strip()         # same, original case

        async def say(s):
            try:
                await msg.channel.send(s)
            except Exception:
                pass

        if cmd in ("help", "commands", "cmds", ""):
            try:
                await msg.channel.send(embed=discord.Embed.from_dict(_help_embed(prefix)))
            except Exception:
                pass
        elif cmd.startswith("prefix"):
            from . import settings
            parts = raw.split()
            if len(parts) >= 2:
                newp = parts[1]
                settings.set("prefix", newp)
                await say(f"done — my prefix is now `{newp}` · try `{newp}help` 💛")
            else:
                await say(f"my prefix is `{prefix}`. change it with `{prefix}prefix >` (any symbol)")
        elif (cmd in ("dm", "dms", "channel", "chan", "both", "where", "nodm", "stopdm")
              or cmd.startswith("dm ") or cmd.startswith("dms ")):
            from . import settings
            if cmd in ("channel", "chan", "nodm", "stopdm", "dm off", "dms off"):
                settings.set("card_destination", "channel")
            elif cmd == "both":
                settings.set("card_destination", "both")
            elif cmd in ("dm", "dms", "dm on", "dms on"):
                settings.set("card_destination", "dm")
            cur = settings.get("card_destination")
            label = {"dm": "your DMs 💌", "channel": "the channel", "both": "both DMs + the channel"}[cur]
            await say(f"{'here’s where' if cmd == 'where' else 'done —'} i send your updates: **{label}**")
        elif cmd.startswith("tone"):
            from . import settings
            opts = ("default", "cutesy", "chill", "detailed")
            parts = cmd.split()
            if len(parts) >= 2 and parts[1] in opts:
                settings.set("tone", parts[1])
                await say(f"done — i'll write in a **{parts[1]}** tone 💛")
            else:
                await say(f"my tone is **{settings.get('tone')}**. "
                          f"try `{prefix}tone cutesy` · `chill` · `detailed` · `default`")
        elif cmd in ("wyd", "doing", "status", "what"):
            events.put(("cmd_activity", cid))
        elif cmd == "recap":
            events.put(("cmd_recap", cid))
        elif cmd in ("song", "music", "listening", "np"):
            events.put(("cmd_song", cid))
        elif cmd in ("peek", "cam", "camera", "see", "selfie"):
            events.put(("cmd_peek", cid))
        elif cmd in ("screen", "screenshot", "ss", "desktop"):
            events.put(("cmd_screen", cid))
        elif cmd == "live" or cmd.startswith("live") or cmd in ("livecam", "livescreen"):
            src = "screen" if ("screen" in cmd) else "cam"
            events.put(("cmd_live", (cid, src)))
        elif cmd in ("poke", "wave"):
            events.put(("poke", name))
        elif cmd in ("miss", "missu"):
            events.put(("miss", name))
        elif cmd in ("callme", "call", "call me"):
            events.put(("callme", name))
        elif cmd == "break":
            events.put(("break", name))
        elif cmd in ("food", "eat"):
            events.put(("food", name))
        elif cmd in ("gm", "morning", "good morning"):
            events.put(("greet", ("gm", name)))
        elif cmd in ("gn", "night", "goodnight", "good night"):
            events.put(("greet", ("gn", name)))
        elif cmd.startswith("say"):
            bits = raw.split(None, 1)
            spoken = bits[1].strip() if len(bits) > 1 else ""
            if spoken:
                events.put(("say", (cid, spoken)))
                await say("🔊 saying that out loud on his mac 💛")
            else:
                await say(f"say what? try `{prefix}say i love you` 💛")
        elif cmd.startswith("remind"):
            bits = raw.split(None, 2)  # ['remind', '<when>', '<message>']
            secs = _parse_duration(bits[1]) if len(bits) >= 2 else None
            message = bits[2].strip() if len(bits) >= 3 else ""
            if secs and message:
                events.put(("remind", (cid, secs, message)))
                await say(f"⏰ okay — i'll nudge him in {_fmt_duration(secs)}: “{message}” 💛")
            else:
                await say(f"try `{prefix}remind 30m drink water` (use s/m/h) 💛")
        elif cmd in ("yes", "allow", "y", "approve"):
            asked = _pop_latest_perm()
            if asked:
                events.put(("permission_result", (True, asked)))
                await say(f"✅ okay — told him yes to “{asked}” 💛")
            else:
                await say("nothing pending to approve rn 🤍")
        elif cmd in ("no", "deny", "n", "nope"):
            asked = _pop_latest_perm()
            if asked:
                events.put(("permission_result", (False, asked)))
                await say(f"❌ okay — told him no to “{asked}”")
            else:
                await say("nothing pending to say no to 🤍")
        # unknown command → silently ignore

    @client.event
    async def on_raw_reaction_add(payload):
        if payload.guild_id is not None and not _in_channel(payload.channel_id):
            return
        if not _is_her(payload.user_id):
            return
        emoji = str(payload.emoji)
        # ✅/❌ on a pending request card resolves that request (not a love-react).
        if payload.message_id in _pending_perms and emoji in ("✅", "❌"):
            asked = _pending_perms.pop(payload.message_id)
            events.put(("permission_result", (emoji == "✅", asked)))
            return
        events.put(("reaction", emoji))


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
