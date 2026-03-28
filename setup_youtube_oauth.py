"""
setup_youtube_oauth.py
======================
Run this ONCE on your local machine to get the YouTube OAuth refresh token.
After running, add the token to GitHub Actions secrets.

Steps:
1. Go to console.cloud.google.com
2. Create project → Enable YouTube Data API v3
3. Create OAuth 2.0 credentials (Desktop app)
4. Download credentials JSON
5. Run: python setup_youtube_oauth.py --credentials client_secret.json
6. Copy the refresh_token to GitHub Actions secrets
"""

import json
import argparse
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]


def main():
    parser = argparse.ArgumentParser(description="Get YouTube OAuth refresh token")
    parser.add_argument(
        "--credentials",
        default="client_secret.json",
        help="Path to OAuth2 credentials JSON from Google Cloud Console",
    )
    args = parser.parse_args()

    creds_path = Path(args.credentials)
    if not creds_path.exists():
        print(f"❌ Credentials file not found: {creds_path}")
        print("\nTo get credentials:")
        print("1. Go to https://console.cloud.google.com")
        print("2. Create a project")
        print("3. Enable YouTube Data API v3")
        print("4. Go to APIs & Services → Credentials")
        print("5. Create OAuth 2.0 Client ID (Desktop app)")
        print("6. Download JSON → rename to client_secret.json")
        return

    print("Opening browser for YouTube OAuth authorization...")
    print("Please log in with the YouTube channel account.\n")

    flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), SCOPES)
    creds = flow.run_local_server(port=8080)

    output = {
        "refresh_token": creds.refresh_token,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "token_uri": creds.token_uri,
    }

    # Save to file
    output_file = Path("youtube_tokens.json")
    output_file.write_text(json.dumps(output, indent=2))

    print("\n✅ SUCCESS! Your tokens have been saved to youtube_tokens.json")
    print("\nAdd these to GitHub Actions Secrets:")
    print(f"  YOUTUBE_REFRESH_TOKEN = {creds.refresh_token}")
    print(f"  YOUTUBE_CLIENT_ID     = {creds.client_id}")
    print(f"  YOUTUBE_CLIENT_SECRET = {creds.client_secret}")
    print("\n⚠️  Keep these tokens SECRET. Delete youtube_tokens.json after copying.")


if __name__ == "__main__":
    main()
