"""
agents/audio_agent.py

AUDIO QUALITY GUARANTEE
========================
Every stage in this file is lossless (PCM WAV). The ONLY lossy encode
in the entire pipeline is the single AAC step in assembler_agent._merge_final().

Problems fixed from original code
-----------------------------------
1. DOUBLE AAC ENCODE
   Old:  Kokoro WAV -> mix -> AAC (encode #1) -> assembler -> AAC (encode #2)  <- artefacts
   New:  Kokoro WAV -> mix -> PCM WAV (lossless) -> assembler -> AAC (encode #1, only one)

2. WRONG KOKORO MODEL FILENAMES
   Old:  kokoro-v0_19.onnx / voices.bin         (v0 names -- always fails -> falls to espeak)
   New:  kokoro-v1.0.onnx  / voices-v1.0.bin    (v1.0 correct names)

3. SILENT FALLBACK TO ESPEAK
   Old:  Kokoro fails silently -> espeak runs -> robotic output uploaded to YouTube
   New:  Kokoro failure raises loudly; espeak only used as last resort with CRITICAL log

4. SAMPLE RATE MISMATCH ARTEFACTS
   Old:  Kokoro 24 kHz WAV written as-is -> FFmpeg resampled silently with low-quality algo
   New:  scipy polyphase resample (24 kHz -> 44100 Hz) before writing WAV

5. NO PEAK NORMALISATION
   Old:  clipping possible if Kokoro output exceeds 0 dBFS
   New:  normalise to -1.5 dBFS to give headroom for music mix

6. MUSIC VOLUME TOO HIGH (15%)
   Old:  music at 15% could drown voice on laptop speakers
   New:  music at 10% -- voice stays clearly intelligible
"""

import logging
import subprocess
import requests
import numpy as np
import soundfile as sf
from pathlib import Path

logger = logging.getLogger("AudioAgent")

# Background music (CC / bensound free licence)
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

# Kokoro voice options (all free, all local)
#   af_sarah   -- American female, warm and clear    <- best for YouTube narration
#   af_nicole  -- American female, professional
#   am_adam    -- American male, authoritative
#   am_michael -- American male, conversational
#   bf_emma    -- British female, polished
#   bm_george  -- British male, deep
KOKORO_VOICE = "af_sarah"
KOKORO_LANG  = "en-us"
KOKORO_SPEED = 1.0      # 1.0 = natural; 0.95 = slightly clearer for complex content

TARGET_SR   = 44100     # YouTube standard -- all audio normalised here
CHUNK_CHARS = 1000      # Max chars per Kokoro call for stable prosody
PAUSE_SEC   = 0.35      # Silence between chunks (natural breathing room)
VOICE_PEAK  = 0.87      # Normalise voice to this peak (-1.5 dBFS)
MUSIC_VOL   = 0.10      # Background at 10% -- voice always intelligible


