"""
agents/trend_agent.py

For the animated cartoon series, there are no "trending topics" to fetch.
Instead, TrendAgent reads the current story state and uses Claude to plan
the next episode beat — what should happen next in the story.

Short:  picks up exactly where yesterday's Short left off
Long:   either merges the week's Shorts into a recap OR generates a
        standalone adventure story with the same characters
"""

import json
import logging
import anthropic

logger = logging.getLogger("TrendAgent")

# Characters — referenced in prompts so Claude stays consistent
CHARACTERS = """
MAIN CHARACTERS (always present):
- Milo (age 10, human boy): brave, kind, loves puzzles, wears a red scarf
- Luna (age 10, human girl): creative, clever, carries a magic compass, loves drawing
- Pip (tiny fox, speaks): cheeky, loyal, secretly brave, loves acorns

WORLD: Whimble — a hidden magical land full of forests, floating islands,
crystal caves, talking animals, and gentle mysteries. Safe, whimsical, warm.
Tone: Pixar-like warmth. Age group: 4-10 years. Always family friendly.
No violence, no fear, no adult themes. Conflict = gentle puzzles and friendship.
"""


class TrendAgent:
    def __init__(self, config):
        self.cfg    = config
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    def find_trending_topic(self, video_type: str) -> dict:
        """
        Returns episode planning dict that ScriptAgent uses.
        For animated series, this is story beat planning, not trend research.
        """
        from story_state import StoryManager
        sm = StoryManager()

        if video_type == "short":
            return self._plan_short_episode(sm.get_context_for_short())
        else:
            return self._plan_long_episode(sm.get_context_for_long())

    # ── Short episode planner ─────────────────────────────────────────────────

    def _plan_short_episode(self, ctx: dict) -> dict:
        ep   = ctx["episode_number"]
        arc  = ctx["current_arc"]
        last = ctx["last_episode_summary"] or "This is the very first episode."
        is_finale = ctx["is_arc_finale"]

        prompt = f"""You are the story editor for "Milo & Luna in Whimble" — a gentle animated cartoon series for children aged 4-10.

{CHARACTERS}

CURRENT ARC: "{arc}"
EPISODE: Short #{ep} (arc episode {ctx['arc_episode']} of {ctx['arc_total']})
IS ARC FINALE: {is_finale}

WHAT HAPPENED LAST:
{last}

CURRENT CHARACTER STATE:
{json.dumps(ctx['character_state'], indent=2)}

CURRENT WORLD STATE:
{json.dumps(ctx['world_state'], indent=2)}

Plan the NEXT 60-second story beat. This must:
1. Continue EXACTLY from where we left off
2. Advance the story meaningfully (not filler)
3. End on a small cliffhanger OR heartwarming moment that makes kids want tomorrow's episode
4. {"RESOLVE the arc with a satisfying conclusion" if is_finale else "Leave one mystery unsolved"}
5. Feature all 3 characters doing something
6. Be gentle, warm, funny — no scary moments

Return ONLY valid JSON:
{{
  "topic": "one-line episode title e.g. 'Pip Finds a Glowing Door'",
  "angle": "the specific story beat that happens in this episode",
  "hook": "first 5 words of the narration that grab kids' attention",
  "episode_beat": "2-3 sentences describing exactly what happens",
  "cliffhanger_or_ending": "how this episode ends (cliffhanger or heartwarming moment)",
  "broll_mood": "animated forest adventure",
  "keywords": ["Milo Luna cartoon", "kids animation", "Whimble", "animated story"],
  "source": "story_arc",
  "search_volume": 9999,
  "context": "continuation of {arc} arc, episode {ctx['arc_episode']}"
}}"""

        resp = self.client.messages.create(
            model=self.cfg.claude_model, max_tokens=800,
            messages=[{"role": "user", "content": prompt}],
        )
        result = json.loads(
            resp.content[0].text.strip().replace("```json","").replace("```","").strip()
        )
        logger.info(f"[TrendAgent] Short EP{ep} planned: {result['topic']}")
        return result

    # ── Long episode planner ──────────────────────────────────────────────────

    def _plan_long_episode(self, ctx: dict) -> dict:
        long_ep  = ctx["long_episode_number"]
        week_sum = ctx["weekly_short_summaries"]
        has_week = len(week_sum) > 0

        if has_week:
            # Merge weekly Shorts into a recap + expansion long video
            return self._plan_weekly_merge(ctx, long_ep, week_sum)
        else:
            # Standalone adventure (different incident, same characters)
            return self._plan_standalone_long(ctx, long_ep)

    def _plan_weekly_merge(self, ctx, long_ep, week_summaries) -> dict:
        prompt = f"""You are the story editor for "Milo & Luna in Whimble" — a children's animated series.

{CHARACTERS}

This is LONG VIDEO #{long_ep} — a weekly recap and expansion.
This week's daily Short episodes covered:
{chr(10).join(week_summaries)}

CURRENT CHARACTER STATE:
{json.dumps(ctx['character_state'], indent=2)}

Plan a 10-minute long video that:
1. Starts with a fun "Previously on Whimble..." recap of the week's adventures (2 min)
2. Expands on the MOST exciting moment from this week with new details (3 min)
3. Shows a NEW extended adventure that bridges to next week (4 min)
4. Ends with a warm, funny moment + tease of next week (1 min)

Return ONLY valid JSON:
{{
  "topic": "Weekly Whimble Adventure — [fun title]",
  "angle": "weekly recap + extended adventure",
  "hook": "opening 5 words for the video",
  "episode_beat": "full description of all 4 parts",
  "cliffhanger_or_ending": "how the long video ends and what it teases",
  "broll_mood": "animated fantasy adventure",
  "keywords": ["Milo Luna cartoon", "Whimble cartoon", "kids cartoon series", "animated adventure"],
  "source": "weekly_merge",
  "search_volume": 9999,
  "context": "weekly merge long video #{long_ep}",
  "new_arc_name": "name of next story arc if this ends one"
}}"""

        resp = self.client.messages.create(
            model=self.cfg.claude_model, max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        result = json.loads(
            resp.content[0].text.strip().replace("```json","").replace("```","").strip()
        )
        logger.info(f"[TrendAgent] Long EP{long_ep} (weekly merge) planned: {result['topic']}")
        return result

    def _plan_standalone_long(self, ctx, long_ep) -> dict:
        prompt = f"""You are the story editor for "Milo & Luna in Whimble" — a children's animated series.

{CHARACTERS}

This is LONG VIDEO #{long_ep} — a standalone adventure story (no weekly Shorts to merge).
Same characters, same world, but a self-contained 10-minute adventure.

CURRENT CHARACTER STATE:
{json.dumps(ctx['character_state'], indent=2)}

Plan a brand new 10-minute self-contained adventure where something unexpected happens —
a new part of Whimble they've never seen, a new friend to meet, a fun mystery to solve.
It should work as a standalone even if someone hasn't seen the Shorts.

Return ONLY valid JSON:
{{
  "topic": "fun self-contained adventure title",
  "angle": "standalone adventure with same characters",
  "hook": "opening 5 words",
  "episode_beat": "full description of the adventure arc",
  "cliffhanger_or_ending": "satisfying conclusion with small tease",
  "broll_mood": "animated fantasy magical",
  "keywords": ["Milo Luna cartoon", "Whimble cartoon", "kids animation", "animated story"],
  "source": "standalone_long",
  "search_volume": 9999,
  "context": "standalone long video #{long_ep}"
}}"""

        resp = self.client.messages.create(
            model=self.cfg.claude_model, max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        result = json.loads(
            resp.content[0].text.strip().replace("```json","").replace("```","").strip()
        )
        logger.info(f"[TrendAgent] Long EP{long_ep} (standalone) planned: {result['topic']}")
        return result
