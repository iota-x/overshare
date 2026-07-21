"""Generates assets/icon.icns — a warm rounded-square with a heart that's
broadcasting little signal waves: lovingly *oversharing*, not a creepy eye.

Run: ../.venv/bin/python make_icon.py   (from the assets/ dir)
"""

import math
import os
import shutil
import subprocess

from PIL import Image, ImageDraw

SIZE = 1024
SS = 4  # supersample factor for crisp, anti-aliased edges
HERE = os.path.dirname(os.path.abspath(__file__))


def _lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _heart_points(cx, cy, scale):
    """A smooth heart via the classic parametric curve."""
    pts = []
    for deg in range(0, 361, 2):
        t = math.radians(deg)
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((cx + x * scale, cy - y * scale))
    return pts


def render(size: int = SIZE) -> Image.Image:
    s = size * SS
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))

    # Warm diagonal gradient: pink (top-left) -> violet (bottom-right).
    c1, c2 = (0xFF, 0x6F, 0xB0), (0x7C, 0x4D, 0xF0)
    grad = Image.new("RGB", (s, s))
    gpx = grad.load()
    for y in range(s):
        for x in range(s):
            gpx[x, y] = _lerp(c1, c2, (x + y) / (2 * s))

    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.225), fill=255)
    img.paste(grad, (0, 0), mask)

    draw = ImageDraw.Draw(img)

    # Heart, centred and slightly left so the broadcast waves have room.
    hx, hy = s * 0.44, s * 0.52
    hscale = s * 0.019
    heart = _heart_points(hx, hy, hscale)

    # Broadcast waves radiating from the heart's upper-right — "sharing".
    # Drawn first (behind), concentric arcs fading outward.
    ox, oy = s * 0.58, s * 0.40
    for i, r in enumerate((0.15, 0.225, 0.30)):
        rr = s * r
        alpha = int(235 - i * 55)
        draw.arc([ox - rr, oy - rr, ox + rr, oy + rr],
                 start=-72, end=6, fill=(255, 255, 255, alpha), width=int(s * 0.022))

    # A soft drop shadow under the heart, then the heart itself.
    shadow = [(x + s * 0.008, y + s * 0.012) for (x, y) in heart]
    draw.polygon(shadow, fill=(60, 20, 80, 70))
    draw.polygon(heart, fill=(255, 255, 255, 255))

    # Tiny highlight on the left lobe for a bit of life.
    hlr = s * 0.05
    draw.ellipse([hx - s * 0.14 - hlr, hy - s * 0.10 - hlr,
                  hx - s * 0.14 + hlr, hy - s * 0.10 + hlr],
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
