"""
discover_videos.py — Pull candidate videos from YouTube via niche keyword search and user's subscriptions.

Usage:
  python tools/discover_videos.py --days 14 --max-per-query 50

Outputs:
  .tmp/videos_raw.json   — hydrated video records with stats
  .tmp/quota_log.json    — estimated quota units consumed
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import isodate
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from setup_oauth import get_credentials

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
TMP_DIR = BASE_DIR / ".tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)


def get_env(key: str, default: str | None = None) -> str:
    val = os.getenv(key, default)
    if not val:
        sys.exit(f"Error: {key} not found in .env")
    return val


def iso_to_seconds(iso_duration: str) -> int:
    try:
        return int(isodate.parse_duration(iso_duration).total_seconds())
    except Exception:
        return 0


def search_by_query(youtube, query: str, published_after_iso: str, max_results: int, quota: dict) -> list[str]:
    """Return list of videoIds for a single search query."""
    video_ids = []
    try:
        resp = youtube.search().list(
            q=query,
            part="id",
            type="video",
            order="viewCount",
            publishedAfter=published_after_iso,
            relevanceLanguage="en",
            maxResults=min(max_results, 50),
        ).execute()
        quota["units"] += 100
        for item in resp.get("items", []):
            vid = item.get("id", {}).get("videoId")
            if vid:
                video_ids.append(vid)
    except HttpError as e:
        print(f"  ! search '{query}' failed: {e}", file=sys.stderr)
    return video_ids


def get_my_subscriptions(youtube, quota: dict) -> list[str]:
    """Return list of channelIds the user is subscribed to."""
    channel_ids = []
    page_token = None
    while True:
        try:
            resp = youtube.subscriptions().list(
                part="snippet",
                mine=True,
                maxResults=50,
                pageToken=page_token,
            ).execute()
            quota["units"] += 1
        except HttpError as e:
            print(f"  ! subscriptions.list failed: {e}", file=sys.stderr)
            break
        for item in resp.get("items", []):
            cid = item.get("snippet", {}).get("resourceId", {}).get("channelId")
            if cid:
                channel_ids.append(cid)
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return channel_ids


def search_channel_recent(youtube, channel_id: str, published_after_iso: str, quota: dict) -> list[str]:
    """Get recent video IDs from one channel within the time window."""
    video_ids = []
    try:
        resp = youtube.search().list(
            channelId=channel_id,
            part="id",
            type="video",
            order="date",
            publishedAfter=published_after_iso,
            maxResults=10,
        ).execute()
        quota["units"] += 100
        for item in resp.get("items", []):
            vid = item.get("id", {}).get("videoId")
            if vid:
                video_ids.append(vid)
    except HttpError as e:
        print(f"  ! channel {channel_id} search failed: {e}", file=sys.stderr)
    return video_ids


def hydrate_videos(youtube, video_ids: list[str], quota: dict) -> dict:
    """Batch-fetch full video records. Returns {videoId: record}."""
    out = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        try:
            resp = youtube.videos().list(
                part="snippet,statistics,contentDetails",
                id=",".join(batch),
                maxResults=50,
            ).execute()
            quota["units"] += 1
        except HttpError as e:
            print(f"  ! videos.list batch failed: {e}", file=sys.stderr)
            continue
        for item in resp.get("items", []):
            sn = item.get("snippet", {})
            st = item.get("statistics", {})
            cd = item.get("contentDetails", {})
            thumbs = sn.get("thumbnails", {})
            thumb = (
                thumbs.get("maxres")
                or thumbs.get("standard")
                or thumbs.get("high")
                or thumbs.get("medium")
                or thumbs.get("default")
                or {}
            )
            out[item["id"]] = {
                "videoId": item["id"],
                "title": sn.get("title", ""),
                "description": sn.get("description", ""),
                "channelId": sn.get("channelId", ""),
                "channelTitle": sn.get("channelTitle", ""),
                "publishedAt": sn.get("publishedAt", ""),
                "tags": sn.get("tags", []),
                "thumbnailUrl": thumb.get("url", ""),
                "durationSeconds": iso_to_seconds(cd.get("duration", "PT0S")),
                "viewCount": int(st.get("viewCount", 0)),
                "likeCount": int(st.get("likeCount", 0)),
                "commentCount": int(st.get("commentCount", 0)),
            }
    return out


def hydrate_channels(youtube, channel_ids: list[str], quota: dict) -> dict:
    """Batch-fetch channel subscriber counts. Returns {channelId: subscribers}."""
    out = {}
    for i in range(0, len(channel_ids), 50):
        batch = channel_ids[i : i + 50]
        try:
            resp = youtube.channels().list(
                part="statistics",
                id=",".join(batch),
                maxResults=50,
            ).execute()
            quota["units"] += 1
        except HttpError as e:
            print(f"  ! channels.list batch failed: {e}", file=sys.stderr)
            continue
        for item in resp.get("items", []):
            stats = item.get("statistics", {})
            subs = stats.get("subscriberCount")
            out[item["id"]] = int(subs) if subs is not None else 0
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--max-per-query", type=int, default=50)
    parser.add_argument("--skip-subscriptions", action="store_true")
    args = parser.parse_args()

    api_key = get_env("YOUTUBE_API_KEY")
    queries = [q.strip() for q in get_env("NICHE_QUERIES").split(",") if q.strip()]

    quota = {"units": 0}
    published_after = (datetime.now(timezone.utc) - timedelta(days=args.days)).isoformat().replace("+00:00", "Z")

    youtube_apikey = build("youtube", "v3", developerKey=api_key)

    print(f"[1/4] Searching {len(queries)} niche queries (window: last {args.days} days)...")
    all_video_ids: set[str] = set()
    sources: dict[str, str] = {}
    for q in queries:
        ids = search_by_query(youtube_apikey, q, published_after, args.max_per_query, quota)
        print(f"  - '{q}': {len(ids)} videos")
        for vid in ids:
            all_video_ids.add(vid)
            sources.setdefault(vid, "search")

    if not args.skip_subscriptions:
        print("[2/4] Loading your subscriptions (OAuth)...")
        creds = get_credentials()
        youtube_oauth = build("youtube", "v3", credentials=creds)
        channel_ids = get_my_subscriptions(youtube_oauth, quota)
        print(f"  - {len(channel_ids)} subscriptions found")
        for idx, cid in enumerate(channel_ids, 1):
            ids = search_channel_recent(youtube_oauth, cid, published_after, quota)
            if ids:
                print(f"  - [{idx}/{len(channel_ids)}] channel {cid}: {len(ids)} recent videos")
            for vid in ids:
                all_video_ids.add(vid)
                sources[vid] = "subscription"
    else:
        print("[2/4] Skipping subscriptions (--skip-subscriptions)")

    print(f"[3/4] Hydrating {len(all_video_ids)} unique videos...")
    videos = hydrate_videos(youtube_apikey, list(all_video_ids), quota)

    channel_ids_to_hydrate = list({v["channelId"] for v in videos.values() if v["channelId"]})
    print(f"[4/4] Hydrating {len(channel_ids_to_hydrate)} channels for subscriber counts...")
    channel_subs = hydrate_channels(youtube_apikey, channel_ids_to_hydrate, quota)

    records = []
    for vid, v in videos.items():
        v["channelSubscribers"] = channel_subs.get(v["channelId"], 0)
        v["source"] = sources.get(vid, "search")
        records.append(v)

    records.sort(key=lambda r: r["viewCount"], reverse=True)

    out_path = TMP_DIR / "videos_raw.json"
    out_path.write_text(json.dumps(records, indent=2, ensure_ascii=False))
    print(f"\nWrote {out_path} ({len(records)} videos)")

    quota_path = TMP_DIR / "quota_log.json"
    quota_path.write_text(json.dumps({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "units_used": quota["units"],
        "videos_discovered": len(records),
    }, indent=2))
    print(f"Quota used: ~{quota['units']} units (daily limit: 10,000)")


if __name__ == "__main__":
    main()
