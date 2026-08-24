"""Two whole-package rules, each written after the bug it would have caught.

1. No platform-specific strftime directives. `%-I` and `%-d` are a glibc/BSD
   extension; Windows raises `ValueError: Invalid format string`. That sat in
   `notifier._timestamp()`, in the path of *every* update, so on Windows every
   activity card, recap and weekly wrap raised before it was sent. It was
   invisible for four releases because the poll loop swallowed the exception.

2. No gendered pronouns. The app should read the same whoever is running it and
   whoever is on the other end.

3. No bare QCheckBox in the settings pages. Toggles are the painted Switch in
   widgets.py; a plain checkbox renders as a featureless pill, which is how the
   uninstall option shipped.

All three are greps, and all run on macOS and Windows.
"""

import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PKG = ROOT / "in_detail"

# `%-` / `%#` anywhere in a strftime format.
BAD_TIME = re.compile(r"%[-#][a-zA-Z]")
PRONOUNS = re.compile(r"\b(he|him|his|she|her|hers|girlfriend|boyfriend)\b")
CHECKBOX = re.compile(r"\bQCheckBox\s*\(")

failures = []
for path in sorted(PKG.rglob("*.py")):
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        rel = path.relative_to(ROOT)
        if BAD_TIME.search(line) and "timefmt.py" not in str(path):
            failures.append(f"{rel}:{n}  platform-specific strftime: {line.strip()[:80]}")
        # timefmt.py documents the rule, and this file names the words itself.
        if PRONOUNS.search(line) and "timefmt.py" not in str(path):
            failures.append(f"{rel}:{n}  gendered pronoun: {line.strip()[:80]}")
        if CHECKBOX.search(line):
            failures.append(
                f"{rel}:{n}  bare QCheckBox — use Switch: {line.strip()[:80]}")

if failures:
    print("\n".join(failures))
    sys.exit(1)
print(f"portable: no platform-specific time formats, no gendered pronouns, "
      f"no bare checkboxes ({len(list(PKG.rglob('*.py')))} files)")
