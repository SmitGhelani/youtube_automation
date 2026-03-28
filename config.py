"""
config.py — Central configuration
All secrets come from environment variables (set in GitHub Actions secrets).
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    # ── API Keys (set as GitHub Actions / environment secrets) ──────────────
    anthropic_api_key: str = field(
        default_factory=lambda: os.environ["ANTHROPIC_API_KEY"]
    )
    elevenlabs_api_key: str = field(
        default_factory=lambda: os.environ.get("ELEVENLABS_API_KEY", "")
    )
    pexels_api_key: str = field(
        default_factory=lambda: os.environ["PEXELS_API_KEY"]
    )
    freesound_api_key: str = field(
        default_factory=lambda: os.environ.get("FREESOUND_API_KEY", "")
    )
    youtube_client_id: str = field(
        default_factory=lambda: os.environ["YOUTUBE_CLIENT_ID"]
    )
    youtube_client_secret: str = field(
        default_factory=lambda: os.environ["YOUTUBE_CLIENT_SECRET"]
    )
    youtube_refresh_token: str = field(
        default_factory=lambda: os.environ["YOUTUBE_REFRESH_TOKEN"]
    )
    notification_email: str = field(
        default_factory=lambda: os.environ.get("NOTIFICATION_EMAIL", "")
    )
    sendgrid_api_key: str = field(
        default_factory=lambda: os.environ.get("SENDGRID_API_KEY", "")
    )

    # ── Channel / Content Settings ──────────────────────────────────────────
    channel_niche: str = field(
        default_factory=lambda: os.environ.get(
            "CHANNEL_NICHE",
            "AI & Technology — Latest discoveries, tools, and breakthroughs"
        )
    )
    channel_language: str = "English"
    target_audience: str = "Tech enthusiasts aged 18-35"

    # ── Video Quality ────────────────────────────────────────────────────────
    short_resolution: str = "1080x1920"   # 9:16 vertical for Shorts
    long_resolution: str = "1920x1080"    # 16:9 horizontal for long video
    video_fps: int = 30
    video_crf: int = 18                   # H.264 quality (lower = better, 18 is visually lossless)
    video_preset: str = "slow"            # FFmpeg encode preset

    # ── Voice Settings (ElevenLabs) ──────────────────────────────────────────
    # Free voices that don't consume your quota: use pyttsx3 as fallback
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # Rachel (free)
    elevenlabs_model: str = "eleven_monolingual_v1"
    tts_fallback: str = "pyttsx3"  # Free local TTS fallback

    # ── Timing ───────────────────────────────────────────────────────────────
    short_max_duration_sec: int = 59      # Keep under 60s for Shorts
    long_min_duration_sec: int = 480      # 8 minutes minimum for monetization
    long_max_duration_sec: int = 720      # 12 minutes target

    # ── Claude Model ─────────────────────────────────────────────────────────
    claude_model: str = "claude-opus-4-5"

    # ── Compliance ───────────────────────────────────────────────────────────
    banned_topics: list = field(default_factory=lambda: [
        "religion", "politics", "violence", "adult content",
        "drugs", "gambling", "hate speech", "misinformation",
        "medical advice", "financial advice without disclaimer"
    ])

    # ── Upload defaults ───────────────────────────────────────────────────────
    youtube_category_id: str = "28"   # Science & Technology
    youtube_privacy: str = "public"
    made_for_kids: bool = False
    license_type: str = "youtube"     # Standard YouTube license
