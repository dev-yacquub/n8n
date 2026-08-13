import os
import io
import textwrap
import urllib.request
import urllib.parse
from flask import Flask, request, send_file
from PIL import Image, ImageDraw, ImageFont
import requests as http_requests

app = Flask(__name__)

# ── Font setup ──────────────────────────────────────────────────────────────
FONT_DIR = "/tmp/fonts"
os.makedirs(FONT_DIR, exist_ok=True)

BOLD_PATH    = f"{FONT_DIR}/Montserrat-Bold.ttf"
REGULAR_PATH = f"{FONT_DIR}/Montserrat-Regular.ttf"

def download_fonts():
    fonts = {
        BOLD_PATH:    "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Bold.ttf",
        REGULAR_PATH: "https://github.com/JulietaUla/Montserrat/raw/master/fonts/ttf/Montserrat-Regular.ttf",
    }
    for path, url in fonts.items():
        if not os.path.exists(path):
            print(f"Downloading font: {url}")
            try:
                urllib.request.urlretrieve(url, path)
                print(f"Saved to {path}")
            except Exception as e:
                print(f"Font download error for {url}: {e}")

try:
    download_fonts()
except Exception as e:
    print(f"Font download failed: {e}")


# ── Banner Layout Generator (3D Character + Bottom Quote Banner) ───────────
def create_banner_post(img: Image.Image, quote: str, character: str, handle: str = "@masculine.aura") -> Image.Image:
    """
    Creates a clean 4:5 Instagram card format (1080x1320) with a clean white bottom banner.
    Ensures the 3D character is 100% visible and NEVER obscured by text!
    """
    img = img.convert("RGB")
    W, H = img.size # 1080x1080

    BANNER_H = 240
    TOTAL_H = H + BANNER_H # 1320px height (ideal Instagram format)

    canvas = Image.new("RGB", (W, TOTAL_H), (255, 255, 255))
    canvas.paste(img, (0, 0))

    draw = ImageDraw.Draw(canvas)

    # Divider line separating image and text banner
    draw.line([(0, H), (W, H)], fill=(230, 230, 230), width=3)

    # Load fonts with fallback
    try:
        font_quote  = ImageFont.truetype(BOLD_PATH, 28)
        font_handle = ImageFont.truetype(REGULAR_PATH, 20)
    except Exception:
        font_quote  = ImageFont.load_default()
        font_handle = font_quote

    BLACK = (15, 15, 15)
    GRAY  = (110, 110, 110)

    # Wrap quote text cleanly inside banner
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


