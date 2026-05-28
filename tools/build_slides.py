"""
build_slides.py — Build a Google Slides deck from analysis.json + chart PNGs.

Usage:
  python tools/build_slides.py --analysis .tmp/analysis.json --charts-dir .tmp/charts

Outputs:
  .tmp/deck_url.txt — URL of the new presentation
"""

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from setup_oauth import get_credentials

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
TMP_DIR = BASE_DIR / ".tmp"

# Slide dimensions for 16:9 widescreen (in EMU; default presentation size)
SLIDE_W = 9144000
SLIDE_H = 5143500


def emu(inches: float) -> int:
    return int(inches * 914400)


def oid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def text_box_requests(slide_id: str, x_in: float, y_in: float, w_in: float, h_in: float,
                      text: str, font_size: int = 14, bold: bool = False,
                      color_hex: str = "#1a1a2e") -> tuple[list[dict], str]:
    shape_id = oid("txt")
    r = int(color_hex[1:3], 16) / 255
    g = int(color_hex[3:5], 16) / 255
    b = int(color_hex[5:7], 16) / 255
    requests = [
        {
            "createShape": {
                "objectId": shape_id,
                "shapeType": "TEXT_BOX",
                "elementProperties": {
                    "pageObjectId": slide_id,
                    "size": {"width": {"magnitude": emu(w_in), "unit": "EMU"},
                             "height": {"magnitude": emu(h_in), "unit": "EMU"}},
                    "transform": {"scaleX": 1, "scaleY": 1,
                                  "translateX": emu(x_in), "translateY": emu(y_in),
                                  "unit": "EMU"},
                },
            }
        },
        {"insertText": {"objectId": shape_id, "text": text}},
        {
            "updateTextStyle": {
                "objectId": shape_id,
                "style": {
                    "fontSize": {"magnitude": font_size, "unit": "PT"},
                    "bold": bold,
                    "foregroundColor": {"opaqueColor": {"rgbColor": {"red": r, "green": g, "blue": b}}},
                    "fontFamily": "Inter",
                },
                "textRange": {"type": "ALL"},
                "fields": "fontSize,bold,foregroundColor,fontFamily",
            }
        },
    ]
    return requests, shape_id


def image_request(slide_id: str, url: str, x_in: float, y_in: float, w_in: float, h_in: float) -> dict:
    return {
        "createImage": {
            "objectId": oid("img"),
            "url": url,
            "elementProperties": {
                "pageObjectId": slide_id,
                "size": {"width": {"magnitude": emu(w_in), "unit": "EMU"},
                         "height": {"magnitude": emu(h_in), "unit": "EMU"}},
                "transform": {"scaleX": 1, "scaleY": 1,
                              "translateX": emu(x_in), "translateY": emu(y_in),
                              "unit": "EMU"},
            },
        }
    }


def background_request(slide_id: str, color_hex: str) -> dict:
    r = int(color_hex[1:3], 16) / 255
    g = int(color_hex[3:5], 16) / 255
    b = int(color_hex[5:7], 16) / 255
    return {
        "updatePageProperties": {
            "objectId": slide_id,
            "pageProperties": {
                "pageBackgroundFill": {
                    "solidFill": {"color": {"rgbColor": {"red": r, "green": g, "blue": b}}}
                }
            },
            "fields": "pageBackgroundFill",
        }
    }


def create_slide_request(slide_id: str) -> dict:
    return {
        "createSlide": {
            "objectId": slide_id,
            "slideLayoutReference": {"predefinedLayout": "BLANK"},
        }
    }


def upload_chart_to_drive(drive, path: Path) -> str:
    """Upload PNG to Drive, make publicly readable, return direct image URL."""
    media = MediaFileUpload(str(path), mimetype="image/png")
    f = drive.files().create(body={"name": path.name}, media_body=media, fields="id").execute()
    file_id = f["id"]
    drive.permissions().create(fileId=file_id, body={"type": "anyone", "role": "reader"}).execute()
    return f"https://drive.google.com/uc?export=view&id={file_id}"


