"""
agents/trend_agent.py

Uses google-genai (NEW SDK — NOT deprecated google.generativeai).
Free tier: 1500 requests/day, 15 RPM on gemini-2.0-flash.
Install: pip install google-genai
"""
import json
import logging
from google import genai
from google.genai import types

logger = logging.getLogger("TrendAgent")

MAHABHARAT_CONTEXT = """
SERIES: Mahabharat — The Epic of Ancient India
STYLE: Cinematic, reverent, emotionally powerful. Like a prestige TV series.
TONE: Epic. Grand. Occasionally poetic. Never childish.
AUDIENCE: Devotees, mythology fans, general Indian audience, global viewers.
"""


class TrendAgent:
    def __init__(self, config):
        self.cfg = config
        self.client = genai.Client(api_key=config.gemini_api_key)

    def _call(self, prompt: str, max_tokens: int = 1024) -> str:
        resp = self.client.models.generate_content(
            model=self.cfg.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=0.7,
            ),
        )
        return resp.text.strip()

    def find_trending_topic(self, video_type: str) -> dict:
        from story_state import StoryManager
        sm = StoryManager()
        if video_type == "short":
            return self._plan_short_teaser(sm.get_context_for_short())
        else:
            return self._plan_long_episode(sm.get_context_for_long())

    def _plan_short_teaser(self, ctx: dict) -> dict:
        ep = ctx["short_episode"]
        prompt = f"""{MAHABHARAT_CONTEXT}

Plan a 60-second SHORT TEASER for the Mahabharat series.

CURRENT PARVA: {ctx['parva']}
SHORT EPISODE: #{ep} (Scene {ctx['parva_scene']} of {ctx['parva_total_scenes']})
IS PARVA FINALE: {ctx['is_parva_finale']}
WHAT WAS SHOWN LAST: {ctx['last_summary']}
CHARACTER STATES: {json.dumps(ctx['character_state'], indent=2)}
WORLD STATE: {json.dumps(ctx['world_state'], indent=2)}

Return ONLY valid JSON, no markdown fences:
{{
  "topic": "Short teaser title",
  "angle": "the dramatic moment being teased",
  "hook": "opening 5 words of narration",
  "episode_beat": "what this teaser shows and how it ends",
  "cliffhanger_or_ending": "the exact dramatic cut or line that ends the short",
  "scene_prompt_style": "cinematic ancient India epic dramatic",
  "keywords": ["mahabharat", "mahabharat episode {ep}", "{ctx['parva']}", "epic of india"],
  "source": "story_arc",
  "search_volume": 9999,
  "context": "{ctx['parva']}, teaser for episode {ctx['parva_scene']}"
}}"""
        text = self._call(prompt, 1024).replace("```json","").replace("```","").strip()
        result = json.loads(text)
        logger.info(f"[TrendAgent] Short teaser EP{ep}: {result['topic']}")
        return result

    def _plan_long_episode(self, ctx: dict) -> dict:
        long_ep  = ctx["long_episode"]
        week_sum = ctx["weekly_short_summaries"]
        prompt = f"""{MAHABHARAT_CONTEXT}

Plan a SATURDAY 15-MINUTE FULL EPISODE of the Mahabharat series.

CURRENT PARVA: {ctx['parva']}
LONG EPISODE: #{long_ep}
THIS WEEK'S TEASER SHORTS: {chr(10).join(week_sum) if week_sum else "No teasers — standalone episode."}
CHARACTER STATES: {json.dumps(ctx['character_state'], indent=2)}
WORLD STATE: {json.dumps(ctx['world_state'], indent=2)}

Return ONLY valid JSON, no markdown fences:
{{
  "topic": "Full episode title",
  "angle": "the full episode story arc in one sentence",
  "hook": "opening 5 words of the episode",
  "episode_beat": "full description of all major scenes",
  "cliffhanger_or_ending": "how the episode ends and what it teases next week",
  "scene_prompt_style": "epic cinematic ancient India kurukshetra palace dramatic",
  "keywords": ["mahabharat full episode", "{ctx['parva']}", "mahabharat {long_ep}", "epic india"],
  "source": "mahabharat_long",
  "search_volume": 9999,
  "context": "{ctx['parva']}, full episode #{long_ep}"
}}"""
        text = self._call(prompt, 1024).replace("```json","").replace("```","").strip()
        result = json.loads(text)
        logger.info(f"[TrendAgent] Long EP{long_ep}: {result['topic']}")
        return result
