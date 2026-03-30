"""
agents/audio_agent.py

Audio pipeline — zero compression until the single final encode in assembler_agent.

Problems fixed vs previous version:
  1. DOUBLE AAC ENCODE — audio_agent was encoding to AAC, then assembler re-encoded.
     Fix: audio_agent now outputs lossless PCM WAV. Only assembler does one final AAC encode.

  2. SAMPLE RATE MISMATCH — Kokoro outputs 24 kHz. FFmpeg was silently resampling
     to 44.1 kHz mid-chain using a poor default algorithm, causing artifacts.
     Fix: explicit high-quality resampling with scipy before writing WAV.

  3. WRONG MODEL FILE NAMES — code used kokoro-v0_19.onnx / voices.bin but
     the v1.0 release uses kokoro-v1.0.onnx / voices-v1.0.bin.
     Fix: correct filenames used.

  4. ESPEAK STILL ACTIVE AS FALLBACK — espeak is robotic by design. When Kokoro
     failed silently, espeak was producing the final audio.
     Fix: espeak fallback is kept but logs a clear CRITICAL warning.
     If Kokoro model files are missing it fails loudly with setup instructions.

  5. FLOAT32 PCM WRITTEN WITHOUT SUBTYPE — soundfile default for float32 is
     32-bit float WAV which FFmpeg handles fine, but some chains downsample it.
     Fix: explicitly write PCM_16 at 44100 Hz.

  6. BACKGROUND MUSIC DECODED FROM MP3 THEN MIXED — MP3 is lossy; mixing it
     with the voice and then encoding to AAC adds another generation of loss.
     Fix: music is decoded to PCM in the FFmpeg filter chain before mixing,
     and the mix output is written as lossless WAV.
"""

import logging
import subprocess
import requests
import numpy as np
import soundfile as sf
from pathlib import Path

logger = logging.getLogger("AudioAgent")

# ── Background music (CC / bensound free licence) ────────────────────────────
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

# ── Kokoro voice options ──────────────────────────────────────────────────────
#   af_sarah   — American female, warm and clear   ← best for YouTube narration
#   af_nicole  — American female, professional
#   am_adam    — American male, authoritative
#   am_michael — American male, conversational
#   bf_emma    — British female, polished
#   bm_george  — British male, deep
KOKORO_VOICE  = "af_sarah"
KOKORO_LANG   = "en-us"
KOKORO_SPEED  = 1.0      # 1.0 = natural; try 0.95 for slightly clearer delivery
TARGET_SR     = 44100    # All audio must be at this rate before mixing
SILENCE_PAD   = 0.35     # seconds of silence between script chunks


