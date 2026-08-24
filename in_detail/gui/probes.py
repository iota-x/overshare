"""Connection checks — "is this key actually good?", answered off the UI thread.

Every probe is cheap and read-only (the one exception is
:func:`send_test_message`, which posts on purpose). Where a provider can list
its models we return them too, so the model picker is populated from the live
account instead of a hardcoded list that quietly goes stale.

Run one with :class:`Prober`, which hands the result back on the UI thread.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

import requests
from PySide6.QtCore import QObject, Signal

_TIMEOUT = 8


@dataclass
class Result:
    ok: bool
    message: str
    # Selectable values discovered during the probe (model ids, etc).
    options: list[str] = field(default_factory=list)
    # Anything extra worth showing — e.g. the channel a webhook posts to.
    detail: dict = field(default_factory=dict)


# --- Discord ------------------------------------------------------------------
def check_webhook(url: str) -> Result:
    """GET the webhook: validates it and names its channel, without posting."""
    url = (url or "").strip()
    if not url:
        return Result(False, "No webhook link yet")
    if "discord.com/api/webhooks/" not in url:
        return Result(False, "That doesn't look like a Discord webhook link")
    try:
        r = requests.get(url, timeout=_TIMEOUT)
    except requests.RequestException as e:
        return Result(False, f"Couldn't reach Discord ({e.__class__.__name__})")
    if r.status_code == 404:
        return Result(False, "Discord doesn't recognise this webhook — it may be deleted")
    if r.status_code == 401:
        return Result(False, "That webhook link isn't valid")
    if r.status_code != 200:
        return Result(False, f"Discord said {r.status_code}")
    try:
        data = r.json()
    except ValueError:
        return Result(False, "Discord sent back something unreadable")
    name = data.get("name") or "webhook"
    return Result(
        True,
        f"Connected as “{name}”",
        detail={"channel_id": str(data.get("channel_id") or ""),
                "guild_id": str(data.get("guild_id") or "")},
    )


def send_telegram_test(token: str, chat_id: str) -> Result:
    """Actually post, so you can confirm it lands in the right chat."""
    token, chat_id = (token or "").strip(), (chat_id or "").strip()
    if not (token and chat_id):
        return Result(False, "Add the bot token and chat first")
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id,
                  "text": "💌 test from Overshare — if you can see this, you're all set."},
            timeout=_TIMEOUT)
    except requests.RequestException as e:
        return Result(False, f"Couldn't reach Telegram ({e.__class__.__name__})")
    if r.status_code == 200:
        return Result(True, "Sent — go check Telegram")
    return Result(False, f"Telegram said {r.status_code}")


def send_test_message(url: str, username: str = "") -> Result:
    """Actually post, so you can confirm it lands where you expect."""
    url = (url or "").strip()
    if not url:
        return Result(False, "No webhook link yet")
    payload = {"content": "💌 test from Overshare — if you can see this, you're all set."}
    if username:
        payload["username"] = username
    try:
        r = requests.post(url, json=payload, timeout=_TIMEOUT)
    except requests.RequestException as e:
        return Result(False, f"Couldn't reach Discord ({e.__class__.__name__})")
    if r.status_code in (200, 204):
        return Result(True, "Sent — go check the channel")
    if r.status_code == 429:
        return Result(False, "Discord is rate-limiting; try again in a moment")
    return Result(False, f"Discord said {r.status_code}")


def check_telegram(token: str, chat_id: str) -> Result:
    """Validate the bot, and that it can actually reach that chat."""
    token, chat_id = (token or "").strip(), (chat_id or "").strip()
    if not token:
        return Result(False, "No bot token yet — get one from @BotFather")
    try:
        me = requests.get(f"https://api.telegram.org/bot{token}/getMe", timeout=_TIMEOUT)
    except requests.RequestException as e:
        return Result(False, f"Couldn't reach Telegram ({e.__class__.__name__})")
    if me.status_code in (401, 404):
        return Result(False, "Telegram rejected that bot token")
    if me.status_code != 200:
        return Result(False, f"Telegram said {me.status_code}")
    name = (me.json().get("result") or {}).get("username", "the bot")

    if not chat_id:
        return Result(
            False,
            f"@{name} works — now send it a message and press “Find my chat”")
    try:
        chat = requests.get(f"https://api.telegram.org/bot{token}/getChat",
                            params={"chat_id": chat_id}, timeout=_TIMEOUT)
    except requests.RequestException as e:
        return Result(False, f"Couldn't reach Telegram ({e.__class__.__name__})")
    if chat.status_code != 200:
        return Result(False, "That chat id isn't one this bot can post to")
    info = chat.json().get("result") or {}
    who = info.get("title") or info.get("username") or info.get("first_name") or chat_id
    return Result(True, f"@{name} → {who}")


def find_telegram_chat(token: str) -> Result:
    """Read the bot's recent updates to discover who's talking to it.

    Telegram has no way to look up "the chat with this person" — the id only
    appears once someone messages the bot. So rather than making people hunt
    for a numeric id, they message the bot and we read it back off getUpdates.
    """
    token = (token or "").strip()
    if not token:
        return Result(False, "Add the bot token first")
    try:
        r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates",
                         params={"limit": 20}, timeout=_TIMEOUT)
    except requests.RequestException as e:
        return Result(False, f"Couldn't reach Telegram ({e.__class__.__name__})")
    if r.status_code != 200:
        return Result(False, f"Telegram said {r.status_code}")

    seen: dict[str, str] = {}
    for update in r.json().get("result", []):
        msg = update.get("message") or update.get("channel_post") or {}
        chat = msg.get("chat") or {}
        if chat.get("id") is not None:
            label = chat.get("title") or chat.get("username") or chat.get("first_name") or ""
            seen[str(chat["id"])] = label
    if not seen:
        return Result(
            False,
            "Nothing yet — open Telegram, send the bot any message, then try again")
    chat_id, label = next(iter(seen.items()))
    return Result(True, f"Found {label or chat_id}", options=list(seen),
                  detail={"chat_id": chat_id})


def check_bot_token(token: str) -> Result:
    token = (token or "").strip()
    if not token:
        return Result(True, "Not set — send-only mode (she can't reply)")
    try:
        r = requests.get(
            "https://discord.com/api/v10/users/@me",
            headers={"Authorization": f"Bot {token}"},
            timeout=_TIMEOUT,
        )
    except requests.RequestException as e:
        return Result(False, f"Couldn't reach Discord ({e.__class__.__name__})")
    if r.status_code == 401:
        return Result(False, "Discord rejected that bot token")
    if r.status_code != 200:
        return Result(False, f"Discord said {r.status_code}")
    data = r.json()
    return Result(True, f"Signed in as {data.get('username', 'the bot')}")


# --- AI providers -------------------------------------------------------------
def check_groq(key: str, base_url: str) -> Result:
    key = (key or "").strip()
    if not key:
        return Result(False, "No key yet — grab a free one at console.groq.com")
    try:
        r = requests.get(
            f"{base_url.rstrip('/')}/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=_TIMEOUT,
        )
    except requests.RequestException as e:
        return Result(False, f"Couldn't reach the API ({e.__class__.__name__})")
    if r.status_code in (401, 403):
        return Result(False, "That key was rejected")
    if r.status_code != 200:
        return Result(False, f"The API said {r.status_code}")
    models = sorted(m.get("id", "") for m in r.json().get("data", []) if m.get("id"))
    return Result(True, f"Key works — {len(models)} models available", options=models)


def check_ollama(host: str) -> Result:
    try:
        r = requests.get(f"{host.rstrip('/')}/api/tags", timeout=_TIMEOUT)
    except requests.RequestException:
        return Result(False, "Ollama isn't running — start it, or pick another provider")
    if r.status_code != 200:
        return Result(False, f"Ollama said {r.status_code}")
    models = sorted(m.get("name", "") for m in r.json().get("models", []) if m.get("name"))
    if not models:
        return Result(False, "Ollama is running but has no models — try `ollama pull llama3.2`")
    return Result(True, f"Running locally — {len(models)} models pulled", options=models)


def check_anthropic(key: str) -> Result:
    key = (key or "").strip()
    if not key:
        return Result(False, "No API key yet")
    try:
        r = requests.get(
            "https://api.anthropic.com/v1/models",
            headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
            timeout=_TIMEOUT,
        )
    except requests.RequestException as e:
        return Result(False, f"Couldn't reach the API ({e.__class__.__name__})")
    if r.status_code in (401, 403):
        return Result(False, "That key was rejected")
    if r.status_code != 200:
        return Result(False, f"The API said {r.status_code}")
    models = [m.get("id", "") for m in r.json().get("data", []) if m.get("id")]
    return Result(True, f"Key works — {len(models)} models available", options=models)


# --- Running one without freezing the window ---------------------------------
class Prober(QObject):
    """Runs a probe on a worker thread and emits the result on the UI thread.

    Each call bumps a generation counter; results from a superseded run are
    dropped, so fast typing can't let a stale answer overwrite a fresh one.
    """

    finished = Signal(object)   # Result
    started_ = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._generation = 0

    def run(self, fn, *args) -> None:
        self._generation += 1
        generation = self._generation
        self.started_.emit()

        def work() -> None:
            try:
                result = fn(*args)
            except Exception as e:                      # never kill the thread
                result = Result(False, f"Check failed ({e.__class__.__name__})")
            if generation == self._generation:
                try:
                    # Queued across threads, so the slot runs on the UI thread.
                    self.finished.emit(result)
                except RuntimeError:
                    # The window owning this Prober was destroyed while the
                    # check was still running — closing it, or switching theme,
                    # which rebuilds the whole window. There's nobody left to
                    # tell, and Qt raises rather than no-ops on a dead object.
                    pass

        threading.Thread(target=work, daemon=True).start()
