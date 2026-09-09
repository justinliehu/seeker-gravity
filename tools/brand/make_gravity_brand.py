#!/usr/bin/env python3
"""Seeker Gravity brand art, generated so nothing of the original ROTA / Harmony Monroe identity ships.

Outputs (all inside the project):
  media/image/UI/title.png                 title-screen wordmark (replaces ROTA's, same slot/size class)
  media/image/UI/credit-rota.png           "ROTA by Harmony Monroe" attribution mark used in the credits list
  media/image/UI/splash.png                boot splash (black background, wordmark)
  media/image/icon/icon256.png, icon192.png, icon512.png, adaptive_fg_432.png, adaptive_bg_432.png
  store-assets/icon-512.png, banner-1200x600.png, feature-1200x1200.png

Font: Alexandria 900 (SIL OFL, already in media/font). Palette: the game's own sky blues + gem purple.
Run:  python tools/brand/make_gravity_brand.py
"""
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import math
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
FONT = ROOT / "media/font/alexandria-latin-900-normal.ttf"
UI = ROOT / "media/image/UI"
ICON = ROOT / "media/image/icon"
STORE = ROOT / "store-assets"

WHITE = (255, 255, 255, 255)
SKY_TOP = (61, 205, 255)
SKY_BOT = (13, 92, 255)
GEM = (196, 84, 255, 255)
GOLD = (255, 214, 68, 255)
INK = (20, 12, 40, 255)


def font(size):
    return ImageFont.truetype(str(FONT), size)


def text_size(draw, s, f):
    x0, y0, x1, y1 = draw.textbbox((0, 0), s, font=f)
    return x1 - x0, y1 - y0, x0, y0


def orbit_glyph(size, stroke, color=WHITE):
    """A ring with two arrowheads chasing each other - the 'bend gravity' motif, our own drawing."""
    s = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = stroke
    box = [pad, pad, s - pad, s - pad]
    d.arc(box, start=200, end=340, fill=color, width=stroke)
    d.arc(box, start=20, end=160, fill=color, width=stroke)
    r = (s - 2 * pad) / 2.0
    cx = cy = s / 2.0
    for ang, sign in ((340, 1), (160, 1)):
        a = math.radians(ang)
        tip = (cx + r * math.cos(a), cy + r * math.sin(a))
        # arrowhead pointing along the arc direction (clockwise)
        t = a + math.radians(90) * sign
        L = stroke * 2.4
        p1 = (tip[0] + L * math.cos(t - 0.55), tip[1] + L * math.sin(t - 0.55))
        p2 = (tip[0] + L * math.cos(t + 0.55), tip[1] + L * math.sin(t + 0.55))
        d.polygon([tip, p1, p2], fill=color)
    return img


def wordmark(width_hint=1300, accent=True):
    """'SEEKER' small over 'GRAVITY' big, orbit glyph standing in for the O. Transparent background."""
    big = font(int(width_hint * 0.19))
    small = font(int(width_hint * 0.075))
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    gw, gh, gx0, gy0 = text_size(probe, "GRAVITY", big)
    sw, sh, sx0, sy0 = text_size(probe, "SEEKER", small)
    W = int(gw + width_hint * 0.06)
    H = int(sh + gh + width_hint * 0.10)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # small line, centred, tracked
    x = (W - sw) / 2.0
    d.text((x - sx0, int(width_hint * 0.02) - sy0), "SEEKER", font=small, fill=WHITE)
    # big line
    gy = int(sh + width_hint * 0.06)
    gx = (W - gw) / 2.0
    d.text((gx - gx0, gy - gy0), "GRAVITY", font=big, fill=WHITE)
    # replace the second letter 'R'? no - drop the orbit ring over the 'A' counter as an accent
    # find the A's approximate x: measure 'GR' prefix width
    prefix_w = probe.textlength("GR", font=big)
    a_w = probe.textlength("A", font=big)
    if accent:
        ring = orbit_glyph(int(a_w * 0.62), max(6, int(width_hint * 0.012)), GOLD)
        img.alpha_composite(ring, (int(gx + prefix_w + a_w * 0.19), int(gy + gh * 0.36)))
    return img


def rounded_gradient(px, radius_ratio=0.22):
    img = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    grad = Image.new("RGBA", (px, px))
    gd = ImageDraw.Draw(grad)
    for y in range(px):
        t = y / max(1, px - 1)
        c = tuple(int(SKY_TOP[i] * (1 - t) + SKY_BOT[i] * t) for i in range(3)) + (255,)
        gd.line([(0, y), (px, y)], fill=c)
    mask = Image.new("L", (px, px), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, px - 1, px - 1], radius=int(px * radius_ratio), fill=255)
    img.paste(grad, (0, 0), mask)
    return img