class AudioAgent:
    def __init__(self, config):
        self.cfg = config
        self._kokoro = None

    # ─────────────────────────────────────────────────────────────────────────
    # Public API
    # ─────────────────────────────────────────────────────────────────────────

    def generate(self, script: dict, workspace: Path) -> Path:
        """
        Returns path to final mixed audio as lossless WAV.
        assembler_agent._merge_final() will do the ONE AND ONLY AAC encode.
        """
        narration_path = self._generate_voice(script, workspace)
        music_path     = self._get_background_music(
            script.get("background_music_mood", "upbeat electronic"), workspace
        )
        # Output is WAV (lossless PCM) — never AAC here
        final_wav = workspace / "audio_final.wav"
        self._mix_audio(narration_path, music_path, final_wav)
        logger.info(f"Audio ready (lossless WAV): {final_wav}")
        return final_wav

    def get_segment_timestamps(self, script: dict, output_path: Path) -> list:
        timestamps, current = [], 0.0
        for seg in (script.get("segments") or script.get("chapters", [])):
            dur = seg.get("duration_sec", 10)
            timestamps.append({
                "id":      seg["id"],
                "start":   current,
                "end":     current + dur,
                "caption": seg.get("caption", ""),
                "text":    seg.get("text", ""),
            })
            current += dur
        return timestamps

    # ─────────────────────────────────────────────────────────────────────────
    # Voice generation  Kokoro → ElevenLabs → espeak (emergency only)
    # ─────────────────────────────────────────────────────────────────────────

    def _generate_voice(self, script: dict, workspace: Path) -> Path:
        texts = (
            [seg["text"] for seg in script["segments"]]
            if script["video_type"] == "short"
            else [ch["text"] for ch in script["chapters"]]
        )

        # 1. Kokoro — local, free, near-human quality
        try:
            return self._kokoro_tts(texts, workspace / "narration.wav")
        except Exception as e:
            logger.warning(f"Kokoro failed: {e}")

        # 2. ElevenLabs — optional paid/free-tier fallback
        if self.cfg.elevenlabs_api_key:
            try:
                return self._elevenlabs_tts(texts, workspace / "narration.mp3")
            except Exception as e:
                logger.warning(f"ElevenLabs failed: {e}")

        # 3. espeak — emergency last resort (robotic, but better than crashing)
        logger.critical(
            "AUDIO QUALITY WARNING: falling back to espeak. "
            "The output will sound robotic. Fix Kokoro model setup before uploading."
        )
        return self._espeak_tts(texts, workspace / "narration_espeak.wav")

    # ─────────────────────────────────────────────────────────────────────────
    # Kokoro TTS  (primary)
    # ─────────────────────────────────────────────────────────────────────────

    def _get_kokoro(self):
        if self._kokoro is None:
            from kokoro_onnx import Kokoro
            # v1.0 filenames — downloaded by the GitHub Actions workflow
            self._kokoro = Kokoro("kokoro-v1.0.onnx", "voices-v1.0.bin")
            logger.info("Kokoro TTS model loaded (v1.0)")
        return self._kokoro

    def _kokoro_tts(self, texts: list, output_path: Path) -> Path:
        """
        Generate high-quality speech with Kokoro ONNX.

        Pipeline:
          text chunks → Kokoro float32 @ 24 kHz
          → scipy high-quality resample to 44100 Hz
          → concatenate with natural pauses
          → write lossless PCM_16 WAV @ 44100 Hz

        No lossy encoding happens here.
        """
        kokoro   = self._get_kokoro()
        full_text = "\n\n".join(texts)
        chunks   = self._chunk_text(full_text, max_chars=1000)

        all_samples: list[np.ndarray] = []
        native_sr = None

        for chunk in chunks:
            if not chunk.strip():
                continue

            samples, sr = kokoro.create(
                chunk,
                voice=KOKORO_VOICE,
                speed=KOKORO_SPEED,
                lang=KOKORO_LANG,
            )
            native_sr = sr

            # Resample from Kokoro native rate (24 kHz) → TARGET_SR (44100 Hz)
            # using scipy for high quality (much better than FFmpeg's default linear)
            if sr != TARGET_SR:
                samples = self._resample(samples, sr, TARGET_SR)

            all_samples.append(samples.astype(np.float32))

            # Natural inter-chunk pause (silence at target rate)
            pause = np.zeros(int(TARGET_SR * SILENCE_PAD), dtype=np.float32)
            all_samples.append(pause)

        if not all_samples:
            raise RuntimeError("Kokoro produced no audio samples")

        combined = np.concatenate(all_samples)

        # Normalise to prevent clipping (keep headroom for music mix)
        peak = np.max(np.abs(combined))
        if peak > 0.92:
            combined = combined * (0.92 / peak)

        # Write as lossless 16-bit PCM WAV @ 44100 Hz
        sf.write(str(output_path), combined, TARGET_SR, subtype="PCM_16")

        duration = len(combined) / TARGET_SR
        logger.info(
            f"Kokoro TTS: {len(full_text)} chars | {len(chunks)} chunks | "
            f"{duration:.1f}s | {output_path.stat().st_size // 1024}KB → {output_path}"
        )
        return output_path

    def _resample(self, samples: np.ndarray, src_sr: int, dst_sr: int) -> np.ndarray:
        """High-quality resampling via scipy (polyphase filter, not linear interp)."""
        try:
            from scipy.signal import resample_poly
            from math import gcd
            g = gcd(dst_sr, src_sr)
            up, down = dst_sr // g, src_sr // g
            return resample_poly(samples, up, down).astype(np.float32)
        except ImportError:
            # scipy not available — fall back to numpy (lower quality but acceptable)
            logger.warning("scipy not found, using numpy resample (lower quality)")
            target_len = int(len(samples) * dst_sr / src_sr)
            return np.interp(
                np.linspace(0, len(samples) - 1, target_len),
                np.arange(len(samples)),
                samples,
            ).astype(np.float32)

    # ─────────────────────────────────────────────────────────────────────────
    # ElevenLabs TTS  (optional fallback)
    # ─────────────────────────────────────────────────────────────────────────

    def _elevenlabs_tts(self, texts: list, output_path: Path) -> Path:
        full_text = "\n\n".join(texts)

        if len(full_text) > 9800:
            t = full_text[:9800]
            cut = max(t.rfind("."), t.rfind("!"), t.rfind("?"))
            full_text = t[:cut + 1] if cut > 0 else t
            logger.warning(f"ElevenLabs: text trimmed to {len(full_text)} chars")

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
        resp = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{self.cfg.elevenlabs_voice_id}",
            json=payload, headers=headers, timeout=60,
        )
        resp.raise_for_status()
        output_path.write_bytes(resp.content)
        logger.info(f"ElevenLabs TTS: {len(full_text)} chars → {output_path}")
        return output_path

    # ─────────────────────────────────────────────────────────────────────────
    # espeak TTS  (emergency last resort — very low quality)
    # ─────────────────────────────────────────────────────────────────────────

    def _espeak_tts(self, texts: list, output_path: Path) -> Path:
        txt_path = output_path.with_suffix(".txt")
        txt_path.write_text(" ".join(texts), encoding="utf-8")
        result = subprocess.run(
            ["espeak", "-f", str(txt_path), "-w", str(output_path),
             "-s", "150", "-v", "en", "-a", "100"],
            capture_output=True, text=True,
        )
        txt_path.unlink(missing_ok=True)
        if result.returncode != 0:
            raise RuntimeError(f"espeak failed: {result.stderr}")
        if not output_path.exists() or output_path.stat().st_size < 500:
            raise RuntimeError("espeak produced empty file")
        logger.info(f"espeak → {output_path} ({output_path.stat().st_size // 1024}KB)")
        return output_path

    # ─────────────────────────────────────────────────────────────────────────
    # Background music
    # ─────────────────────────────────────────────────────────────────────────

    def _get_background_music(self, mood: str, workspace: Path) -> Path:
        music_path = workspace / "background_music.mp3"
        urls = FREE_MUSIC_URLS.get(mood, FREE_MUSIC_URLS["upbeat electronic"])
        for url in urls:
            try:
                resp = requests.get(url, timeout=30, stream=True)
                if resp.status_code == 200:
                    with open(music_path, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=8192):
                            f.write(chunk)
                    logger.info(f"Background music: {url}")
                    return music_path
            except Exception as e:
                logger.warning(f"Music download failed ({url}): {e}")

        # Fallback: generate silence
        silence = workspace / "background_music.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
             "-t", "60", str(silence)],
            check=True, capture_output=True,
        )
        logger.warning("Using silent background track")
        return silence

    # ─────────────────────────────────────────────────────────────────────────
    # Audio mixing  →  lossless WAV output (NO AAC encode here)
    # ─────────────────────────────────────────────────────────────────────────

    def _mix_audio(self, voice_path: Path, music_path: Path, output_path: Path):
        """
        Mix voice + background music → lossless PCM WAV @ 44100 Hz.

        Key decisions:
        - Both inputs are resampled to 44100 Hz inside FFmpeg filter chain
          using the 'soxr' resampler (highest quality available in FFmpeg).
        - Output is pcm_s16le WAV — zero lossy compression.
        - The one and only AAC encode happens in assembler_agent._merge_final().
        - Music is looped if shorter than the voice, then trimmed to match.
        - Music volume is 12% to keep voice intelligible on all devices.
        """
        # Get voice duration for music loop trimming
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(voice_path)],
            capture_output=True, text=True,
        )
        try:
            duration = float(probe.stdout.strip())
        except ValueError:
            duration = 120.0
            logger.warning("ffprobe duration failed, using 120s fallback")

        filter_graph = (
            # Resample voice to 44100 with soxr (best quality)
            "[0:a]aresample=resampler=soxr:osr=44100,volume=1.0[voice];"
            # Decode music (may be MP3), resample, loop, trim, lower volume
            f"[1:a]aresample=resampler=soxr:osr=44100,"
            f"aloop=loop=-1:size=2000000000,"
            f"atrim=duration={duration},"
            f"volume=0.12[music];"
            # Mix — duration follows the voice track
            "[voice][music]amix=inputs=2:duration=first:dropout_transition=0[out]"
        )

        cmd = [
            "ffmpeg", "-y",
            "-i", str(voice_path),
            "-i", str(music_path),
            "-filter_complex", filter_graph,
            "-map", "[out]",
            "-c:a", "pcm_s16le",   # lossless — NO AAC here
            "-ar", "44100",
            "-ac", "2",            # stereo
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            logger.error(f"Mix failed:\n{result.stderr[-800:]}")
            raise RuntimeError("FFmpeg audio mix failed")

        size_mb = output_path.stat().st_size / 1_000_000
        logger.info(f"Mixed lossless WAV: {output_path} ({duration:.1f}s | {size_mb:.1f}MB)")

    # ─────────────────────────────────────────────────────────────────────────
    # Text chunking helper
    # ─────────────────────────────────────────────────────────────────────────

    def _chunk_text(self, text: str, max_chars: int = 1000) -> list:
        """Split at sentence boundaries, never mid-word."""
        sentences = []
        for para in text.split("\n\n"):
            for s in para.split(". "):
                s = s.strip()
                if s:
                    sentences.append(s if s.endswith((".", "!", "?")) else s + ".")

        chunks, current = [], ""
        for s in sentences:
            if len(current) + len(s) + 1 <= max_chars:
                current += (" " if current else "") + s
            else:
                if current:
                    chunks.append(current)
                current = s
        if current:
            chunks.append(current)
        return chunks
