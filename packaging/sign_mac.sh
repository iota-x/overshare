#!/usr/bin/env bash
# Sign Overshare.app with Overshare's own self-made certificate.
#
#   OVERSHARE_CERT_P12=<base64 .p12> OVERSHARE_CERT_PASSWORD=<pw> \
#     ./packaging/sign_mac.sh [path/to/Overshare.app]
#
# Why bother, when the certificate isn't Apple's: macOS files Accessibility and
# Screen Recording grants under the app's "designated requirement". Ad-hoc
# signing makes that the cdhash, which changes with every build, so every
# update silently lost both permissions. Signed with a fixed certificate, the
# requirement becomes `identifier "com.iota.overshare" and certificate root =
# H"…"` — the same for every build signed with it, so a grant survives updates.
#
# It does nothing for Gatekeeper: the first launch still needs right-click →
# Open, exactly as with ad-hoc. That part needs a paid Developer ID.
#
# The keychain is a throwaway one, on the search list only while codesign runs
# (codesign can't find an identity in a keychain that isn't on the list, even
# with --keychain), and the list is put back afterwards.

set -euo pipefail

APP="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/dist/Overshare.app}"
: "${OVERSHARE_CERT_P12:?base64 of the .p12}"
: "${OVERSHARE_CERT_PASSWORD:?password for the .p12}"
IDENTITY="Overshare Self-Signed"

WORK="$(mktemp -d)"
KC="$WORK/sign.keychain-db"
ORIG=()
while IFS= read -r line; do
  line="${line#"${line%%[![:space:]]*}"}"; line="${line//\"/}"
  [[ -n "$line" ]] && ORIG+=("$line")
done < <(security list-keychains -d user)

cleanup() {
  security list-keychains -d user -s "${ORIG[@]}" || true
  security delete-keychain "$KC" 2>/dev/null || true
  rm -rf "$WORK"
}
trap cleanup EXIT

echo "$OVERSHARE_CERT_P12" | base64 --decode > "$WORK/cert.p12"
security create-keychain -p overshare "$KC"
security set-keychain-settings "$KC"            # no auto-lock mid-sign
security unlock-keychain -p overshare "$KC"
security import "$WORK/cert.p12" -k "$KC" -P "$OVERSHARE_CERT_PASSWORD" -T /usr/bin/codesign >/dev/null
security set-key-partition-list -S apple-tool:,apple: -s -k overshare "$KC" >/dev/null
security list-keychains -d user -s "$KC" "${ORIG[@]}"

# No hardened runtime: it would need entitlements for the embedded Python and
# the camera, and buys nothing without notarization.
codesign --force --deep --sign "$IDENTITY" "$APP"
codesign --verify --deep --strict "$APP"
codesign -d -r- "$APP" 2>&1 | grep designated
