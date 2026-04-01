"""
config.py — Central configuration
All secrets come from /etc/youtube-pipeline.env file.
"""

import os
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


def _load_secrets():
    """Load API keys from /etc/youtube-pipeline.env file."""
    secrets_file = Path("/etc/youtube-pipeline.env")
    
    if not secrets_file.exists():
        return {}
    
    secrets = {}
    try:
        with open(secrets_file, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    if "=" in line:
                        key, value = line.split("=", 1)
                        secrets[key.strip()] = value.strip()
    except Exception as e:
        print(f"Warning: Could not load secrets from {secrets_file}: {e}")
    
    return secrets


_SECRETS = _load_secrets()


def _get_secret(key: str, default: str = "") -> str:
    """Get a secret from the loaded file or environment."""
    return _SECRETS.get(key) or os.environ.get(key, default)


@dataclass
class Config:
    # ── API Keys (from /etc/youtube-pipeline.env) ────────────────────────────
    anthropic_api_key: str = field(
        default_factory=lambda: _get_secret("ANTHROPIC_API_KEY")
    )
    elevenlabs_api_key: str = field(
        default_factory=lambda: _get_secret("ELEVENLABS_API_KEY")
    )
    pexels_api_key: str = field(
        default_factory=lambda: _get_secret("PEXELS_API_KEY")
    )
    freesound_api_key: str = field(
        default_factory=lambda: _get_secret("FREESOUND_API_KEY")
    )
    youtube_client_id: str = field(
        default_factory=lambda: _get_secret("YOUTUBE_CLIENT_ID")
    )
    youtube_client_secret: str = field(
        default_factory=lambda: _get_secret("YOUTUBE_CLIENT_SECRET")
    )
    youtube_refresh_token: str = field(
        default_factory=lambda: _get_secret("YOUTUBE_REFRESH_TOKEN")
    )
    notification_email: str = field(
        default_factory=lambda: _get_secret("NOTIFICATION_EMAIL")
    )
    sendgrid_api_key: str = field(
        default_factory=lambda: _get_secret("SENDGRID_API_KEY")
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
    youtube_category_id: str = "28"   # Science & Technology
    youtube_privacy: str = "public"
    made_for_kids: bool = False
    license_type: str = "youtube"     # Standard YouTube license

    def __post_init__(self):
        """Validate required credentials are available."""
        required = {
            "ANTHROPIC_API_KEY": self.anthropic_api_key,
            "PEXELS_API_KEY": self.pexels_api_key,
            "YOUTUBE_CLIENT_ID": self.youtube_client_id,
            "YOUTUBE_CLIENT_SECRET": self.youtube_client_secret,
            "YOUTUBE_REFRESH_TOKEN": self.youtube_refresh_token,
        }
        
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(
                f"Missing required credentials in /etc/youtube-pipeline.env:\n"
                f"  {', '.join(missing)}"
            )
