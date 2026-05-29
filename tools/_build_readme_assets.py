"""
_build_readme_assets.py — Generate Apple-aesthetic PNGs for the README.

Run once whenever the visual identity changes:
  python tools/_build_readme_assets.py

Outputs (written to docs/):
  hero.png            — wordmark + tagline
  pipeline.png        — 5-step flow
  report-preview.png  — email + PDF mockup
  metrics.png         — 4 metric cards
  architecture.png    — WAT framework stack
"""

from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE_DIR = Path(__file__).parent.parent
DOCS_DIR = BASE_DIR / "docs"
DOCS_DIR.mkdir(exist_ok=True)

# ---------- Design system ----------

BG = (255, 255, 255)
PANEL = (245, 245, 247)
HAIRLINE = (210, 210, 215)
INK = (29, 29, 31)
INK_SOFT = (110, 110, 115)
INK_MUTED = (160, 160, 165)
ACCENT = (0, 113, 227)
ACCENT_SOFT = (0, 113, 227, 28)

SF = "/System/Library/Fonts/SFNS.ttf"
SF_MONO = "/System/Library/Fonts/SFNSMono.ttf"
HELV = "/System/Library/Fonts/Helvetica.ttc"


def font(size: int, weight: str = "regular") -> ImageFont.FreeTypeFont:
    # SFNS.ttf is a variable font; PIL picks default instance. For weight we fall back to size-derived hierarchy.
    try:
        f = ImageFont.truetype(SF, size)
        return f
    except Exception:
        return ImageFont.truetype(HELV, size)


