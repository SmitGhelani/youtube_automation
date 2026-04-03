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
        default_factory=lambda: os.environ.get("PEXELS_API_KEY", "")
        # No longer required — video is generated from cartoon art, not Pexels stock
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
            "Milo & Luna in Whimble — animated cartoon adventure series for kids aged 4-10"
        )
    )
    channel_language: str = "English"
    target_audience: str = "Children aged 4-10 and their parents"

    # ── Video Quality ────────────────────────────────────────────────────────
    short_resolution: str = "1080x1920"   # 9:16 vertical for Shorts
    long_resolution: str = "1920x1080"    # 16:9 horizontal for long video
    video_fps: int = 30
    video_crf: int = 23                   # 23 = good quality, 2x faster encode than 18. YouTube re-encodes anyway.
    video_preset: str = "faster"          # faster/fast = good balance on t3.medium; "slow" causes timeouts

    # ── Voice Settings — Kokoro (primary, local, free) ───────────────────────
    # Voices: af_sarah (warm female), af_nicole, am_adam, am_michael,
    #         bf_emma (British female), bm_george (British male)
    kokoro_voice: str = "af_sarah"   # American female — warm, clear, great for YouTube
    kokoro_speed: float = 1.0        # 1.0 = natural; 0.9 = slightly slower/clearer
    kokoro_lang: str = "en-us"

    # ── Voice Settings — ElevenLabs (optional fallback, uses monthly quota) ──
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # Rachel (free)
    elevenlabs_model: str = "eleven_multilingual_v2"
    elevenlabs_output_format: str = "mp3_44100_192"     # Best quality on free tier

    # ── Timing ───────────────────────────────────────────────────────────────
    short_max_duration_sec: int = 59      # Keep under 60s for Shorts
    long_min_duration_sec: int = 480      # 8 minutes minimum for monetization
    long_max_duration_sec: int = 720      # 12 minutes target

    # ── Claude Model ─────────────────────────────────────────────────────────
    claude_model: str = "claude-sonnet-4-6"

    # ── Compliance ───────────────────────────────────────────────────────────
    banned_topics: list = field(default_factory=lambda: [
        "religion", "politics", "violence", "adult content",
        "drugs", "gambling", "hate speech", "misinformation",
        "medical advice", "financial advice without disclaimer"
    ])

    # ── Upload defaults ───────────────────────────────────────────────────────
    youtube_category_id: str = "1"    # Film & Animation (best for cartoon series)
    youtube_privacy: str = "public"
    made_for_kids: bool = True        # Kids cartoon — must be true for compliance
    license_type: str = "youtube"
