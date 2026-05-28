# YouTube Trend Pulse

**A weekly AI/automation trend report — delivered to your inbox as a polished PDF.**

Discover what's actually trending in the AI and automation space on YouTube. The pipeline fetches videos, computes velocity/engagement metrics, uses Claude to synthesize themes, renders charts, builds a designed PDF report, and emails it to you — all in about 3 minutes for ~$0.05.

---

## What you get

```
Your inbox, every week:

┌─────────────────────────────────────────────────────┐
│  AI · Automation · May 29, 2026                     │
│                                                     │
│  Your YouTube Trend Report is ready                 │
│                                                     │
│  Multi-agent orchestration is dominating this week, │
│  with 12 new tutorials on LangGraph and CrewAI...   │
│                                                     │
│  📎 Full report attached as PDF (14 pages)          │
│                                                     │
│  AT A GLANCE                                        │
│  312 videos · 48 channels · 84M total views         │
│                                                     │
│  WHAT'S TRENDING                                    │
│  • Multi-agent orchestration                        │
│  • n8n vs Make showdowns                            │
│  • Cursor / Claude Code workflows                   │
│  • Local LLM deployments                            │
│                                                     │
│  TOP 5 TO WATCH  [thumbnails + reasons]             │
└─────────────────────────────────────────────────────┘
```

The attached PDF contains:
- Cover page with aggregate stats
- Executive summary + theme breakdown
- 6 data visualizations (view velocity, engagement scatter, hidden gems, posting cadence, and more)
- Per-theme deep-dives with example video thumbnails
- Top 5 curated watch recommendations with reasoning

---

## How it works

```
discover_videos.py   →   analyze_videos.py   →   generate_charts.py   →   build_pdf.py   →   send_report.py
      │                        │                        │                      │                    │
  YouTube API           Claude Sonnet             matplotlib              reportlab            Gmail SMTP
  search + subs         theme synthesis            6 PNG charts          14-page PDF          HTML email
  ~800 quota units      ~$0.05 / run               dark design           canvas-design        + attachment
```

All intermediate files land in `.tmp/` and are regenerated on each run. Each step is independent — if one fails, fix and rerun just that step.

---

## Requirements

