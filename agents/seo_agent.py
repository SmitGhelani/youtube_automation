"""
agents/seo_agent.py

Uses google-genai (NEW SDK — NOT deprecated google.generativeai).
Free tier: 1500 requests/day on gemini-2.0-flash.
Install: pip install google-genai
"""
import json
import logging
from google import genai
from google.genai import types

logger = logging.getLogger("SEOAgent")


class SEOAgent:
    def __init__(self, config):
        self.cfg = config
        self.client = genai.Client(api_key=config.gemini_api_key)

    def generate(self, script: dict, trend: dict, video_type: str) -> dict:
        is_short = video_type == "short"
        prompt = f"""You are the YouTube SEO manager for a Mahabharat epic series.

Episode: {script.get('title_raw', '')}
Topic: {trend.get('topic')}
Type: {'60-second teaser Short' if is_short else '15-minute full Saturday episode'}
Summary: {script.get('episode_summary', '')}

Generate YouTube metadata optimised for Mahabharat mythology content.
Titles should be dramatic and click-worthy.

Return ONLY valid JSON, no markdown fences:
{{
  "title": "YouTube title max 70 chars — dramatic, episode context included",
  "description": "700-900 chars. Episode summary. About the series. End with: #Mahabharat #MahabharatEpic #EpicIndia",
  "tags": ["mahabharat","mahabharat full episode","mahabharat story","mahabharata","kurukshetra","pandavas","kauravas","arjuna","krishna","bhishma","karna","draupadi","epic india","hindu mythology","indian epic","mahabharat series"],
  "chapters": [{{"time": "0:00", "title": "Opening"}}],
  "category_id": "22",
  "default_language": "en",
  "music_attribution": "Music: Bensound.com (CC licensed)"
}}"""

        resp = self.client.models.generate_content(
            model=self.cfg.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=1024,
                temperature=0.7,
            ),
        )
        text     = resp.text.strip().replace("```json","").replace("```","").strip()
        metadata = json.loads(text)
        logger.info(f"[SEOAgent] {metadata['title']}")
        return metadata
