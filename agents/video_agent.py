"""
agents/video_agent.py

Generates cinematic video clips for each Mahabharat scene using:
  1. fal.ai Seedance 1.5 Pro (via API) — configured for Seedance 2.0 when it goes GA
  2. Pollinations.ai — free AI image gen fallback
  3. PIL procedural — hand-painted ancient India scenes (always-works offline fallback)

Each clip is animated with a cinematic Ken Burns effect (pan/zoom).
"""

import logging
import math
import random
import subprocess
import time
import requests
import json
import os
from pathlib import Path
from urllib.parse import quote

logger = logging.getLogger("VideoAgent")

# Cinematic ancient India colour palettes
PALETTES = {
    "palace":      {"sky": "#1a0a05", "ground": "#5c2d0e", "accent": "#ffd54f", "mid": "#8d4e0a"},
    "forest":      {"sky": "#0d1a0a", "ground": "#1b4332", "accent": "#ffe082", "mid": "#2d6a4f"},
    "battlefield": {"sky": "#2d0a0a", "ground": "#4a1010", "accent": "#ff6b35", "mid": "#8b2020"},
    "dawn":        {"sky": "#ff6b35", "ground": "#5c3317", "accent": "#ffe082", "mid": "#cc4400"},
    "night":       {"sky": "#05051a", "ground": "#0a1628", "accent": "#b39ddb", "mid": "#1a237e"},
    "river":       {"sky": "#0a1628", "ground": "#1565c0", "accent": "#ffe082", "mid": "#1976d2"},
}

MOTIONS = [
    {"zoom_start": 1.0,  "zoom_end": 1.08, "x_drift": 25,  "y_drift": 0},
    {"zoom_start": 1.08, "zoom_end": 1.0,  "x_drift": -25, "y_drift": 0},
    {"zoom_start": 1.0,  "zoom_end": 1.12, "x_drift": 0,   "y_drift": -20},
    {"zoom_start": 1.05, "zoom_end": 1.0,  "x_drift": 20,  "y_drift": 15},
    {"zoom_start": 1.0,  "zoom_end": 1.06, "x_drift": -15, "y_drift": -10},
]

# Seedance model IDs — swap SEEDANCE_MODEL to "fal-ai/seedance-2" when 2.0 GA
SEEDANCE_MODEL   = "fal-ai/seedance-1-5-pro/text-to-video"
SEEDANCE_MODEL_V2 = "fal-ai/seedance-2/text-to-video"  # ready for when GA

MAHABHARAT_STYLE = (
    "ancient India, Mahabharat epic, cinematic, painterly illustration style, "
    "Amar Chitra Katha meets Game of Thrones, rich ochre and crimson, "
    "dramatic lighting, gold accents, detailed costumes, majestic"
)