# ── 20 3D Cartoon Characters Prompt Mapping ──────────────────────────────────
PROMPTS = {
    "King Leo": "3D animated cartoon character, a cool dapper Lion, round stylized yellow face, thick cartoon mane, wearing black sunglasses and a black tuxedo suit with a black bowtie, solid dark studio background, octane 3d render, claymation style, plastic texture, masterpiece",
    "Agent Fox": "3D animated cartoon character, a sleek dapper Fox with orange fur, pointed ears, wearing black sunglasses and a sharp black suit with tie, solid dark studio background, octane 3d render, claymation style, plastic texture, masterpiece",
    "Boss Bulldog": "3D animated cartoon character, a tough dapper Bulldog, wrinkled face, floppy ears, wearing black sunglasses and a pinstripe black suit, solid dark studio background, octane 3d render, claymation style, plastic texture, masterpiece",
    "Mr. Grizzly": "3D animated cartoon character, a massive dapper Grizzly Bear, round ears, wearing black sunglasses and a custom-fitted black tuxedo, solid dark studio background, octane 3d render, claymation style, plastic texture, masterpiece",
    "Sir Stag": "3D animated cartoon character, a majestic dapper Stag (deer) with antlers, wearing black sunglasses and a velvet black tuxedo, solid dark studio background, octane 3d render, claymation style, plastic texture, masterpiece",
    "Shadow Panther": "3D animated cartoon character, a sleek black Panther, yellow eyes, wearing black sunglasses and a slim-fit black suit, solid dark studio background, octane 3d render, claymation style, plastic texture, masterpiece",
    "Major Eagle": "3D animated cartoon character, a sharp bald Eagle, white head feathers, yellow beak, wearing black aviator sunglasses and a black tuxedo, solid dark studio background, octane 3d render, claymation style, plastic texture, masterpiece",
    "Don Rhino": "3D animated cartoon character, a strong dapper Rhinoceros, thick skin, horn on nose, wearing black sunglasses and a double-breasted black suit, solid dark studio background, octane 3d render, claymation style, plastic texture, masterpiece",
    "Commander Wolf": "3D animated cartoon character, a stern grey Wolf, pointed ears, glowing eyes, wearing black sunglasses and a sharp tuxedo, solid dark studio background, octane 3d render, claymation style, plastic texture, masterpiece",
    "Duke Owl": "3D animated cartoon character, a wise dapper Owl, feather details, wearing black round sunglasses and a high-collar black coat suit, solid dark studio background, octane 3d render, claymation style, plastic texture, masterpiece",
    "Baron Badger": "3D animated cartoon character, a gritty honey Badger, black and white face stripes, wearing black sunglasses and a fitted black suit, solid dark studio background, octane 3d render, claymation style, plastic texture, masterpiece",
    "Chief Gorilla": "3D animated cartoon character, a powerful Silverback Gorilla, broad chest, wearing black sunglasses and a black three-piece suit, solid dark studio background, octane 3d render, claymation style, plastic texture, masterpiece",
    "Captain Tiger": "3D animated cartoon character, a dapper orange Tiger with black stripes, wearing black sunglasses and a black tuxedo, solid dark studio background, octane 3d render, claymation style, plastic texture, masterpiece",
    "Lord Cobra": "3D animated cartoon character, an elegant anthropomorphic Cobra snake, flared hood, wearing black sunglasses and a sleek silk black suit, solid dark studio background, octane 3d render, claymation style, plastic texture, masterpiece",
    "Slick Cheetah": "3D animated cartoon character, a fast sleek Cheetah with black spots, wearing black sunglasses and a slim black suit, solid dark studio background, octane 3d render, claymation style, plastic texture, masterpiece",
    "Gritty Ram": "3D animated cartoon character, a tough Ram with curved horns, wearing black sunglasses and a textured black suit, solid dark studio background, octane 3d render, claymation style, plastic texture, masterpiece",
    "General Falcon": "3D animated cartoon character, a sleek Falcon, sharp eyes, wearing black sunglasses and a tailored black suit, solid dark studio background, octane 3d render, claymation style, plastic texture, masterpiece",
    "Professor Koala": "3D animated cartoon character, a friendly dapper Koala, round fluffy ears, wearing black sunglasses and a black suit with bowtie, solid dark studio background, octane 3d render, claymation style, plastic texture, masterpiece",
    "Mr. Raccoon": "3D animated cartoon character, a clever Raccoon with mask-like eyes, wearing black sunglasses and a black tuxedo, solid dark studio background, octane 3d render, claymation style, plastic texture, masterpiece",
    "Officer Panda": "3D animated cartoon character, a dapper giant Panda, black patches around eyes, wearing black sunglasses and a sharp black suit, solid dark studio background, octane 3d render, claymation style, plastic texture, masterpiece"
}


# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/health")
def health():
    return {"status": "ok", "service": "aura-image-processor"}


@app.route("/process")
def process():
    char    = request.args.get("char", "King Leo")
    show    = request.args.get("show", "Originals")
    quote   = request.args.get("quote", "A lion does not concern himself with the opinions of sheep.")
    handle  = request.args.get("handle", "@masculine.aura")
    seed    = request.args.get("seed", "999")

    # Get prompt for character
    prompt = PROMPTS.get(char, f"3D animated cartoon character, {char} wearing elegant black tuxedo suit and sunglasses, solid dark studio background, dapper masculine aura, high detail 3d render")
    
    pollinations_url = (
        "https://image.pollinations.ai/prompt/"
        + urllib.parse.quote(prompt)
        + f"?width=1080&height=1080&nologo=true&seed={seed}&model=flux"
    )

    # Fetch base 3D image from Pollinations AI
    try:
        resp = http_requests.get(pollinations_url, timeout=60)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content))
    except Exception as e:
        return {"error": f"Failed to fetch base image: {e}"}, 500

    # Apply clean bottom banner card layout
    result = create_banner_post(img, quote, char, handle)

    # Return high quality JPEG
    buf = io.BytesIO()
    result.save(buf, format="JPEG", quality=95)
    buf.seek(0)
    return send_file(buf, mimetype="image/jpeg", download_name="aura_3d_post.jpg")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
