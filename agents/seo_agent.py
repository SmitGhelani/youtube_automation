"""agents/seo_agent.py — SEO metadata for Mahabharat series."""
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
        prompt = f"""You are the YouTube SEO manager for a Mahabharat epic series.

Episode: {script.get('title_raw', '')}
Topic: {trend.get('topic')}
Type: {'60-second teaser Short' if is_short else '15-minute full Saturday episode'}
Summary: {script.get('episode_summary', '')}

Generate YouTube metadata optimised for Mahabharat mythology content.
Titles should be dramatic and click-worthy. Tags should cover Mahabharat
search terms in English and transliterated Sanskrit.

Return ONLY valid JSON, no markdown fences:
{{
  "title": "YouTube title max 70 chars — dramatic, includes episode context",
  "description": "700-900 chars. What happens in this episode. About the series. 3 hashtags: #Mahabharat #MahabharatEpic #EpicIndia",
  "tags": ["mahabharat", "mahabharat full episode", "mahabharat story", "mahabharat series", "mahabharata", "kurukshetra", "pandavas", "kauravas", "arjuna", "krishna", "epic india", "hindu mythology", "indian epic"],
  "chapters": [{{"time": "0:00", "title": "Opening"}}],
  "category_id": "22",
  "default_language": "en",
  "music_attribution": "Music: Bensound.com (CC licensed)"
}}"""

        message  = self.client.messages.create(
            model=self.cfg.claude_model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text     = message.content[0].text.strip().replace("```json", "").replace("```", "").strip()
        metadata = json.loads(text)
        logger.info(f"[SEOAgent] {metadata['title']}")
        return metadata
