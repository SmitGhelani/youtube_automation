"""
agents/thumbnail_agent.py
Generates professional YouTube thumbnails using Pillow (free).
1280x720 pixels, high contrast, readable at small sizes.
"""

import logging
import requests
import textwrap
from pathlib import Path
from io import BytesIO

logger = logging.getLogger("ThumbnailAgent")

# Free font downloads (will be fetched once)
FONT_URLS = {
    "bold": "https://github.com/google/fonts/raw/main/apache/opensans/OpenSans%5Bwdth%2Cwght%5D.ttf",
    "regular": "https://github.com/google/fonts/raw/main/apache/opensans/OpenSans%5Bwdth%2Cwght%5D.ttf",
}

# Thumbnail color palettes (proven CTR performers)
PALETTES = [
    {"bg": (10, 10, 46), "accent": (0, 212, 255), "text": (255, 255, 255), "sub": (255, 200, 0)},
    {"bg": (20, 0, 30), "accent": (255, 50, 100), "text": (255, 255, 255), "sub": (255, 210, 0)},
    {"bg": (0, 20, 10), "accent": (0, 255, 120), "text": (255, 255, 255), "sub": (255, 165, 0)},
    {"bg": (30, 10, 0), "accent": (255, 140, 0), "text": (255, 255, 255), "sub": (255, 50, 50)},
]


