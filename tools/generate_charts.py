"""
generate_charts.py — Render PNG charts for the trend report deck.

Usage:
  python tools/generate_charts.py --analysis .tmp/analysis.json --style dark

Outputs:
  .tmp/charts/*.png  (1600x900 @ 100 dpi)
"""

import argparse
import json
import sys
import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
CHARTS_DIR = BASE_DIR / ".tmp" / "charts"
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

THEMES = {
    "light": {
        "bg": "#ffffff",
        "text": "#1a1a2e",
        "accent": "#4361ee",
        "accent2": "#7209b7",
        "grid": "#e0e0e0",
        "bar_colors": ["#4361ee", "#7209b7", "#f72585", "#3a86ff", "#06d6a0"],
    },
    "dark": {
        "bg": "#1a1a2e",
        "text": "#f0f0f0",
        "accent": "#7b9cff",
        "accent2": "#c77dff",
        "grid": "#2d2d50",
        "bar_colors": ["#7b9cff", "#c77dff", "#ff6b9d", "#5bc0eb", "#4ecdc4"],
    },
}

FIGSIZE = (16, 9)
DPI = 100


def apply_style(ax, fig, theme: dict, title: str, x_label: str, y_label: str):
    fig.patch.set_facecolor(theme["bg"])
    ax.set_facecolor(theme["bg"])
    ax.set_title(title, color=theme["text"], fontsize=20, fontweight="bold", pad=18)
    ax.set_xlabel(x_label, color=theme["text"], fontsize=13)
    ax.set_ylabel(y_label, color=theme["text"], fontsize=13)
    ax.tick_params(colors=theme["text"], labelsize=11)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)
    for spine in ["left", "bottom"]:
        ax.spines[spine].set_color(theme["grid"])
    ax.xaxis.grid(True, color=theme["grid"], alpha=0.6, linewidth=0.8)
    ax.set_axisbelow(True)


def wrap_label(text: str, width: int = 50) -> str:
    return "\n".join(textwrap.wrap(text, width=width, max_lines=2, placeholder="…"))


def fmt_num(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def hbar_chart(items: list[dict], value_key: str, label_key: str, title: str,
               x_label: str, theme: dict, filename: str, value_fmt=fmt_num, top_n: int = 10):
    items = items[:top_n]
    if not items:
        return None
    items = list(reversed(items))
    labels = [wrap_label(it[label_key], 50) for it in items]
    values = [it[value_key] for it in items]

    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    bars = ax.barh(labels, values, color=theme["accent"], edgecolor=theme["accent2"], linewidth=0.5)
    apply_style(ax, fig, theme, title, x_label, "")
    for bar, v in zip(bars, values):
        ax.text(bar.get_width(), bar.get_y() + bar.get_height() / 2,
                f"  {value_fmt(int(v))}", va="center", color=theme["text"], fontsize=11)
    plt.tight_layout()
    out = CHARTS_DIR / filename
    plt.savefig(out, dpi=DPI, facecolor=theme["bg"])
    plt.close(fig)
    return out


def scatter_chart(videos: list[dict], theme: dict, filename: str):
    if not videos:
        return None
    xs = [max(v["viewCount"], 1) for v in videos]
    ys = [v["engagementRate"] for v in videos]
    subs = [max(v["channelSubscribers"], 1) for v in videos]
    sizes = [min(max(s ** 0.4 * 0.3, 20), 400) for s in subs]
    colors = [theme["bar_colors"][i % len(theme["bar_colors"])] for i in range(len(videos))]

    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    ax.scatter(xs, ys, s=sizes, c=colors, alpha=0.7, edgecolors=theme["text"], linewidth=0.4)
    ax.set_xscale("log")
    apply_style(ax, fig, theme, "Engagement Rate vs Views (bubble size = channel subscribers)",
                "Views (log scale)", "Engagement rate (likes+comments / views)")
    plt.tight_layout()
    out = CHARTS_DIR / filename
    plt.savefig(out, dpi=DPI, facecolor=theme["bg"])
    plt.close(fig)
    return out


def themes_chart(themes: list[dict], theme: dict, filename: str):
    if not themes:
        return None
    themes = sorted(themes, key=lambda t: t.get("importance", 0))
    labels = [wrap_label(t["name"], 30) for t in themes]
    values = [t.get("importance", 0) for t in themes]

    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    colors = [theme["bar_colors"][i % len(theme["bar_colors"])] for i in range(len(themes))]
    bars = ax.barh(labels, values, color=colors, edgecolor=theme["text"], linewidth=0.3)
    apply_style(ax, fig, theme, "Trending Themes by Importance", "Importance (1–10)", "")
    for bar, v in zip(bars, values):
        ax.text(bar.get_width(), bar.get_y() + bar.get_height() / 2,
                f"  {v}", va="center", color=theme["text"], fontsize=12)
    ax.set_xlim(0, 10.5)
    plt.tight_layout()
    out = CHARTS_DIR / filename
    plt.savefig(out, dpi=DPI, facecolor=theme["bg"])
    plt.close(fig)
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", default=str(BASE_DIR / ".tmp" / "analysis.json"))
    parser.add_argument("--style", choices=["light", "dark"], default="dark")
    args = parser.parse_args()

    path = Path(args.analysis)
    if not path.exists():
        sys.exit(f"Error: {path} not found. Run analyze_videos.py first.")

    data = json.loads(path.read_text())
    theme = THEMES[args.style]

    print(f"Generating charts (style: {args.style})...")

    out1 = hbar_chart(data["top_by_views"], "viewCount", "title",
                      "Top 10 Videos by Views (last 14d)", "Views", theme, "top_videos_by_views.png")
    print(f"  - {out1}")

    out2 = hbar_chart(data["top_by_velocity"], "viewVelocity", "title",
                      "Top 10 Videos by View Velocity", "Views per day", theme, "view_velocity_top10.png")
    print(f"  - {out2}")

    out3 = scatter_chart(data["top_by_views"][:30], theme, "engagement_rate_scatter.png")
    print(f"  - {out3}")

    out4 = themes_chart(data["synthesis"].get("themes", []), theme, "themes_importance.png")
    print(f"  - {out4}")

    out5 = hbar_chart(data["channel_cadence"], "videoCount", "channelTitle",
                      "Most Active Channels (videos in window)", "Videos posted",
                      theme, "posting_cadence.png", value_fmt=str, top_n=10)
    print(f"  - {out5}")

    out6 = hbar_chart(data["hidden_gems"], "viewsPerSub", "title",
                      "Hidden Gems: Highest Views per Subscriber", "Views ÷ subscribers",
                      theme, "hidden_gems.png", value_fmt=lambda v: f"{v:.1f}x")
    print(f"  - {out6}")

    print(f"\nAll charts written to {CHARTS_DIR}")


if __name__ == "__main__":
    main()
