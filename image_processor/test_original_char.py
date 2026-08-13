"""
Test an original, non-existing cartoon character for perfect 3D rendering.
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

def create_banner_post(img, quote, character, handle="@masculine.aura"):
    img = img.convert("RGB")
    W, H = img.size
    BANNER_H = 240
    TOTAL_H = H + BANNER_H
    canvas = Image.new("RGB", (W, TOTAL_H), (255, 255, 255))
    canvas.paste(img, (0, 0))
    draw = ImageDraw.Draw(canvas)
    draw.line([(0, H), (W, H)], fill=(230, 230, 230), width=3)
    font_quote  = ImageFont.truetype(BOLD_PATH, 28)
    font_handle = ImageFont.truetype(REGULAR_PATH, 20)
    BLACK = (15, 15, 15)
    GRAY  = (110, 110, 110)
    quote_text = quote.upper()
    wrapped = textwrap.wrap(quote_text, width=32)
    line_h = 38
    text_block_h = len(wrapped) * line_h + 30
    start_y = H + (BANNER_H - text_block_h) // 2
    for i, line in enumerate(wrapped):
        bbox = draw.textbbox((0, 0), line, font=font_quote)
        tw = bbox[2] - bbox[0]
        tx = (W - tw) // 2
        draw.text((tx, start_y + i * line_h), line, font=font_quote, fill=BLACK)
        
    handle_text = f"— {character.upper()}  |  {handle}"
    h_bbox = draw.textbbox((0, 0), handle_text, font=font_handle)
    htw = h_bbox[2] - h_bbox[0]
    htx = (W - htw) // 2
    draw.text((htx, start_y + len(wrapped) * line_h + 10), handle_text, font=font_handle, fill=GRAY)
    return canvas

print("Downloading original 3D character image from Pollinations...")
# Original character prompt
prompt = "3D animated cartoon character, a cool dapper Lion, round stylized yellow face, thick cartoon mane, wearing black sunglasses and a black tuxedo suit with a black bowtie, solid dark studio background, octane 3d render, claymation style, plastic texture, masterpiece"
url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt) + "?width=1080&height=1080&nologo=true&seed=888&model=flux"
resp = http_requests.get(url, timeout=60)
print(f"Downloaded: {resp.status_code} | {len(resp.content)} bytes")

img = Image.open(io.BytesIO(resp.content))
result = create_banner_post(
    img,
    quote="A lion does not concern himself with the opinions of sheep.",
    character="King Leo",
    handle="@masculine.aura"
)

out_path = r"d:\zdiiv\N8N\image_processor\original_char_output.jpg"
result.save(out_path, format="JPEG", quality=95)
print(f"\nSaved to: {out_path}")
