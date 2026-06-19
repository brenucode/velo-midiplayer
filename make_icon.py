"""Generates the Velo app icon (green tile + play/velocity mark) as .ico + .png.
Pure Pillow (no cairo dependency)."""
import os
from PIL import Image, ImageDraw

ACCENT = (200, 255, 77, 255)   # #C8FF4D
INK = (12, 20, 0, 255)         # #0C1400

S = 1024  # supersample then downscale for crisp edges
scale = S / 256.0

def px(v):
    return int(round(v * scale))

img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# rounded green tile
d.rounded_rectangle([(px(20), px(20)), (px(236), px(236))], radius=px(50), fill=ACCENT)

# play triangle
d.polygon([(px(62), px(72)), (px(62), px(184)), (px(140), px(128))], fill=INK)

# two velocity bars
d.rounded_rectangle([(px(156), px(72)), (px(171), px(184))], radius=px(7.5), fill=INK)
d.rounded_rectangle([(px(182), px(72)), (px(197), px(184))], radius=px(7.5), fill=INK)

outDir = os.path.join("assets", "icons")
os.makedirs(outDir, exist_ok=True)

png = img.resize((256, 256), Image.LANCZOS)
png.save(os.path.join(outDir, "velo_logo.png"))

ico_path = os.path.join(outDir, "velo.ico")
img.resize((256, 256), Image.LANCZOS).save(
    ico_path, format="ICO",
    sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
)
print("wrote", ico_path, "and velo_logo.png")
