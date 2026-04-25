"""
agents/trend_agent.py — Plans Mahabharat episodes using local Ollama (FREE).
No API keys. No quotas. No cost. Runs on EC2 locally.
"""
import json
import logging
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from llm_client import LLMClient

logger = logging.getLogger("TrendAgent")

MAHABHARAT_CONTEXT = """You are a creative director for the Mahabharat YouTube series.
SERIES: Mahabharat - The Epic of Ancient India
STYLE: Cinematic, reverent, emotionally powerful. Like a prestige TV series.
TONE: Epic. Grand. Occasionally poetic. Never childish.
AUDIENCE: Devotees, mythology fans, general Indian audience, global viewers."""


class TrendAgent:
    def __init__(self, config):
        self.cfg = config
        self.llm = LLMClient()

    def find_trending_topic(self, video_type: str) -> dict:
        from story_state import StoryManager
        sm = StoryManager()
        if video_type == "short":
            return self._plan_short_teaser(sm.get_context_for_short())
        else:
            return self._plan_long_episode(sm.get_context_for_long())

    def _plan_short_teaser(self, ctx: dict) -> dict:
        ep        = ctx["short_episode"]
        parva     = ctx["parva"]
        last      = ctx["last_summary"]
        is_finale = ctx["is_parva_finale"]

        prompt = (
            f"{MAHABHARAT_CONTEXT}\n\n"
            f"Plan a 60-second SHORT TEASER for the Mahabharat YouTube series.\n"
            f"CURRENT PARVA: {parva}\n"
            f"SHORT EPISODE: #{ep} (Scene {ctx['parva_scene']} of {ctx['parva_total_scenes']})\n"
            f"IS PARVA FINALE TEASER: {is_finale}\n"
            f"WHAT WAS SHOWN LAST: {last}\n"
            f"CHARACTER STATES: {json.dumps(ctx['character_state'])}\n\n"
            f"Return a JSON object with these exact keys:\n"
            '{\n'
            f'  "topic": "Short teaser title",\n'
            f'  "angle": "the dramatic moment being teased",\n'
            f'  "hook": "opening 5 words of narration",\n'
            f'  "episode_beat": "what this teaser shows",\n'
            f'  "cliffhanger_or_ending": "the dramatic line that ends the short",\n'
            f'  "scene_prompt_style": "cinematic ancient India epic dramatic",\n'
            f'  "keywords": ["mahabharat", "{parva}", "epic india"],\n'
            f'  "source": "story_arc",\n'
            f'  "search_volume": 9999,\n'
            f'  "context": "{parva} teaser"\n'
            '}'
        )

        result = self.llm.generate_json(prompt, max_tokens=512)
        logger.info(f"[TrendAgent] Short EP{ep}: {result.get('topic','')}")
        return result

    def _plan_long_episode(self, ctx: dict) -> dict:
        long_ep  = ctx["long_episode"]
        parva    = ctx["parva"]
        week_sum = ctx["weekly_short_summaries"]

        prompt = (
            f"{MAHABHARAT_CONTEXT}\n\n"
            f"Plan a SATURDAY 15-MINUTE FULL EPISODE of the Mahabharat series.\n"
            f"CURRENT PARVA: {parva}\n"
            f"LONG EPISODE: #{long_ep}\n"
            f"THIS WEEK TEASERS: {'; '.join(week_sum) if week_sum else 'standalone episode'}\n"
            f"CHARACTER STATES: {json.dumps(ctx['character_state'])}\n\n"
            f"Return a JSON object with these exact keys:\n"
            '{\n'
            f'  "topic": "Full episode title",\n'
            f'  "angle": "the story arc in one sentence",\n'
            f'  "hook": "opening 5 words",\n'
            f'  "episode_beat": "description of all major scenes",\n'
            f'  "cliffhanger_or_ending": "how the episode ends",\n'
            f'  "scene_prompt_style": "epic cinematic ancient India palace dramatic",\n'
            f'  "keywords": ["mahabharat full episode", "{parva}", "epic india"],\n'
            f'  "source": "mahabharat_long",\n'
            f'  "search_volume": 9999,\n'
            f'  "context": "{parva} full episode {long_ep}"\n'
            '}'
        )

        result = self.llm.generate_json(prompt, max_tokens=512)
        logger.info(f"[TrendAgent] Long EP{long_ep}: {result.get('topic','')}")
        return result
