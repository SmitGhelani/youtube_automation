"""
agents/video_agent.py

Generates cartoon-style scene images for each script segment,
then animates them with FFmpeg Ken Burns effect (pan + zoom).

NO real-world footage. Every frame looks like a cartoon illustration.

Image sources (tried in order):
  1. Pollinations.ai  — free AI image gen, no API key, cartoon/illustration style
  2. PIL procedural   — hand-drawn cartoon scenes using Pillow (always works offline)

Each image is then animated with a slow Ken Burns pan/zoom to create
the illusion of motion, making the video feel alive even from stills.
"""

import logging
import math
import random
import subprocess
import time
import requests
from pathlib import Path
from urllib.parse import quote

logger = logging.getLogger("VideoAgent")

# Cartoon scene colour palettes — warm, Pixar-like
PALETTES = {
    "forest":  {"sky": "#1a0a3d", "ground": "#2d6a4f", "accent": "#ffe082", "mid": "#40916c"},
    "cave":    {"sky": "#0d0221", "ground": "#1b1b3a", "accent": "#ce93d8", "mid": "#3d2b69"},
    "meadow":  {"sky": "#87ceeb", "ground": "#4caf50", "accent": "#ffeb3b", "mid": "#81c784"},
    "village": {"sky": "#ffd54f", "ground": "#8d6e63", "accent": "#ff7043", "mid": "#a1887f"},
    "night":   {"sky": "#0a0520", "ground": "#1b4332", "accent": "#b39ddb", "mid": "#2d6a4f"},
    "beach":   {"sky": "#81d4fa", "ground": "#f9a825", "accent": "#ff7043", "mid": "#4dd0e1"},
}

# Ken Burns motion presets — slow, gentle, cinematic
MOTIONS = [
    {"zoom_start": 1.0,  "zoom_end": 1.08, "x_drift": 20,  "y_drift": 0},
    {"zoom_start": 1.08, "zoom_end": 1.0,  "x_drift": -20, "y_drift": 0},
    {"zoom_start": 1.0,  "zoom_end": 1.1,  "x_drift": 0,   "y_drift": -15},
    {"zoom_start": 1.05, "zoom_end": 1.0,  "x_drift": 15,  "y_drift": 10},
    {"zoom_start": 1.0,  "zoom_end": 1.06, "x_drift": -10, "y_drift": -10},
]


