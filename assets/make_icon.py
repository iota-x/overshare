"""Generates assets/icon.icns — a rounded-square gradient with a watching eye.

Run: ../.venv/bin/python make_icon.py   (from the assets/ dir)
"""

import math
import os
import shutil
import subprocess

from PIL import Image, ImageDraw

SIZE = 1024
HERE = os.path.dirname(os.path.abspath(__file__))


def _lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def render(size: int = SIZE) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Diagonal gradient: purple (top-left) -> blue (bottom-right).
    c1, c2 = (0x6D, 0x5F, 0xF6), (0x36, 0x8E, 0xF7)
    grad = Image.new("RGB", (size, size))
    gpx = grad.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * size)
            gpx[x, y] = _lerp(c1, c2, t)

    # Rounded-square mask.
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [0, 0, size - 1, size - 1], radius=int(size * 0.225), fill=255
    )
    img.paste(grad, (0, 0), mask)

    # The eye: white almond + dark pupil + highlight.
    cx, cy = size / 2, size / 2
    ew, eh = size * 0.62, size * 0.40
    draw.ellipse([cx - ew / 2, cy - eh / 2, cx + ew / 2, cy + eh / 2],
                 fill=(255, 255, 255, 255))
    pr = size * 0.145
    draw.ellipse([cx - pr, cy - pr, cx + pr, cy + pr], fill=(0x1E, 0x29, 0x54, 255))
    hr = size * 0.045
    draw.ellipse([cx - pr * 0.35 - hr, cy - pr * 0.35 - hr,
                  cx - pr * 0.35 + hr, cy - pr * 0.35 + hr],
                 fill=(255, 255, 255, 235))
    return img


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
