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
# typed version is the joke. Drawn as strokes so it keeps the marker feel.
LW = 11
d.line([(cx - 52, cy), (cx - 12, cy - 34)], fill=INK, width=LW, joint="curve")
d.line([(cx - 52, cy), (cx - 12, cy + 34)], fill=INK, width=LW, joint="curve")

# The 3: two stacked bowls, open to the left.
d.arc([cx + 2, cy - 40, cx + 62, cy + 2], start=-95, end=115, fill=INK, width=LW)
d.arc([cx + 2, cy - 2, cx + 62, cy + 40], start=-115, end=95, fill=INK, width=LW)

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
