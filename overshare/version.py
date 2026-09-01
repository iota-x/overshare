"""The version this build is.

Committed as a placeholder and rewritten by the release workflow from the git
tag, so a packaged app knows what it is. Nothing else did: __init__ said 0.1.0,
the plist said 1.0.0, and the real number lived only in CI — which is fine
until something has to ask "is there a newer one than me?".
"""

VERSION = "0.0.0-dev"


def parts(v: str) -> tuple:
    """`1.3.10` -> (1, 3, 10), for comparing. Anything unparsable sorts first,
    so a dev build always looks older than a release rather than newer."""
    core = (v or "").lstrip("vV").split("-")[0].split("+")[0]
    out = []
    for chunk in core.split("."):
        out.append(int(chunk) if chunk.isdigit() else 0)
    while len(out) < 3:
        out.append(0)
    return tuple(out[:3])


def is_newer(candidate: str, than: str = "") -> bool:
    """Is `candidate` a later release than `than` (this build by default)?"""
    return parts(candidate) > parts(than or VERSION)
