"""
analyze_videos.py — Compute trend metrics and synthesize themes via Claude.

Usage:
  python tools/analyze_videos.py --input .tmp/videos_raw.json

Outputs:
  .tmp/analysis.json — rankings + Claude theme synthesis
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
TMP_DIR = BASE_DIR / ".tmp"

CLAUDE_MODEL = "claude-sonnet-4-6"


def get_env(key: str) -> str:
    val = os.getenv(key)
    if not val:
        sys.exit(f"Error: {key} not found in .env")
    return val


def age_days(published_at: str) -> float:
    try:
        dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
        delta = datetime.now(timezone.utc) - dt
        return max(delta.total_seconds() / 86400, 0.5)
    except Exception:
        return 999.0


def enrich(videos: list[dict]) -> list[dict]:
    for v in videos:
        v["ageDays"] = round(age_days(v["publishedAt"]), 2)
        views = max(v["viewCount"], 1)
        v["engagementRate"] = round((v["likeCount"] + v["commentCount"]) / views, 5)
        v["viewVelocity"] = round(v["viewCount"] / v["ageDays"], 0)
        subs = max(v["channelSubscribers"], 1)
        v["viewsPerSub"] = round(v["viewCount"] / subs, 3)
    return videos


def channel_cadence(videos: list[dict]) -> list[dict]:
    by_channel: dict[str, dict] = {}
    for v in videos:
        cid = v["channelId"]
        if cid not in by_channel:
            by_channel[cid] = {
                "channelId": cid,
                "channelTitle": v["channelTitle"],
                "subscribers": v["channelSubscribers"],
                "videoCount": 0,
                "totalViews": 0,
            }
        by_channel[cid]["videoCount"] += 1
        by_channel[cid]["totalViews"] += v["viewCount"]
    return sorted(by_channel.values(), key=lambda c: c["videoCount"], reverse=True)


def parse_json_from_text(text: str) -> dict:
    """Extract first JSON object from Claude's response, robust to fenced blocks."""
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        return json.loads(m.group(1))
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        return json.loads(m.group(0))
    raise ValueError("No JSON found in Claude response")


def synthesize_themes(top_videos: list[dict]) -> dict:
    client = Anthropic(api_key=get_env("ANTHROPIC_API_KEY"))

    video_blob = []
    for i, v in enumerate(top_videos, 1):
        desc = (v.get("description") or "")[:300].replace("\n", " ")
        video_blob.append(
            f"{i}. [{v['videoId']}] {v['title']} — {v['channelTitle']} "
            f"({v['viewCount']:,} views, {v['ageDays']}d old)\n   {desc}"
        )
    videos_text = "\n\n".join(video_blob)

    system_prompt = (
        "You analyze trending YouTube content in the AI / AI automation niche. "
        "You extract recurring themes from a list of trending videos and identify what's "
        "actually worth watching for someone building AI agents and automation systems. "
        "Output strict JSON only — no preamble, no markdown."
    )

    user_prompt = f"""Below are the top trending AI/automation YouTube videos from the last 1–2 weeks.

{videos_text}

Identify 4–6 distinct THEMES that explain what is trending in this niche right now. Each theme should group videos by what they're actually about (e.g. "Multi-agent orchestration", "n8n vs Make showdowns", "Cursor/Claude Code workflows").

Then pick 5 "must-watch" videos for someone serious about learning AI automation — prioritize learning value over pure popularity.

Return strict JSON with this exact schema:
{{
  "executive_summary": "3 sentences capturing the state of the niche this period",
  "themes": [
    {{
      "name": "short theme name",
      "description": "1-2 sentence explanation of what's happening",
      "exampleVideoIds": ["videoId1", "videoId2", "videoId3"],
      "importance": 8
    }}
  ],
  "watch_recommendations": [
    {{
      "videoId": "videoId",
      "reason": "1 sentence on why someone building AI agents and automation systems should watch this"
    }}
  ]
}}

importance is 1-10. exampleVideoIds must be IDs from the list above.
"""

    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4000,
        system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user_prompt}],
    )
    text = resp.content[0].text
    return parse_json_from_text(text)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(TMP_DIR / "videos_raw.json"))
    parser.add_argument("--top-n-for-themes", type=int, default=40)
    args = parser.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        sys.exit(f"Error: {in_path} not found. Run discover_videos.py first.")

    videos = json.loads(in_path.read_text())
    print(f"Loaded {len(videos)} videos")

    videos = enrich(videos)

    top_by_views = sorted(videos, key=lambda v: v["viewCount"], reverse=True)[:20]
    top_by_velocity = sorted(videos, key=lambda v: v["viewVelocity"], reverse=True)[:20]
    top_by_engagement = sorted(videos, key=lambda v: v["engagementRate"], reverse=True)[:20]
    hidden_gems = [v for v in videos if v["channelSubscribers"] < 100_000]
    hidden_gems = sorted(hidden_gems, key=lambda v: v["viewsPerSub"], reverse=True)[:10]
    cadence = channel_cadence(videos)[:15]

    theme_input = top_by_velocity[: args.top_n_for_themes]
    print(f"Asking Claude to synthesize themes from top {len(theme_input)} videos...")
    synthesis = synthesize_themes(theme_input)

    summary_stats = {
        "videos_analyzed": len(videos),
        "channels_analyzed": len({v["channelId"] for v in videos}),
        "total_views": sum(v["viewCount"] for v in videos),
        "median_engagement_rate": sorted([v["engagementRate"] for v in videos])[len(videos) // 2] if videos else 0,
    }

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary_stats": summary_stats,
        "top_by_views": top_by_views,
        "top_by_velocity": top_by_velocity,
        "top_by_engagement": top_by_engagement,
        "hidden_gems": hidden_gems,
        "channel_cadence": cadence,
        "synthesis": synthesis,
        "all_videos": videos,
    }

    out_path = TMP_DIR / "analysis.json"
    out_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))
    print(f"Wrote {out_path}")
    print(f"Themes: {[t['name'] for t in synthesis.get('themes', [])]}")


if __name__ == "__main__":
    main()
