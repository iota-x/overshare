"""Where messages go — one card, any number of destinations.

Every outbound message in the app funnels through `notifier._deliver`, so this
is the only place that needs to know there's more than one service. Each channel
module exposes the same four functions (`configured`, `enabled`, `healthy`,
`send`) and is asked in turn; a card counts as delivered if any of them took it.

Adding another service means adding a module here and a line in `ALL` — nothing
upstream changes, because the card builders keep speaking the one format.
"""

from __future__ import annotations

from . import discord, telegram

# Order matters only for reporting; sends go to every enabled channel.
ALL = (discord, telegram)


def active() -> list:
    """The channels that are switched on *and* filled in."""
    return [c for c in ALL if c.enabled()]


def names() -> list[str]:
    return [c.__name__.rsplit(".", 1)[-1] for c in active()]


def any_configured() -> bool:
    return any(c.configured() for c in ALL)


def deliver(content: str = "", embed: dict | None = None) -> bool:
    """Send one card everywhere it should go. True if anywhere accepted it.

    A failure in one destination must not stop the others — losing Telegram
    shouldn't cost them the Discord card too.
    """
    sent = False
    for channel in active():
        try:
            if channel.send(content, embed):
                sent = True
        except Exception:
            pass
    return sent


def healthy() -> bool:
    """Unhealthy only if something that should be working isn't.

    With nothing configured there's nothing to be unhealthy about — that's a
    setup state, and the settings window says so far better than a ⚠️ would.
    """
    live = active()
    if not live:
        return True
    return all(c.healthy() for c in live)
