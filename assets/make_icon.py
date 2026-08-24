"""Draw the app icon: a message bubble caught mid-sentence.

The mark used to be an eye. An eye is what every app in this category reaches
for, and it collapsed into two dots and a dash the moment it hit a menu bar. A
bubble with three dots says the same thing more honestly and survives 16px: the
app is always partway through telling her something, and you never typed it.

Drawn at 4x and downsampled, because PIL's antialiasing on curves is only good
enough if you give it the pixels. Run this and it rewrites all three formats —
the PNG, the .icns macOS bundles, and the .ico Windows and Inno Setup want.
"""
import math
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
S, K = 1024, 4
W = S * K

INK_TOP, INK_BOT = (32, 26, 40), (17, 13, 22)
ROSE, DARK = (255, 111, 165), (20, 16, 24)


def tile() -> Image.Image:
    """The squircle, with a soft vertical gradient."""
    grad = Image.new("RGB", (1, W))
    for y in range(W):
        f = y / W
        grad.putpixel((0, y), tuple(
            int(INK_TOP[i] + (INK_BOT[i] - INK_TOP[i]) * f) for i in range(3)))
    grad = grad.resize((W, W))

    mask = Image.new("L", (W, W), 0)
    pad = int(W * 0.085)                      # macOS leaves the artwork some air
    ImageDraw.Draw(mask).rounded_rectangle(
        [pad, pad, W - pad, W - pad], radius=int(W * 0.2237), fill=255)

    im = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    im.paste(grad, (0, 0), mask)
    return im


def bubble(d: ImageDraw.ImageDraw, col, glow: bool) -> None:
    cx, cy = W * 0.5, W * 0.465
    hw, hh = W * 0.295, W * 0.225
    d.rounded_rectangle([cx - hw, cy - hh, cx + hw, cy + hh],
                        radius=W * 0.115, fill=col)
    # The tail starts inside the body so the two read as one shape, not a
    # rectangle with a triangle parked under it.
    d.polygon([(cx - W * 0.205, cy + hh - W * 0.02),
               (cx - W * 0.055, cy + hh - W * 0.01),
               (cx - W * 0.245, cy + W * 0.335)], fill=col)

    # The dots are knocked out of the bubble, not drawn over it, so they stay
    # dark against the rose at every size. They are deliberately fat and widely
    # spaced: at 16px anything tighter merges into a single smear.
    if not glow:
        r = W * 0.048
        for k in (-1, 0, 1):
            x = cx + k * W * 0.125
            d.ellipse([x - r, cy - r, x + r, cy + r], fill=DARK + (255,))


def draw() -> Image.Image:
    icon = tile()
    g = Image.new("RGBA", (W, W), (0, 0, 0, 0))
    bubble(ImageDraw.Draw(g), ROSE + (115,), glow=True)
    icon.alpha_composite(g.filter(ImageFilter.GaussianBlur(W * 0.035)))
    bubble(ImageDraw.Draw(icon), ROSE + (255,), glow=False)
    return icon.resize((S, S), Image.LANCZOS)


def write_icns(icon: Image.Image, out: Path) -> bool:
    """iconutil is macOS-only; elsewhere the committed .icns just stays put."""
    if not shutil.which("iconutil"):
        print("no iconutil — leaving", out.name, "alone")
        return False
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "icon.iconset"
        iconset.mkdir()
        for px in (16, 32, 128, 256, 512):
            icon.resize((px, px), Image.LANCZOS).save(iconset / f"icon_{px}x{px}.png")
            icon.resize((px * 2, px * 2), Image.LANCZOS).save(
                iconset / f"icon_{px}x{px}@2x.png")
        subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(out)],
                       check=True)
    return True


icon = draw()
icon.save(ROOT / "assets" / "icon.png")
print("wrote assets/icon.png", icon.size)

icon.convert("RGBA").save(
    ROOT / "assets" / "icon.ico",
    sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("wrote assets/icon.ico")

if write_icns(icon, ROOT / "assets" / "icon.icns"):
    print("wrote assets/icon.icns")
