"""
send_report.py — Send the YouTube trend report via Gmail SMTP.

Usage:
  python tools/send_report.py
  python tools/send_report.py --deck-url https://docs.google.com/presentation/d/... --analysis .tmp/analysis.json
"""

import argparse
import json
import os
import smtplib
import ssl
import sys
from datetime import datetime
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
TMP_DIR = BASE_DIR / ".tmp"

SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465


def get_env(key: str, default: str | None = None) -> str:
    val = os.getenv(key, default)
    if not val:
        sys.exit(f"Error: {key} not found in .env")
    return val


def fmt_num(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def build_html(data: dict) -> str:
    synthesis = data.get("synthesis", {})
    summary = synthesis.get("executive_summary", "")
    stats = data.get("summary_stats", {})
    recs = synthesis.get("watch_recommendations", [])[:5]
    videos_by_id = {v["videoId"]: v for v in data.get("all_videos", [])}

    rec_html_parts = []
    for i, r in enumerate(recs, 1):
        v = videos_by_id.get(r.get("videoId"))
        if not v:
            continue
        rec_html_parts.append(f"""
        <tr>
          <td style="padding:12px 0;vertical-align:top;width:170px;">
            <a href="https://youtu.be/{escape(v['videoId'])}" style="text-decoration:none;">
              <img src="{escape(v.get('thumbnailUrl', ''))}" width="160" style="border-radius:8px;display:block;" alt="">
            </a>
          </td>
          <td style="padding:12px 0 12px 16px;vertical-align:top;">
            <div style="font-size:15px;font-weight:600;color:#1a1a2e;line-height:1.3;">
              <a href="https://youtu.be/{escape(v['videoId'])}" style="color:#1a1a2e;text-decoration:none;">
                {i}. {escape(v['title'])}
              </a>
            </div>
            <div style="font-size:12px;color:#7a7a90;margin-top:4px;">
              {escape(v['channelTitle'])} · {fmt_num(v['viewCount'])} views
            </div>
            <div style="font-size:13px;color:#4361ee;margin-top:6px;font-style:italic;">
              {escape(r.get('reason', ''))}
            </div>
          </td>
        </tr>
        """)
    rec_html = "".join(rec_html_parts) or "<tr><td>No recommendations.</td></tr>"

    themes = synthesis.get("themes", [])
    themes_html = ""
    if themes:
        items = "".join(
            f"<li style='margin-bottom:6px;'><b>{escape(t['name'])}</b> "
            f"<span style='color:#7a7a90;'>— {escape(t.get('description', ''))}</span></li>"
            for t in themes[:5]
        )
        themes_html = f"<ul style='font-size:14px;color:#1a1a2e;line-height:1.5;padding-left:20px;'>{items}</ul>"

    return f"""<!DOCTYPE html>
<html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;background:#f5f5f7;margin:0;padding:24px;">
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:640px;margin:0 auto;background:#ffffff;border-radius:12px;overflow:hidden;">
    <tr><td style="padding:32px 32px 8px;">
      <div style="font-size:12px;color:#7b9cff;font-weight:600;letter-spacing:1.5px;text-transform:uppercase;">
        AI · Automation · {datetime.now().strftime('%B %d, %Y')}
      </div>
      <h1 style="font-size:26px;color:#1a1a2e;margin:8px 0 16px;line-height:1.2;">Your YouTube Trend Report is ready</h1>
      <p style="font-size:15px;color:#3a3a5a;line-height:1.55;margin:0 0 20px;">{escape(summary)}</p>
      <p style="font-size:13px;color:#7a7a90;margin:0 0 20px;">📎 Full report attached as PDF.</p>
    </td></tr>

    <tr><td style="padding:0 32px 8px;">
      <div style="font-size:11px;color:#7a7a90;text-transform:uppercase;letter-spacing:1px;font-weight:600;border-top:1px solid #ececf0;padding-top:20px;">
        At a glance
      </div>
      <table width="100%" style="margin:12px 0 20px;">
        <tr>
          <td style="font-size:13px;color:#1a1a2e;"><b>{stats.get('videos_analyzed', 0):,}</b> videos</td>
          <td style="font-size:13px;color:#1a1a2e;"><b>{stats.get('channels_analyzed', 0):,}</b> channels</td>
          <td style="font-size:13px;color:#1a1a2e;"><b>{fmt_num(stats.get('total_views', 0))}</b> total views</td>
        </tr>
      </table>
    </td></tr>

    <tr><td style="padding:0 32px 8px;">
      <div style="font-size:11px;color:#7a7a90;text-transform:uppercase;letter-spacing:1px;font-weight:600;border-top:1px solid #ececf0;padding-top:20px;">
        What's trending
      </div>
      {themes_html}
    </td></tr>

    <tr><td style="padding:8px 32px 32px;">
      <div style="font-size:11px;color:#7a7a90;text-transform:uppercase;letter-spacing:1px;font-weight:600;border-top:1px solid #ececf0;padding-top:20px;">
        Top 5 to watch
      </div>
      <table width="100%" cellpadding="0" cellspacing="0">
        {rec_html}
      </table>
    </td></tr>

    <tr><td style="padding:16px 32px 28px;text-align:center;background:#fafafc;">
      <div style="font-size:11px;color:#9a9ab0;margin-top:10px;">
        Generated by your Youtube Analysis WAT pipeline
      </div>
    </td></tr>
  </table>
</body></html>"""


def build_plain(data: dict) -> str:
    synthesis = data.get("synthesis", {})
    summary = synthesis.get("executive_summary", "")
    recs = synthesis.get("watch_recommendations", [])[:5]
    videos_by_id = {v["videoId"]: v for v in data.get("all_videos", [])}

    lines = ["AI / Automation YouTube Trend Report", "=" * 40, "", summary, "", "Full report attached as PDF.", "", "Top 5 to watch:"]
    for i, r in enumerate(recs, 1):
        v = videos_by_id.get(r.get("videoId"))
        if v:
            lines.append(f"{i}. {v['title']} — {v['channelTitle']}")
            lines.append(f"   https://youtu.be/{v['videoId']}")
            lines.append(f"   {r.get('reason', '')}")
            lines.append("")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--analysis", default=str(TMP_DIR / "analysis.json"))
    parser.add_argument("--pdf", default=str(TMP_DIR / "report.pdf"))
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        sys.exit(f"Error: {pdf_path} not found. Run build_slides.py first.")

    analysis_path = Path(args.analysis)
    if not analysis_path.exists():
        sys.exit(f"Error: {analysis_path} not found.")
    data = json.loads(analysis_path.read_text())

    gmail = get_env("GMAIL_ADDRESS")
    password = get_env("GMAIL_APP_PASSWORD")
    recipient = os.getenv("REPORT_RECIPIENT") or gmail

    subject = f"📺 AI/Automation Trend Report — {datetime.now().strftime('%b %d, %Y')}"

    msg = MIMEMultipart("mixed")
    msg["From"] = f"YouTube Trend Pulse <{gmail}>"
    msg["To"] = recipient
    msg["Subject"] = subject

    body = MIMEMultipart("alternative")
    plain = build_plain(data)
    html = build_html(data)
    body.attach(MIMEText(plain, "plain", "utf-8"))
    body.attach(MIMEText(html, "html", "utf-8"))
    msg.attach(body)

    pdf_filename = f"AI_Automation_Trend_Report_{datetime.now().strftime('%Y-%m-%d')}.pdf"
    pdf_part = MIMEApplication(pdf_path.read_bytes(), _subtype="pdf")
    pdf_part.add_header("Content-Disposition", "attachment", filename=pdf_filename)
    msg.attach(pdf_part)

    print(f"Sending to {recipient}...")
    ctx = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx) as server:
        server.login(gmail, password)
        server.sendmail(gmail, [recipient], msg.as_string())
    print("Sent.")


if __name__ == "__main__":
    main()
