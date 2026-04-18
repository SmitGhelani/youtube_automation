"""
agents/trend_agent.py

Plans the next Mahabharat episode beat using Claude (Anthropic).
Replaced google.generativeai (deprecated, 20 RPD free limit) with
anthropic SDK which uses ANTHROPIC_API_KEY already in the environment.

Short:  60-second teaser of the upcoming Saturday episode
Long:   15-minute full Mahabharat episode every Saturday
"""

import json
import logging
import anthropic

logger = logging.getLogger("TrendAgent")

MAHABHARAT_CONTEXT = """
SERIES: Mahabharat — The Epic of Ancient India
STYLE: Cinematic, reverent, emotionally powerful. Like a prestige TV series.
       Vivid descriptions of characters, landscapes, and inner emotions.
       Narrated by a wise storyteller voice (like a shloka being recited).
TONE: Epic. Grand. Occasionally poetic. Never childish.
AUDIENCE: Devotees, mythology fans, general Indian audience, global viewers.
"""


class TrendAgent:
    def __init__(self, config):
        self.cfg = config
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    def find_trending_topic(self, video_type: str) -> dict:
        from story_state import StoryManager
        sm = StoryManager()
        if video_type == "short":
            return self._plan_short_teaser(sm.get_context_for_short())
        else:
            return self._plan_long_episode(sm.get_context_for_long())

    def _call_claude(self, prompt: str, max_tokens: int = 1024) -> str:
        """Single helper — all Claude calls go through here."""
        message = self.client.messages.create(
            model=self.cfg.claude_model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return message.content[0].text.strip()

    def _plan_short_teaser(self, ctx: dict) -> dict:
        ep        = ctx["short_episode"]
        parva     = ctx["parva"]
        last      = ctx["last_summary"]
        is_finale = ctx["is_parva_finale"]

        prompt = f"""{MAHABHARAT_CONTEXT}

You are planning a 60-second SHORT TEASER for the Mahabharat series.
Shorts are TEASERS — they hint at what happens in the upcoming Saturday episode
and end on a dramatic hook that makes viewers desperate to watch the full video.

CURRENT PARVA: {parva}
SHORT EPISODE: #{ep} (Scene {ctx['parva_scene']} of {ctx['parva_total_scenes']})
IS PARVA FINALE TEASER: {is_finale}

WHAT WAS SHOWN LAST:
{last}

CHARACTER STATES:
{json.dumps(ctx['character_state'], indent=2)}

WORLD STATE:
{json.dumps(ctx['world_state'], indent=2)}

Plan a SHORT TEASER that:
1. Opens with ONE dramatic visual moment from the upcoming episode
2. Shows a key character at a turning point — facial expression, inner conflict
3. Drops ONE shocking line of dialogue or narration
4. Ends on a hard cut with "SATURDAY — THE FULL STORY" type hook
5. Makes viewers comment and share — maximum curiosity, minimum spoilers

Return ONLY valid JSON, no markdown fences:
{{
  "topic": "Short teaser title e.g. 'Arjuna Raises His Bow...'",
  "angle": "the dramatic moment being teased",
  "hook": "opening 5 words of narration",
  "episode_beat": "what this teaser shows and how it ends",
  "cliffhanger_or_ending": "the exact dramatic cut or line that ends the short",
  "scene_prompt_style": "cinematic ancient India epic dramatic",
  "keywords": ["mahabharat", "mahabharat episode {ep}", "{parva}", "epic of india"],
  "source": "story_arc",
  "search_volume": 9999,
  "context": "{parva}, teaser for episode {ctx['parva_scene']}"
}}"""

        text   = self._call_claude(prompt, max_tokens=1024)
        text   = text.replace("```json", "").replace("```", "").strip()
        result = json.loads(text)
        logger.info(f"[TrendAgent] Short teaser EP{ep} planned: {result['topic']}")
        return result

    def _plan_long_episode(self, ctx: dict) -> dict:
        parva    = ctx["parva"]
        long_ep  = ctx["long_episode"]
        week_sum = ctx["weekly_short_summaries"]

        prompt = f"""{MAHABHARAT_CONTEXT}

You are planning a SATURDAY 15-MINUTE FULL EPISODE of the Mahabharat series.
This is the banger episode viewers have been waiting for all week.
The week's Shorts were teasers for THIS episode.

CURRENT PARVA: {parva}
LONG EPISODE: #{long_ep}

THIS WEEK'S TEASER SHORTS SHOWED:
{chr(10).join(week_sum) if week_sum else "No teasers this week — standalone episode."}

CHARACTER STATES:
{json.dumps(ctx['character_state'], indent=2)}

WORLD STATE:
{json.dumps(ctx['world_state'], indent=2)}

Plan a FULL 15-MINUTE EPISODE that:
1. Picks up from exactly where the teasers left off
2. Has a complete story arc — setup, rising tension, climax, resolution
3. Ends with a major revelation or cliffhanger that sets up next week's teasers
4. Features iconic Mahabharat moments with full dramatic weight
5. Feels like a prestige TV episode — GoT / Bahubali quality storytelling

Return ONLY valid JSON, no markdown fences:
{{
  "topic": "Full episode title e.g. 'The Dice Game — Draupadi's Vow'",
  "angle": "the full episode story arc in one sentence",
  "hook": "opening 5 words of the episode",
  "episode_beat": "full description of all major scenes in the episode",
  "cliffhanger_or_ending": "how the episode ends and what it teases for next week",
  "scene_prompt_style": "epic cinematic ancient India kurukshetra palace dramatic",
  "keywords": ["mahabharat full episode", "{parva}", "mahabharat {long_ep}", "epic india"],
  "source": "mahabharat_long",
  "search_volume": 9999,
  "context": "{parva}, full episode #{long_ep}"
}}"""

        text   = self._call_claude(prompt, max_tokens=1024)
        text   = text.replace("```json", "").replace("```", "").strip()
        result = json.loads(text)
        logger.info(f"[TrendAgent] Long EP{long_ep} planned: {result['topic']}")
        return result