class ThumbnailAgent:
    def __init__(self, config):
        self.cfg = config
        self.fonts_dir = Path("fonts")
        self.fonts_dir.mkdir(exist_ok=True)

    def generate(self, script: dict, trend: dict, workspace: Path) -> Path:
        """
        Generate a professional 1280x720 thumbnail.
        Returns path to thumbnail PNG.
        """
        try:
            from PIL import Image, ImageDraw, ImageFont, ImageFilter
            return self._create_thumbnail(script, trend, workspace)
        except ImportError:
            logger.error("Pillow not installed. Run: pip install Pillow")
            return self._placeholder_thumbnail(workspace)

    def _create_thumbnail(self, script: dict, trend: dict, workspace: Path) -> Path:
        from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
        import random
        import math

        thumb_path = workspace / "thumbnail.png"
        W, H = 1280, 720

        # Pick color palette (rotate based on topic hash)
        palette_idx = hash(trend.get("topic", "")) % len(PALETTES)
        palette = PALETTES[palette_idx]

        # Create base image
        img = Image.new("RGB", (W, H), palette["bg"])
        draw = ImageDraw.Draw(img)

        # ── Background: particle/tech grid effect ──────────────────────────
        self._draw_tech_grid(draw, W, H, palette["accent"])

        # ── Gradient overlay (left darkening for text readability) ─────────
        gradient = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        grad_draw = ImageDraw.Draw(gradient)
        for x in range(W):
            alpha = int(180 * (1 - x / W * 0.6))
            grad_draw.line([(x, 0), (x, H)], fill=(0, 0, 0, alpha))
        img = Image.alpha_composite(img.convert("RGBA"), gradient).convert("RGB")
        draw = ImageDraw.Draw(img)

        # ── Accent bar (left side) ─────────────────────────────────────────
        draw.rectangle([0, 0, 8, H], fill=palette["accent"])

        # ── Load fonts ─────────────────────────────────────────────────────
        font_title, font_sub, font_emoji = self._load_fonts()

        # ── Main headline text ──────────────────────────────────────────────
        headline = script.get("thumbnail_text", trend.get("topic", "AMAZING DISCOVERY"))
        headline = headline.upper()
        emoji = script.get("thumbnail_emoji", "🤯")

        # Wrap text for thumbnail
        lines = textwrap.wrap(headline, width=14)[:3]  # Max 3 lines

        # Calculate text block height
        line_height = 110
        total_text_h = len(lines) * line_height
        text_start_y = (H - total_text_h) // 2 - 40

        # Draw text with shadow
        for i, line in enumerate(lines):
            y = text_start_y + i * line_height
            # Shadow
            draw.text((52, y + 4), line, font=font_title, fill=(0, 0, 0, 180))
            # Main text with gradient (simulate by drawing twice with offset)
            draw.text((50, y), line, font=font_title, fill=palette["text"])

        # ── Subtitle / subtext ─────────────────────────────────────────────
        sub_y = text_start_y + len(lines) * line_height + 20
        sub_text = trend.get("topic", "")[:50]
        draw.text((52, sub_y + 2), sub_text, font=font_sub, fill=(0, 0, 0, 150))
        draw.text((50, sub_y), sub_text, font=font_sub, fill=palette["sub"])

        # ── Emoji (large, right side) ──────────────────────────────────────
        try:
            draw.text((900, H // 2 - 100), emoji, font=font_emoji, fill=palette["text"])
        except Exception:
            pass  # Some systems don't support emoji in PIL

        # ── "NEW" badge ────────────────────────────────────────────────────
        badge_x, badge_y = 50, 40
        draw.rounded_rectangle(
            [badge_x, badge_y, badge_x + 110, badge_y + 44],
            radius=6,
            fill=palette["accent"],
        )
        draw.text((badge_x + 55, badge_y + 22), "TODAY", font=font_sub,
                  fill=palette["bg"], anchor="mm")

        # ── Bottom info bar ────────────────────────────────────────────────
        draw.rectangle([0, H - 50, W, H], fill=(0, 0, 0, 180))

        # Save
        img.save(str(thumb_path), "PNG", optimize=True, quality=95)
        logger.info(f"Thumbnail saved: {thumb_path} ({W}x{H})")
        return thumb_path

    def _draw_tech_grid(self, draw, W: int, H: int, color: tuple):
        """Draw a subtle tech grid pattern on the background."""
        r, g, b = color
        grid_color = (r, g, b, 30)  # Very transparent

        # Horizontal lines
        for y in range(0, H, 60):
            draw.line([(0, y), (W, y)], fill=(r//4, g//4, b//4), width=1)

        # Vertical lines
        for x in range(0, W, 80):
            draw.line([(x, 0), (x, H)], fill=(r//4, g//4, b//4), width=1)

        # Accent dots at grid intersections
        for y in range(0, H, 120):
            for x in range(0, W, 160):
                draw.ellipse([x-3, y-3, x+3, y+3], fill=(r//2, g//2, b//2))

    def _load_fonts(self):
        """Load fonts from system or download free fonts."""
        from PIL import ImageFont
        import platform

        # Try system fonts first
        system_fonts = {
            "Linux": [
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
                "/usr/share/fonts/truetype/ubuntu/Ubuntu-Bold.ttf",
            ],
            "Darwin": [
                "/Library/Fonts/Arial Bold.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
            ],
            "Windows": [
                "C:/Windows/Fonts/arialbd.ttf",
                "C:/Windows/Fonts/calibrib.ttf",
            ],
        }

        os_name = platform.system()
        font_paths = system_fonts.get(os_name, system_fonts["Linux"])

        font_path = None
        for fp in font_paths:
            if Path(fp).exists():
                font_path = fp
                break

        if font_path:
            try:
                font_title = ImageFont.truetype(font_path, 105)
                font_sub = ImageFont.truetype(font_path, 36)
                font_emoji = ImageFont.truetype(font_path, 120)
                return font_title, font_sub, font_emoji
            except Exception as e:
                logger.warning(f"Font load failed: {e}")

        # Ultimate fallback: PIL default font (looks basic but works)
        default = ImageFont.load_default()
        return default, default, default

    def _placeholder_thumbnail(self, workspace: Path) -> Path:
        """Create a minimal placeholder if Pillow is not available."""
        thumb_path = workspace / "thumbnail.png"
        # Use FFmpeg to generate a thumbnail
        import subprocess
        cmd = [
            "ffmpeg", "-y",
            "-f", "lavfi",
            "-i", "color=c=0x0a0a2e:s=1280x720:r=1",
            "-vframes", "1",
            str(thumb_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return thumb_path
