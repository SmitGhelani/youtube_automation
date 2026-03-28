"""
agents/seo_agent.py — Generates title, description, tags, chapters
"""
import json
import logging
import anthropic

logger = logging.getLogger("SEOAgent")


class SEOAgent:
    def __init__(self, config):
        self.cfg = config
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    def generate(self, script: dict, trend: dict, video_type: str) -> dict:
        is_short = video_type == "short"
        prompt = f"""You are a YouTube SEO expert. Generate optimized metadata.

Topic: {trend.get('topic')}
Script title: {script.get('title_raw', '')}
Keywords: {trend.get('keywords', [])}
Video type: {'YouTube Short (60s)' if is_short else 'Long-form video (10 min)'}
Channel niche: {self.cfg.channel_niche}

Return ONLY valid JSON:
{{
  "title": "YouTube title max 70 chars with main keyword near start",
  "description": "Full description 800-1000 chars. Include hook, what viewers learn, 3 hashtags. Be honest.",
  "tags": ["tag1","tag2","tag3","tag4","tag5","tag6","tag7","tag8","tag9","tag10"],
  "chapters": [{{"time": "0:00", "title": "Introduction"}}],
  "category_id": "28",
  "default_language": "en",
  "music_attribution": "Music: Bensound.com"
}}"""

        message = self.client.messages.create(
            model=self.cfg.claude_model,
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        text = message.content[0].text.strip().replace("```json","").replace("```","").strip()
        metadata = json.loads(text)
        logger.info(f"SEO metadata: {metadata['title']}")
        return metadata
