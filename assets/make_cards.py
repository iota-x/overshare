"""Build the link-preview card and the favicons from the live hero.

The og:image used to point at a light-theme settings screenshot, so sharing the
link showed a picture that looked nothing like the page it opened. This renders
the actual hero instead.

The hero is captured with Chrome forced into reduced motion, which the page
already honours by not typing the headline and not advancing the tour — so the
capture is deterministic: "everything." intact, the Setup page showing, and no
caret. Nothing capture-only had to be added to the site to make that work.

Usage:  python assets/make_cards.py   (serves docs/ on a spare port itself)
"""
from __future__ import annotations

import http.server, functools, socket, subprocess, tempfile, threading
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
BG = (14, 12, 17)          # --bg, so the padding is invisible


def _serve(directory: Path):
    handler = functools.partial(http.server.SimpleHTTPRequestHandler,
                                directory=str(directory))
    with socket.socket() as s:                 # let the OS pick a free port
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, port


def _shoot(url: str, out: Path, w: int, h: int) -> Image.Image:
    subprocess.run(
        [CHROME, "--headless", "--disable-gpu", "--hide-scrollbars",
         "--force-prefers-reduced-motion", "--force-device-scale-factor=2",
         f"--window-size={w},{h}", "--virtual-time-budget=4000",
         f"--screenshot={out}", url],
        check=True, capture_output=True)
    return Image.open(out).convert("RGB")


def _compose(band: Image.Image, w: int, h: int, top: int) -> Image.Image:
    """Scale the hero band to `w` and sit it on a `w`x`h` field.

    Consumers crop this: the portfolio card slot is object-cover/object-top, and
    cover takes the overflow off whichever axis is longer. Sitting a little
    *taller* than the slot is deliberate — then the crop comes off the bottom,
    which is empty, instead of off the sides, which is where the headline is.
    That crop ate the headline twice before anyone measured the slot.
    """
    band = band.resize((w, round(w * band.height / band.width)), Image.LANCZOS)
    card = Image.new("RGB", (w, h), BG)
    card.paste(band, (0, top))
    return card


def main() -> None:
    srv, port = _serve(DOCS)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            raw = _shoot(f"http://127.0.0.1:{port}/", Path(tmp) / "hero.png",
                         1600, 1080)
            # Never trim the right: the window is meant to run off it.
            #
            # The link preview is much wider than it is tall, so it starts below
            # the nav — fitting the nav in leaves only a sliver of the Install
            # pill along the top edge, which reads as a rendering fault.
            og_band = raw.crop((0, 190, 3200, 1760))
            og = _compose(og_band, 1200, 630, top=21)
            og.save(DOCS / "og.png", optimize=True)
            print("docs/og.png", og.size)

            # The portfolio card is nearly square by comparison and has room for
            # the nav, which is what names the product to someone scrolling past.
            card = _compose(raw.crop((0, 20, 3200, 1760)), 1600, 1150, top=60)
            out = ROOT / "build" / "portfolio-card.webp"
            out.parent.mkdir(exist_ok=True)
            card.save(out, "WEBP", quality=92, method=6)
            print(out, card.size)

        icon = Image.open(ROOT / "assets" / "icon.png")
        icon.resize((180, 180), Image.LANCZOS).save(DOCS / "icon-180.png")
        icon.resize((32, 32), Image.LANCZOS).save(DOCS / "favicon.png")
        print("docs/favicon.png, docs/icon-180.png")
    finally:
        srv.shutdown()


if __name__ == "__main__":
    main()
