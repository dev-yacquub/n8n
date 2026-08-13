"""
Test multiple seeds to find the best SpongeBob render
"""
import sys, os
sys.path.insert(0, r"d:\zdiiv\vids\venv\Lib\site-packages")
os.chdir(r"d:\zdiiv\N8N\image_processor")

import io
import urllib.parse
from PIL import Image
import requests as http_requests

# Try multiple very specific prompts and seeds
prompts = {
    "spongebob_v1": "3D render of SpongeBob SquarePants, square shaped yellow sponge with rectangular flat head, big blue eyes, buck teeth smile, wearing elegant black tuxedo and black sunglasses, studio black background, Pixar quality 3D CGI",
    "spongebob_v2": "SpongeBob SquarePants 3D figurine toy, iconic square yellow sea sponge cartoon character with holes in body, buck teeth, wearing black business suit and cool sunglasses, solid dark background, 4k studio render",
    "spongebob_v3": "SpongeBob SquarePants action figure 3D render, square yellow sponge character from Nickelodeon cartoon, signature buck teeth and big eyes, dressed in black tuxedo with sunglasses, dark studio background, octane render 4k",
}

os.makedirs(r"d:\zdiiv\N8N\image_processor\sponge_tests", exist_ok=True)

for name, prompt in prompts.items():
    for seed in [1, 55, 123]:
        url = "https://image.pollinations.ai/prompt/" + urllib.parse.quote(prompt) + f"?width=1080&height=1080&nologo=true&seed={seed}&model=flux"
        print(f"Trying {name} seed={seed}...")
        resp = http_requests.get(url, timeout=60)
        if resp.status_code == 200:
            path = rf"d:\zdiiv\N8N\image_processor\sponge_tests\{name}_seed{seed}.jpg"
            with open(path, "wb") as f:
                f.write(resp.content)
            print(f"  Saved {path}")
        else:
            print(f"  Error: {resp.status_code}")

print("\nDone! Check sponge_tests folder.")
