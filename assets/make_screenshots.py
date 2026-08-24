"""Regenerate the site's app screenshots in the dark theme.

The page is near-black; a light-mode window sat on it as a glowing slab. The
app follows the system theme anyway, so showing the dark one is both truer and
easier on the page.
"""
from PySide6.QtWidgets import QApplication, QLineEdit
from PySide6.QtCore import QEventLoop, QTimer
from in_detail.gui.main import SettingsWindow
from in_detail.gui import theme
from PySide6.QtCore import Qt
from PIL import Image

FAKE = "https://discord.com/api/webhooks/••••••••••••••••••/••••••••••••••••"

def settle(ms=900):
    loop = QEventLoop(); QTimer.singleShot(ms, loop.quit); loop.exec()

def redact(page):
    for f in page.findChildren(QLineEdit):
        s = f.text()
        if "discord.com/api/webhooks" in s:
            f.setText(FAKE)
        elif s.replace(",", "").isdigit() and len(s.replace(",", "")) > 8:
            f.setText("41234567890123456")
    for attr, msg in (("_hook_status", 'Connected as “overshare”'),
                      ("_bot_status", "Signed in as overshare")):
        if hasattr(page, attr):
            getattr(page, attr).set_state("good", msg)
    if hasattr(page, "_tg_status"):
        page._tg_status.set_state("idle", "Not set — Discord only")

app = QApplication([])
app.setStyleSheet(theme.qss(True))
w = SettingsWindow(dark=True)
w.resize(980, 700)
w.show()

FULL = {1: "settings-setup", 4: "settings-privacy-dark", 3: "settings-ai-dark",
        5: "settings-recaps", 2: "settings-activity"}

for i in range(w._nav.count()):
    name = w._nav.item(i).text().strip().lower().replace(" ", "-")
    w.select_page(i)
    page = w._stack.currentWidget()
    page.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    settle()
    redact(w._stack.currentWidget())
    settle(140)

    tmp = f"/tmp/_dark{i}.png"
    w.grab().save(tmp, "PNG")
    full = Image.open(tmp).convert("RGB")

    # The hero tour: same 62% crop, web-sane width.
    tour = full.crop((0, 0, int(full.width * 0.62), full.height))
    tour.thumbnail((880, 880 * 4), Image.LANCZOS)
    tour.save(f"docs/screenshots/app/{i}-{name}.webp", "WEBP", quality=82, method=6)

    # The standalone shots used further down the page.
    if i in FULL:
        page = full.copy()
        page.thumbnail((1600, 1600), Image.LANCZOS)
        page.save(f"docs/screenshots/{FULL[i]}.png")
    print(f"  {i} {name}")