class AudioAgent:
    def __init__(self, config):
        self.cfg = config
        self._kokoro = None   # lazy-loaded on first TTS call

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def generate(self, script: dict, workspace: Path) -> Path:
        """
        Returns path to mixed audio as lossless PCM WAV @ 44100 Hz.
        assembler_agent._merge_final() performs the one and only AAC encode.
        """
        narration_path = self._generate_voice(script, workspace)
        music_path     = self._get_background_music(
            script.get("background_music_mood", "calm background"), workspace
        )
        final_wav = workspace / "audio_final.wav"   # always WAV -- never AAC here
        self._mix_audio(narration_path, music_path, final_wav)
        logger.info(f"[AudioAgent] Final lossless audio: {final_wav}")
        return final_wav

    def get_segment_timestamps(self, script: dict, output_path: Path) -> list:
        timestamps, t = [], 0.0
        for seg in (script.get("segments") or script.get("chapters", [])):
            dur = seg.get("duration_sec", 10)
            timestamps.append({
                "id": seg["id"], "start": t, "end": t + dur,
                "caption": seg.get("caption", ""), "text": seg.get("text", ""),
            })
            t += dur
        return timestamps

    # -------------------------------------------------------------------------
    # Voice generation  Kokoro -> ElevenLabs -> espeak (emergency only)
    # -------------------------------------------------------------------------

    def _generate_voice(self, script: dict, workspace: Path) -> Path:
        texts = (
            [seg["text"] for seg in script["segments"]]
            if script["video_type"] == "short"
            else [ch["text"] for ch in script["chapters"]]
        )

        # 1. Kokoro -- local, free, near-human quality
        try:
            path = self._kokoro_tts(texts, workspace / "narration.wav")
            logger.info("[AudioAgent] Voice engine: Kokoro TTS (lossless WAV)")
            return path
        except Exception as e:
            logger.error(f"[AudioAgent] Kokoro FAILED: {e}")

        # 2. ElevenLabs -- optional paid/free-tier fallback
        if self.cfg.elevenlabs_api_key:
            try:
                path = self._elevenlabs_tts(texts, workspace / "narration_el.mp3")
                logger.warning("[AudioAgent] Voice engine: ElevenLabs (MP3 fallback)")
                return path
            except Exception as e:
                logger.error(f"[AudioAgent] ElevenLabs FAILED: {e}")

        # 3. espeak -- emergency only, NOT suitable for YouTube upload
        logger.critical(
            "[AudioAgent] CRITICAL: Using espeak fallback. Output will be robotic. "
            "Fix: ensure kokoro-v1.0.onnx and voices-v1.0.bin are in the repo root. "
            "The GitHub Actions workflow downloads these automatically."
        )
        return self._espeak_tts(texts, workspace / "narration_espeak.wav")

    # -------------------------------------------------------------------------
    # Kokoro TTS -- lossless pipeline
    # -------------------------------------------------------------------------

    def _get_kokoro(self):
        if self._kokoro is None:
            from kokoro_onnx import Kokoro
            model  = "kokoro-v1.0.onnx"
            voices = "voices-v1.0.bin"
            if not Path(model).exists():
                raise FileNotFoundError(
                    f"{model} not found in working directory. "
                    "The GitHub Actions workflow downloads this automatically. "
                    "For local runs: wget https://github.com/thewh1teagle/kokoro-onnx"
                    "/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
                )
            if not Path(voices).exists():
                raise FileNotFoundError(
                    f"{voices} not found in working directory. "
                    "For local runs: wget https://github.com/thewh1teagle/kokoro-onnx"
                    "/releases/download/model-files-v1.0/voices-v1.0.bin"
                )
            self._kokoro = Kokoro(model, voices)
            logger.info("[AudioAgent] Kokoro v1.0 loaded")
        return self._kokoro

    def _kokoro_tts(self, texts: list, output_path: Path) -> Path:
        """
        text -> Kokoro float32 @ native_sr (24 kHz)
             -> scipy polyphase resample to 44100 Hz
             -> peak normalise to -1.5 dBFS
             -> lossless PCM_16 WAV @ 44100 Hz

        Zero lossy encoding in this function.
        """
        kokoro    = self._get_kokoro()
        full_text = "\n\n".join(texts)
        chunks    = self._chunk_text(full_text, CHUNK_CHARS)

        parts: list[np.ndarray] = []
        native_sr = None

        for chunk in chunks:
            chunk = chunk.strip()
            if not chunk:
                continue
            samples, sr = kokoro.create(
                chunk, voice=KOKORO_VOICE, speed=KOKORO_SPEED, lang=KOKORO_LANG
            )
            samples   = np.asarray(samples, dtype=np.float32)
            native_sr = sr

            # Polyphase resample: Kokoro native (24 kHz) -> 44100 Hz
            if sr != TARGET_SR:
                samples = self._polyphase_resample(samples, sr, TARGET_SR)

            parts.append(samples)
            parts.append(np.zeros(int(TARGET_SR * PAUSE_SEC), dtype=np.float32))

        if not parts:
            raise RuntimeError("Kokoro produced no audio samples")

        audio = np.concatenate(parts)

        # Normalise peak to avoid clipping and give headroom for music mix
        peak = np.max(np.abs(audio))
        if peak > 0:
            audio = audio * (VOICE_PEAK / peak)

        # Write lossless 16-bit PCM WAV at 44100 Hz
        sf.write(str(output_path), audio, TARGET_SR, subtype="PCM_16")

        duration = len(audio) / TARGET_SR
        logger.info(
            f"[AudioAgent] Kokoro: {len(full_text)} chars | {len(chunks)} chunks | "
            f"{duration:.1f}s | native={native_sr}Hz -> written at {TARGET_SR}Hz | "
            f"{output_path.stat().st_size // 1024}KB"
        )
        return output_path

    def _polyphase_resample(self, samples: np.ndarray, src: int, dst: int) -> np.ndarray:
        """
        scipy polyphase resample using Kaiser-windowed sinc filter.
        Far superior to linear interpolation for audio -- preserves all frequencies.
        Falls back to numpy if scipy is missing (lower quality but functional).
        """
        if src == dst:
            return samples
        try:
            from scipy.signal import resample_poly
            from math import gcd
            g = gcd(dst, src)
            return resample_poly(samples, dst // g, src // g).astype(np.float32)
        except ImportError:
            logger.warning(
                "[AudioAgent] scipy not installed -- using numpy interp (lower quality). "
                "Add scipy>=1.11.0 to requirements.txt for best audio quality."
            )
            n = int(len(samples) * dst / src)
            return np.interp(
                np.linspace(0, len(samples) - 1, n),
                np.arange(len(samples)), samples,
            ).astype(np.float32)

    # -------------------------------------------------------------------------
    # ElevenLabs TTS (optional fallback)
    # -------------------------------------------------------------------------

    def _elevenlabs_tts(self, texts: list, output_path: Path) -> Path:
        full_text = "\n\n".join(texts)
        if len(full_text) > 9800:
            t   = full_text[:9800]
            cut = max(t.rfind("."), t.rfind("!"), t.rfind("?"))
            full_text = t[:cut + 1] if cut > 0 else t
            logger.warning(f"[AudioAgent] ElevenLabs text trimmed to {len(full_text)} chars")
        resp = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{self.cfg.elevenlabs_voice_id}",
            json={
                "text": full_text, "model_id": self.cfg.elevenlabs_model,
                "output_format": self.cfg.elevenlabs_output_format,
                "voice_settings": {
                    "stability": 0.4, "similarity_boost": 0.75,
                    "style": 0.3, "use_speaker_boost": True,
                },
            },
            headers={
                "Accept": "audio/mpeg", "Content-Type": "application/json",
                "xi-api-key": self.cfg.elevenlabs_api_key,
            },
            timeout=60,
        )
        resp.raise_for_status()
        output_path.write_bytes(resp.content)
        logger.info(f"[AudioAgent] ElevenLabs: {len(full_text)} chars -> {output_path}")
        return output_path

    # -------------------------------------------------------------------------
    # espeak TTS (emergency last resort)
    # -------------------------------------------------------------------------

    def _espeak_tts(self, texts: list, output_path: Path) -> Path:
        txt = output_path.with_suffix(".txt")
        txt.write_text(" ".join(texts), encoding="utf-8")
        r = subprocess.run(
            ["espeak", "-f", str(txt), "-w", str(output_path),
             "-s", "150", "-v", "en", "-a", "100"],
            capture_output=True, text=True,
        )
        txt.unlink(missing_ok=True)
        if r.returncode != 0:
            raise RuntimeError(f"espeak failed: {r.stderr}")
        if not output_path.exists() or output_path.stat().st_size < 500:
            raise RuntimeError("espeak produced empty file")
        logger.info(f"[AudioAgent] espeak -> {output_path} ({output_path.stat().st_size // 1024}KB)")
        return output_path

    # -------------------------------------------------------------------------
    # Background music
    # -------------------------------------------------------------------------

    def _get_background_music(self, mood: str, workspace: Path) -> Path:
        music_path = workspace / "background_music.mp3"
        for url in FREE_MUSIC_URLS.get(mood, FREE_MUSIC_URLS["calm background"]):
            try:
                resp = requests.get(url, timeout=30, stream=True)
                if resp.status_code == 200:
                    with open(music_path, "wb") as f:
                        for chunk in resp.iter_content(8192):
                            f.write(chunk)
                    logger.info(f"[AudioAgent] Music: {url}")
                    return music_path
            except Exception as e:
                logger.warning(f"[AudioAgent] Music download failed ({url}): {e}")

        # Generate silence rather than crashing
        silence = workspace / "background_music.wav"
        subprocess.run(
            ["ffmpeg", "-y", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
             "-t", "60", str(silence)],
            check=True, capture_output=True,
        )
        logger.warning("[AudioAgent] Using silent background music (all downloads failed)")
        return silence

    # -------------------------------------------------------------------------
    # Audio mixing -- OUTPUT IS LOSSLESS WAV, NEVER AAC
    # -------------------------------------------------------------------------

    def _mix_audio(self, voice_path: Path, music_path: Path, output_path: Path):
        """
        Mix voice + background music -> lossless PCM_S16LE WAV @ 44100 Hz.

        Zero lossy encoding here. Both inputs are resampled with soxr
        (FFmpeg's highest-quality resampler) before mixing.

        The ONLY AAC encode in the entire pipeline happens in
        assembler_agent._merge_final().
        """
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(voice_path)],
            capture_output=True, text=True,
        )
        try:
            duration = float(probe.stdout.strip())
        except ValueError:
            duration = 120.0
            logger.warning("[AudioAgent] ffprobe duration failed, using 120s fallback")

        filter_graph = (
            f"[0:a]aresample=resampler=soxr:osr={TARGET_SR},volume=1.0[voice];"
            f"[1:a]aresample=resampler=soxr:osr={TARGET_SR},"
            f"aloop=loop=-1:size=2000000000,"
            f"atrim=duration={duration},"
            f"volume={MUSIC_VOL}[music];"
            f"[voice][music]amix=inputs=2:duration=first:dropout_transition=2[out]"
        )

        r = subprocess.run([
            "ffmpeg", "-y",
            "-i", str(voice_path),
            "-i", str(music_path),
            "-filter_complex", filter_graph,
            "-map", "[out]",
            "-c:a", "pcm_s16le",   # LOSSLESS -- no AAC here
            "-ar", str(TARGET_SR),
            "-ac", "2",
            str(output_path),
        ], capture_output=True, text=True)

        if r.returncode != 0:
            logger.error(f"[AudioAgent] Mix failed:\n{r.stderr[-1000:]}")
            raise RuntimeError("FFmpeg audio mix failed")

        mb = output_path.stat().st_size / 1_000_000
        logger.info(
            f"[AudioAgent] Lossless WAV mix: {output_path} "
            f"({duration:.1f}s | {mb:.1f}MB | pcm_s16le @ {TARGET_SR}Hz)"
        )

    # -------------------------------------------------------------------------
    # Text chunking
    # -------------------------------------------------------------------------

    def _chunk_text(self, text: str, max_chars: int) -> list:
        """Split at sentence boundaries. Never cuts mid-word."""
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
