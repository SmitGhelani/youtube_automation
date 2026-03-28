"""
agents/audio_agent.py
Generates:
1. Voice narration via ElevenLabs (free tier) or pyttsx3 (completely free fallback)
2. Background music via freesound.org API (free)
3. Mixes both with FFmpeg
"""

import os
import logging
import subprocess
import requests
from pathlib import Path

logger = logging.getLogger("AudioAgent")

# Background music URLs (Creative Commons, royalty-free)
# These are from freemusicarchive.org and similar CC sources
FREE_MUSIC_URLS = {
    "upbeat electronic": [
        "https://www.bensound.com/bensound-music/bensound-ukulele.mp3",
        "https://www.bensound.com/bensound-music/bensound-creativeminds.mp3",
    ],
    "cinematic inspiring": [
        "https://www.bensound.com/bensound-music/bensound-epic.mp3",
        "https://www.bensound.com/bensound-music/bensound-inspiring.mp3",
    ],
    "calm background": [
        "https://www.bensound.com/bensound-music/bensound-slowmotion.mp3",
    ],
}


class AudioAgent:
    def __init__(self, config):
        self.cfg = config

    def generate(self, script: dict, workspace: Path) -> Path:
        """
        Returns path to final mixed audio file (voice + bg music).
        """
        # Step 1: Generate voice narration
        narration_path = self._generate_voice(script, workspace)

        # Step 2: Download background music
        music_path = self._get_background_music(
            script.get("background_music_mood", "upbeat electronic"),
            workspace
        )

        # Step 3: Mix voice + background music
        final_path = workspace / "audio_final.mp3"
        self._mix_audio(narration_path, music_path, final_path)

        logger.info(f"Audio ready: {final_path}")
        return final_path

    def _generate_voice(self, script: dict, workspace: Path) -> Path:
        """Try ElevenLabs first, fall back to pyttsx3."""
        # Extract all spoken text
        if script["video_type"] == "short":
            segments_text = []
            for seg in script["segments"]:
                segments_text.append(seg["text"])
        else:
            segments_text = []
            for ch in script["chapters"]:
                segments_text.append(ch["text"])

        output_path = workspace / "narration.mp3"

        # Try ElevenLabs (10k free chars/month)
        if self.cfg.elevenlabs_api_key:
            try:
                return self._elevenlabs_tts(segments_text, output_path)
            except Exception as e:
                logger.warning(f"ElevenLabs failed ({e}), falling back to pyttsx3")

        # Fallback: pyttsx3 (100% free, offline)
        return self._pyttsx3_tts(segments_text, output_path)

    def _elevenlabs_tts(self, texts: list, output_path: Path) -> Path:
        """ElevenLabs TTS — 10,000 free characters/month on free tier."""
        full_text = " ... ".join(texts)  # Pause between segments

        # Respect free tier: 10k chars/month. Shorts are ~300-500 chars.
        if len(full_text) > 10000:
            full_text = full_text[:10000]
            logger.warning("Text truncated to 10k chars for ElevenLabs free tier")

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.cfg.elevenlabs_voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.cfg.elevenlabs_api_key,
        }
        payload = {
            "text": full_text,
            "model_id": self.cfg.elevenlabs_model,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True,
            },
        }

        response = requests.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()

        output_path.write_bytes(response.content)
        logger.info(f"ElevenLabs TTS: {len(full_text)} chars → {output_path}")
        return output_path

    def _pyttsx3_tts(self, texts: list, output_path: Path) -> Path:
        """
        pyttsx3: 100% free, offline TTS using system voices.
        Quality is basic but functional and zero cost.
        """
        import pyttsx3
        import tempfile

        engine = pyttsx3.init()

        # Improve voice quality settings
        engine.setProperty("rate", 165)   # Words per minute (normal = 150-200)
        engine.setProperty("volume", 0.95)

        # Use a better voice if available
        voices = engine.getProperty("voices")
        for voice in voices:
            if "female" in voice.name.lower() or "zira" in voice.name.lower():
                engine.setProperty("voice", voice.id)
                break

        full_text = " ".join(texts)

        # pyttsx3 saves to WAV, then we convert to MP3 with FFmpeg
        wav_path = output_path.with_suffix(".wav")
        engine.save_to_file(full_text, str(wav_path))
        engine.runAndWait()

        # Convert WAV → MP3
        cmd = [
            "ffmpeg", "-y",
            "-i", str(wav_path),
            "-codec:a", "libmp3lame",
            "-b:a", "128k",
            str(output_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        wav_path.unlink(missing_ok=True)

        logger.info(f"pyttsx3 TTS done → {output_path}")
        return output_path

    def _get_background_music(self, mood: str, workspace: Path) -> Path:
        """
        Download royalty-free background music.
        Uses bensound.com (free for YouTube with attribution in description).
        """
        music_path = workspace / "background_music.mp3"

        urls = FREE_MUSIC_URLS.get(mood, FREE_MUSIC_URLS["upbeat electronic"])

        for url in urls:
            try:
                resp = requests.get(url, timeout=30, stream=True)
                if resp.status_code == 200:
                    with open(music_path, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=8192):
                            f.write(chunk)
                    logger.info(f"Background music downloaded: {url}")
                    return music_path
            except Exception as e:
                logger.warning(f"Music download failed ({url}): {e}")

        # Last resort: generate 60s of silence
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", "60",
            str(music_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        logger.warning("Using silent background track (no music available)")
        return music_path

    def _mix_audio(self, voice_path: Path, music_path: Path, output_path: Path):
        """
        Mix voice (full volume) with background music (15% volume).
        Voice is -3dB louder to ensure clarity.
        """
        # Get voice duration
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(voice_path)],
            capture_output=True, text=True
        )
        duration = float(result.stdout.strip())

        cmd = [
            "ffmpeg", "-y",
            "-i", str(voice_path),
            "-i", str(music_path),
            "-filter_complex",
            # Voice at full volume, music at 15%, loop music if shorter than voice
            f"[0:a]volume=1.0[voice];"
            f"[1:a]aloop=loop=-1:size=2e+09,atrim=duration={duration},volume=0.15[music];"
            f"[voice][music]amix=inputs=2:duration=first[out]",
            "-map", "[out]",
            "-codec:a", "libmp3lame",
            "-b:a", "192k",
            str(output_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        logger.info(f"Audio mixed → {output_path} ({duration:.1f}s)")

    def get_segment_timestamps(self, script: dict, output_path: Path) -> list:
        """
        Generate per-segment timing for subtitle/caption overlay.
        Uses cumulative duration from script.
        """
        timestamps = []
        current = 0.0
        segments = script.get("segments") or script.get("chapters", [])

        for seg in segments:
            dur = seg.get("duration_sec", 10)
            timestamps.append({
                "id": seg["id"],
                "start": current,
                "end": current + dur,
                "caption": seg.get("caption", ""),
                "text": seg.get("text", ""),
            })
            current += dur

        return timestamps
