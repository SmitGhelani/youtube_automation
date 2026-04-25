"""
agents/seo_agent.py — SEO metadata using local Ollama (FREE).
No API keys. No quotas. No cost.
"""
import json
import logging
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from llm_client import LLMClient

logger = logging.getLogger("SEOAgent")


class SEOAgent:
    def __init__(self, config):
        self.cfg = config
        self.llm = LLMClient()

    def generate(self, script: dict, trend: dict, video_type: str) -> dict:
        is_short = video_type == "short"
        prompt = (
            f"You are the YouTube SEO manager for a Mahabharat epic series.\n\n"
            f"Episode: {script.get('title_raw', '')}\n"
            f"Topic: {trend.get('topic', '')}\n"
            f"Type: {'60-second teaser Short' if is_short else '15-minute full Saturday episode'}\n"
            f"Summary: {script.get('episode_summary', '')}\n\n"
            f"Generate YouTube metadata. Return a JSON object with these exact keys:\n"
            '{\n'
            '  "title": "YouTube title max 70 chars, dramatic and click-worthy",\n'
            '  "description": "Write 700-900 chars. Episode summary. Series info. End with: #Mahabharat #MahabharatEpic #EpicIndia",\n'
            '  "tags": ["mahabharat","mahabharat full episode","mahabharat story","mahabharata","kurukshetra","pandavas","kauravas","arjuna","krishna","bhishma","karna","draupadi","epic india","hindu mythology","indian epic","mahabharat series"],\n'
            '  "chapters": [{"time": "0:00", "title": "Opening"}],\n'
            '  "category_id": "22",\n'
            '  "default_language": "en",\n'
            '  "music_attribution": "Music: Bensound.com (CC licensed)"\n'
            '}'
        )

        metadata = self.llm.generate_json(prompt, max_tokens=1024)

        # Safety: ensure title is not too long
        if len(metadata.get("title", "")) > 100:
            metadata["title"] = metadata["title"][:97] + "..."

        logger.info(f"[SEOAgent] {metadata.get('title','')}")
        return metadata
