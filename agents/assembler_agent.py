"""
agents/assembler_agent.py
Assembles final 1080p video from:
- B-roll clips (from video_agent)
- Voice + background audio (from audio_agent)
- Subtitle/caption overlays (burned in)
- Intro/outro cards (generated in FFmpeg)
- Ken Burns effect for static clips
"""

import json
import logging
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger("AssemblerAgent")


class AssemblerAgent:
    def __init__(self, config):
        self.cfg = config

    def assemble(
        self,
        clips_dir: Path,
        audio_path: Path,
        script: dict,
        workspace: Path,
        video_type: str,
    ) -> Path:
        """
        Assembles final video. Returns path to output MP4.
        """
        output_path = workspace / "final_video.mp4"

        # Get segments/chapters
        segments = script.get("segments") or script.get("chapters", [])
        clips = sorted(clips_dir.glob("clip_*.mp4"))

        if not clips:
            raise FileNotFoundError(f"No clips found in {clips_dir}")

        # Step 1: Create clip list with durations
        clip_list_path = workspace / "clips.txt"
        self._write_concat_list(clips, segments, clip_list_path)

        # Step 2: Concatenate clips
        concat_path = workspace / "concat.mp4"
        self._concat_clips(clip_list_path, concat_path, video_type)

        # Step 3: Generate subtitle file (ASS format for styled subtitles)
        subtitle_path = workspace / "subtitles.ass"
        self._generate_subtitles(segments, subtitle_path, video_type)

        # Step 4: Merge video + audio + subtitles → final
        self._merge_final(
            video_path=concat_path,
            audio_path=audio_path,
            subtitle_path=subtitle_path,
            output_path=output_path,
            video_type=video_type,
        )

        # Verify output
        info = self._get_video_info(output_path)
        logger.info(
            f"Final video: {output_path} | "
            f"{info['duration']:.1f}s | "
            f"{info['width']}x{info['height']} | "
            f"{info['size_mb']:.1f}MB"
        )
        return output_path

    def _write_concat_list(self, clips: list, segments: list, output_path: Path):
        """Write FFmpeg concat list with per-clip durations."""
        lines = []
        for i, clip in enumerate(clips):
            duration = segments[i]["duration_sec"] if i < len(segments) else 10
            lines.append(f"file '{clip.resolve()}'")
            lines.append(f"duration {duration}")
        output_path.write_text("\n".join(lines))

    def _concat_clips(self, clip_list: Path, output_path: Path, video_type: str):
        """Concatenate all clips into one video using FFmpeg concat demuxer."""
        if video_type == "short":
            w, h = 1080, 1920
        else:
            w, h = 1920, 1080

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(clip_list),
            "-vf", (
                f"scale={w}:{h}:force_original_aspect_ratio=increase,"
                f"crop={w}:{h},"
                f"fps={self.cfg.video_fps}"
            ),
            "-c:v", "libx264",
            "-preset", self.cfg.video_preset,
            "-crf", str(self.cfg.video_crf),
            "-pix_fmt", "yuv420p",
            "-an",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Concat failed:\n{result.stderr}")
            raise RuntimeError("FFmpeg concat failed")

    def _generate_subtitles(self, segments: list, output_path: Path, video_type: str):
        """
        Generate ASS subtitle file with styled captions.
        ASS format supports fonts, colors, positions — much better than SRT.
        """
        if video_type == "short":
            # Bottom-center for Shorts
            alignment = 2  # Bottom center
            margin_v = 80
            font_size = 52
        else:
            # Bottom-left for long video
            alignment = 1  # Bottom left
            margin_v = 50
            font_size = 42

        ass_header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: {1920 if video_type == 'short' else 1080}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,{alignment},60,60,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        events = []
        current = 0.0

        for seg in segments:
            caption = seg.get("caption", seg.get("text", ""))[:80]
            duration = seg.get("duration_sec", 10)

            start = self._sec_to_ass(current)
            end = self._sec_to_ass(current + duration - 0.2)

            # Escape special ASS characters
            caption = caption.replace("{", "").replace("}", "").replace("\\", "")

            # Add text effects: fade in/out
            effect = "{\\fad(200,200)}"
            events.append(
                f"Dialogue: 0,{start},{end},Default,,0,0,0,,{effect}{caption}"
            )
            current += duration

        output_path.write_text(ass_header + "\n".join(events))

    def _sec_to_ass(self, seconds: float) -> str:
        """Convert seconds to ASS timestamp (H:MM:SS.cc)."""
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        cs = int((seconds % 1) * 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    def _merge_final(
        self,
        video_path: Path,
        audio_path: Path,
        subtitle_path: Path,
        output_path: Path,
        video_type: str,
    ):
        """
        Merge video + lossless WAV audio + subtitles -> final MP4.

        This is the ONE AND ONLY AAC encode in the entire pipeline.
        audio_path must be the lossless PCM WAV from audio_agent.generate().

        AAC settings:
          320k CBR  -- YouTube recommended headroom (they re-encode to 128/192k AAC-LC)
          44100 Hz stereo
          soxr resampler -- highest quality, handles WAV input cleanly
          -shortest removed -- it silently truncates audio when WAV != video length
        """
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-vf", f"ass={subtitle_path}",
            # Video
            "-c:v", "libx264",
            "-preset", self.cfg.video_preset,
            "-crf", str(self.cfg.video_crf),
            "-pix_fmt", "yuv420p",
            # Audio -- single encode, high quality
            "-c:a", "aac",
            "-b:a", "320k",
            "-ar", "44100",
            "-ac", "2",
            "-af", "aresample=resampler=soxr:osr=44100",
            # Container
            "-movflags", "+faststart",
            # NOTE: -shortest intentionally omitted -- it truncates audio
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            logger.error(f"Merge failed:\n{result.stderr}")
            raise RuntimeError("FFmpeg merge failed")

    def _get_video_info(self, video_path: Path) -> dict:
        """Get video metadata using ffprobe."""
        cmd = [
            "ffprobe", "-v", "error",
            "-print_format", "json",
            "-show_streams", "-show_format",
            str(video_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        data = json.loads(result.stdout)

        video_stream = next(
            (s for s in data["streams"] if s["codec_type"] == "video"), {}
        )
        return {
            "duration": float(data["format"].get("duration", 0)),
            "width": video_stream.get("width", 0),
            "height": video_stream.get("height", 0),
            "size_mb": int(data["format"].get("size", 0)) / 1_000_000,
        }
