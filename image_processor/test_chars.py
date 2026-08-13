"""
Test multiple cartoon characters to find which ones render accurately.
"""
import sys, os
sys.path.insert(0, r"d:\zdiiv\vids\venv\Lib\site-packages")
os.chdir(r"d:\zdiiv\N8N\image_processor")

import io
import textwrap
import urllib.request
import urllib.parse
from PIL import Image, ImageDraw, ImageFont
import requests as http_requests

FONT_DIR = r"d:\zdiiv\N8N\image_processor\fonts"
BOLD_PATH    = f"{FONT_DIR}/Montserrat-Bold.ttf"
REGULAR_PATH = f"{FONT_DIR}/Montserrat-Regular.ttf"

def add_banner(img, quote, character, handle="@masculine.aura"):
    img = img.convert("RGB")
    W, H = img.size
    BANNER_H = 220
    canvas = Image.new("RGB", (W, H + BANNER_H), (255, 255, 255))
    canvas.paste(img, (0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.line([(0, H), (W, H)], fill=(220, 220, 220), width=3)
    font_q = ImageFont.truetype(BOLD_PATH, 28)
    font_h = ImageFont.truetype(REGULAR_PATH, 20)
    lines = textwrap.wrap(quote.upper(), width=32)
    line_h = 38
    start_y = H + (BANNER_H - len(lines) * line_h - 30) // 2
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font_q)
        tx = (W - (bbox[2] - bbox[0])) // 2
        draw.text((tx, start_y + i * line_h), line, font=font_q, fill=(15, 15, 15))
    htxt = f"— {character.upper()}  |  {handle}"
    hbbox = draw.textbbox((0, 0), htxt, font=font_h)
    htx = (W - (hbbox[2] - hbbox[0])) // 2
    draw.text((htx, start_y + len(lines) * line_h + 8), htxt, font=font_h, fill=(100, 100, 100))
    return canvas

# Test these characters with accurate descriptors
chars = [
    ("Bugs Bunny",   "3D octane render 4k, Bugs Bunny, grey anthropomorphic rabbit with long ears and white fluffy tail, wearing elegant black tuxedo suit and black bowtie, holding cigar, solid black studio background, cinematic lighting, masterpiece"),
    ("Shrek",        "3D octane render 4k, Shrek, large green ogre with round ears, bald head, wearing tailored black tuxedo suit and bow tie, confident alpha pose, solid black studio background, cinematic lighting, masterpiece"),
    ("Goofy",        "3D octane render 4k, Goofy Disney character, tall lanky brown cartoon dog with floppy ears and buck teeth, wearing black suit and fedora hat, solid dark studio background, cinematic 3d render, masterpiece"),
    ("Garfield",     "3D octane render 4k, Garfield the orange tabby cat with black stripes, chubby lazy fat cat, wearing black suit jacket and dark sunglasses, solid black studio background, cinematic lighting, masterpiece"),
    ("Mickey Mouse", "3D octane render 4k, Mickey Mouse, round black cartoon mouse with iconic round ears and white gloves, wearing luxury black tuxedo suit with gold cufflinks, solid black background, studio lighting, masterpiece"),
]

os.makedirs(r"d:\zdiiv\N8N\image_processor\char_tests", exist_ok=True)

for char_name, prompt in chars:
    url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt) + f"?width=1080&height=1080&nologo=true&seed=99&model=flux"
    print(f"Generating {char_name}...")
    try:
        resp = http_requests.get(url, timeout=90)
        if resp.status_code == 200:
            img = Image.open(io.BytesIO(resp.content))
            result = add_banner(img, "Silence is the loudest flex.", char_name)
            safe = char_name.lower().replace(" ", "_")
            out = rf"d:\zdiiv\N8N\image_processor\char_tests\{safe}.jpg"
            result.save(out, format="JPEG", quality=92)
            print(f"  Saved: {out}")
    except Exception as e:
        print(f"  Error: {e}")

print("\nDone!")
