"""
config.py — Central configuration
All secrets come from environment variables (set in GitHub Actions secrets).
"""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Config:
    # ── API Keys ──────────────────────────────────────────────────────────────
    # Gemini (replaces Claude — free tier, 1500 RPD on Flash)
    gemini_api_key: str = field(
        default_factory=lambda: os.environ["GEMINI_API_KEY"]
    )
    # Anthropic key kept as optional fallback
    anthropic_api_key: str = field(
        default_factory=lambda: os.environ.get("ANTHROPIC_API_KEY", "")
    )
    # fal.ai for Seedance video generation (free credits on signup, then ~$0.05/5s)
    fal_api_key: str = field(
        default_factory=lambda: os.environ.get("FAL_API_KEY", "")
    )
    elevenlabs_api_key: str = field(
        default_factory=lambda: os.environ.get("ELEVENLABS_API_KEY", "")
    )
    pexels_api_key: str = field(
        default_factory=lambda: os.environ.get("PEXELS_API_KEY", "")
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
            "Mahabharat — The Epic Retold. Cinematic Mahabharat story series on YouTube."
        )
    )
    channel_language: str = "English"
    target_audience: str = "Indian mythology fans, Mahabharat devotees, global epic story lovers"

    # ── Video Quality ────────────────────────────────────────────────────────
    short_resolution: str = "1080x1920"   # 9:16 vertical for Shorts
    long_resolution: str = "1920x1080"    # 16:9 horizontal for long video
    video_fps: int = 30
    video_crf: int = 23                   # 23 = good quality, 2x faster encode than 18. YouTube re-encodes anyway.
    video_preset: str = "faster"          # faster/fast = good balance on t3.medium; "slow" causes timeouts

    # ── Voice Settings — Kokoro (primary, local, free) ───────────────────────
    # Voices: af_sarah (warm female), af_nicole, am_adam, am_michael,
    #         bf_emma (British female), bm_george (British male)
    kokoro_voice: str = "am_adam"    # American male — deep, authoritative — fits epic narrator
    kokoro_speed: float = 1.0        # 1.0 = natural; 0.9 = slightly slower/clearer
    kokoro_lang: str = "en-us"

    # ── Voice Settings — ElevenLabs (optional fallback, uses monthly quota) ──
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # Rachel (free)
    elevenlabs_model: str = "eleven_multilingual_v2"
    elevenlabs_output_format: str = "mp3_44100_192"     # Best quality on free tier

    # ── Timing ───────────────────────────────────────────────────────────────
    short_max_duration_sec: int = 59      # Keep under 60s for Shorts
    long_min_duration_sec: int = 480      # 8 minutes minimum for monetization
    long_max_duration_sec: int = 900      # 15 minutes — Saturday banger

    # ── LLM Model (Gemini — free tier) ───────────────────────────────────────
    # gemini-2.5-flash: free tier, 15 RPM, 1500 RPD, best free model
    gemini_model: str = "gemini-2.5-flash"

    # ── Video Model (Seedance via fal.ai) ─────────────────────────────────────
    # Seedance 1.5 Pro now. When Seedance 2.0 API goes GA, change to:
    # seedance_model = "fal-ai/seedance-2/text-to-video"
    seedance_model: str = "fal-ai/seedance-1-5-pro/text-to-video"

    # ── Compliance ───────────────────────────────────────────────────────────
    banned_topics: list = field(default_factory=lambda: [
        "religion", "politics", "violence", "adult content",
        "drugs", "gambling", "hate speech", "misinformation",
        "medical advice", "financial advice without disclaimer"
    ])

    # ── Upload defaults ───────────────────────────────────────────────────────
    youtube_category_id: str = "22"   # People & Blogs / Entertainment — best for Mahabharat
    youtube_privacy: str = "public"
    made_for_kids: bool = False       # Mahabharat is for general audience
    license_type: str = "youtube"
