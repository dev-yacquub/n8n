import os
import io
import textwrap
import urllib.request
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
            urllib.request.urlretrieve(url, path)
            print(f"Saved to {path}")

try:
    download_fonts()
except Exception as e:
    print(f"Font download failed: {e}")

# ── Image processing ─────────────────────────────────────────────────────────
def add_quote_overlay(img: Image.Image, quote: str, character: str, handle: str = "@masculine.aura") -> Image.Image:
    img = img.convert("RGBA")
    W, H = img.size

    # Load fonts with fallback
    try:
        font_quote   = ImageFont.truetype(BOLD_PATH, 52)
        font_name    = ImageFont.truetype(BOLD_PATH, 36)
        font_handle  = ImageFont.truetype(REGULAR_PATH, 28)
    except Exception:
        font_quote   = ImageFont.load_default()
        font_name    = font_quote
        font_handle  = font_quote

    GOLD   = (218, 165, 32, 255)
    WHITE  = (255, 255, 255, 255)
    BLACK  = (0, 0, 0, 255)

    # Wrap quote text
    wrapped = textwrap.wrap(f'"{quote}"', width=22)

    PAD        = 32
    LINE_H     = 65
    BOX_W      = 660
    BOX_H      = PAD * 2 + len(wrapped) * LINE_H + 90
    BOX_X, BOX_Y = 40, 40

    # ── Draw semi-transparent box ──────────────────────────────────────────
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

    # ── Quote text ─────────────────────────────────────────────────────────
    text_x = BOX_X + PAD
    text_y = BOX_Y + PAD
    for i, line in enumerate(wrapped):
        draw.text(
            (text_x + 2, text_y + i * LINE_H + 2),   # shadow
            line, font=font_quote, fill=(0, 0, 0, 160)
        )
        draw.text(
            (text_x, text_y + i * LINE_H),
            line, font=font_quote, fill=WHITE
        )

    # ── Character name in gold ─────────────────────────────────────────────
    name_y = BOX_Y + BOX_H - 85
    draw.text((text_x, name_y), f"\u25a0  {character}", font=font_name, fill=GOLD)

    # ── Handle pill badge ──────────────────────────────────────────────────
    handle_y = BOX_Y + BOX_H - 46
    dummy_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    bbox = dummy_draw.textbbox((0, 0), handle, font=font_handle)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pill_pad_x, pill_pad_y = 14, 6
    pill = [text_x, handle_y, text_x + tw + pill_pad_x * 2, handle_y + th + pill_pad_y * 2]
    draw.rounded_rectangle(pill, radius=12, fill=(218, 165, 32, 235))
    draw.text((text_x + pill_pad_x, handle_y + pill_pad_y), handle, font=font_handle, fill=BLACK)

    return img.convert("RGB")


# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/health")
def health():
    return {"status": "ok", "service": "aura-image-processor"}