def icon(px, with_bg=True):
    """Our own mark: a floating cube tilted by gravity with the orbit ring - not ROTA's X-on-a-stem."""
    base = rounded_gradient(px) if with_bg else Image.new("RGBA", (px, px), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)
    cx, cy = px / 2.0, px / 2.0
    # cube: rotated square with a face highlight
    s = px * 0.34
    ang = math.radians(12)
    pts = []
    for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        x = dx * s / 2.0
        y = dy * s / 2.0
        pts.append((cx + x * math.cos(ang) - y * math.sin(ang), cy + px * 0.06 + x * math.sin(ang) + y * math.cos(ang)))
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).polygon([(x + px * 0.02, y + px * 0.04) for x, y in pts], fill=(0, 0, 60, 120))
    base.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(px * 0.02)))
    d.polygon(pts, fill=GEM)
    inner = [(cx + (x - cx) * 0.62, cy + px * 0.06 + (y - cy - px * 0.06) * 0.62 - px * 0.04) for x, y in pts]
    d.polygon(inner, fill=(232, 170, 255, 255))
    ring = orbit_glyph(int(px * 0.78), max(4, int(px * 0.06)), WHITE)
    base.alpha_composite(ring, (int(cx - ring.width / 2), int(cy - ring.height / 2 + px * 0.02)))
    return base


def main():
    for p in (UI, ICON, STORE):
        p.mkdir(parents=True, exist_ok=True)

    wm = wordmark(1300)
    flat = wordmark(1300, accent=False)
    # title slot: ROTA's title.png was 650x220 drawn at scale 0.9; ours keeps a similar footprint
    title = flat.resize((int(flat.width * 0.5), int(flat.height * 0.5)), Image.LANCZOS)
    title.save(UI / "title.png")

    # attribution mark for the credits list ("a game by" -> this image)
    f = font(56)
    probe = ImageDraw.Draw(Image.new("RGBA", (10, 10)))
    txt = "ROTA by Harmony Monroe"
    w, h, x0, y0 = text_size(probe, txt, f)
    credit = Image.new("RGBA", (w + 40, h + 30), (0, 0, 0, 0))
    ImageDraw.Draw(credit).text((20 - x0, 15 - y0), txt, font=f, fill=WHITE)
    credit.save(UI / "credit-rota.png")

    # boot splash
    splash = Image.new("RGBA", (1920, 1080), INK)
    sw = wm.resize((int(wm.width * 0.8), int(wm.height * 0.8)), Image.LANCZOS)
    splash.alpha_composite(sw, ((1920 - sw.width) // 2, (1080 - sw.height) // 2))
    splash.convert("RGB").save(UI / "splash.png")

    for px in (256, 192, 512):
        icon(px).save(ICON / f"icon{px}.png")
    icon(432, with_bg=False).save(ICON / "adaptive_fg_432.png")
    rounded_gradient(432, 0.0).save(ICON / "adaptive_bg_432.png")

    icon(512).save(STORE / "icon-512.png")
    for size, name in (((1200, 600), "banner-1200x600.png"), ((1200, 1200), "feature-1200x1200.png")):
        W, H = size
        bg = Image.new("RGBA", size)
        gd = ImageDraw.Draw(bg)
        for y in range(H):
            t = y / (H - 1)
            c = tuple(int(SKY_TOP[i] * (1 - t) + SKY_BOT[i] * t) for i in range(3)) + (255,)
            gd.line([(0, y), (W, y)], fill=c)
        ic = icon(int(H * 0.5), with_bg=False)
        mark = wm.resize((int(W * 0.55), int(wm.height * (W * 0.55) / wm.width)), Image.LANCZOS)
        if W > H:
            bg.alpha_composite(ic, (int(W * 0.06), (H - ic.height) // 2))
            bg.alpha_composite(mark, (int(W * 0.40), (H - mark.height) // 2))
        else:
            bg.alpha_composite(ic, ((W - ic.width) // 2, int(H * 0.10)))
            bg.alpha_composite(mark, ((W - mark.width) // 2, int(H * 0.66)))
        bg.convert("RGB").save(STORE / name)

    for p in sorted(list(UI.glob("title.png")) + list(UI.glob("credit-rota.png")) + list(UI.glob("splash.png"))
                    + list(ICON.glob("*.png")) + list(STORE.glob("*.png"))):
        print("  %-46s %s" % (p.relative_to(ROOT), Image.open(p).size))


if __name__ == "__main__":
    main()
