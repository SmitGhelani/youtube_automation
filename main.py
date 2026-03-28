"""
Autonomous YouTube Channel Pipeline
====================================
Runs daily (shorts 9-10 AM) and weekly (long video Saturday 6 PM).
Zero human intervention required.

FREE TOOLS USED:
- Claude API (free tier / Anthropic) — Script + SEO generation
- ElevenLabs (free tier, 10k chars/month) — Voice synthesis
- Pexels API (free) — Stock video footage
- Freesound API (free) — Background music/sounds
- YouTube Data API v3 (free) — Video upload
- GitHub Actions (free) — Cron scheduling
- Pillow (free) — Thumbnail generation
- FFmpeg (free) — Video assembly
"""

import os
import sys
import json
import logging
import argparse
from datetime import datetime
from pathlib import Path

# Import pipeline agents
from agents.trend_agent import TrendAgent
from agents.script_agent import ScriptAgent
from agents.audio_agent import AudioAgent
from agents.video_agent import VideoAgent
from agents.thumbnail_agent import ThumbnailAgent
from agents.assembler_agent import AssemblerAgent
from agents.seo_agent import SEOAgent
from agents.compliance_agent import ComplianceAgent
from agents.upload_agent import UploadAgent
from agents.notification_agent import NotificationAgent
from config import Config

# ─── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("pipeline.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("main")


def run_pipeline(video_type: str = "short"):
    """
    Master pipeline runner.
    video_type: "short" (60s vertical) or "long" (8-12 min horizontal)
    """
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger.info(f"=== Pipeline START | run_id={run_id} | type={video_type} ===")

    cfg = Config()
    workspace = Path(f"workspace/{run_id}")
    workspace.mkdir(parents=True, exist_ok=True)

    result = {
        "run_id": run_id,
        "video_type": video_type,
        "status": "failed",
        "youtube_url": None,
        "error": None,
    }

    try:
        # ── Step 1: Find trending topic ──────────────────────────────────────
        logger.info("Step 1/9 | Trend research...")
        trend = TrendAgent(cfg).find_trending_topic(video_type)
        logger.info(f"Topic selected: {trend['topic']}")

        # ── Step 2: Generate script ──────────────────────────────────────────
        logger.info("Step 2/9 | Script generation...")
        script = ScriptAgent(cfg).generate(trend, video_type)
        (workspace / "script.json").write_text(json.dumps(script, indent=2))

        # ── Step 3: Generate audio (voice + background) ──────────────────────
        logger.info("Step 3/9 | Audio synthesis...")
        audio_path = AudioAgent(cfg).generate(script, workspace)

        # ── Step 4: Fetch and assemble B-roll video footage ──────────────────
        logger.info("Step 4/9 | Video footage fetch...")
        clips_path = VideoAgent(cfg).fetch_clips(script, workspace, video_type)

        # ── Step 5: Generate thumbnail ────────────────────────────────────────
        logger.info("Step 5/9 | Thumbnail generation...")
        thumb_path = ThumbnailAgent(cfg).generate(script, trend, workspace)

        # ── Step 6: Assemble final video ─────────────────────────────────────
        logger.info("Step 6/9 | Video assembly (FFmpeg)...")
        video_path = AssemblerAgent(cfg).assemble(
            clips_path, audio_path, script, workspace, video_type
        )

        # ── Step 7: Generate SEO metadata ────────────────────────────────────
        logger.info("Step 7/9 | SEO metadata generation...")
        metadata = SEOAgent(cfg).generate(script, trend, video_type)
        (workspace / "metadata.json").write_text(json.dumps(metadata, indent=2))

        # ── Step 8: Compliance gate ───────────────────────────────────────────
        logger.info("Step 8/9 | Compliance check...")
        is_compliant, issues = ComplianceAgent(cfg).check(script, metadata)
        if not is_compliant:
            raise ValueError(f"Compliance failed: {issues}")

        # ── Step 9: Upload to YouTube ─────────────────────────────────────────
        logger.info("Step 9/9 | Uploading to YouTube...")
        youtube_url = UploadAgent(cfg).upload(
            video_path=video_path,
            thumb_path=thumb_path,
            metadata=metadata,
            video_type=video_type,
        )

        result["status"] = "success"
        result["youtube_url"] = youtube_url
        result["topic"] = trend["topic"]
        logger.info(f"✅ SUCCESS | {youtube_url}")

    except Exception as e:
        result["error"] = str(e)
        logger.exception(f"❌ Pipeline failed: {e}")

    finally:
        # Always send notification (success or failure)
        NotificationAgent(cfg).send(result)
        (workspace / "result.json").write_text(json.dumps(result, indent=2))

    return result


def main():
    parser = argparse.ArgumentParser(description="Autonomous YouTube Pipeline")
    parser.add_argument(
        "--type",
        choices=["short", "long"],
        default="short",
        help="Video type: 'short' (daily) or 'long' (weekly)",
    )
    args = parser.parse_args()
    result = run_pipeline(args.type)
    sys.exit(0 if result["status"] == "success" else 1)


if __name__ == "__main__":
    main()
