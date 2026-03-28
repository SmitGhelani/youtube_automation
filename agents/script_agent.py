"""
agents/script_agent.py
Generates full video scripts using Claude API.
Scripts include: hook, main content, B-roll cues, CTA.
"""

import json
import logging
import anthropic

logger = logging.getLogger("ScriptAgent")


class ScriptAgent:
    def __init__(self, config):
        self.cfg = config
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    def generate(self, trend: dict, video_type: str) -> dict:
        """
        Returns a full structured script.
        """
        if video_type == "short":
            return self._generate_short(trend)
        else:
            return self._generate_long(trend)

    def _generate_short(self, trend: dict) -> dict:
        """Generate a 55-60 second Short script."""
        prompt = f"""You are an expert YouTube Shorts scriptwriter creating VIRAL, educational content.

TOPIC: {trend['topic']}
ANGLE: {trend.get('angle', 'fascinating discovery')}
HOOK: {trend.get('hook', 'Did you know')}
CHANNEL NICHE: {self.cfg.channel_niche}
AUDIENCE: {self.cfg.target_audience}

Write a 55-second YouTube Shorts script that:
1. HOOK (0-5s): Start with a shocking fact or question — no "hi" or "welcome"
2. CONTENT (5-50s): Deliver 3-5 punchy facts, use simple language, build tension
3. CTA (50-59s): "Follow for daily tech facts" + visual prompt
4. SAFE CONTENT: No hate, no politics, no religion, no violence, family-friendly
5. ENGAGING: Write for 18-35 tech enthusiasts who scroll fast

Return ONLY valid JSON (no markdown):
{{
  "title_raw": "draft title for script",
  "topic": "{trend['topic']}",
  "duration_sec": 58,
  "segments": [
    {{
      "id": 1,
      "type": "hook",
      "text": "spoken narration here",
      "duration_sec": 5,
      "broll_query": "search query for Pexels video",
      "caption": "on-screen text overlay",
      "emotion": "shock"
    }},
    {{
      "id": 2,
      "type": "fact",
      "text": "spoken narration here",
      "duration_sec": 12,
      "broll_query": "search query for Pexels video",
      "caption": "key stat or quote to show on screen",
      "emotion": "curious"
    }},
    {{
      "id": 3,
      "type": "fact",
      "text": "spoken narration here",
      "duration_sec": 12,
      "broll_query": "search query for Pexels video",
      "caption": "key stat or quote",
      "emotion": "amazed"
    }},
    {{
      "id": 4,
      "type": "fact",
      "text": "spoken narration here",
      "duration_sec": 14,
      "broll_query": "search query for Pexels video",
      "caption": "key stat or quote",
      "emotion": "excited"
    }},
    {{
      "id": 5,
      "type": "cta",
      "text": "Follow for daily tech discoveries that will blow your mind!",
      "duration_sec": 5,
      "broll_query": "technology future abstract",
      "caption": "FOLLOW for daily mind-blowing tech facts! 🚀",
      "emotion": "energetic"
    }}
  ],
  "background_music_mood": "upbeat electronic",
  "color_theme": "dark blue with neon accents",
  "thumbnail_text": "3-4 word thumbnail headline",
  "thumbnail_emoji": "🤯",
  "keywords": {json.dumps(trend.get('keywords', []))}
}}"""

        message = self.client.messages.create(
            model=self.cfg.claude_model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )

        text = message.content[0].text.strip().replace("```json", "").replace("```", "").strip()
        script = json.loads(text)
        script["video_type"] = "short"
        logger.info(f"Short script generated: {script['title_raw']}")
        return script

    def _generate_long(self, trend: dict) -> dict:
        """Generate an 8-12 minute long-form video script."""
        prompt = f"""You are an expert YouTube scriptwriter creating VIRAL, educational long-form content.

TOPIC: {trend['topic']}
ANGLE: {trend.get('angle', 'deep dive')}
CHANNEL NICHE: {self.cfg.channel_niche}
AUDIENCE: {self.cfg.target_audience}
TARGET LENGTH: 10 minutes (600 seconds)

Write a full 10-minute YouTube video script with:
1. HOOK (0-30s): Tease the most shocking reveal — don't give it away yet
2. INTRO (30-60s): Who you are, what viewers will learn, why it matters NOW
3. SECTION 1 (60-180s): Background and context — make it fascinating
4. SECTION 2 (180-360s): The main discovery/development — detailed but accessible
5. SECTION 3 (360-480s): Implications and real-world impact
6. SECTION 4 (480-570s): What's next / future predictions
7. OUTRO (570-600s): Recap + CTA to subscribe + tease next video

Rules:
- No hate, politics, religion, violence — 100% family safe
- Cite general facts (avoid specific unverifiable claims)
- Use storytelling, analogies, and rhetorical questions
- Add chapter markers for viewer retention

Return ONLY valid JSON (no markdown):
{{
  "title_raw": "draft title",
  "topic": "{trend['topic']}",
  "duration_sec": 600,
  "chapters": [
    {{
      "id": 1,
      "title": "chapter title",
      "timestamp_sec": 0,
      "type": "hook",
      "text": "full spoken script for this section",
      "duration_sec": 30,
      "broll_queries": ["query1", "query2"],
      "key_points": ["point1", "point2"],
      "caption_overlays": ["overlay text"]
    }}
  ],
  "background_music_mood": "cinematic inspiring",
  "color_theme": "dark professional blue",
  "thumbnail_text": "thumbnail headline 4-6 words",
  "thumbnail_emoji": "🚀",
  "keywords": {json.dumps(trend.get('keywords', []))}
}}

Include all 7 sections as chapters."""

        message = self.client.messages.create(
            model=self.cfg.claude_model,
            max_tokens=6000,
            messages=[{"role": "user", "content": prompt}],
        )

        text = message.content[0].text.strip().replace("```json", "").replace("```", "").strip()
        script = json.loads(text)
        script["video_type"] = "long"
        logger.info(f"Long script generated: {script['title_raw']} ({len(script['chapters'])} chapters)")
        return script

    def get_full_narration(self, script: dict) -> str:
        """Extract all spoken text from script for TTS."""
        if script["video_type"] == "short":
            return " ".join(seg["text"] for seg in script["segments"])
        else:
            return " ".join(ch["text"] for ch in script["chapters"])
