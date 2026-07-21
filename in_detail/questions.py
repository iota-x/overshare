"""A tiny bank of "question of the day" prompts for the couple to answer.

Picked randomly, avoiding an immediate repeat of the last one sent.
"""

from __future__ import annotations

import random

_QUESTIONS = [
    "what's your favorite memory of us so far? 💭",
    "what's one thing i do that makes you feel loved?",
    "if we could teleport anywhere right now, where would we go?",
    "what's a small thing that made you smile today?",
    "what song reminds you of me?",
    "what's something you're looking forward to together?",
    "what's your favorite way for us to spend a lazy day?",
    "what's one thing you want to try together this year?",
    "what made you fall for me? 🥰",
    "what's your comfort food today, and would you share it with me?",
    "if we had a random day off together, what would we do?",
    "what's something about me you're proud of?",
    "what's a place you'd love to take me to?",
    "what's your love language today — words, time, touch, gifts, or acts?",
    "what's one silly inside joke of ours you love?",
]

_last: str | None = None


def pick() -> str:
    global _last
    choices = [q for q in _QUESTIONS if q != _last] or _QUESTIONS
    q = random.choice(choices)
    _last = q
    return q
