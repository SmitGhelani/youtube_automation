"""
agents/seo_agent.py — Generates YouTube metadata for the cartoon series.
"""
import json
import logging
import anthropic

logger = logging.getLogger("SEOAgent")


class SEOAgent:
    def __init__(self, config):
        self.cfg    = config
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    def generate(self, script: dict, trend: dict, video_type: str) -> dict:
        ep_num = script.get("title_raw", "")
        is_short = video_type == "short"

        prompt = f"""You are the YouTube SEO manager for "Milo & Luna in Whimble" —
a children's animated cartoon series for ages 4-10.

Episode: {ep_num}
Topic: {trend.get('topic')}
Video type: {'YouTube Short (60s)' if is_short else 'Long-form episode (10 min)'}
Summary: {script.get('episode_summary', '')}

Generate YouTube metadata optimised for a kids cartoon channel.
Title must include episode number and be enticing for parents browsing for kids content.
Description should briefly tell parents what the episode is about.
Tags should include cartoon, kids, animated, children's show variants.

Return ONLY valid JSON:
{{
  "title": "YouTube title max 70 chars — include 'Milo & Luna' and episode flavour",
  "description": "600-800 char description. 1st para: what happens in this episode. 2nd para: about the series. End with hashtags #MiloAndLuna #WhimbleAdventures #KidsCartoon",
  "tags": ["Milo and Luna", "Whimble", "kids cartoon", "children animation", "cartoon series", "animated story", "kids show", "family friendly", "bedtime stories", "cartoon for kids"],
  "chapters": [{{"time": "0:00", "title": "Start"}}],
  "category_id": "1",
  "default_language": "en",
  "music_attribution": "Music: Bensound.com (CC licensed)"
}}"""

        msg = self.client.messages.create(
            model=self.cfg.claude_model, max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip().replace("```json","").replace("```","").strip()
        metadata = json.loads(text)
        logger.info(f"[SEOAgent] Metadata: {metadata['title']}")
        return metadata
