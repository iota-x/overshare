"""Recolour the supplied artwork to the site palette, and swap the doodle.

The eye on the notepad becomes a heart: the eye already appears twice on the
page (the wordmark and the app icon), and the joke lands warmer this way.
"""
from PIL import Image, ImageDraw, ImageFilter
import numpy as np, math

SRC = "/Users/ankit_pandey/.claude/image-cache/cf94f7ff-3d32-4c07-9416-38c605780cec/3.png"
im = Image.open(SRC).convert("RGB")

# --- swap the doodle, before recolouring, so it picks up the same treatment ---
d = ImageDraw.Draw(im)
X0, X1, Y0, Y1 = 950, 1140, 800, 940            # measured from the red clusters
paper = im.crop((X0 - 90, Y0 + 20, X0 - 30, Y0 + 80)).resize((1, 1), Image.LANCZOS).getpixel((0, 0))
d.rectangle([X0, Y0, X1, Y1], fill=paper)

cx, cy = (X0 + X1) / 2, (Y0 + Y1) / 2
INK = (176, 38, 74)                              # the marker red already in the art

# "<3" written out, not a heart glyph — it's a note somebody scrawled, and the
# typed version is the joke.
#
# Every stroke is a sampled bezier rather than a line or an arc. PIL's `arc`
# ends square, so the 3 used to finish on four flat edges and read as two
# stacked brackets — a plotted shape sitting next to a page of brush lettering.
LW = 11


def _bez(pts, n=72):
    """Sample a bezier of any order from its control points."""
    m = len(pts) - 1
    out = []
    for i in range(n + 1):
        t = i / n
        x = y = 0.0
        for k, (px, py) in enumerate(pts):
            w = math.comb(m, k) * (t ** k) * ((1 - t) ** (m - k))
            x += px * w
            y += py * w
        out.append((x, y))
    return out


def _stroke(pts):
    """A curve with round joints and round ends — a marker, not a plotter."""
    d.line(pts, fill=INK, width=LW, joint="curve")
    r = LW / 2
    for x, y in (pts[0], pts[-1]):
        d.ellipse([x - r, y - r, x + r, y + r], fill=INK)


# The <, bowed outward — but only about five pixels of it. Anything more and the
# two arms close up into a C, which is what the first attempt read as. Both arms
# finish on the same point, so their round caps overlap into one tip and the
# vertex softens the way a felt pen would leave it.
_stroke(_bez([(cx - 12, cy - 34), (cx - 38, cy - 25), (cx - 52, cy)]))
_stroke(_bez([(cx - 12, cy + 34), (cx - 38, cy + 25), (cx - 52, cy)]))

# The 3: two bowls meeting at a waist, each a cubic that swings out to the right
# and comes back. The tips curl inward rather than pointing away, which is the
# difference between a written 3 and a drawn one.
waist = (cx + 26, cy)
_stroke(_bez([(cx + 8, cy - 28), (cx + 18, cy - 54), (cx + 74, cy - 38), waist]))
_stroke(_bez([waist, (cx + 78, cy + 8), (cx + 40, cy + 58), (cx + 4, cy + 34)]))

# --- now the palette shift ----------------------------------------------------
a = np.asarray(im).astype(np.float32) / 255.0
r, g, b = a[..., 0], a[..., 1], a[..., 2]
red_mask = np.clip(np.clip(r - np.maximum(g, b), 0, 1) / 0.18, 0, 1)[..., None]
lum = (0.299 * r + 0.587 * g + 0.114 * b)[..., None]

INKC  = np.array([0x0E, 0x0C, 0x11], np.float32) / 255
PAPER = np.array([0xF2, 0xE9, 0xF0], np.float32) / 255
base = INKC + (PAPER - INKC) * (np.clip((lum - 0.06) / 0.88, 0, 1) ** 1.12)

ROSE = np.array([0xFF, 0x6F, 0xA5], np.float32) / 255
out = np.clip(base * (1 - red_mask) + (ROSE * (0.55 + 0.75 * lum)) * red_mask, 0, 1)

img = Image.fromarray((out * 255).astype(np.uint8))
img.thumbnail((1400, 1400), Image.LANCZOS)
img.save("docs/screenshots/watching.webp", "WEBP", quality=90, method=6)
print("wrote docs/screenshots/watching.webp", img.size)
