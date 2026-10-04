"""Compose marketplace Thumbnail (1920x960) and Gallery (1920x960) images
from raw widget screenshots, matching the widget's own dark theme.

Usage:
  1. Open CrealityMonitor_Template/index.html in a browser, inject sample
     `data`/`settings` and call `render()` to reach the desired visual state
     (see the session notes for the exact snippets used).
  2. Save full-page screenshots next to this script (e.g. shot_printing.png,
     shot_complete.png).
  3. Run `python tools/compose_media.py` from the repo root.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H = 1920, 960
BG_TOP = (10, 13, 18)
BG_BOTTOM = (5, 7, 10)
FONT_DIR = r"C:\Windows\Fonts"
ROOT = Path(__file__).resolve().parent.parent
MEDIA_DIR = ROOT / "media"


def vertical_gradient(size, top, bottom):
    w, h = size
    base = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(h - 1, 1)
        px = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        base.putpixel((0, y), px)
    return base.resize((w, h))


def rounded_mask(size, radius):
    mask = Image.new("L", size, 0)
    d = ImageDraw.Draw(mask)
    d.rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=255)
    return mask


def soft_glow(size, color, blur):
    glow = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(glow)
    d.ellipse([size[0] * 0.15, -size[1] * 0.4, size[0] * 0.85, size[1] * 0.6], fill=color)
    return glow.filter(ImageFilter.GaussianBlur(blur))


def paste_card(canvas, shot_path, accent, scale=1.0, y_offset=0):
    shot = Image.open(shot_path).convert("RGB")
    sw, sh = shot.size
    target_w = int(1660 * scale)
    target_h = int(sh * (target_w / sw))
    shot = shot.resize((target_w, target_h), Image.LANCZOS)

    mask = rounded_mask(shot.size, 18)
    shadow = Image.new("RGBA", (shot.width + 80, shot.height + 80), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle([40, 48, 40 + shot.width, 48 + shot.height], radius=22,
                          fill=(0, 0, 0, 160))
    shadow = shadow.filter(ImageFilter.GaussianBlur(28))

    x = (W - shot.width) // 2
    y = (H - shot.height) // 2 + y_offset
    canvas.paste(shadow, (x - 40, y - 40), shadow)
    canvas.paste(shot, (x, y), mask)
    return x, y, shot.width, shot.height


def build(out_path, shot_path, accent, title=None, subtitle=None, badge=None):
    canvas = vertical_gradient((W, H), BG_TOP, BG_BOTTOM).convert("RGBA")

    glow = soft_glow((W, H), accent + (70,), 180)
    canvas.alpha_composite(glow)

    # subtle grid texture
    grid = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(grid)
    for gx in range(0, W, 64):
        gd.line([(gx, 0), (gx, H)], fill=(255, 255, 255, 5))
    for gy in range(0, H, 64):
        gd.line([(0, gy), (W, gy)], fill=(255, 255, 255, 5))
    canvas.alpha_composite(grid)

    y_offset = 40 if title else 0
    paste_card(canvas, shot_path, accent, scale=1.0, y_offset=y_offset)

    draw = ImageDraw.Draw(canvas)
    if title:
        font_title = ImageFont.truetype(FONT_DIR + r"\seguibl.ttf", 64)
        font_sub = ImageFont.truetype(FONT_DIR + r"\segoeui.ttf", 30)
        tw = draw.textlength(title, font=font_title)
        draw.text(((W - tw) / 2, 56), title, font=font_title, fill=(255, 255, 255, 255))
        if subtitle:
            sw = draw.textlength(subtitle, font=font_sub)
            draw.text(((W - sw) / 2, 134), subtitle, font=font_sub,
                       fill=(190, 200, 210, 255))

    if badge:
        font_badge = ImageFont.truetype(FONT_DIR + r"\seguisb.ttf", 26)
        bw = draw.textlength(badge, font=font_badge)
        pad = 18
        bx0, by0 = W - bw - pad * 2 - 36, H - 70
        badge_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        bdraw = ImageDraw.Draw(badge_layer)
        bdraw.rounded_rectangle([bx0, by0, bx0 + bw + pad * 2, by0 + 44], radius=22,
                                 fill=(10, 13, 18, 210), outline=accent + (255,), width=2)
        bdraw.text((bx0 + pad, by0 + 9), badge, font=font_badge, fill=(255, 255, 255, 255))
        canvas.alpha_composite(badge_layer)

    canvas.convert("RGB").save(out_path, quality=95)
    print("saved", out_path)


ACCENT_BLUE = (0, 179, 255)
ACCENT_GREEN = (46, 227, 107)

MEDIA_DIR.mkdir(exist_ok=True)

build(
    str(MEDIA_DIR / "thumbnail.png"), str(ROOT / "shot_printing.png"), ACCENT_BLUE,
    title="Creality Monitor",
    subtitle="Real-time K-Series printer monitoring for Corsair iCUE",
)

build(
    str(MEDIA_DIR / "gallery-complete.png"), str(ROOT / "shot_complete.png"), ACCENT_GREEN,
    badge="Creality Monitor",
)
