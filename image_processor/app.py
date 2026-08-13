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
    "SpongeBob SquarePants": "3D octane render 4k, SpongeBob SquarePants wearing stylish black sunglasses and tailored tuxedo suit with red bow tie, solid black studio background, dramatic studio lighting, dapper masculine aura, high detail 3d character render, masterpiece",
    "Bugs Bunny":             "3D octane render 4k, Bugs Bunny wearing an elegant black tuxedo suit and black tie holding martini glass, solid dark studio background, cinematic lighting, dapper masculine aura, high detail 3d cartoon character, masterpiece",
    "Mickey Mouse":           "3D octane render 4k, Mickey Mouse in tailored black luxury suit with gold cufflinks and dark sunglasses, solid black background, studio lighting, masculine aura, high detail 3d render",
    "Goku":                   "3D octane render 4k, Son Goku from Dragon Ball Z wearing tailored luxury black suit with glowing golden super saiyan aura, solid dark background, studio lighting, masculine aura, masterpiece",
    "Patrick Star":           "3D octane render 4k, Patrick Star wearing dark sunglasses and custom fitted tuxedo, solid dark studio background, cinematic lighting, confident dapper pose, high detail 3d render",
    "Homer Simpson":          "3D octane render 4k, Homer Simpson wearing luxury black suit with expensive watch and dark sunglasses, solid dark studio background, sharp 3d render, masculine aura",
    "Shrek":                  "3D octane render 4k, Shrek wearing tailored black tuxedo suit and bow tie, solid dark studio background, powerful dapper masculine pose, high detail 3d render",
    "Tom Cat":                "3D octane render 4k, Tom Cat from Tom and Jerry wearing sharp black suit and sunglasses holding cigar, solid dark background, studio lighting, high detail 3d character render",
    "Jerry Mouse":            "3D octane render 4k, Jerry Mouse from Tom and Jerry wearing miniature elegant black tuxedo suit, solid dark studio background, confident masculine pose, 3d render",
    "Donald Duck":            "3D octane render 4k, Donald Duck wearing custom black tuxedo and bow tie with dark aviator sunglasses, solid dark background, studio lighting, 3d render",
    "Goofy":                  "3D octane render 4k, Goofy wearing tailored black suit and fedora hat, solid dark studio background, elegant masculine pose, high detail 3d character render",
    "Scooby-Doo":             "3D octane render 4k, Scooby-Doo wearing stylish black tuxedo collar and gold chain, solid dark studio background, confident masculine pose, high detail 3d render",
    "Garfield":               "3D octane render 4k, Garfield the cat wearing dark sunglasses and black suit jacket, solid dark studio background, laid back dapper masculine pose, 3d render",
    "Pink Panther":           "3D octane render 4k, Pink Panther wearing sleek black tuxedo suit and black sunglasses, solid dark studio background, elegant masculine aura, high detail 3d render",
    "Popeye":                 "3D octane render 4k, Popeye the sailor man wearing black suit and captain hat with pipe, solid dark studio background, powerful muscular 3d render",
    "Daffy Duck":             "3D octane render 4k, Daffy Duck wearing tailored black tuxedo suit and bowtie, solid dark studio background, confident dapper pose, 3d render",
    "Woody Woodpecker":       "3D octane render 4k, Woody Woodpecker wearing stylish black suit and sunglasses, solid dark studio background, dapper masculine pose, 3d render",
    "Fred Flintstone":        "3D octane render 4k, Fred Flintstone wearing custom black suit and tie, solid dark studio background, powerful dapper pose, high detail 3d render",
    "Rick Sanchez":           "3D octane render 4k, Rick Sanchez from Rick and Morty wearing sleek black tuxedo suit and aviator sunglasses, solid dark studio background, masculine aura 3d render",
    "Stitch":                 "3D octane render 4k, Stitch from Lilo and Stitch wearing miniature black suit and sunglasses, solid dark studio background, cool masculine pose, high detail 3d render"
}


# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/health")
def health():
    return {"status": "ok", "service": "aura-image-processor"}


@app.route("/process")
def process():
    char    = request.args.get("char", "Bugs Bunny")
    show    = request.args.get("show", "Looney Tunes")
    quote   = request.args.get("quote", "What's up, doc? I just play by my own rules.")
    handle  = request.args.get("handle", "@masculine.aura")
    seed    = request.args.get("seed", "999")

    # Get prompt for character
    prompt = PROMPTS.get(char, f"3D octane render 4k, {char} wearing elegant black tuxedo suit and sunglasses, solid dark studio background, dapper masculine aura, high detail 3d render")
    
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
