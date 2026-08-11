"""
Local test - generates a sample aura post image and saves it to see how it looks.
Run: python test_local.py
"""
import sys, os
sys.path.insert(0, r"d:\zdiiv\vids\venv\Lib\site-packages")

# Patch path so app.py imports work
os.chdir(r"d:\zdiiv\N8N\image_processor")

import io
import textwrap
import urllib.request
from PIL import Image, ImageDraw, ImageFont
import requests as http_requests

# ── Download fonts ──────────────────────────────────────────────────────────
FONT_DIR = r"d:\zdiiv\N8N\image_processor\fonts"
os.makedirs(FONT_DIR, exist_ok=True)
BOLD_PATH    = f"{FONT_DIR}/Montserrat-Bold.ttf"
REGULAR_PATH = f"{FONT_DIR}/Montserrat-Regular.ttf"

for path, url in [
    (BOLD_PATH,    "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf"),
    (REGULAR_PATH, "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Regular.ttf"),
]:
    if not os.path.exists(path):
        print(f"Downloading {url}...")
        urllib.request.urlretrieve(url, path)
        print(f"Saved.")

# ── Image processing ─────────────────────────────────────────────────────────
def add_quote_overlay(img, quote, character, handle="@aura.clips"):
    img = img.convert("RGBA")

    font_quote   = ImageFont.truetype(BOLD_PATH, 52)
    font_name    = ImageFont.truetype(BOLD_PATH, 36)
    font_handle  = ImageFont.truetype(REGULAR_PATH, 28)

    GOLD   = (218, 165, 32, 255)
    WHITE  = (255, 255, 255, 255)
    BLACK  = (0, 0, 0, 255)

    wrapped = textwrap.wrap(f'"{quote}"', width=22)

    PAD        = 32
    LINE_H     = 65
    BOX_W      = 660
    BOX_H      = PAD * 2 + len(wrapped) * LINE_H + 90
    BOX_X, BOX_Y = 40, 40

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle(
        [BOX_X, BOX_Y, BOX_X + BOX_W, BOX_Y + BOX_H],
        radius=22, fill=(0, 0, 0, 185)
    )
    od.rounded_rectangle(
        [BOX_X, BOX_Y, BOX_X + BOX_W, BOX_Y + BOX_H],
        radius=22, outline=(218, 165, 32, 210), width=3
    )
    img = Image.alpha_composite(img, overlay)
    draw = ImageDraw.Draw(img)

    text_x = BOX_X + PAD
    text_y = BOX_Y + PAD
    for i, line in enumerate(wrapped):
        draw.text((text_x + 2, text_y + i * LINE_H + 2), line, font=font_quote, fill=(0, 0, 0, 160))
        draw.text((text_x, text_y + i * LINE_H), line, font=font_quote, fill=WHITE)

    name_y = BOX_Y + BOX_H - 85
    draw.text((text_x, name_y), f"\u25a0  {character}", font=font_name, fill=GOLD)

    handle_y = BOX_Y + BOX_H - 46
    dummy_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = dummy_draw.textbbox((0, 0), handle, font=font_handle)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    px, py = 14, 6
    pill = [text_x, handle_y, text_x + tw + px * 2, handle_y + th + py * 2]
    draw.rounded_rectangle(pill, radius=12, fill=(218, 165, 32, 235))
    draw.text((text_x + px, handle_y + py), handle, font=font_handle, fill=BLACK)

    return img.convert("RGB")


# ── Test run ──────────────────────────────────────────────────────────────────
print("Downloading test image from Pollinations...")
import urllib.parse
prompt = "Itachi Uchiha from Naruto, Akatsuki cloak, Sharingan eyes glowing red, dark misty forest, arms folded, purple black aura surrounding silhouette, ultra cinematic anime"
url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt) + "?width=1080&height=1080&nologo=true&seed=42&model=flux"
resp = http_requests.get(url, timeout=60)
print(f"Downloaded: {resp.status_code} | {len(resp.content)} bytes")

img = Image.open(io.BytesIO(resp.content))
result = add_quote_overlay(
    img,
    quote="Silence is the loudest flex. Let your results speak.",
    character="Itachi Uchiha",
    handle="@aura.clips"
)

out_path = r"d:\zdiiv\N8N\image_processor\test_output.jpg"
result.save(out_path, format="JPEG", quality=92)
print(f"\nSaved to: {out_path}")
print("Open the file to preview the styling!")
