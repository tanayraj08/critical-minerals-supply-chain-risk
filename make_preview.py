"""
Compose the two static preview images the README embeds:

  docs/dashboard-preview.png        the matplotlib dashboard panels stacked
  docs/powerbi-report-mockup.png    the five page Power BI build target

GitHub cannot preview a .pbix and will not run dashboard.html, so without these
images a reader of the repo page sees no visual work at all.

The Power BI render needs headless Chrome. If Chrome is not on the machine the
script still writes the dashboard preview and says which one it skipped.

Usage: python make_preview.py
"""

import base64
import io
import os
import re
import shutil
import subprocess

from PIL import Image, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(HERE, "docs")


def dashboard_preview():
    html = open(os.path.join(HERE, "dashboard.html"), encoding="utf-8").read()
    imgs = re.findall(r'data:image/png;base64,([^"]+)', html)
    # panels are emitted light then dark, so every second image is the light one
    light = [Image.open(io.BytesIO(base64.b64decode(imgs[i]))) for i in range(0, len(imgs), 2)]

    pad, bg = 28, (252, 252, 251)
    width = max(im.width for im in light) + pad * 2
    height = sum(im.height for im in light) + pad * (len(light) + 1)
    canvas = Image.new("RGB", (width, height), bg)
    y = pad
    for im in light:
        canvas.paste(im, ((width - im.width) // 2, y))
        y += im.height + pad

    canvas.thumbnail((1600, 20000), Image.LANCZOS)
    out = os.path.join(DOCS, "dashboard-preview.png")
    canvas.save(out, optimize=True)
    return out, canvas.size


def powerbi_preview():
    chrome = (
        shutil.which("google-chrome")
        or shutil.which("chromium")
        or shutil.which("chromium-browser")
        or "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    )
    if not os.path.exists(chrome):
        return None, None
    src = os.path.join(HERE, "powerbi", "mockup", "report-mockup.html")
    raw = os.path.join(DOCS, "_powerbi_raw.png")
    subprocess.run(
        [
            chrome,
            "--headless",
            "--disable-gpu",
            "--no-sandbox",
            "--hide-scrollbars",
            "--window-size=1400,6400",
            "--virtual-time-budget=6000",
            "--screenshot=" + raw,
            "file://" + src,
        ],
        check=True,
        capture_output=True,
    )
    im = Image.open(raw).convert("RGB")
    # the window is taller than the page, so trim the empty tail
    bg = im.getpixel((5, im.height - 5))
    bbox = ImageChops.difference(im, Image.new("RGB", im.size, bg)).getbbox()
    im = im.crop((0, 0, im.width, min(im.height, bbox[3] + 30)))
    out = os.path.join(DOCS, "powerbi-report-mockup.png")
    im.save(out, optimize=True)
    os.remove(raw)
    return out, im.size


if __name__ == "__main__":
    os.makedirs(DOCS, exist_ok=True)
    path, size = dashboard_preview()
    print("wrote " + path + "  " + str(size))
    path, size = powerbi_preview()
    if path:
        print("wrote " + path + "  " + str(size))
    else:
        print("skipped the Power BI mockup render, no Chrome found on this machine")
