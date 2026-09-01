"""Where a row's value actually lives.

The app has always had two kinds of setting and they stay separate:

  * :class:`Cfg`      — install configuration (webhook, keys, timings). Backed by
    ``config.json``, read through ``config.<NAME>``.
  * :class:`Runtime`  — the things they flip day to day (tone, mood, camera
    permission). Backed by ``settings.json``, and already shared with the menu
    bar's checkmarks.

Both expose the same two methods so a widget doesn't care which it's bound to.
"""

from __future__ import annotations

from .. import config, settings


class Cfg:
    """Install configuration — uppercase keys, mirrors the old .env names."""

    def get(self, key: str):
        return getattr(config, key, None)

    def set(self, key: str, value) -> None:
        config.save({key: value})


class Runtime:
    """Your partner's live preferences — lowercase keys in settings.json."""

    def get(self, key: str):
        return settings.get(key)

    def set(self, key: str, value) -> None:
        settings.set(key, value)


class Memory:
    """A throwaway store for controls that drive the UI but persist nothing."""

    def __init__(self, initial: dict | None = None):
        self._values = dict(initial or {})

    def get(self, key: str):
        return self._values.get(key)

    def set(self, key: str, value) -> None:
        self._values[key] = value


CFG = Cfg()
RUNTIME = Runtime()