def mono(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(SF_MONO, size)
    except Exception:
        return ImageFont.load_default()


# ---------- Helpers ----------

def new_canvas(w: int, h: int, bg=BG) -> Image.Image:
    return Image.new("RGB", (w, h), bg)


def rounded_rect(img: Image.Image, xy, radius: int, fill=None, outline=None, width: int = 1):
    ImageDraw.Draw(img).rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def drop_shadow(card_size: tuple[int, int], radius: int, blur: int = 22, opacity: int = 22) -> Image.Image:
    """Return an RGBA shadow blob the size of card+padding to paste behind a rounded card."""
    pad = blur * 2
    w, h = card_size
    shadow = Image.new("RGBA", (w + pad * 2, h + pad * 2), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle(
        (pad, pad + 6, pad + w, pad + h + 6),
        radius=radius,
        fill=(0, 0, 0, opacity),
    )
    return shadow.filter(ImageFilter.GaussianBlur(blur))


def paste_card(canvas: Image.Image, top_left: tuple[int, int], size: tuple[int, int],
               radius: int = 20, fill=BG, border=HAIRLINE, shadow_opacity: int = 22):
    x, y = top_left
    w, h = size
    sh = drop_shadow((w, h), radius, blur=22, opacity=shadow_opacity)
    canvas.paste(sh, (x - 44, y - 44), sh)
    rounded_rect(canvas, (x, y, x + w, y + h), radius, fill=fill, outline=border, width=1)


def text_center(draw: ImageDraw.ImageDraw, xy, text: str, fnt, fill):
    w = draw.textlength(text, font=fnt)
    x, y = xy
    draw.text((x - w / 2, y), text, font=fnt, fill=fill)


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=fnt)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


# ---------- Asset 1: HERO ----------

def build_hero():
    W, H = 1600, 600
    img = new_canvas(W, H, BG)
    d = ImageDraw.Draw(img)

    # subtle gradient panel behind wordmark
    grad = Image.new("RGB", (W, H), BG)
    gd = ImageDraw.Draw(grad)
    for i in range(H):
        t = i / H
        r = int(255 - 8 * t)
        g = int(255 - 6 * t)
        b = int(255 - 2 * t)
        gd.line([(0, i), (W, i)], fill=(r, g, b))
    img.paste(grad)

    # small accent pill
    pill_text = "WEEKLY · AI / AUTOMATION"
    pf = font(20)
    pw = d.textlength(pill_text, font=pf)
    ph = 44
    px = (W - pw) / 2 - 22
    py = 170
    rounded_rect(img, (px, py, px + pw + 44, py + ph), radius=22,
                 fill=(245, 245, 247), outline=HAIRLINE, width=1)
    d.text((px + 22, py + 11), pill_text, font=pf, fill=INK_SOFT)

    # wordmark
    title = "YouTube Trend Pulse"
    tf = font(108)
    text_center(d, (W / 2, 240), title, tf, INK)

    # tagline
    tag = "A weekly AI & automation trend report — in your inbox."
    text_center(d, (W / 2, 380), tag, font(34), INK_SOFT)

    # delicate accent underline
    line_w = 80
    d.rectangle(((W - line_w) / 2, 460, (W + line_w) / 2, 463), fill=ACCENT)

    img.save(DOCS_DIR / "hero.png", optimize=True)
    print("✓ hero.png")


# ---------- Asset 2: PIPELINE ----------

def build_pipeline():
    W, H = 1600, 420
    img = new_canvas(W, H, BG)
    d = ImageDraw.Draw(img)

    steps = [
        ("01", "Discover", "YouTube API"),
        ("02", "Analyze", "Claude Sonnet"),
        ("03", "Visualize", "matplotlib"),
        ("04", "Compose", "reportlab PDF"),
        ("05", "Deliver", "Gmail SMTP"),
    ]

    card_w, card_h = 240, 240
    gap = (W - card_w * 5) // 6
    y = (H - card_h) // 2

    for i, (num, label, sub) in enumerate(steps):
        x = gap + i * (card_w + gap)
        paste_card(img, (x, y), (card_w, card_h), radius=24, fill=BG, shadow_opacity=20)

        # number chip
        nf = mono(18)
        d.text((x + 24, y + 22), num, font=nf, fill=INK_MUTED)

        # label
        lf = font(34)
        d.text((x + 24, y + 100), label, font=lf, fill=INK)

        # sub
        sf = font(20)
        d.text((x + 24, y + 152), sub, font=sf, fill=INK_SOFT)

        # tiny accent dot
        d.ellipse((x + 24, y + 200, x + 32, y + 208), fill=ACCENT)

        # arrow (between cards)
        if i < len(steps) - 1:
            ax = x + card_w + gap // 2
            ay = y + card_h // 2
            d.line([(ax - 14, ay), (ax + 14, ay)], fill=HAIRLINE, width=2)
            d.polygon([(ax + 14, ay - 5), (ax + 22, ay), (ax + 14, ay + 5)], fill=HAIRLINE)

    img.save(DOCS_DIR / "pipeline.png", optimize=True)
    print("✓ pipeline.png")


# ---------- Asset 3: REPORT PREVIEW ----------

def build_report_preview():
    W, H = 1400, 900
    img = new_canvas(W, H, PANEL)

    # Email card (left)
    ex, ey, ew, eh = 80, 100, 560, 720
    paste_card(img, (ex, ey), (ew, eh), radius=28, fill=BG, shadow_opacity=28)
    d = ImageDraw.Draw(img)

    # Email "header"
    d.text((ex + 40, ey + 40), "Inbox", font=font(22), fill=INK_MUTED)
    d.text((ex + 40, ey + 80), "Your YouTube Trend Report", font=font(34), fill=INK)
    d.text((ex + 40, ey + 130), "trend-pulse@you.com  ·  May 29", font=font(20), fill=INK_SOFT)

    # divider
    d.line([(ex + 40, ey + 180), (ex + ew - 40, ey + 180)], fill=HAIRLINE, width=1)

    # email body
    body_y = ey + 220
    d.text((ex + 40, body_y), "AT A GLANCE", font=font(18), fill=INK_MUTED)
    d.text((ex + 40, body_y + 32), "312 videos · 48 channels", font=font(28), fill=INK)
    d.text((ex + 40, body_y + 70), "84M total views", font=font(28), fill=INK)

    d.text((ex + 40, body_y + 150), "WHAT'S TRENDING", font=font(18), fill=INK_MUTED)
    trends = [
        "Multi-agent orchestration",
        "n8n vs Make showdowns",
        "Cursor / Claude Code workflows",
        "Local LLM deployments",
    ]
    for i, t in enumerate(trends):
        ty = body_y + 190 + i * 42
        d.ellipse((ex + 40, ty + 12, ex + 48, ty + 20), fill=ACCENT)
        d.text((ex + 64, ty), t, font=font(24), fill=INK)

    # attachment chip
    chip_y = ey + eh - 100
    cx, cw, chh = ex + 40, ew - 80, 60
    rounded_rect(img, (cx, chip_y, cx + cw, chip_y + chh), radius=14,
                 fill=PANEL, outline=HAIRLINE, width=1)
    d.text((cx + 20, chip_y + 16), "📎  trend-report.pdf  ·  14 pages", font=font(20), fill=INK)

    # PDF card (right) — mock cover
    px, py, pw, ph = 720, 100, 600, 720
    paste_card(img, (px, py), (pw, ph), radius=28, fill=(20, 20, 24), shadow_opacity=36, border=(40, 40, 48))
    # dark PDF cover
    dd = ImageDraw.Draw(img)
    dd.text((px + 40, py + 60), "VOL. 21", font=font(20), fill=(140, 140, 150))
    dd.text((px + 40, py + 100), "Trend Pulse", font=font(72), fill=(255, 255, 255))
    dd.text((px + 40, py + 200), "AI · Automation", font=font(28), fill=(180, 180, 195))
    dd.text((px + 40, py + 250), "May 29, 2026", font=font(28), fill=(180, 180, 195))

    # accent line on PDF
    dd.rectangle((px + 40, py + 330, px + 120, py + 333), fill=(123, 156, 255))

    # mock chart panel
    rounded_rect(img, (px + 40, py + 380, px + pw - 40, py + ph - 60), radius=16,
                 fill=(30, 30, 38), outline=(50, 50, 60), width=1)
    # mock bars
    for i in range(6):
        bx = px + 80 + i * 70
        bh = 30 + i * 22
        dd.rectangle((bx, py + ph - 100 - bh, bx + 50, py + ph - 100), fill=(123, 156, 255))

    dd.text((px + 60, py + 410), "VIEW VELOCITY", font=font(18), fill=(180, 180, 195))

    img.save(DOCS_DIR / "report-preview.png", optimize=True)
    print("✓ report-preview.png")


# ---------- Asset 4: METRICS ----------

def build_metrics():
    W, H = 1600, 520
    img = new_canvas(W, H, BG)
    d = ImageDraw.Draw(img)

    metrics = [
        ("View Velocity", "views / age", "Fast-rising content,\nregardless of age"),
        ("Engagement", "(likes + comments) / views", "Content that\nactually resonates"),
        ("Views / Sub", "views / subscribers", "Small channels\npunching above weight"),
        ("Cadence", "videos in window", "Most active creators\nin the niche"),
    ]

    card_w, card_h = 340, 360
    gap = (W - card_w * 4) // 5
    y = (H - card_h) // 2

    for i, (name, formula, desc) in enumerate(metrics):
        x = gap + i * (card_w + gap)
        paste_card(img, (x, y), (card_w, card_h), radius=24, fill=BG, shadow_opacity=20)

        # tiny index
        d.text((x + 30, y + 26), f"0{i+1}", font=mono(18), fill=INK_MUTED)

        # name
        d.text((x + 30, y + 80), name, font=font(32), fill=INK)

        # formula in mono with light bg — auto-shrink to fit
        formula_bg_y = y + 150
        rounded_rect(img, (x + 30, formula_bg_y, x + card_w - 30, formula_bg_y + 48),
                     radius=10, fill=PANEL)
        inner_w = card_w - 60 - 28  # 14px side padding inside chip
        fsize = 18
        while fsize > 12 and d.textlength(formula, font=mono(fsize)) > inner_w:
            fsize -= 1
        d.text((x + 44, formula_bg_y + 14), formula, font=mono(fsize), fill=ACCENT)

        # description (2-line)
        for j, line in enumerate(desc.split("\n")):
            d.text((x + 30, y + 240 + j * 32), line, font=font(20), fill=INK_SOFT)

    img.save(DOCS_DIR / "metrics.png", optimize=True)
    print("✓ metrics.png")


# ---------- Asset 5: ARCHITECTURE ----------

def build_architecture():
    W, H = 1400, 760
    img = new_canvas(W, H, BG)
    d = ImageDraw.Draw(img)

    layers = [
        ("Workflows", "workflows/*.md", "Plain-language SOPs", "What to do · why · edge cases"),
        ("Agent", "Claude Code", "Orchestrates the work", "Reads intent · routes tools · recovers from failure"),
        ("Tools", "tools/*.py", "Deterministic execution", "API calls · transforms · file I/O"),
    ]

    card_w = 1080
    card_h = 160
    gap = 40
    x = (W - card_w) // 2
    start_y = 80

    for i, (title, sub, line1, line2) in enumerate(layers):
        y = start_y + i * (card_h + gap)
        # layer card
        fill = BG if i != 1 else PANEL
        paste_card(img, (x, y), (card_w, card_h), radius=22, fill=fill, shadow_opacity=18)

        # layer index
        d.text((x + 36, y + 30), f"LAYER 0{i+1}", font=mono(16), fill=INK_MUTED)

        # title
        d.text((x + 36, y + 60), title, font=font(40), fill=INK)

        # sub label (mono, right side aligned to left block)
        d.text((x + 300, y + 76), sub, font=mono(20), fill=ACCENT)

        # description
        d.text((x + 36, y + 116), line1, font=font(20), fill=INK_SOFT)
        # second column
        d.text((x + 500, y + 116), line2, font=font(20), fill=INK_MUTED)

        # vertical connector to next
        if i < len(layers) - 1:
            cx = W // 2
            cy1 = y + card_h
            cy2 = y + card_h + gap
            d.line([(cx, cy1), (cx, cy2)], fill=HAIRLINE, width=2)

    img.save(DOCS_DIR / "architecture.png", optimize=True)
    print("✓ architecture.png")


# ---------- Main ----------

def main():
    build_hero()
    build_pipeline()
    build_report_preview()
    build_metrics()
    build_architecture()
    print(f"\nAll assets written to {DOCS_DIR}")


if __name__ == "__main__":
    main()
