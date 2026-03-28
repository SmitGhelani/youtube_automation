"""
agents/upload_agent.py — Uploads video to YouTube via Data API v3
"""
import logging
from pathlib import Path

logger = logging.getLogger("UploadAgent")


class UploadAgent:
    def __init__(self, config):
        self.cfg = config

    def upload(self, video_path: Path, thumb_path: Path, metadata: dict, video_type: str) -> str:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google.auth.transport.requests import Request

        creds = Credentials(
            token=None,
            refresh_token=self.cfg.youtube_refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=self.cfg.youtube_client_id,
            client_secret=self.cfg.youtube_client_secret,
            scopes=["https://www.googleapis.com/auth/youtube.upload"],
        )
        creds.refresh(Request())
        youtube = build("youtube", "v3", credentials=creds)

        body = {
            "snippet": {
                "title": metadata["title"],
                "description": metadata["description"],
                "tags": metadata.get("tags", []),
                "categoryId": metadata.get("category_id", "28"),
                "defaultLanguage": "en",
            },
            "status": {
                "privacyStatus": self.cfg.youtube_privacy,
                "selfDeclaredMadeForKids": self.cfg.made_for_kids,
            },
        }

        media = MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True)
        request = youtube.videos().insert(part=",".join(body.keys()), body=body, media_body=media)

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                logger.info(f"Upload: {int(status.progress()*100)}%")

        video_id = response["id"]

        if thumb_path.exists():
            try:
                youtube.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(str(thumb_path), mimetype="image/png"),
                ).execute()
            except Exception as e:
                logger.warning(f"Thumbnail upload failed: {e}")

        url = f"https://youtu.be/{video_id}"
        logger.info(f"Uploaded: {url}")
        return url
