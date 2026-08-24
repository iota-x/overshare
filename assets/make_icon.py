"""Draw the app icon: a dark squircle with a single rose eye.

Minimal on purpose — the mark has to survive 16px in a menu bar and a Dock
full of competitors, so it's one shape and one accent. Drawn at 4x and
downsampled, because PIL's antialiasing on curves is only good enough if you
give it the pixels.
"""
from PIL import Image, ImageDraw, ImageFilter

S = 1024
K = 4                      # supersample
W = S * K

INK_TOP = (32, 26, 40)
INK_BOT = (17, 13, 22)
ROSE    = (255, 111, 165)
DARK    = (20, 16, 24)


def bezier(p0, p1, p2, n=160):
    return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t * t * p2[0],
             (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t * t * p2[1])
            for t in (i / n for i in range(n + 1))]


# --- the squircle, with a soft vertical gradient -----------------------------
grad = Image.new("RGB", (1, W))
for y in range(W):
    f = y / W
    grad.putpixel((0, y), tuple(int(INK_TOP[i] + (INK_BOT[i] - INK_TOP[i]) * f) for i in range(3)))
grad = grad.resize((W, W))

mask = Image.new("L", (W, W), 0)
pad = int(W * 0.085)                       # macOS leaves the artwork some air
ImageDraw.Draw(mask).rounded_rectangle(
    [pad, pad, W - pad, W - pad], radius=int(W * 0.2237), fill=255)

icon = Image.new("RGBA", (W, W), (0, 0, 0, 0))
icon.paste(grad, (0, 0), mask)

# --- the eye ------------------------------------------------------------------
cx, cy = W / 2, W / 2
# Taller and less pointed than it wants to be: at 16px a thin almond
# collapses to two dots either side of the iris and stops reading as an eye.
half, lift = W * 0.275, W * 0.215
almond = (bezier((cx - half, cy), (cx, cy - lift), (cx + half, cy)) +
          bezier((cx + half, cy), (cx, cy + lift), (cx - half, cy)))

glow = Image.new("RGBA", (W, W), (0, 0, 0, 0))
ImageDraw.Draw(glow).polygon(almond, fill=ROSE + (110,))
icon.alpha_composite(glow.filter(ImageFilter.GaussianBlur(W * 0.035)))

d = ImageDraw.Draw(icon)
d.polygon(almond, fill=ROSE + (255,))

r = W * 0.088                              # iris: dark, so the eye reads open
d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=DARK + (255,))
# No pupil highlight: below ~32px it merges with the iris and just muddies it.

icon = icon.resize((S, S), Image.LANCZOS)
icon.save("assets/icon.png")
print("wrote assets/icon.png", icon.size)
