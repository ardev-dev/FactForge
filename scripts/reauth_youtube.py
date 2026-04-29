#!/usr/bin/env python3
"""
reauth_youtube.py — Refresh YouTube OAuth token via browser flow.

Use when get_youtube_client() fails with "Token has been expired or revoked".
Opens a browser window, you sign in, token gets saved to config/youtube_token.json.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CREDENTIALS = ROOT / "config/youtube_credentials.json"
TOKEN = ROOT / "config/youtube_token.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube.upload",
]


def main():
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not CREDENTIALS.exists():
        print(f"❌ {CREDENTIALS} missing — cannot start OAuth flow")
        sys.exit(1)

    print("🔐 Starting browser-based OAuth flow...")
    print("   A browser window will open. Sign in with the channel's Google account.")
    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS), SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN.write_text(creds.to_json())
    print(f"\n✅ Token saved to {TOKEN}")
    print(f"   Valid: {creds.valid}")
    print(f"   Has refresh: {creds.refresh_token is not None}")


if __name__ == "__main__":
    main()
