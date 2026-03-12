"""Render Ari's ASCII face to a PNG image for ComfyUI input."""

from PIL import Image, ImageDraw, ImageFont

HAMSTER = r"""
   (\(\ /)/)
    ( ^.^ )
  * ( " ^ " ) *
     ( w )
      (   )
"""

WIDTH, HEIGHT = 1024, 1024
BG = (30, 30, 35)
FG = (255, 200, 100)

img = Image.new("RGB", (WIDTH, HEIGHT), BG)
draw = ImageDraw.Draw(img)

# Try to get a monospace font
try:
    font = ImageFont.truetype("consola.ttf", 64)
except OSError:
    try:
        font = ImageFont.truetype("cour.ttf", 64)
    except OSError:
        font = ImageFont.load_default()

lines = HAMSTER.strip().split("\n")
line_height = 72
total_height = len(lines) * line_height
y_start = (HEIGHT - total_height) // 2

for i, line in enumerate(lines):
    bbox = draw.textbbox((0, 0), line, font=font)
    text_width = bbox[2] - bbox[0]
    x = (WIDTH - text_width) // 2
    y = y_start + i * line_height
    draw.text((x, y), line, fill=FG, font=font)

out_path = "ari_face.png"
img.save(out_path)
print(f"Saved {out_path} ({WIDTH}x{HEIGHT})")
