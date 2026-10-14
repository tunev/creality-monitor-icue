"""Composes the Marketplace thumbnail + gallery images (1920x960 PNG) from real renders of
the widget (see render_shots.py). Each image = real widget screenshot + one short caption.

Usage (from repo root):
  python tools/render_shots.py
  python tools/compose_media.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1920, 960
BG_TOP = (10, 13, 18)
BG_BOTTOM = (5, 7, 10)
FONT_DIR = r"C:\Windows\Fonts"
ROOT = Path(__file__).resolve().parent.parent
SHOTS = Path(__file__).resolve().parent / "_shots"
MEDIA_DIR = ROOT / "media"

ACCENT_BLUE = (0, 179, 255)
ACCENT_GREEN = (46, 227, 107)
ACCENT_AMBER = (255, 176, 32)
ACCENT_RED = (255, 59, 59)

CARD_W = 1350  # widget card width on the 1920 canvas (16:9 -> 759 tall)


def vertical_gradient(size, top, bottom):
    w, h = size
    base = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        base.putpixel((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return base.resize((w, h))


def rounded_mask(size, radius):
    mask = Image.new("L", size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=255)
    return mask


def soft_glow(size, color, blur):
    glow = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([size[0] * 0.15, -size[1] * 0.4, size[0] * 0.85, size[1] * 0.6], fill=color)
    return glow.filter(ImageFilter.GaussianBlur(blur))


def paste_card(canvas, shot_path, y):
    shot = Image.open(shot_path).convert("RGB")
    shot = shot.resize((CARD_W, round(shot.height * CARD_W / shot.width)), Image.LANCZOS)
    mask = rounded_mask(shot.size, 20)
    shadow = Image.new("RGBA", (shot.width + 120, shot.height + 120), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        [60, 70, 60 + shot.width, 70 + shot.height], radius=24, fill=(0, 0, 0, 170)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(30))
    x = (W - shot.width) // 2
    canvas.paste(shadow, (x - 60, y - 60), shadow)
    canvas.paste(shot, (x, y), mask)


def build(out_name, shot_name, accent, title, subtitle):
    canvas = vertical_gradient((W, H), BG_TOP, BG_BOTTOM).convert("RGBA")
    canvas.alpha_composite(soft_glow((W, H), accent + (70,), 180))

    grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grid)
    for gx in range(0, W, 64):
        gd.line([(gx, 0), (gx, H)], fill=(255, 255, 255, 5))
    for gy in range(0, H, 64):
        gd.line([(0, gy), (W, gy)], fill=(255, 255, 255, 5))
    canvas.alpha_composite(grid)

    paste_card(canvas, SHOTS / shot_name, 168)

    draw = ImageDraw.Draw(canvas)
    font_title = ImageFont.truetype(FONT_DIR + r"\seguibl.ttf", 62)
    font_sub = ImageFont.truetype(FONT_DIR + r"\segoeui.ttf", 30)
    tw = draw.textlength(title, font=font_title)
    draw.text(((W - tw) / 2, 28), title, font=font_title, fill=(255, 255, 255, 255))
    sw = draw.textlength(subtitle, font=font_sub)
    draw.text(((W - sw) / 2, 108), subtitle, font=font_sub, fill=(190, 200, 210, 255))

    MEDIA_DIR.mkdir(exist_ok=True)
    out = MEDIA_DIR / out_name
    canvas.convert("RGB").save(out, "PNG", optimize=True)
    print("saved", out)


build("thumbnail.png", "shot_printing.png", ACCENT_BLUE,
      "Creality Monitor", "Real-time K-Series printer monitoring for Corsair iCUE")
build("gallery-1-printing.png", "shot_printing.png", ACCENT_BLUE,
      "Live print progress", "Progress ring with layer count, elapsed and remaining time")
build("gallery-2-heating.png", "shot_heating.png", ACCENT_BLUE,
      "Nozzle and bed temperatures", "Current and target values with progress bars, plus chamber and filament")
build("gallery-3-paused.png", "shot_paused.png", ACCENT_AMBER,
      "Printer state at a glance", "Printing, paused, complete or failed \u2014 always visible in the header")
build("gallery-4-complete.png", "shot_complete.png", ACCENT_GREEN,
      "Print complete", "Know the moment your print is finished")
build("gallery-5-failed.png", "shot_failed.png", ACCENT_RED,
      "Failed prints are flagged", "A red FAILED pill shows the moment something goes wrong")

if (SHOTS / "shot_camera.png").exists():
    build("gallery-6-camera.png", "shot_camera.png", ACCENT_BLUE,
          "Live camera", "Optional WebRTC camera feed from the printer")