- Python 3.11+
- A [Google Cloud](https://console.cloud.google.com) project with **YouTube Data API v3** enabled
- An [Anthropic](https://console.anthropic.com) API key
- A Gmail account with [App Passwords](https://myaccount.google.com/apppasswords) enabled (requires 2FA)

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/YOUR_USERNAME/youtube-trend-pulse.git
cd youtube-trend-pulse
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

| Variable | Where to get it |
|---|---|
| `YOUTUBE_API_KEY` | [Google Cloud Console](https://console.cloud.google.com) → APIs & Services → Credentials → API key |
| `ANTHROPIC_API_KEY` | [Anthropic Console](https://console.anthropic.com) → API Keys |
| `GMAIL_ADDRESS` | Your Gmail address |
| `GMAIL_APP_PASSWORD` | Gmail → Security → 2-Step Verification → App Passwords (16-char code) |
| `REPORT_RECIPIENT` | Who gets the email (leave blank to send to yourself) |
| `NICHE_QUERIES` | Comma-separated search terms — tune to your interests |

### 3. Set up Google OAuth (one-time)

The pipeline reads your YouTube subscriptions to surface content from channels you already follow. This requires OAuth.

**In Google Cloud Console:**
1. Go to **APIs & Services → Credentials**
2. Click **Create Credentials → OAuth client ID**
3. Choose **Desktop app**, download the JSON, save it as `credentials.json` at the project root

**Then run the one-time auth flow:**

```bash
python tools/setup_oauth.py
```

A browser window will open. Sign in and grant read-only YouTube access. This creates `token.json` which is reused automatically on subsequent runs.

> `credentials.json` and `token.json` are gitignored and never committed.

---

## Running the pipeline

Run each step in order:

```bash
# Step 1 — Fetch trending videos (uses ~800–1,200 YouTube API quota units)
python tools/discover_videos.py --days 14

# Step 2 — Compute metrics and synthesize themes via Claude (~$0.05)
python tools/analyze_videos.py

# Step 3 — Render 6 charts
python tools/generate_charts.py --style dark

# Step 4 — Build the PDF report
python tools/build_pdf.py

# Step 5 — Email it
python tools/send_report.py
```

**Total runtime:** ~3 minutes  
**Total cost:** ~$0.05 (one Claude API call) + free YouTube quota

---

## Customization

### Change the niche

Edit `NICHE_QUERIES` in your `.env`. Each query becomes a YouTube search.

```
NICHE_QUERIES=AI agents,n8n workflow,Cursor AI,vibe coding,local LLM,AI SaaS
```

Good additions: `"AI workflow"`, `"Cursor AI"`, `"vibe coding"`, `"local LLM"`, `"AI SaaS"`. Avoid single broad terms like `"AI"` — too noisy.

### Change the lookback window

```bash
python tools/discover_videos.py --days 7   # last week only
python tools/discover_videos.py --days 30  # last month
```

### Skip subscription scanning

If your YouTube subscriptions are private, the subscriptions step will return nothing. Either make them public in YouTube settings, or skip them:

```bash
python tools/discover_videos.py --skip-subscriptions
```

### Light mode charts

```bash
python tools/generate_charts.py --style light
```

---

## How videos are ranked

The pipeline computes four metrics beyond raw view count:

| Metric | Formula | What it surfaces |
|---|---|---|
| **View velocity** | `views / age_in_days` | Fast-rising content, regardless of age |
| **Engagement rate** | `(likes + comments) / views` | Content that resonates |
| **Views per subscriber** | `views / channel_subscribers` | Small channels punching above weight |
| **Channel cadence** | videos posted in window | Most active creators in the niche |

Claude receives the top 40 videos by velocity and synthesizes 4–6 themes with importance scores, plus 5 curated watch recommendations.

---

## Troubleshooting

**`403 quotaExceeded`** — YouTube's free tier gives 10,000 units/day. Eight search queries = ~800 units. If you hit the limit, wait until midnight Pacific Time (when it resets) or reduce `NICHE_QUERIES`.

**Empty subscriptions** — YouTube hides subscriptions by default. Go to YouTube → Settings → Privacy → uncheck "Keep all my subscriptions private".

**`SMTPAuthenticationError`** — Use the 16-character App Password, not your regular Gmail password. Spaces are not allowed.

**Malformed Claude response** — `analyze_videos.py` has a robust JSON extractor that handles markdown-fenced responses. If it still fails, re-run just step 2 — the video data from step 1 is cached in `.tmp/videos_raw.json`.

**Thumbnail 404s** — Missing thumbnails render as a dark placeholder. The PDF still builds completely.

---

## Project structure

```
.
├── tools/
│   ├── setup_oauth.py          # One-time Google OAuth flow
│   ├── discover_videos.py      # YouTube API: search + subscription scraping
│   ├── analyze_videos.py       # Metric computation + Claude theme synthesis
│   ├── generate_charts.py      # matplotlib chart rendering (6 charts)
│   ├── build_pdf.py            # reportlab PDF generation (14+ pages)
│   └── send_report.py          # Gmail SMTP delivery with HTML summary
├── workflows/
│   └── youtube_trend_report.md # Full SOP — edge cases, quota notes, design decisions
├── .env.example                # Template — copy to .env and fill in values
├── requirements.txt
└── README.md
```

---

## Architecture

This project follows the **WAT framework** (Workflows → Agents → Tools):

- **Workflows** (`workflows/`) — plain-language SOPs defining what to do and why
- **Tools** (`tools/`) — deterministic Python scripts that do the actual work
- **Agent** — Claude Code (or you) orchestrates the steps, handles failures, and keeps the system improving

The key insight: keeping AI in the reasoning layer and Python in the execution layer keeps each step reliable and independently testable.

---

## Contributing

PRs welcome. Good areas to contribute:

- Additional chart types or layout options
- Support for other niches beyond AI/automation (the queries are fully configurable)
- A CLI wrapper to run all 5 steps in one command
- Scheduling support (cron / GitHub Actions)
- Alternative email providers beyond Gmail

---

## License

MIT
