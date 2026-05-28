#!/usr/bin/env python3
"""
build_pdf.py — Canvas-design PDF report from analysis.json + chart PNGs.

Design philosophy: "Signal in the Dark"
Dark void backgrounds let data glow with intentional color. Information
hierarchy encoded spatially — large breathing room separates signal from
noise. Typography alternates between BigShoulders-Bold display headers
and GeistMono data labels.

Usage:
    python tools/build_pdf.py
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import requests
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as rl_canvas

BASE_DIR = Path(__file__).parent.parent
TMP_DIR = BASE_DIR / ".tmp"
CHARTS_DIR = TMP_DIR / "charts"
THUMBS_DIR = TMP_DIR / "thumbnails"
FONTS_DIR = BASE_DIR / ".claude/skills/canvas-design/canvas-fonts"
SYS_FONTS = Path("/System/Library/Fonts/Supplemental")
OUTPUT_PDF = TMP_DIR / "report.pdf"

PAGE_W, PAGE_H = landscape(letter)  # 792 x 612 pts
MARGIN = 44

# Color palette — "Signal in the Dark"
BG       = (0.039, 0.039, 0.071)   # #0a0a12
CARD     = (0.102, 0.102, 0.180)   # #1a1a2e
CARD2    = (0.071, 0.071, 0.129)   # #121221  slightly lighter card variant
PRIMARY  = (0.482, 0.612, 1.000)   # #7b9cff
SECONDARY= (0.780, 0.490, 1.000)   # #c77dff
TEXT     = (0.941, 0.941, 0.941)   # #f0f0f0
MUTED    = (0.533, 0.533, 0.667)   # #8888aa


# ─── FONT REGISTRATION ────────────────────────────────────────────────────────

def register_fonts():
    # The canvas-design TTFs are variable/OpenType and not supported by reportlab's
    # TTF parser. Fall back to macOS system fonts with equivalent visual roles.
    needed = {
        "BigShoulders":   SYS_FONTS / "DIN Condensed Bold.ttf",   # bold condensed display
        "Instrument":     SYS_FONTS / "Arial.ttf",                 # clean sans body
        "InstrumentBold": SYS_FONTS / "Arial Bold.ttf",            # bold sans
        "Geist":          SYS_FONTS / "Andale Mono.ttf",           # monospace data labels
        "Lora":           SYS_FONTS / "Georgia Italic.ttf",        # serif italic callouts
    }
    for name, path in needed.items():
        if path.exists():
            pdfmetrics.registerFont(TTFont(name, str(path)))
        else:
            print(f"  Warning: font missing → {path}")


# ─── DRAWING HELPERS ──────────────────────────────────────────────────────────

def _fill(c, color):
    c.setFillColorRGB(*color)

def _stroke(c, color):
    c.setStrokeColorRGB(*color)

def draw_bg(c):
    _fill(c, BG)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

def draw_card(c, x, y, w, h, color=None, border_color=None, radius=4):
    _fill(c, color or CARD)
    _stroke(c, border_color or PRIMARY)
    c.setLineWidth(0.4)
    c.roundRect(x, y, w, h, radius, fill=1, stroke=1)

def draw_line(c, x1, y, x2, color=None, width=0.8):
    _stroke(c, color or PRIMARY)
    c.setLineWidth(width)
    c.line(x1, y, x2, y)

def draw_section_label(c, text, x=None, y=None):
    x = x or MARGIN
    y = y or (PAGE_H - MARGIN - 10)
    c.setFont("Geist", 8)
    _fill(c, MUTED)
    c.drawString(x, y, text.upper())
    label_w = c.stringWidth(text.upper(), "Geist", 8)
    draw_line(c, x, y - 5, x + label_w + 24, color=PRIMARY, width=0.5)

def wrap_text(c, text, font, size, max_width):
    words = text.split()
    lines, current = [], ""
    for word in words:
        candidate = (current + " " + word).strip()
        if c.stringWidth(candidate, font, size) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines

def draw_text_block(c, text, font, size, x, y, max_width, leading, color=None):
    _fill(c, color or TEXT)
    c.setFont(font, size)
    for line in wrap_text(c, text, font, size, max_width):
        if y < MARGIN:
            break
        c.drawString(x, y, line)
        y -= leading
    return y

def fmt_num(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.0f}K"
    return str(int(n))

def fmt_pct(f):
    return f"{f * 100:.1f}%"

def truncate(s, n):
    return s if len(s) <= n else s[:n - 1] + "…"


# ─── THUMBNAIL DOWNLOAD ───────────────────────────────────────────────────────

def fetch_thumbnail(video_id, url):
    THUMBS_DIR.mkdir(parents=True, exist_ok=True)
    path = THUMBS_DIR / f"{video_id}.jpg"
    if path.exists():
        return path
    try:
        r = requests.get(url, timeout=8)
        if r.status_code == 200:
            path.write_bytes(r.content)
            return path
    except Exception:
        pass
    return None


def embed_image(c, path, x, y, w, h):
    try:
        c.drawImage(ImageReader(str(path)), x, y, width=w, height=h,
                    preserveAspectRatio=True, anchor="c", mask="auto")
    except Exception:
        draw_card(c, x, y, w, h, color=CARD2)


# ─── PAGE 1: COVER ────────────────────────────────────────────────────────────

def page_cover(c, data):
    draw_bg(c)

    stats = data["summary_stats"]
    gen_at = data.get("generated_at", "")
    try:
        dt = datetime.fromisoformat(gen_at.replace("Z", "+00:00"))
        date_str = dt.strftime("%B %d, %Y")
    except Exception:
        date_str = gen_at[:10]

    # Right panel — thin double-rect geometric frame
    rx = PAGE_W - 290
    _stroke(c, PRIMARY)
    c.setLineWidth(0.5)
    c.rect(rx, MARGIN, 246, PAGE_H - 2 * MARGIN, fill=0, stroke=1)
    _stroke(c, SECONDARY)
    c.setLineWidth(0.25)
    c.rect(rx + 8, MARGIN + 8, 230, PAGE_H - 2 * MARGIN - 16, fill=0, stroke=1)

    # Top-left corner marks
    _stroke(c, MUTED)
    c.setLineWidth(0.6)
    c.line(MARGIN, PAGE_H - MARGIN, MARGIN + 22, PAGE_H - MARGIN)
    c.line(MARGIN, PAGE_H - MARGIN, MARGIN, PAGE_H - MARGIN - 22)

    # Category eyebrow
    c.setFont("Geist", 8)
    _fill(c, MUTED)
    c.drawString(MARGIN, PAGE_H - MARGIN - 14, "AI / AUTOMATION")
    draw_line(c, MARGIN, PAGE_H - MARGIN - 20, rx - 20, color=MUTED, width=0.4)

    # Main title
    c.setFont("BigShoulders", 74)
    _fill(c, TEXT)
    c.drawString(MARGIN, PAGE_H - MARGIN - 90, "TREND")
    _fill(c, PRIMARY)
    c.drawString(MARGIN, PAGE_H - MARGIN - 165, "REPORT")

    # Date
    c.setFont("Lora", 14)
    _fill(c, MUTED)
    c.drawString(MARGIN, PAGE_H - MARGIN - 196, date_str)

    # Bottom accent
    draw_line(c, MARGIN, MARGIN + 70, rx - 20, color=PRIMARY, width=0.6)
    c.setFont("Geist", 7)
    _fill(c, MUTED)
    c.drawString(MARGIN, MARGIN + 56, "YOUTUBE ANALYSIS PIPELINE  ·  WEEKLY EDITION")

    # Stat boxes inside right panel
    stat_items = [
        ("VIDEOS ANALYZED", fmt_num(stats["videos_analyzed"])),
        ("CHANNELS",         fmt_num(stats["channels_analyzed"])),
        ("TOTAL VIEWS",      fmt_num(stats["total_views"])),
        ("MED. ENGAGEMENT",  fmt_pct(stats["median_engagement_rate"])),
    ]
    bx = rx + 18
    bw = 210
    bh = 82
    gap = 8
    by_start = PAGE_H - MARGIN - 16

    for i, (label, value) in enumerate(stat_items):
        by = by_start - i * (bh + gap) - bh
        draw_card(c, bx, by, bw, bh, color=CARD2, border_color=PRIMARY)

        c.setFont("Geist", 7)
        _fill(c, MUTED)
        c.drawString(bx + 12, by + bh - 16, label)

        c.setFont("BigShoulders", 34)
        _fill(c, PRIMARY if i < 3 else SECONDARY)
        c.drawString(bx + 12, by + 14, value)

    c.showPage()


# ─── PAGE 2: EXECUTIVE SUMMARY ────────────────────────────────────────────────

def page_executive_summary(c, data):
    draw_bg(c)
    draw_section_label(c, "Executive Summary")

    stats = data["summary_stats"]
    summary = data["synthesis"]["executive_summary"]

    # 4 stat cards
    cw = (PAGE_W - 2 * MARGIN - 24) / 4
    ch = 64
    cy = PAGE_H - MARGIN - 80

    stat_items = [
        ("VIDEOS",       fmt_num(stats["videos_analyzed"])),
        ("CHANNELS",     fmt_num(stats["channels_analyzed"])),
        ("TOTAL VIEWS",  fmt_num(stats["total_views"])),
        ("ENGAGEMENT",   fmt_pct(stats["median_engagement_rate"])),
    ]
    for i, (label, value) in enumerate(stat_items):
        cx_ = MARGIN + i * (cw + 8)
        draw_card(c, cx_, cy, cw, ch, color=CARD, border_color=PRIMARY if i < 2 else SECONDARY)
        c.setFont("Geist", 7)
        _fill(c, MUTED)
        c.drawString(cx_ + 10, cy + ch - 14, label)
        c.setFont("BigShoulders", 26)
        _fill(c, PRIMARY if i < 2 else SECONDARY)
        c.drawString(cx_ + 10, cy + 12, value)

    draw_line(c, MARGIN, cy - 14, PAGE_W - MARGIN, color=MUTED, width=0.4)

    # Executive summary body
    draw_text_block(c, summary, "Instrument", 10.5,
                    MARGIN, cy - 30, PAGE_W - 2 * MARGIN, 16)

    c.showPage()


# ─── PAGE 3: THEMES OVERVIEW ──────────────────────────────────────────────────

def page_themes_overview(c, data):
    draw_bg(c)
    draw_section_label(c, "Themes · This Week")

    chart = CHARTS_DIR / "themes_importance.png"
    if chart.exists():
        img_y = MARGIN + 28
        img_h = PAGE_H - MARGIN - 40 - img_y
        embed_image(c, chart, MARGIN, img_y, PAGE_W - 2 * MARGIN, img_h)

    # Theme name strip at very bottom
    themes = data["synthesis"]["themes"]
    n = max(len(themes), 1)
    tw = (PAGE_W - 2 * MARGIN) / n
    for i, theme in enumerate(themes):
        tx = MARGIN + i * tw
        c.setFont("Geist", 7)
        _fill(c, MUTED)
        label = truncate(theme["name"], 30)
        c.drawString(tx + 4, MARGIN + 12, f"{theme['importance']}/10  {label}")

    c.showPage()


# ─── PAGES 4+: THEME DETAIL ───────────────────────────────────────────────────

def page_theme(c, theme, video_map):
    draw_bg(c)

    name = theme["name"]
    importance = theme.get("importance", 0)

    # Importance badge (top right)
    bx = PAGE_W - MARGIN - 90
    by = PAGE_H - MARGIN - 76
    draw_card(c, bx, by, 80, 66, color=CARD, border_color=SECONDARY)
    c.setFont("Geist", 7)
    _fill(c, MUTED)
    c.drawString(bx + 10, by + 52, "IMPORTANCE")
    c.setFont("BigShoulders", 28)
    _fill(c, SECONDARY)
    c.drawString(bx + 10, by + 18, f"{importance}/10")

    # Theme name — large BigShoulders, may wrap
    c.setFont("BigShoulders", 46)
    _fill(c, TEXT)
    name_lines = wrap_text(c, name, "BigShoulders", 46, PAGE_W - 2 * MARGIN - 110)
    ny = PAGE_H - MARGIN - 52
    for nl in name_lines[:2]:
        c.drawString(MARGIN, ny, nl)
        ny -= 54

    # Divider
    draw_line(c, MARGIN, ny + 10, PAGE_W - MARGIN, color=PRIMARY, width=0.6)

    # Description
    desc_bottom = draw_text_block(
        c, theme["description"], "Instrument", 11,
        MARGIN, ny - 6, PAGE_W - 2 * MARGIN, 17
    )

    # Thumbnails
    example_ids = theme.get("exampleVideoIds", [])[:3]
    if not example_ids:
        c.showPage()
        return

    thumb_area_top = desc_bottom - 20
    thumb_h = min(max(thumb_area_top - MARGIN - 40, 60), 110)
    thumb_w = thumb_h * (16 / 9)
    gap = 14

    c.setFont("Geist", 7)
    _fill(c, MUTED)
    c.drawString(MARGIN, thumb_area_top, "EXAMPLE VIDEOS")
    draw_line(c, MARGIN, thumb_area_top - 6, MARGIN + 110, color=MUTED, width=0.4)

    for i, vid_id in enumerate(example_ids):
        video = video_map.get(vid_id)
        if not video:
            continue
        tx = MARGIN + i * (thumb_w + gap)
        ty = MARGIN + 30

        thumb_path = fetch_thumbnail(vid_id, video.get("thumbnailUrl", ""))
        if thumb_path:
            embed_image(c, thumb_path, tx, ty, thumb_w, thumb_h)
        else:
            draw_card(c, tx, ty, thumb_w, thumb_h, color=CARD2)

        # Title + meta below thumbnail
        title_text = truncate(video.get("title", ""), 52)
        c.setFont("Instrument", 7)
        _fill(c, TEXT)
        c.drawString(tx, ty - 13, title_text)

        channel = truncate(video.get("channelTitle", ""), 28)
        views = fmt_num(video.get("viewCount", 0))
        c.setFont("Geist", 6)
        _fill(c, MUTED)
        c.drawString(tx, ty - 23, f"{channel}  ·  {views} views")

    c.showPage()


# ─── CHART PAGES ──────────────────────────────────────────────────────────────

def page_chart(c, section_label, chart_filename):
    draw_bg(c)
    draw_section_label(c, section_label)

    chart_path = CHARTS_DIR / chart_filename
    if chart_path.exists():
        embed_image(c, chart_path,
                    MARGIN, MARGIN + 8,
                    PAGE_W - 2 * MARGIN,
                    PAGE_H - 2 * MARGIN - 28)

    c.showPage()


# ─── WATCH RECOMMENDATIONS ────────────────────────────────────────────────────

def page_watch_recommendations(c, data, video_map):
    draw_bg(c)
    draw_section_label(c, "What to Watch This Week")

    recs = data["synthesis"]["watch_recommendations"][:5]
    n = len(recs)
    if n == 0:
        c.showPage()
        return

    total_gap = (n - 1) * 10
    cw = (PAGE_W - 2 * MARGIN - total_gap) / n
    ch = PAGE_H - 2 * MARGIN - 28
    cy = MARGIN

    for i, rec in enumerate(recs):
        video = video_map.get(rec["videoId"])
        if not video:
            continue
        cx_ = MARGIN + i * (cw + 10)
        draw_card(c, cx_, cy, cw, ch, color=CARD, border_color=PRIMARY)

        # Thumbnail
        th = cw * (9 / 16)
        ty_ = cy + ch - th - 8
        thumb_path = fetch_thumbnail(rec["videoId"], video.get("thumbnailUrl", ""))
        if thumb_path:
            embed_image(c, thumb_path, cx_ + 5, ty_, cw - 10, th)

        inner_w = cw - 14

        # Title
        title_y = ty_ - 14
        c.setFont("InstrumentBold", 7.5)
        _fill(c, TEXT)
        for tl in wrap_text(c, video.get("title", ""), "InstrumentBold", 7.5, inner_w)[:3]:
            c.drawString(cx_ + 7, title_y, tl)
            title_y -= 10

        # Reason
        reason_y = title_y - 5
        c.setFont("Instrument", 6.5)
        _fill(c, MUTED)
        for rl in wrap_text(c, rec.get("reason", ""), "Instrument", 6.5, inner_w)[:5]:
            if reason_y > cy + 18:
                c.drawString(cx_ + 7, reason_y, rl)
                reason_y -= 9

        # Views chip at bottom
        views = fmt_num(video.get("viewCount", 0))
        c.setFont("Geist", 6)
        _fill(c, PRIMARY)
        c.drawString(cx_ + 7, cy + 7, f"{views} views")

    c.showPage()


# ─── METHODOLOGY ──────────────────────────────────────────────────────────────

def page_methodology(c, data):
    draw_bg(c)
    draw_section_label(c, "Methodology")

    gen_at = data.get("generated_at", "")
    try:
        dt = datetime.fromisoformat(gen_at.replace("Z", "+00:00"))
        date_str = dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        date_str = gen_at

    stats = data["summary_stats"]

    sections = [
        ("DATA SOURCES", [
            "YouTube Data API v3: search.list (keyword queries), subscriptions.list, videos.list, channels.list",
            "Claude AI (claude-sonnet-4-6): theme synthesis and watch recommendations",
        ]),
        ("METRICS", [
            "View Velocity: views ÷ age in days  —  captures content rising fast regardless of total count",
            "Engagement Rate: (likes + comments) ÷ views",
            "Views per Subscriber: views ÷ channel subscribers  —  surfaces channels punching above their weight",
        ]),
        ("COLLECTION WINDOW", [
            f"Generated: {date_str}",
            f"Videos analyzed: {stats['videos_analyzed']:,} across {stats['channels_analyzed']:,} channels",
        ]),
        ("THRESHOLDS", [
            "Hidden gems: channels with fewer than 100K subscribers and elevated views-per-subscriber ratio",
            "Theme synthesis derived from top 40 videos by view velocity, passed to Claude for clustering",
        ]),
    ]

    y = PAGE_H - MARGIN - 34
    for section_title, items in sections:
        c.setFont("Geist", 8)
        _fill(c, PRIMARY)
        c.drawString(MARGIN, y, section_title)
        y -= 4
        draw_line(c, MARGIN, y, MARGIN + 190, color=PRIMARY, width=0.5)
        y -= 14

        for item in items:
            c.setFont("Instrument", 9)
            _fill(c, TEXT)
            for line in wrap_text(c, item, "Instrument", 9, PAGE_W - 2 * MARGIN):
                c.drawString(MARGIN + 12, y, line)
                y -= 13
        y -= 10

    c.showPage()


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    analysis_path = TMP_DIR / "analysis.json"
    if not analysis_path.exists():
        sys.exit(f"Error: {analysis_path} not found. Run analyze_videos.py first.")

    with open(analysis_path) as f:
        data = json.load(f)

    register_fonts()

    video_map = {v["videoId"]: v for v in data.get("all_videos", [])}
    themes = data["synthesis"]["themes"]

    print(f"Building PDF report → {OUTPUT_PDF}")

    c = rl_canvas.Canvas(str(OUTPUT_PDF), pagesize=landscape(letter))
    c.setTitle("AI / Automation Trend Report")
    c.setAuthor("YouTube Analysis Pipeline")

    print("  p1  Cover")
    page_cover(c, data)

    print("  p2  Executive Summary")
    page_executive_summary(c, data)

    print("  p3  Themes Overview")
    page_themes_overview(c, data)

    for i, theme in enumerate(themes):
        print(f"  p{4+i}  Theme: {theme['name'][:50]}")
        page_theme(c, theme, video_map)

    chart_start = 4 + len(themes)
    chart_pages = [
        ("Top Videos · Views",            "top_videos_by_views.png"),
        ("Rising Fast · Views per Day",   "view_velocity_top10.png"),
        ("Engagement · Views vs Rate",    "engagement_rate_scatter.png"),
        ("Hidden Gems · Views/Subscriber","hidden_gems.png"),
        ("Posting Cadence",               "posting_cadence.png"),
    ]
    for i, (label, fname) in enumerate(chart_pages):
        print(f"  p{chart_start+i}  {label}")
        page_chart(c, label, fname)

    watch_p = chart_start + len(chart_pages)
    print(f"  p{watch_p}  Watch Recommendations")
    page_watch_recommendations(c, data, video_map)

    meth_p = watch_p + 1
    print(f"  p{meth_p}  Methodology")
    page_methodology(c, data)

    c.save()
    print(f"\nDone — {meth_p} pages → {OUTPUT_PDF}")


if __name__ == "__main__":
    main()