class VideoAgent:
    def __init__(self, config):
        self.cfg = config

    def fetch_clips(self, script: dict, workspace: Path, video_type: str) -> Path:
        """
        Generates one animated cartoon clip per segment.
        Returns path to folder containing all clips.
        """
        clips_dir = workspace / "clips"
        clips_dir.mkdir(exist_ok=True)

        segments = script.get("segments") or script.get("chapters", [])

        if video_type == "short":
            w, h = 1080, 1920
        else:
            w, h = 1920, 1080

        for i, seg in enumerate(segments):
            seg_id = seg.get("id", i + 1)
            duration = seg.get("duration_sec", 10)
            clip_path = clips_dir / f"clip_{seg_id:03d}.mp4"

            # Build a rich scene description from the segment
            scene_desc = self._build_scene_description(seg, script)

            logger.info(f"[VideoAgent] Segment {seg_id}: generating cartoon scene — {scene_desc[:60]}...")

            # Try Pollinations first, fall back to PIL procedural art
            img_path = workspace / f"scene_{seg_id:03d}.png"
            success = self._generate_with_pollinations(scene_desc, img_path, w, h)
            if not success:
                logger.warning(f"[VideoAgent] Pollinations failed for seg {seg_id} — using PIL art")
                self._generate_with_pil(scene_desc, seg, img_path, w, h)

            # Animate the image with Ken Burns effect
            motion = MOTIONS[i % len(MOTIONS)]
            self._animate_ken_burns(img_path, clip_path, duration, w, h, motion)
            logger.info(f"[VideoAgent] Clip {seg_id} ready: {clip_path.name}")

        return clips_dir

    # ── Scene description builder ─────────────────────────────────────────────

    def _build_scene_description(self, seg: dict, script: dict) -> str:
        """
        Build a cartoon illustration prompt from segment data.
        Always includes character names and Whimble world style cues.
        """
        base = seg.get("broll_query", "") or ", ".join(seg.get("broll_queries", []))

        # Extract emotion and type hints
        emotion = seg.get("emotion", "wonder")
        seg_type = seg.get("type", "story")

        # Always anchor to Whimble art style
        style = (
            "children's book illustration, Pixar cartoon style, "
            "warm magical lighting, soft colours, whimsical, family friendly, "
            "Milo and Luna cartoon characters, cute fox Pip, "
            "Whimble magical forest world"
        )

        # Map segment type to visual framing
        framing_map = {
            "hook":        "wide establishing shot, dramatic lighting",
            "story":       "mid shot, characters in action",
            "cliffhanger": "close-up, suspenseful framing, glowing mystery",
            "cta":         "warm wide shot, characters waving, sunny",
            "recap_or_hook": "storybook collage, multiple scenes",
            "resolution":  "warm close-up, happy expressions",
            "outro":       "golden sunset, characters together, heartwarming",
        }
        framing = framing_map.get(seg_type, "mid shot")

        prompt = f"{base}, {framing}, {style}, {emotion} mood"
        return prompt

    # ── Pollinations.ai image generation ──────────────────────────────────────

    def _generate_with_pollinations(self, prompt: str, output_path: Path,
                                     w: int, h: int) -> bool:
        """
        Pollinations.ai — completely free, no API key required.
        Returns True on success, False on any failure.

        Model options: flux (best quality), flux-realism, turbo
        """
        try:
            encoded = quote(prompt)
            url = (
                f"https://image.pollinations.ai/prompt/{encoded}"
                f"?width={min(w, 1024)}&height={min(h, 1024)}"
                f"&model=flux&nologo=true&enhance=true"
            )

            # Pollinations can be slow (10-30s) — give it 60s
            resp = requests.get(url, timeout=60, stream=True)
            if resp.status_code != 200:
                logger.warning(f"[VideoAgent] Pollinations HTTP {resp.status_code}")
                return False

            content_type = resp.headers.get("content-type", "")
            if "image" not in content_type:
                logger.warning(f"[VideoAgent] Pollinations returned non-image: {content_type}")
                return False

            raw = b""
            for chunk in resp.iter_content(chunk_size=65536):
                raw += chunk

            if len(raw) < 5000:
                logger.warning(f"[VideoAgent] Pollinations image too small ({len(raw)} bytes)")
                return False

            # Resize to exact target dimensions with Pillow
            from PIL import Image
            from io import BytesIO
            img = Image.open(BytesIO(raw)).convert("RGB")
            img = self._fit_and_crop(img, w, h)
            img.save(str(output_path), "PNG", quality=95)

            logger.info(f"[VideoAgent] Pollinations OK: {output_path.name} ({len(raw)//1024}KB)")
            return True

        except Exception as e:
            logger.warning(f"[VideoAgent] Pollinations error: {e}")
            return False

    # ── PIL procedural cartoon art (always-available fallback) ────────────────

    def _generate_with_pil(self, scene_desc: str, seg: dict,
                            output_path: Path, w: int, h: int):
        """
        Draw a cartoon scene procedurally using Pillow.
        Produces stylised, recognisable scenes that look like children's book art.
        Always works offline with zero external dependencies.
        """
        from PIL import Image, ImageDraw, ImageFont
        import hashlib

        # Pick colour palette based on scene content
        desc_lower = scene_desc.lower()
        if any(x in desc_lower for x in ["cave", "crystal", "underground", "dark"]):
            pal_key = "cave"
        elif any(x in desc_lower for x in ["night", "moon", "star"]):
            pal_key = "night"
        elif any(x in desc_lower for x in ["village", "house", "town"]):
            pal_key = "village"
        elif any(x in desc_lower for x in ["beach", "sea", "ocean", "water"]):
            pal_key = "beach"
        elif any(x in desc_lower for x in ["meadow", "field", "flower"]):
            pal_key = "meadow"
        else:
            pal_key = "forest"

        pal = PALETTES[pal_key]

        # Deterministic random from scene hash so same scene = same art
        seed = int(hashlib.md5(scene_desc.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)

        img  = Image.new("RGB", (w, h), self._hex(pal["sky"]))
        draw = ImageDraw.Draw(img)

        # Sky gradient (hand-drawn bands)
        sky_col  = self._hex(pal["sky"])
        sky_dark = self._darken(sky_col, 0.7)
        band_h   = h // 12
        for i in range(6):
            alpha = i / 6
            col   = self._lerp_color(sky_dark, sky_col, alpha)
            draw.rectangle([0, i * band_h, w, (i + 1) * band_h], fill=col)

        # Stars (for night/cave/forest)
        if pal_key in ("night", "cave", "forest"):
            for _ in range(80):
                sx = rng.randint(0, w)
                sy = rng.randint(0, h // 2)
                sr = rng.choice([1, 1, 1, 2])
                draw.ellipse([sx-sr, sy-sr, sx+sr, sy+sr], fill="#ffffff")

        # Moon or sun
        if pal_key in ("night", "cave"):
            draw.ellipse([w-200, 60, w-100, 160], fill="#ffe082")
            draw.ellipse([w-175, 50, w-80, 145], fill=self._hex(pal["sky"]))
        elif pal_key in ("meadow", "village", "beach"):
            draw.ellipse([w-180, 40, w-60, 160], fill="#fff9c4")
            for _ in range(12):
                a = rng.uniform(0, 2 * math.pi)
                r = rng.randint(70, 100)
                draw.ellipse([w-120 + int(r*math.cos(a)) - 18,
                               100  + int(r*math.sin(a)) - 18,
                               w-120 + int(r*math.cos(a)) + 18,
                               100  + int(r*math.sin(a)) + 18], fill="#fff9c4")

        # Distant mountains / hills (back)
        self._draw_hills(draw, w, h, pal["mid"], y_base=int(h*0.55),
                         count=5, rng=rng, amplitude=int(h*0.18))

        # Ground
        draw.rectangle([0, int(h*0.62), w, h], fill=self._hex(pal["ground"]))

        # Trees
        tree_col   = self._hex(pal["mid"])
        trunk_col  = "#5c3317"
        for tx in [int(w*0.08), int(w*0.18), int(w*0.78), int(w*0.88)]:
            th_  = int(h * rng.uniform(0.22, 0.30))
            ty_  = int(h * 0.62) - th_
            tw_  = int(w * 0.04)
            draw.rectangle([tx - tw_//2, ty_ + th_//2, tx + tw_//2, int(h*0.62)],
                            fill=trunk_col)
            for cr, oy in [(int(w*0.09), 0), (int(w*0.07), int(h*0.06)),
                            (int(w*0.07), -int(h*0.06))]:
                draw.ellipse([tx-cr, ty_+oy-cr, tx+cr, ty_+oy+cr], fill=tree_col)

        # Cave entrance (if cave/crystal scene)
        if pal_key in ("cave",):
            cx, cy = w//2, int(h*0.58)
            draw.ellipse([cx-120, cy-80, cx+120, cy+40], fill="#0d0221")
            for px, pc in [(cx, "#ce93d8"), (cx-60, "#9575cd"), (cx+60, "#7e57c2")]:
                draw.polygon([(px, cy-90), (px-15, cy-40), (px+15, cy-40)],
                              fill=pc)

        # Path
        path_pts = [(w//2, int(h*0.62)),
                    (int(w*0.45), int(h*0.75)),
                    (int(w*0.47), h)]
        draw.line(path_pts, fill=self._lighten(self._hex(pal["ground"]), 1.3),
                  width=max(8, w//60))

        # Milo (left) — simplified cartoon figure
        self._draw_milo(draw, int(w*0.35), int(h*0.62), w, h)

        # Luna (right) — simplified cartoon figure
        self._draw_luna(draw, int(w*0.58), int(h*0.62), w, h)

        # Pip the fox (centre, small)
        self._draw_pip(draw, int(w*0.48), int(h*0.65), w, h)

        # Glowing accent particles
        accent = self._hex(pal["accent"])
        for _ in range(25):
            px = rng.randint(int(w*0.2), int(w*0.8))
            py = rng.randint(int(h*0.3), int(h*0.65))
            pr = rng.choice([2, 3, 4])
            draw.ellipse([px-pr, py-pr, px+pr, py+pr], fill=accent)

        # Episode caption bar at bottom
        caption = seg.get("caption", "")[:50]
        if caption:
            bar_h = max(60, h // 14)
            draw.rectangle([0, h - bar_h, w, h], fill=(0, 0, 0, 180))
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/open-sans/"
                                          "OpenSans-Bold.ttf", max(24, w//40))
            except Exception:
                font = ImageFont.load_default()
            draw.text((w//2, h - bar_h//2), caption,
                       font=font, fill="white", anchor="mm")

        img.save(str(output_path), "PNG")
        logger.info(f"[VideoAgent] PIL cartoon art saved: {output_path.name}")

    # ── Ken Burns animation ───────────────────────────────────────────────────

    def _animate_ken_burns(self, img_path: Path, output_path: Path,
                            duration: int, w: int, h: int, motion: dict):
        """
        Animate a still image with a slow pan + zoom (Ken Burns effect).
        Creates the illusion of a moving camera — makes stills feel alive.

        Uses FFmpeg zoompan filter. The overscan (1.15x) gives room to move
        without revealing canvas edges.
        """
        fps        = self.cfg.video_fps
        n_frames   = duration * fps
        z_start    = motion["zoom_start"] * 1.15   # 1.15 overscan for movement room
        z_end      = motion["zoom_end"]   * 1.15
        x_drift    = motion["x_drift"]
        y_drift    = motion["y_drift"]

        # zoompan expression: zoom and x/y drift linearly over n_frames
        z_expr = f"'min({z_start}+({z_end}-{z_start})*on/{n_frames},{z_end})'"
        x_expr = f"'iw/2-(iw/zoom/2)+{x_drift}*on/{n_frames}'"
        y_expr = f"'ih/2-(ih/zoom/2)+{y_drift}*on/{n_frames}'"

        vf = (
            f"scale={w*2}:{h*2},"   # oversample first for quality
            f"zoompan=z={z_expr}:x={x_expr}:y={y_expr}"
            f":d={n_frames}:s={w}x{h}:fps={fps},"
            f"scale={w}:{h}"
        )

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", str(img_path),
            "-vf", vf,
            "-t", str(duration),
            "-c:v", "libx264",
            "-preset", self.cfg.video_preset,
            "-crf", str(self.cfg.video_crf),
            "-pix_fmt", "yuv420p",
            "-an",
            str(output_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            logger.error(f"[VideoAgent] Ken Burns failed:\n{result.stderr[-500:]}")
            # Hard fallback: static image as video
            self._static_image_to_video(img_path, output_path, duration, w, h)

    def _static_image_to_video(self, img_path: Path, output_path: Path,
                                 duration: int, w: int, h: int):
        """Convert still image to video with no motion — emergency fallback."""
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", str(img_path),
            "-vf", f"scale={w}:{h}",
            "-t", str(duration),
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-pix_fmt", "yuv420p", "-an",
            str(output_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)

    # ── PIL drawing helpers ───────────────────────────────────────────────────

    def _draw_milo(self, draw, cx, ground_y, W, H):
        """Draw a simplified Milo figure (red scarf boy)."""
        scale = W / 1080
        s = lambda v: int(v * scale)
        # Body
        draw.rounded_rectangle([cx-s(18), ground_y-s(80), cx+s(18), ground_y-s(20)],
                                 radius=s(6), fill="#4a90d9")
        # Head
        draw.ellipse([cx-s(22), ground_y-s(118), cx+s(22), ground_y-s(74)], fill="#f4c68d")
        # Hair
        draw.ellipse([cx-s(22), ground_y-s(130), cx+s(22), ground_y-s(108)], fill="#5c3317")
        # Red scarf
        draw.rounded_rectangle([cx-s(20), ground_y-s(88), cx+s(20), ground_y-s(74)],
                                 radius=s(4), fill="#e63946")
        # Eyes
        draw.ellipse([cx-s(12), ground_y-s(108), cx-s(6), ground_y-s(100)], fill="#2c1810")
        draw.ellipse([cx+s(6),  ground_y-s(108), cx+s(12), ground_y-s(100)], fill="#2c1810")
        # Legs
        draw.rounded_rectangle([cx-s(16), ground_y-s(20), cx-s(4), ground_y+s(8)],
                                 radius=s(3), fill="#1d3557")
        draw.rounded_rectangle([cx+s(4),  ground_y-s(20), cx+s(16), ground_y+s(8)],
                                 radius=s(3), fill="#1d3557")

    def _draw_luna(self, draw, cx, ground_y, W, H):
        """Draw a simplified Luna figure (yellow dress, dark hair)."""
        scale = W / 1080
        s = lambda v: int(v * scale)
        draw.rounded_rectangle([cx-s(18), ground_y-s(80), cx+s(18), ground_y-s(20)],
                                 radius=s(6), fill="#f7b731")
        draw.ellipse([cx-s(22), ground_y-s(118), cx+s(22), ground_y-s(74)], fill="#f4c68d")
        # Long dark hair
        draw.ellipse([cx-s(24), ground_y-s(130), cx+s(24), ground_y-s(108)], fill="#2c1810")
        draw.rounded_rectangle([cx-s(26), ground_y-s(110), cx-s(18), ground_y-s(60)],
                                 radius=s(4), fill="#2c1810")
        draw.rounded_rectangle([cx+s(18), ground_y-s(110), cx+s(26), ground_y-s(60)],
                                 radius=s(4), fill="#2c1810")
        draw.ellipse([cx-s(12), ground_y-s(108), cx-s(6), ground_y-s(100)], fill="#2c1810")
        draw.ellipse([cx+s(6),  ground_y-s(108), cx+s(12), ground_y-s(100)], fill="#2c1810")
        draw.rounded_rectangle([cx-s(16), ground_y-s(20), cx-s(4), ground_y+s(8)],
                                 radius=s(3), fill="#7b2d8b")
        draw.rounded_rectangle([cx+s(4),  ground_y-s(20), cx+s(16), ground_y+s(8)],
                                 radius=s(3), fill="#7b2d8b")

    def _draw_pip(self, draw, cx, ground_y, W, H):
        """Draw Pip the tiny fox."""
        scale = W / 1080
        s = lambda v: int(v * scale)
        draw.ellipse([cx-s(20), ground_y-s(28), cx+s(20), ground_y], fill="#e07b39")
        draw.ellipse([cx-s(18), ground_y-s(50), cx+s(18), ground_y-s(22)], fill="#e07b39")
        draw.polygon([(cx-s(18), ground_y-s(44)), (cx-s(26), ground_y-s(62)),
                       (cx-s(10), ground_y-s(46))], fill="#e07b39")
        draw.polygon([(cx+s(10), ground_y-s(46)), (cx+s(26), ground_y-s(62)),
                       (cx+s(18), ground_y-s(44))], fill="#e07b39")
        draw.ellipse([cx-s(10), ground_y-s(46), cx-s(4), ground_y-s(38)], fill="#2c1810")
        draw.ellipse([cx+s(4),  ground_y-s(46), cx+s(10), ground_y-s(38)], fill="#2c1810")
        draw.ellipse([cx-s(4),  ground_y-s(35), cx+s(4),  ground_y-s(29)], fill="#2c1810")

    def _draw_hills(self, draw, W, H, color, y_base, count, rng, amplitude):
        """Draw rolling hills in the background."""
        pts = [(0, y_base)]
        step = W // (count * 2)
        for i in range(count * 2 + 1):
            x = i * step
            y = y_base - rng.randint(0, amplitude) if i % 2 == 1 else y_base
            pts.append((x, y))
        pts += [(W, y_base), (W, H), (0, H)]
        draw.polygon(pts, fill=color)

    # ── Colour utilities ──────────────────────────────────────────────────────

    def _fit_and_crop(self, img, w, h):
        from PIL import Image
        iw, ih = img.size
        scale = max(w / iw, h / ih)
        nw, nh = int(iw * scale), int(ih * scale)
        img = img.resize((nw, nh), Image.LANCZOS)
        x0 = (nw - w) // 2
        y0 = (nh - h) // 2
        return img.crop((x0, y0, x0 + w, y0 + h))

    @staticmethod
    def _hex(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

    @staticmethod
    def _darken(rgb, factor):
        return tuple(int(c * factor) for c in rgb)

    @staticmethod
    def _lighten(rgb, factor):
        return tuple(min(255, int(c * factor)) for c in rgb)

    @staticmethod
    def _lerp_color(c1, c2, t):
        return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