def fmt_num(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


# Theme colors (mirrors generate_charts.py dark theme so the deck matches the charts)
BG = "#1a1a2e"
TEXT = "#f0f0f0"
ACCENT = "#7b9cff"
ACCENT2 = "#c77dff"
MUTED = "#a0a0c0"


def build_title_slide(slide_id: str, date_range: str) -> list[dict]:
    reqs = [background_request(slide_id, BG)]
    t1, _ = text_box_requests(slide_id, 0.6, 2.0, 9.0, 1.0,
                              "AI & AI Automation", font_size=54, bold=True, color_hex=TEXT)
    t2, _ = text_box_requests(slide_id, 0.6, 3.0, 9.0, 0.8,
                              "Weekly Trend Pulse", font_size=36, bold=False, color_hex=ACCENT)
    t3, _ = text_box_requests(slide_id, 0.6, 4.5, 9.0, 0.4,
                              date_range, font_size=14, color_hex=MUTED)
    reqs.extend(t1)
    reqs.extend(t2)
    reqs.extend(t3)
    return reqs


def build_summary_slide(slide_id: str, stats: dict, summary_text: str) -> list[dict]:
    reqs = [background_request(slide_id, BG)]
    t1, _ = text_box_requests(slide_id, 0.5, 0.3, 9.0, 0.6,
                              "Executive Summary", font_size=32, bold=True, color_hex=ACCENT)
    reqs.extend(t1)

    t2, _ = text_box_requests(slide_id, 0.5, 1.1, 9.0, 2.0,
                              summary_text, font_size=18, color_hex=TEXT)
    reqs.extend(t2)

    stat_lines = (
        f"Videos analyzed:   {stats['videos_analyzed']:,}\n"
        f"Channels covered:   {stats['channels_analyzed']:,}\n"
        f"Total views:   {fmt_num(stats['total_views'])}\n"
        f"Median engagement rate:   {stats['median_engagement_rate'] * 100:.2f}%"
    )
    t3, _ = text_box_requests(slide_id, 0.5, 3.7, 9.0, 1.5,
                              stat_lines, font_size=16, bold=True, color_hex=ACCENT2)
    reqs.extend(t3)
    return reqs


def build_chart_slide(slide_id: str, title: str, chart_url: str, caption: str = "") -> list[dict]:
    reqs = [background_request(slide_id, BG)]
    t1, _ = text_box_requests(slide_id, 0.5, 0.2, 9.0, 0.6,
                              title, font_size=28, bold=True, color_hex=ACCENT)
    reqs.extend(t1)
    reqs.append(image_request(slide_id, chart_url, 0.5, 0.95, 9.0, 4.0))
    if caption:
        t2, _ = text_box_requests(slide_id, 0.5, 5.0, 9.0, 0.5,
                                  caption, font_size=12, color_hex=MUTED)
        reqs.extend(t2)
    return reqs


def build_theme_slide(slide_id: str, theme: dict, videos_by_id: dict) -> list[dict]:
    reqs = [background_request(slide_id, BG)]
    t1, _ = text_box_requests(slide_id, 0.5, 0.2, 9.0, 0.6,
                              f"Theme: {theme['name']}", font_size=28, bold=True, color_hex=ACCENT)
    reqs.extend(t1)

    t2, _ = text_box_requests(slide_id, 0.5, 0.95, 9.0, 1.0,
                              theme.get("description", ""), font_size=16, color_hex=TEXT)
    reqs.extend(t2)

    example_ids = theme.get("exampleVideoIds", [])[:3]
    for i, vid in enumerate(example_ids):
        v = videos_by_id.get(vid)
        if not v:
            continue
        x = 0.5 + i * 3.05
        if v.get("thumbnailUrl"):
            reqs.append(image_request(slide_id, v["thumbnailUrl"], x, 2.2, 2.9, 1.63))
        title_text = v["title"][:90] + ("…" if len(v["title"]) > 90 else "")
        t, _ = text_box_requests(slide_id, x, 3.9, 2.9, 0.5,
                                 title_text, font_size=11, bold=True, color_hex=TEXT)
        reqs.extend(t)
        meta = f"{v['channelTitle']}  ·  {fmt_num(v['viewCount'])} views"
        t, _ = text_box_requests(slide_id, x, 4.45, 2.9, 0.3,
                                 meta, font_size=10, color_hex=MUTED)
        reqs.extend(t)
    return reqs


def build_recommendations_slide(slide_id: str, recs: list[dict], videos_by_id: dict) -> list[dict]:
    reqs = [background_request(slide_id, BG)]
    t1, _ = text_box_requests(slide_id, 0.5, 0.2, 9.0, 0.6,
                              "What to Watch This Week", font_size=28, bold=True, color_hex=ACCENT)
    reqs.extend(t1)

    y = 1.0
    for i, rec in enumerate(recs[:5], 1):
        v = videos_by_id.get(rec.get("videoId"))
        if not v:
            continue
        if v.get("thumbnailUrl"):
            reqs.append(image_request(slide_id, v["thumbnailUrl"], 0.5, y, 1.5, 0.84))
        title_text = f"{i}. {v['title']}"
        t, _ = text_box_requests(slide_id, 2.2, y, 7.3, 0.4,
                                 title_text, font_size=14, bold=True, color_hex=TEXT)
        reqs.extend(t)
        meta = f"{v['channelTitle']}  ·  {fmt_num(v['viewCount'])} views  ·  https://youtu.be/{v['videoId']}"
        t, _ = text_box_requests(slide_id, 2.2, y + 0.35, 7.3, 0.3,
                                 meta, font_size=10, color_hex=MUTED)
        reqs.extend(t)
        t, _ = text_box_requests(slide_id, 2.2, y + 0.65, 7.3, 0.4,
                                 rec.get("reason", ""), font_size=11, color_hex=ACCENT2)
        reqs.extend(t)
        y += 0.95
    return reqs


def build_methodology_slide(slide_id: str, queries: list[str], days: int, quota_units: int) -> list[dict]:
    reqs = [background_request(slide_id, BG)]
    t1, _ = text_box_requests(slide_id, 0.5, 0.3, 9.0, 0.6,
                              "Methodology", font_size=28, bold=True, color_hex=ACCENT)
    reqs.extend(t1)

    body = (
        f"Time window: last {days} days\n"
        f"Data source: YouTube Data API v3 (quota used: ~{quota_units} units / 10,000 daily)\n"
        f"Discovery: keyword search + your YouTube subscriptions\n"
        f"Theme synthesis: Claude Sonnet 4.6\n\n"
        f"Niche queries:\n  • " + "\n  • ".join(queries) +
        f"\n\nMetrics:\n"
        f"  • View velocity = views ÷ days since publish\n"
        f"  • Engagement rate = (likes + comments) ÷ views\n"
        f"  • Hidden gems = views ÷ subscribers (channels under 100k subs)"
    )
    t2, _ = text_box_requests(slide_id, 0.5, 1.1, 9.0, 4.0,
                              body, font_size=12, color_hex=TEXT)
    reqs.extend(t2)
    return reqs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", default=str(TMP_DIR / "analysis.json"))
    parser.add_argument("--charts-dir", default=str(TMP_DIR / "charts"))
    parser.add_argument("--days", type=int, default=14)
    args = parser.parse_args()

    data = json.loads(Path(args.analysis).read_text())
    charts_dir = Path(args.charts_dir)
    if not charts_dir.exists():
        sys.exit(f"Error: {charts_dir} not found. Run generate_charts.py first.")

    creds = get_credentials()
    slides = build("slides", "v1", credentials=creds)
    drive = build("drive", "v3", credentials=creds)

    print("Uploading chart images to Drive...")
    chart_urls: dict[str, str] = {}
    for png in sorted(charts_dir.glob("*.png")):
        chart_urls[png.stem] = upload_chart_to_drive(drive, png)
        print(f"  - {png.name}")

    now = datetime.now(timezone.utc)
    date_range = f"{(now.replace(microsecond=0)).strftime('%b %d, %Y')} · last {args.days} days"
    title = f"AI / Automation Trend Report — {now.strftime('%Y-%m-%d')}"

    print(f"Creating presentation: {title}")
    pres = slides.presentations().create(body={"title": title}).execute()
    pres_id = pres["presentationId"]
    first_slide_id = pres["slides"][0]["objectId"]

    videos_by_id = {v["videoId"]: v for v in data["all_videos"]}
    synthesis = data.get("synthesis", {})
    themes = synthesis.get("themes", [])[:4]
    quota_units = 0
    quota_log = TMP_DIR / "quota_log.json"
    if quota_log.exists():
        quota_units = json.loads(quota_log.read_text()).get("units_used", 0)

    queries = [q.strip() for q in (Path(".env").read_text() if Path(".env").exists() else "")
               .split("\n") if q.startswith("NICHE_QUERIES=")]
    import os
    queries_str = os.getenv("NICHE_QUERIES", "")
    query_list = [q.strip() for q in queries_str.split(",") if q.strip()]

    requests = []

    # Slide 1 — reuse the default first slide
    requests.extend(build_title_slide(first_slide_id, date_range))

    # Helper: append a new slide and its content
    def add_slide(builder, *args, **kwargs):
        sid = oid("slide")
        requests.append(create_slide_request(sid))
        requests.extend(builder(sid, *args, **kwargs))

    add_slide(build_summary_slide,
              data["summary_stats"],
              synthesis.get("executive_summary", "No summary available."))

    if "themes_importance" in chart_urls:
        add_slide(build_chart_slide,
                  "Top Themes by Importance",
                  chart_urls["themes_importance"],
                  "Themes extracted by Claude from the top trending videos.")

    for theme in themes:
        add_slide(build_theme_slide, theme, videos_by_id)

    if "top_videos_by_views" in chart_urls:
        add_slide(build_chart_slide, "Top Videos by Views",
                  chart_urls["top_videos_by_views"],
                  "Raw view counts in the time window.")

    if "view_velocity_top10" in chart_urls:
        add_slide(build_chart_slide, "Top by View Velocity",
                  chart_urls["view_velocity_top10"],
                  "Views per day since publish — surfaces fast risers.")

    if "engagement_rate_scatter" in chart_urls:
        add_slide(build_chart_slide, "Engagement vs Views",
                  chart_urls["engagement_rate_scatter"],
                  "High engagement at any scale = a sticky topic.")

    if "hidden_gems" in chart_urls:
        add_slide(build_chart_slide, "Hidden Gems",
                  chart_urls["hidden_gems"],
                  "Small channels punching above their subscriber weight.")

    if "posting_cadence" in chart_urls:
        add_slide(build_chart_slide, "Most Active Channels",
                  chart_urls["posting_cadence"],
                  "Who is posting the most in the niche right now.")

    add_slide(build_recommendations_slide,
              synthesis.get("watch_recommendations", []),
              videos_by_id)

    add_slide(build_methodology_slide, query_list, args.days, quota_units)

    print(f"Executing {len(requests)} batch update requests...")
    # Chunk requests to avoid hitting payload limits
    CHUNK = 200
    for i in range(0, len(requests), CHUNK):
        slides.presentations().batchUpdate(
            presentationId=pres_id,
            body={"requests": requests[i : i + CHUNK]},
        ).execute()

    deck_url = f"https://docs.google.com/presentation/d/{pres_id}/edit"
    (TMP_DIR / "deck_url.txt").write_text(deck_url)
    print(f"\nDeck created: {deck_url}")

    print("Exporting as PDF...")
    pdf_bytes = drive.files().export(
        fileId=pres_id,
        mimeType="application/pdf",
    ).execute()
    pdf_path = TMP_DIR / "report.pdf"
    pdf_path.write_bytes(pdf_bytes)
    print(f"PDF saved: {pdf_path} ({len(pdf_bytes) // 1024} KB)")


if __name__ == "__main__":
    main()
