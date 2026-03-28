"""
agents/video_agent.py
Fetches royalty-free B-roll video clips from Pexels (free API).
Downloads and prepares clips for each script segment.
"""

import logging
import requests
import subprocess
from pathlib import Path

logger = logging.getLogger("VideoAgent")

PEXELS_VIDEO_API = "https://api.pexels.com/videos/search"


class VideoAgent:
    def __init__(self, config):
        self.cfg = config
        self.headers = {"Authorization": config.pexels_api_key}

    def fetch_clips(self, script: dict, workspace: Path, video_type: str) -> Path:
        """
        Downloads one B-roll clip per script segment.
        Returns path to folder containing all clips.
        """
        clips_dir = workspace / "clips"
        clips_dir.mkdir(exist_ok=True)

        segments = script.get("segments") or script.get("chapters", [])

        # Determine resolution based on video type
        if video_type == "short":
            orientation = "portrait"   # 9:16 for Shorts
            min_width = 1080
            min_height = 1920
        else:
            orientation = "landscape"  # 16:9 for long video
            min_width = 1920
            min_height = 1080

        downloaded_clips = []
        for seg in segments:
            seg_id = seg.get("id", len(downloaded_clips) + 1)
            duration = seg.get("duration_sec", 10)

            # Get B-roll search query
            if "broll_query" in seg:
                queries = [seg["broll_query"]]
            elif "broll_queries" in seg:
                queries = seg["broll_queries"]
            else:
                queries = [script.get("topic", "technology")]

            clip_path = clips_dir / f"clip_{seg_id:03d}.mp4"

            # Try each query until we find a clip
            clip_found = False
            for query in queries:
                try:
                    clip_url = self._search_pexels(query, orientation, duration)
                    if clip_url:
                        self._download_clip(clip_url, clip_path, duration, video_type)
                        downloaded_clips.append(clip_path)
                        clip_found = True
                        logger.info(f"Clip {seg_id}: '{query}' → {clip_path.name}")
                        break
                except Exception as e:
                    logger.warning(f"Clip {seg_id} query '{query}' failed: {e}")

            if not clip_found:
                # Generate a solid color fallback clip
                logger.warning(f"Clip {seg_id}: using fallback color clip")
                self._generate_fallback_clip(clip_path, duration, video_type)
                downloaded_clips.append(clip_path)

        return clips_dir

    def _search_pexels(self, query: str, orientation: str, duration_needed: int) -> str:
        """
        Search Pexels for a video clip.
        Returns the download URL of the best matching clip.
        Pexels API is FREE with an API key (sign up at pexels.com/api).
        """
        params = {
            "query": query,
            "orientation": orientation,
            "size": "large",       # Minimum 4K or Full HD
            "per_page": 10,
            "page": 1,
        }

        resp = requests.get(
            PEXELS_VIDEO_API,
            headers=self.headers,
            params=params,
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        videos = data.get("videos", [])
        if not videos:
            return None

        # Find a clip that is long enough
        for video in videos:
            duration = video.get("duration", 0)
            if duration >= duration_needed:
                # Pick highest quality file
                video_files = sorted(
                    video.get("video_files", []),
                    key=lambda x: x.get("width", 0) or 0,
                    reverse=True,
                )
                for vf in video_files:
                    if vf.get("file_type") == "video/mp4":
                        return vf["link"]

        # If no clip is long enough, take the first one (we'll loop it)
        for video in videos:
            video_files = sorted(
                video.get("video_files", []),
                key=lambda x: x.get("width", 0) or 0,
                reverse=True,
            )
            for vf in video_files:
                if vf.get("file_type") == "video/mp4":
                    return vf["link"]

        return None

    def _download_clip(self, url: str, output_path: Path, duration: int, video_type: str):
        """Download and trim/scale a video clip using FFmpeg."""
        import tempfile

        # Download to temp file
        temp_path = output_path.with_suffix(".tmp.mp4")
        resp = requests.get(url, stream=True, timeout=60)
        resp.raise_for_status()
        with open(temp_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)

        # Set target resolution
        if video_type == "short":
            vf_scale = "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
        else:
            vf_scale = "scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080"

        # Trim to needed duration and re-encode to target resolution
        cmd = [
            "ffmpeg", "-y",
            "-i", str(temp_path),
            "-t", str(duration + 1),       # +1 second buffer
            "-vf", vf_scale,
            "-r", str(self.cfg.video_fps),
            "-c:v", "libx264",
            "-preset", "fast",             # Faster during downloads
            "-crf", "20",
            "-an",                          # Remove audio (we add our own)
            str(output_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        temp_path.unlink(missing_ok=True)

    def _generate_fallback_clip(self, output_path: Path, duration: int, video_type: str):
        """Generate a dark gradient clip as fallback (FFmpeg only)."""
        if video_type == "short":
            size = "1080x1920"
        else:
            size = "1920x1080"

        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", f"color=c=0x0a0a2e:s={size}:r=30",
            "-t", str(duration),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "20",
            str(output_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