@app.route("/process")
def process():
    """
    Query params:
      char      - character name, e.g. "Itachi Uchiha"
      show      - show name, e.g. "Naruto"
      quote     - the motivational quote
      handle    - instagram handle, default @aura.clips
      seed      - random seed for image variety
    """
    char    = request.args.get("char", "Goku")
    show    = request.args.get("show", "Dragon Ball Z")
    quote   = request.args.get("quote", "Aura is not inherited. It is built in the shadows.")
    handle  = request.args.get("handle", "@masculine.aura")
    seed    = request.args.get("seed", "1")

    # Character → image prompt mapping
    prompts = {
        "Goku":           "Son Goku from Dragon Ball Z, golden super saiyan aura blazing, sitting cross-legged meditation, dramatic golden energy, dark stormy sky, ultra cinematic",
        "Itachi Uchiha":  "Itachi Uchiha from Naruto, Akatsuki cloak, Sharingan eyes red, dark misty forest, arms folded, purple black aura silhouette, ultra cinematic",
        "Vegeta":         "Vegeta from Dragon Ball Z, royal blue super saiyan aura, arms crossed, arrogant stoic, dark space planets, ultra cinematic",
        "Madara Uchiha":  "Madara Uchiha from Naruto Shippuden, Rinnegan purple, susanoo ribcage, dark red black aura, standing on rubble, god-like, ultra cinematic anime art",
        "Levi Ackerman":  "Levi Ackerman from Attack on Titan, ODM gear, cold steel grey eyes, dark rainy rooftop, silver aura, stoic elite, ultra cinematic",
        "Saitama":        "Saitama from One Punch Man, bald yellow cape, calmly meditating, invisible overwhelming aura cracking ground, ultra cinematic",
        "Zoro":           "Roronoa Zoro from One Piece, three swords across lap, dark green Conqueror Haki aura, meditation, ultra cinematic",
        "Sukuna":         "Ryomen Sukuna from Jujutsu Kaisen, four arms tattoos, pink cursed energy aura, sitting throne skulls, ultra cinematic anime",
        "Gojo Satoru":    "Gojo Satoru from Jujutsu Kaisen, six eyes revealed, limitless infinity light blue aura, confident smile, dark void, ultra cinematic",
        "Meruem":         "Meruem from Hunter x Hunter, dark royal purple aura, throne, cold calculating expression, overwhelming presence, ultra cinematic anime",
        "Aizen Sosuke":   "Sosuke Aizen from Bleach, glasses removed, golden spiritual pressure aura, calm omnipotent, ultra cinematic",
        "Eren Yeager":    "Eren Yeager from Attack on Titan final season, long black hair, green eyes, Founding Titan dark energy aura, ruins, ultra cinematic",
        "Sasuke Uchiha":  "Sasuke Uchiha from Naruto, Rinnegan Sharingan, dark blue purple Indra chakra aura, moon, lightning, ultra cinematic anime",
        "Killua Zoldyck": "Killua Zoldyck from Hunter x Hunter, silver hair, godspeed electricity blue white aura, calm assassin, ultra cinematic",
        "Pain Nagato":    "Pain Nagato from Naruto, Rinnegan eyes, levitating, metallic piercings, purple gravity aura, rain, ultra cinematic",
        "Tanjiro Kamado": "Tanjiro Kamado from Demon Slayer, checkered haori, sun breathing aura gold blue, meditation sunrise, ultra cinematic anime",
        "Mob":            "Shigeo Mob from Mob Psycho 100, 100 percent power, white hair floating, psychic white energy aura, dramatic, ultra cinematic",
        "Whitebeard":     "Edward Whitebeard from One Piece, enormous frame, Conqueror Haki black lightning, throne, bisento, ultra cinematic",
        "Giorno Giovanna":"Giorno Giovanna from JoJo Bizarre Adventure, golden aura, white suit, life energy radiating, ultra cinematic",
        "Luffy Gear 5":   "Monkey D Luffy Gear 5, white hair clothes, Nika sun god gold aura, laughing freely, clouds parting, ultra cinematic"
    }

    prompt = prompts.get(char, f"{char} from {show}, dramatic aura energy field, ultra cinematic anime art")
    pollinations_url = (
        "https://image.pollinations.ai/prompt/"
        + urllib.request.pathname2url(prompt)
        + f"?width=1080&height=1080&nologo=true&seed={seed}&model=flux"
    )

    # Download image from Pollinations
    try:
        resp = http_requests.get(pollinations_url, timeout=60)
        resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content))
    except Exception as e:
        return {"error": f"Failed to fetch base image: {e}"}, 500

    # Add styled overlay
    result = add_quote_overlay(img, quote, char, handle)

    # Return as JPEG
    buf = io.BytesIO()
    result.save(buf, format="JPEG", quality=92)
    buf.seek(0)
    return send_file(buf, mimetype="image/jpeg", download_name="aura_post.jpg")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
