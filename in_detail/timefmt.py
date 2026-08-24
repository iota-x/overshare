"""Formatting times and dates the same way on every platform.

`%-I` and `%-d` — the no-leading-zero forms — are a glibc/BSD extension. On
Windows `strftime` rejects them outright with `ValueError: Invalid format
string`, and the equivalent there is `%#I`. Using either means writing the
format twice and picking by platform.

So neither is used. The numbers are built directly, which is shorter than the
platform check and can't be wrong on one OS and right on the other.

This is not hypothetical: `notifier._timestamp()` used `%-I:%M %p` and sat in
the path of *every* update, so on Windows every activity card, every recap and
every weekly wrap raised before it was ever sent.
"""

from __future__ import annotations

import datetime as _dt


def clock(when: _dt.datetime | None = None) -> str:
    """`8:42 pm` — 12-hour, no leading zero, lowercase."""
    when = when or _dt.datetime.now()
    hour = when.hour % 12 or 12
    return f"{hour}:{when.minute:02d} {'am' if when.hour < 12 else 'pm'}"


def day(date: _dt.date) -> str:
    """`aug 3` — month short name, no leading zero on the day."""
    return f"{date.strftime('%b')} {date.day}".lower()


def weekday(date: _dt.date) -> str:
    """`monday, aug 3`."""
    return f"{date.strftime('%A')}, {day(date)}".lower()
