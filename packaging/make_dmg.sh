#!/usr/bin/env bash
# Wrap dist/Overshare.app into a drag-to-install .dmg.
#
#   ./packaging/make_dmg.sh [version]
#
# Run it after `pyinstaller packaging/Overshare.spec --noconfirm`. Uses hdiutil,
# which ships with macOS, so there's nothing to install first.

set -euo pipefail

VERSION="${1:-1.0.0}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$ROOT/dist/Overshare.app"
DMG="$ROOT/dist/Overshare-$VERSION.dmg"

if [[ ! -d "$APP" ]]; then
  echo "error: $APP not found — build it first:" >&2
  echo "  pyinstaller packaging/Overshare.spec --noconfirm" >&2
  exit 1
fi

STAGING="$(mktemp -d)"
trap 'rm -rf "$STAGING"' EXIT

echo "==> staging"
cp -R "$APP" "$STAGING/"
# The Applications symlink is what makes the window a drag-to-install target.
ln -s /Applications "$STAGING/Applications"

# A short read-me in the disk image, because an unsigned app needs the
# right-click trick the first time and Finder gives no hint about it.
cat > "$STAGING/READ ME FIRST.txt" <<'EOF'
Installing Overshare
====================

1. Drag Overshare onto the Applications folder shown here.

2. The first time you open it, macOS will say it "could not verify" the app.
   That's what happens with any app not signed by a paid Apple developer
   account — it isn't a sign anything is wrong.

   To get past it: open your Applications folder, RIGHT-CLICK Overshare,
   choose Open, then click Open in the dialog. You only do this once.

3. A 💌 appears in your menu bar. Click it -> Settings… to set things up.

macOS will ask for a few permissions as you use it:
  * Accessibility  — to read window and file titles
  * Automation     — to read your browser tab and what's playing
  * Camera/Screen  — only if you use the peek features
EOF

rm -f "$DMG"
echo "==> building $DMG"
hdiutil create \
  -volname "Overshare" \
  -srcfolder "$STAGING" \
  -ov -format UDZO \
  "$DMG" >/dev/null

echo "==> done: $DMG"
ls -lh "$DMG" | awk '{print "    " $5}'
