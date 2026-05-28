"""
setup_oauth.py — One-time OAuth flow for YouTube (read-only).

Usage:
  python tools/setup_oauth.py

Opens a browser. After consent, writes token.json at project root.
Subsequent tools load this token and refresh automatically.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

load_dotenv()

BASE_DIR = Path(__file__).parent.parent

SCOPES = [
    "https://www.googleapis.com/auth/youtube.readonly",
]


def get_credentials() -> Credentials:
    creds_path = BASE_DIR / os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
    token_path = BASE_DIR / os.getenv("GOOGLE_TOKEN_PATH", "token.json")

    if not creds_path.exists():
        sys.exit(
            f"Error: {creds_path} not found.\n"
            "Download OAuth client (Desktop type) from Google Cloud Console "
            "and save as credentials.json at project root."
        )

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
            creds = flow.run_local_server(port=0)
        token_path.write_text(creds.to_json())
        print(f"Wrote {token_path}")

    return creds


if __name__ == "__main__":
    creds = get_credentials()
    print("OAuth setup complete. Scopes:")
    for s in SCOPES:
        print(f"  - {s}")