class VideoAgent:
    def __init__(self, config):
        self.cfg = config

    def fetch_clips(self, script: dict, workspace: Path, video_type: str) -> Path:
        clips_dir = workspace / "clips"
        clips_dir.mkdir(exist_ok=True)
        segments  = script.get("segments") or script.get("chapters", [])
        w, h      = (1080, 1920) if video_type == "short" else (1920, 1080)

        for i, seg in enumerate(segments):
            seg_id   = seg.get("id", i + 1)
            duration = seg.get("duration_sec", 10)
            clip_path = clips_dir / f"clip_{seg_id:03d}.mp4"
            prompt    = self._build_scene_prompt(seg, script)

            logger.info(f"[VideoAgent] Seg {seg_id}: generating scene...")

            img_path = workspace / f"scene_{seg_id:03d}.png"

            # Try fal.ai Seedance first (best quality)
            success = self._generate_with_seedance(prompt, img_path, w, h, duration)
            if success and img_path.exists() and img_path.suffix == ".mp4":
                # Seedance returned a video directly — just copy it
                img_path.rename(clip_path)
                logger.info(f"[VideoAgent] Seedance video clip {seg_id} ready")
                continue

            # Seedance returned an image or failed — try Pollinations
            if not success:
                success = self._generate_with_pollinations(prompt, img_path, w, h)

            # PIL fallback
            if not success:
                self._generate_with_pil(prompt, seg, img_path, w, h)

            # Animate the image with Ken Burns effect
            motion = MOTIONS[i % len(MOTIONS)]
            self._animate_ken_burns(img_path, clip_path, duration, w, h, motion)
            logger.info(f"[VideoAgent] Clip {seg_id} ready: {clip_path.name}")

        return clips_dir

    def _build_scene_prompt(self, seg: dict, script: dict) -> str:
        base    = seg.get("broll_query", "") or ", ".join(seg.get("broll_queries", []))
        emotion = seg.get("emotion", "dramatic")
        style   = MAHABHARAT_STYLE

        framing_map = {
            "hook":        "extreme wide establishing shot, dramatic silhouette",
            "scene":       "mid shot, characters in action, emotionally expressive",
            "cliffhanger": "extreme close-up face, shock or determination",
            "climax":      "wide battle shot, chaos and heroism",
            "recap":       "collage of scenes, painterly",
            "resolution":  "golden light, emotional aftermath",
            "revelation":  "dramatic close-up, intense expression",
            "outro":       "epic sunset over ancient landscape",
            "cta":         "title card, ornate ancient Indian design",
        }
        seg_type = seg.get("type", "scene")
        framing  = framing_map.get(seg_type, "mid shot")

        return f"{base}, {framing}, {style}, {emotion} mood, no text overlays"

    def _generate_with_seedance(self, prompt: str, output_path: Path,
                                  w: int, h: int, duration: int) -> bool:
        """
        Generate video via fal.ai Seedance API.
        Async submit-poll-download pattern.
        Seedance 1.5 Pro currently available; switch SEEDANCE_MODEL to V2 when GA.
        """
        fal_key = self.cfg.fal_api_key
        if not fal_key:
            return False

        try:
            aspect = "9:16" if w < h else "16:9"
            clip_dur = min(max(duration, 4), 8)  # Seedance supports 4-8s

            headers = {
                "Authorization": f"Key {fal_key}",
                "Content-Type":  "application/json",
            }

            # Submit generation job
            payload = {
                "prompt":        prompt,
                "duration":      clip_dur,
                "aspect_ratio":  aspect,
                "resolution":    "720p",
                "model":         "seedance-1-5-pro",
            }
            submit_url = f"https://queue.fal.run/{SEEDANCE_MODEL}"
            resp = requests.post(submit_url, headers=headers,
                                  json=payload, timeout=30)
            if resp.status_code != 200:
                logger.warning(f"[VideoAgent] Seedance submit failed: {resp.status_code} {resp.text[:200]}")
                return False

            job = resp.json()
            request_id = job.get("request_id")
            status_url  = f"https://queue.fal.run/{SEEDANCE_MODEL}/requests/{request_id}/status"
            result_url  = f"https://queue.fal.run/{SEEDANCE_MODEL}/requests/{request_id}"

            # Poll for completion (up to 3 minutes)
            for attempt in range(36):
                time.sleep(5)
                status_resp = requests.get(status_url, headers=headers, timeout=15)
                status_data = status_resp.json()
                status = status_data.get("status", "")
                logger.info(f"[VideoAgent] Seedance poll {attempt+1}: {status}")

                if status == "COMPLETED":
                    result_resp = requests.get(result_url, headers=headers, timeout=15)
                    result_data = result_resp.json()
                    video_url   = result_data.get("video", {}).get("url") or                                   result_data.get("outputs", [{}])[0].get("url", "")
                    if video_url:
                        # Download the video
                        vid_path = output_path.with_suffix(".mp4")
                        vid_resp = requests.get(video_url, timeout=60, stream=True)
                        with open(vid_path, "wb") as f:
                            for chunk in vid_resp.iter_content(65536):
                                f.write(chunk)
                        # Rename with .mp4 marker so caller knows it's a video
                        vid_path.rename(output_path.with_suffix(".mp4"))
                        output_path = output_path.with_suffix(".mp4")
                        logger.info(f"[VideoAgent] Seedance video: {output_path.name}")
                        return True

                elif status in ("FAILED", "ERROR"):
                    logger.warning(f"[VideoAgent] Seedance job failed: {status_data}")
                    return False

            logger.warning("[VideoAgent] Seedance timed out after 3 min")
            return False

        except Exception as e:
            logger.warning(f"[VideoAgent] Seedance error: {e}")
            return False

    def _generate_with_pollinations(self, prompt: str, output_path: Path,
                                     w: int, h: int) -> bool:
        try:
            encoded = quote(prompt[:500])
            url     = (
                f"https://image.pollinations.ai/prompt/{encoded}"
                f"?width={min(w, 1024)}&height={min(h, 1024)}"
                f"&model=flux&nologo=true&enhance=true"
            )
            resp = requests.get(url, timeout=60, stream=True)
            if resp.status_code != 200 or "image" not in resp.headers.get("content-type",""):
                return False
            raw = b""
            for chunk in resp.iter_content(65536):
                raw += chunk
            if len(raw) < 5000:
                return False
            from PIL import Image
            from io import BytesIO
            img = Image.open(BytesIO(raw)).convert("RGB")
            img = self._fit_and_crop(img, w, h)
            img.save(str(output_path), "PNG", quality=95)
            logger.info(f"[VideoAgent] Pollinations OK: {output_path.name}")
            return True
        except Exception as e:
            logger.warning(f"[VideoAgent] Pollinations error: {e}")
            return False

    def _generate_with_pil(self, prompt: str, seg: dict,
                             output_path: Path, w: int, h: int):
        """Procedural ancient India scene using Pillow."""
        from PIL import Image, ImageDraw, ImageFont
        import hashlib

        desc  = prompt.lower()
        if any(x in desc for x in ["battle", "war", "kurukshetra", "fight", "battlefield"]):
            pal_key = "battlefield"
        elif any(x in desc for x in ["palace", "king", "throne", "hastinapura"]):
            pal_key = "palace"
        elif any(x in desc for x in ["dawn", "sunrise", "morning"]):
            pal_key = "dawn"
        elif any(x in desc for x in ["night", "dark", "moon"]):
            pal_key = "night"
        elif any(x in desc for x in ["river", "ganga", "water"]):
            pal_key = "river"
        else:
            pal_key = "forest"

        pal  = PALETTES[pal_key]
        seed = int(hashlib.md5(prompt.encode()).hexdigest()[:8], 16)
        rng  = random.Random(seed)

        img  = Image.new("RGB", (w, h), self._hex(pal["sky"]))
        draw = ImageDraw.Draw(img)

        # Sky gradient
        sky   = self._hex(pal["sky"])
        dark  = self._darken(sky, 0.5)
        for i in range(8):
            col = self._lerp_color(dark, sky, i / 8)
            draw.rectangle([0, i * h // 8, w, (i + 1) * h // 8], fill=col)

        # Stars
        for _ in range(60):
            sx = rng.randint(0, w)
            sy = rng.randint(0, h // 3)
            draw.ellipse([sx-1, sy-1, sx+1, sy+1], fill="#fffde7")

        # Sun/moon
        if pal_key == "dawn":
            draw.ellipse([w//2 - 60, h//6 - 60, w//2 + 60, h//6 + 60], fill="#ff6b35")
        elif pal_key in ("night", "forest"):
            draw.ellipse([w - 160, 50, w - 60, 150], fill="#fff9c4")

        # Horizon hills
        self._draw_hills(draw, w, h, self._hex(pal["mid"]),
                          y_base=int(h * 0.5), count=4, rng=rng, amplitude=int(h * 0.15))

        # Ground
        draw.rectangle([0, int(h * 0.55), w, h], fill=self._hex(pal["ground"]))

        # Temple/palace silhouette (if palace/dawn)
        if pal_key in ("palace", "dawn"):
            self._draw_temple(draw, w // 2, int(h * 0.55), w, h)

        # Battle scene elements
        if pal_key == "battlefield":
            for tx in range(int(w * 0.1), int(w * 0.9), int(w * 0.08)):
                self._draw_warrior(draw, tx, int(h * 0.55), w, h, rng)

        # Dramatic character silhouette
        self._draw_hero_silhouette(draw, int(w * 0.5), int(h * 0.55), w, h, pal_key)

        # Gold accent particles (embers / stars)
        for _ in range(40):
            px = rng.randint(int(w * 0.1), int(w * 0.9))
            py = rng.randint(int(h * 0.1), int(h * 0.7))
            pr = rng.choice([1, 2, 3])
            draw.ellipse([px-pr, py-pr, px+pr, py+pr],
                          fill=self._hex(pal["accent"]))

        # Caption overlay
        caption = seg.get("caption", "")[:60]
        if caption:
            bar_h = max(70, h // 12)
            draw.rectangle([0, h - bar_h, w, h], fill=(0, 0, 0, 200))
            try:
                font = ImageFont.truetype(
                    "/usr/share/fonts/truetype/open-sans/OpenSans-Bold.ttf",
                    max(28, w // 35)
                )
            except Exception:
                font = ImageFont.load_default()
            draw.text((w // 2, h - bar_h // 2), caption,
                       font=font, fill="#ffd54f", anchor="mm")

        img.save(str(output_path), "PNG")
        logger.info(f"[VideoAgent] PIL Mahabharat scene: {output_path.name}")

    def _draw_temple(self, draw, cx, base_y, W, H):
        s = W / 1080
        h = lambda v: int(v * s)
        # Shikhara
        draw.polygon([
            (cx - h(60), base_y),
            (cx, base_y - h(200)),
            (cx + h(60), base_y)
        ], fill="#8d4e0a")
        draw.polygon([
            (cx - h(40), base_y),
            (cx, base_y - h(160)),
            (cx + h(40), base_y)
        ], fill="#a0522d")
        # Platform
        draw.rectangle([cx - h(80), base_y, cx + h(80), base_y + h(20)], fill="#6d3b0e")

    def _draw_warrior(self, draw, cx, base_y, W, H, rng):
        s  = W / 1920
        sh = int(60 * s)
        draw.polygon([
            (cx, base_y - sh),
            (cx - int(10 * s), base_y),
            (cx + int(10 * s), base_y)
        ], fill="#2c1810")
        draw.ellipse([
            cx - int(8 * s), base_y - sh - int(12 * s),
            cx + int(8 * s), base_y - sh + int(12 * s)
        ], fill="#2c1810")

    def _draw_hero_silhouette(self, draw, cx, base_y, W, H, pal_key):
        s = W / 1080
        h = lambda v: int(v * s)
        col = "#1a0a00" if pal_key != "night" else "#0a0a1e"
        # Body
        draw.polygon([
            (cx, base_y - h(180)),
            (cx - h(35), base_y),
            (cx + h(35), base_y)
        ], fill=col)
        # Head
        draw.ellipse([cx - h(25), base_y - h(225),
                       cx + h(25), base_y - h(175)], fill=col)
        # Crown/helmet
        draw.polygon([
            (cx - h(20), base_y - h(225)),
            (cx, base_y - h(270)),
            (cx + h(20), base_y - h(225))
        ], fill="#ffd54f")
        # Bow arm
        draw.line([
            (cx + h(35), base_y - h(120)),
            (cx + h(90), base_y - h(160)),
            (cx + h(80), base_y - h(60))
        ], fill=col, width=h(5))

    def _draw_hills(self, draw, W, H, color, y_base, count, rng, amplitude):
        pts = [(0, y_base)]
        step = W // (count * 2)
        for i in range(count * 2 + 1):
            x = i * step
            y = y_base - rng.randint(0, amplitude) if i % 2 == 1 else y_base
            pts.append((x, y))
        pts += [(W, y_base), (W, H), (0, H)]
        draw.polygon(pts, fill=color)

    def _animate_ken_burns(self, img_path: Path, output_path: Path,
                             duration: int, w: int, h: int, motion: dict):
        fps      = self.cfg.video_fps
        n_frames = duration * fps
        z_start  = motion["zoom_start"] * 1.15
        z_end    = motion["zoom_end"]   * 1.15
        x_drift  = motion["x_drift"]
        y_drift  = motion["y_drift"]

        z_expr = f"min({z_start}+({z_end}-{z_start})*on/{n_frames},{z_end})"
        x_expr = f"iw/2-(iw/zoom/2)+{x_drift}*on/{n_frames}"
        y_expr = f"ih/2-(ih/zoom/2)+{y_drift}*on/{n_frames}"
        vf     = (
            f"scale={w*2}:{h*2},"
            f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}'"
            f":d={n_frames}:s={w}x{h}:fps={fps},"
            f"scale={w}:{h}"
        )

        r = subprocess.run([
            "ffmpeg", "-y", "-loop", "1", "-i", str(img_path),
            "-vf", vf, "-t", str(duration),
            "-c:v", "libx264", "-preset", self.cfg.video_preset,
            "-crf", str(self.cfg.video_crf),
            "-pix_fmt", "yuv420p", "-an", str(output_path),
        ], capture_output=True, text=True, timeout=300)

        if r.returncode != 0:
            logger.error(f"[VideoAgent] Ken Burns failed: {r.stderr[-300:]}")
            subprocess.run([
                "ffmpeg", "-y", "-loop", "1", "-i", str(img_path),
                "-vf", f"scale={w}:{h}", "-t", str(duration),
                "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                "-pix_fmt", "yuv420p", "-an", str(output_path),
            ], check=True, capture_output=True)

    def _fit_and_crop(self, img, w, h):
        from PIL import Image
        iw, ih = img.size
        scale  = max(w / iw, h / ih)
        nw, nh = int(iw * scale), int(ih * scale)
        img    = img.resize((nw, nh), Image.LANCZOS)
        x0     = (nw - w) // 2
        y0     = (nh - h) // 2
        return img.crop((x0, y0, x0 + w, y0 + h))

    @staticmethod
    def _hex(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    @staticmethod
    def _darken(rgb, f):
        return tuple(int(c * f) for c in rgb)

    @staticmethod
    def _lighten(rgb, f):
        return tuple(min(255, int(c * f)) for c in rgb)

    @staticmethod
    def _lerp_color(c1, c2, t):
        return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
