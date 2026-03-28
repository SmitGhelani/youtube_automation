"""
agents/audio_agent.py
Generates:
1. Voice narration via Kokoro TTS (free, local, near-human quality) — PRIMARY
2. ElevenLabs (optional, if API key set and chars remain)
3. Background music via bensound (CC licensed)
4. Mixes both with FFmpeg

Kokoro TTS runs fully locally — no API key, no quota, no cost.
Voice quality is far superior to espeak.
"""

import logging
import subprocess
import requests
import numpy as np
import soundfile as sf
from pathlib import Path

logger = logging.getLogger("AudioAgent")

# Background music URLs (Creative Commons / bensound free license)
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

# Kokoro voice options (all free, local):
#   af_sarah   — American female, warm and clear        ← default, best for YouTube
#   af_nicole  — American female, professional
#   am_adam    — American male, authoritative
#   am_michael — American male, conversational
#   bf_emma    — British female, polished
#   bm_george  — British male, deep
KOKORO_VOICE = "af_sarah"
KOKORO_LANG  = "en-us"
KOKORO_SPEED = 1.0   # 1.0 = natural pace; 0.9 = slightly slower for clarity


class AudioAgent:
    def __init__(self, config):
        self.cfg = config
        self._kokoro = None   # lazy-loaded

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def generate(self, script: dict, workspace: Path) -> Path:
        """Returns path to final mixed audio file (voice + bg music)."""
        narration_path = self._generate_voice(script, workspace)

        music_path = self._get_background_music(
            script.get("background_music_mood", "upbeat electronic"),
            workspace,
        )

        final_path = workspace / "audio_final.aac"
        self._mix_audio(narration_path, music_path, final_path)

        logger.info(f"Audio ready: {final_path}")
        return final_path

    def get_segment_timestamps(self, script: dict, output_path: Path) -> list:
        """Generate per-segment timing for subtitle/caption overlay."""
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

    # ─────────────────────────────────────────────────────────────────────────
    # Voice generation — priority: Kokoro → ElevenLabs → espeak
    # ─────────────────────────────────────────────────────────────────────────

    def _generate_voice(self, script: dict, workspace: Path) -> Path:
        """Extract spoken text then run through TTS chain."""
        if script["video_type"] == "short":
            texts = [seg["text"] for seg in script["segments"]]
        else:
            texts = [ch["text"] for ch in script["chapters"]]

        output_path = workspace / "narration.wav"

        # 1. Kokoro — local, free, high quality
        try:
            return self._kokoro_tts(texts, output_path)
        except Exception as e:
            logger.warning(f"Kokoro TTS failed ({e}), trying ElevenLabs...")

        # 2. ElevenLabs — if key set (burns quota)
        if self.cfg.elevenlabs_api_key:
            try:
                el_path = workspace / "narration.mp3"
                return self._elevenlabs_tts(texts, el_path)
            except Exception as e:
                logger.warning(f"ElevenLabs failed ({e}), falling back to espeak...")

        # 3. espeak — last resort, robotic but always works
        logger.warning("Using espeak fallback — audio quality will be low")
        return self._espeak_tts(texts, workspace / "narration_espeak.wav")

    # ─────────────────────────────────────────────────────────────────────────
    # Kokoro TTS  (primary — local, no API key, excellent quality)
    # ─────────────────────────────────────────────────────────────────────────

    def _get_kokoro(self):
        """Lazy-load Kokoro model (keeps startup fast when not needed)."""
        if self._kokoro is None:
            try:
                from kokoro_onnx import Kokoro
                self._kokoro = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")
                logger.info("Kokoro TTS model loaded")
            except Exception as e:
                raise RuntimeError(
                    f"Kokoro model load failed: {e}. "
                    "Ensure kokoro-onnx is installed and model files are present. "
                    "See README for setup instructions."
                )
        return self._kokoro

    def _kokoro_tts(self, texts: list, output_path: Path) -> Path:
        """
        Generate speech with Kokoro ONNX.
        Handles long scripts by splitting into chunks and concatenating.
        Kokoro has no character limit — runs fully locally.
        """
        kokoro = self._get_kokoro()
        full_text = "\n\n".join(texts)

        # Split at ~1000 chars for stable prosody
        chunks = self._chunk_text(full_text, max_chars=1000)
        all_samples = []
        sample_rate = 24000  # Kokoro default

        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            samples, sr = kokoro.create(
                chunk,
                voice=KOKORO_VOICE,
                speed=KOKORO_SPEED,
                lang=KOKORO_LANG,
            )
            sample_rate = sr
            all_samples.append(samples)

            # Small natural pause between segments (0.4s silence)
            silence = np.zeros(int(sr * 0.4), dtype=samples.dtype)
            all_samples.append(silence)

        if not all_samples:
            raise RuntimeError("Kokoro produced no audio samples")

        combined = np.concatenate(all_samples)
        sf.write(str(output_path), combined, sample_rate)

        duration = len(combined) / sample_rate
        size_kb = output_path.stat().st_size // 1024
        logger.info(
            f"Kokoro TTS: {len(full_text)} chars | "
            f"{len(chunks)} chunks | {duration:.1f}s | {size_kb}KB -> {output_path}"
        )
        return output_path

    # ─────────────────────────────────────────────────────────────────────────
    # ElevenLabs TTS  (optional — uses monthly quota)
    # ─────────────────────────────────────────────────────────────────────────

    def _elevenlabs_tts(self, texts: list, output_path: Path) -> Path:
        """ElevenLabs TTS — 10,000 free chars/month on free tier."""
        full_text = "\n\n".join(texts)

        if len(full_text) > 9800:
            truncated = full_text[:9800]
            last_stop = max(
                truncated.rfind("."),
                truncated.rfind("!"),
                truncated.rfind("?"),
            )
            full_text = truncated[:last_stop + 1] if last_stop > 0 else truncated
            logger.warning(f"Text trimmed to {len(full_text)} chars for ElevenLabs free tier")

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.cfg.elevenlabs_voice_id}"
        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self.cfg.elevenlabs_api_key,
        }
        payload = {
            "text": full_text,
            "model_id": self.cfg.elevenlabs_model,
            "output_format": self.cfg.elevenlabs_output_format,
            "voice_settings": {
                "stability": 0.4,
                "similarity_boost": 0.75,
                "style": 0.3,
                "use_speaker_boost": True,
            },
        }

        response = requests.post(url, json=payload, headers=headers, timeout=60)
        response.raise_for_status()

        output_path.write_bytes(response.content)
        logger.info(f"ElevenLabs TTS: {len(full_text)} chars -> {output_path}")
        return output_path

    # ─────────────────────────────────────────────────────────────────────────
    # espeak TTS  (last-resort fallback — robotic but always available)
    # ─────────────────────────────────────────────────────────────────────────

    def _espeak_tts(self, texts: list, output_path: Path) -> Path:
        """espeak via subprocess — headless Linux safe, low quality fallback."""
        full_text = " ".join(texts)
        txt_path = output_path.with_suffix(".txt")
        txt_path.write_text(full_text, encoding="utf-8")

        cmd = [
            "espeak",
            "-f", str(txt_path),
            "-w", str(output_path),
            "-s", "150",
            "-v", "en",
            "-a", "100",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        txt_path.unlink(missing_ok=True)

        if result.returncode != 0:
            raise RuntimeError(f"espeak failed: {result.stderr}")
        if not output_path.exists() or output_path.stat().st_size < 500:
            raise RuntimeError(f"espeak produced empty file: {output_path}")

        logger.info(f"espeak TTS -> {output_path} ({output_path.stat().st_size // 1024}KB)")
        return output_path

    # ─────────────────────────────────────────────────────────────────────────
    # Background music
    # ─────────────────────────────────────────────────────────────────────────

    def _get_background_music(self, mood: str, workspace: Path) -> Path:
        """Download royalty-free background music from bensound."""
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

        # Fallback: 60s of silence
        silence_path = workspace / "background_music.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
             "-t", "60", str(silence_path)],
            check=True, capture_output=True,
        )
        logger.warning("Using silent background track (no music downloaded)")
        return silence_path

    # ─────────────────────────────────────────────────────────────────────────
    # Audio mixing
    # ─────────────────────────────────────────────────────────────────────────

    def _mix_audio(self, voice_path: Path, music_path: Path, output_path: Path):
        """Mix voice (100%) + background music (15%) -> AAC output."""
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(voice_path)],
            capture_output=True, text=True,
        )
        try:
            duration = float(result.stdout.strip())
        except ValueError:
            duration = 60.0

        cmd = [
            "ffmpeg", "-y",
            "-i", str(voice_path),
            "-i", str(music_path),
            "-filter_complex",
            f"[0:a]volume=1.0[voice];"
            f"[1:a]aloop=loop=-1:size=2000000000,atrim=duration={duration},volume=0.15[music];"
            f"[voice][music]amix=inputs=2:duration=first[out]",
            "-map", "[out]",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "44100",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Mix failed:\n{result.stderr[-500:]}")
            raise RuntimeError("FFmpeg audio mix failed")
        logger.info(f"Audio mixed -> {output_path} ({duration:.1f}s)")

    # ─────────────────────────────────────────────────────────────────────────
    # Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _chunk_text(self, text: str, max_chars: int = 1000) -> list:
        """Split text into chunks at sentence boundaries under max_chars."""
        sentences = []
        for para in text.split("\n\n"):
            for s in para.split(". "):
                s = s.strip()
                if s:
                    sentences.append(s if s.endswith(".") else s + ".")

        chunks, current = [], ""
        for sentence in sentences:
            if len(current) + len(sentence) + 1 <= max_chars:
                current += (" " if current else "") + sentence
            else:
                if current:
                    chunks.append(current)
                current = sentence

        if current:
            chunks.append(current)

        return chunks
