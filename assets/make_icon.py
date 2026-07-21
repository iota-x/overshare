"""Generates assets/icon.icns — a love letter: an envelope with a heart wax
seal. Ties directly to the app's own 💌 menu-bar glyph and its "overshare via
message" premise, instead of a generic heart-with-signal-waves mark.

Run: ../.venv/bin/python make_icon.py   (from the assets/ dir)
"""

import math
import os
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFilter

SIZE = 1024
SS = 4  # supersample factor for crisp, anti-aliased edges
HERE = os.path.dirname(os.path.abspath(__file__))


def _lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _heart_points(cx, cy, scale):
    pts = []
    for deg in range(0, 361, 3):
        t = math.radians(deg)
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * scale, cy - y * scale))
    return pts


def render(size: int = SIZE) -> Image.Image:
    s = size * SS
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))

    # Warm diagonal gradient background: pink (top-left) -> violet (bottom-right).
    c1, c2 = (0xFF, 0x6F, 0xB0), (0x7C, 0x4D, 0xF0)
    grad = Image.new("RGB", (s, s))
    gpx = grad.load()
    for y in range(s):
        for x in range(s):
            gpx[x, y] = _lerp(c1, c2, (x + y) / (2 * s))

    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.225), fill=255)
    img.paste(grad, (0, 0), mask)

    # A soft shadow layer, drawn first so the envelope reads as lifted off the bg.
    shadow = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)

    # Envelope geometry.
    ew, eh = s * 0.60, s * 0.40
    ex0, ey0 = (s - ew) / 2, (s - eh) / 2 + s * 0.045
    ex1, ey1 = ex0 + ew, ey0 + eh
    radius = s * 0.028

    sd.rounded_rectangle([ex0 + s * 0.01, ey0 + s * 0.018, ex1 + s * 0.01, ey1 + s * 0.018],
                         radius=radius, fill=(40, 10, 60, 110))
    shadow = shadow.filter(ImageFilter.GaussianBlur(s * 0.012))
    img.alpha_composite(shadow)

    draw = ImageDraw.Draw(img)

    # Envelope body — warm white so it sits forward of the gradient.
    draw.rounded_rectangle([ex0, ey0, ex1, ey1], radius=radius, fill=(255, 250, 248, 255))

    # Back flap fold-lines (the "V" and the two side diagonals), in a soft warm
    # grey so the envelope doesn't read as a flat blank card.
    cx = (ex0 + ex1) / 2
    tip_y = ey0 + eh * 0.52
    fold = (0xE9, 0xDD, 0xDD, 255)
    lw = max(2, int(s * 0.006))
    draw.line([(ex0, ey0), (cx, tip_y)], fill=fold, width=lw)
    draw.line([(ex1, ey0), (cx, tip_y)], fill=fold, width=lw)
    draw.line([(ex0, ey1), (cx, tip_y - eh * 0.06)], fill=fold, width=lw)
    draw.line([(ex1, ey1), (cx, tip_y - eh * 0.06)], fill=fold, width=lw)

    # Heart wax seal, centered where the flap's point lands.
    seal_r = s * 0.105
    scx, scy = cx, tip_y - s * 0.006
    draw.ellipse([scx - seal_r, scy - seal_r, scx + seal_r, scy + seal_r],
                 fill=(0xE3, 0x1B, 0x6B, 255))
    # A subtle darker ring for wax depth, then the embossed heart on top.
    draw.ellipse([scx - seal_r, scy - seal_r, scx + seal_r, scy + seal_r],
                 outline=(0xB8, 0x12, 0x54, 255), width=max(2, int(s * 0.006)))
    heart = _heart_points(scx, scy, seal_r * 0.052)
    draw.polygon(heart, fill=(0xFF, 0xB4, 0xD3, 255))
    # Gloss highlight on the seal.
    hl_r = seal_r * 0.28
    draw.ellipse([scx - seal_r * 0.55 - hl_r, scy - seal_r * 0.55 - hl_r,
                  scx - seal_r * 0.55 + hl_r, scy - seal_r * 0.55 + hl_r],
                 fill=(255, 255, 255, 90))

    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    base = render(SIZE)
    iconset = os.path.join(HERE, "In Detail.iconset")
    if os.path.exists(iconset):
        shutil.rmtree(iconset)
    os.makedirs(iconset)

    specs = [
        (16, "icon_16x16.png"), (32, "icon_16x16@2x.png"),
        (32, "icon_32x32.png"), (64, "icon_32x32@2x.png"),
        (128, "icon_128x128.png"), (256, "icon_128x128@2x.png"),
        (256, "icon_256x256.png"), (512, "icon_256x256@2x.png"),
        (512, "icon_512x512.png"), (1024, "icon_512x512@2x.png"),
    ]
    for px, name in specs:
        base.resize((px, px), Image.LANCZOS).save(os.path.join(iconset, name))

    icns = os.path.join(HERE, "icon.icns")
    subprocess.run(["iconutil", "-c", "icns", iconset, "-o", icns], check=True)
    shutil.rmtree(iconset)
    base.save(os.path.join(HERE, "icon.png"))
    print("wrote", icns)


if __name__ == "__main__":
    main()
