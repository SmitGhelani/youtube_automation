"""
agents/script_agent.py

Generates animated cartoon story scripts for "Milo & Luna in Whimble".

Short: 55-60 second continuation episode — picks up from yesterday
Long:  10-minute weekly recap+expansion OR standalone adventure
"""

import json
import logging
import anthropic

logger = logging.getLogger("ScriptAgent")

CHARACTERS = """
CHARACTERS (stay 100% consistent):
- Milo (10, boy): brave, kind, red scarf, loves puzzles. Voice: warm, curious.
- Luna (10, girl): creative, magic compass, sketchbook. Voice: bright, enthusiastic.
- Pip (tiny fox, speaks): cheeky, loyal, secretly brave, loves acorns. Voice: squeaky, funny.
WORLD: Whimble — magical hidden land, warm Pixar tone, age 4-10, always family safe.
"""


class ScriptAgent:
    def __init__(self, config):
        self.cfg    = config
        self.client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    def generate(self, trend: dict, video_type: str) -> dict:
        if video_type == "short":
            return self._generate_short(trend)
        else:
            return self._generate_long(trend)

    # ── Short script ──────────────────────────────────────────────────────────

    def _generate_short(self, trend: dict) -> dict:
        prompt = f"""You are writing a 60-second episode of "Milo & Luna in Whimble" — a gentle animated cartoon for children aged 4-10.

{CHARACTERS}

EPISODE PLAN:
Topic/Title: {trend['topic']}
Story beat: {trend['angle']}
Opening hook: {trend['hook']}
What happens: {trend['episode_beat']}
How it ends: {trend['cliffhanger_or_ending']}

Write the full 60-second narration script as if a warm storyteller is narrating.
Sentences must be SHORT — kids' attention spans are small.
Use sound words (WHOOSH, CRUNCH, GIGGLE) in narration naturally.
Keep it magical, funny, and warm. No scary moments.

Return ONLY valid JSON (no markdown):
{{
  "title_raw": "Episode title",
  "topic": "{trend['topic']}",
  "video_type": "short",
  "duration_sec": 58,
  "segments": [
    {{
      "id": 1,
      "type": "hook",
      "text": "narration (5-8 seconds worth)",
      "duration_sec": 7,
      "broll_query": "animated cartoon forest magical",
      "caption": "short on-screen text",
      "emotion": "excited"
    }},
    {{
      "id": 2,
      "type": "story",
      "text": "narration (12-15 seconds)",
      "duration_sec": 13,
      "broll_query": "cartoon adventure kids forest",
      "caption": "caption text",
      "emotion": "curious"
    }},
    {{
      "id": 3,
      "type": "story",
      "text": "narration (12-15 seconds)",
      "duration_sec": 13,
      "broll_query": "cartoon magical glowing cave",
      "caption": "caption text",
      "emotion": "amazed"
    }},
    {{
      "id": 4,
      "type": "story",
      "text": "narration (12-15 seconds)",
      "duration_sec": 13,
      "broll_query": "cartoon kids discover treasure",
      "caption": "caption text",
      "emotion": "wonder"
    }},
    {{
      "id": 5,
      "type": "cliffhanger",
      "text": "cliffhanger or heartwarming ending narration",
      "duration_sec": 7,
      "broll_query": "cartoon mystery door glowing",
      "caption": "WHAT HAPPENS NEXT? 👀",
      "emotion": "suspense"
    }},
    {{
      "id": 6,
      "type": "cta",
      "text": "Follow Milo, Luna and Pip for a new adventure every single day!",
      "duration_sec": 5,
      "broll_query": "cartoon kids waving happy",
      "caption": "NEW EPISODE EVERY DAY! 🦊✨",
      "emotion": "warm"
    }}
  ],
  "background_music_mood": "calm background",
  "color_theme": "warm forest greens and golden light",
  "thumbnail_text": "3-4 word episode title",
  "thumbnail_emoji": "✨",
  "keywords": ["milo luna cartoon", "whimble", "kids animation", "cartoon series"],
  "episode_summary": "2-3 sentence summary of what happened for story continuity tracking",
  "updated_character_state": {{
    "Milo": {{"mood": "...", "location": "...", "last_action": "...", "items": [], "friends_met": [], "goal": "..."}},
    "Luna": {{"mood": "...", "location": "...", "last_action": "...", "items": [], "friends_met": [], "goal": "..."}},
    "Pip":  {{"mood": "...", "location": "...", "last_action": "...", "items": [], "friends_met": [], "goal": "..."}}
  }},
  "updated_world_state": {{
    "time_of_day": "...",
    "weather": "...",
    "discovered_locations": [],
    "unsolved_mysteries": [],
    "friendly_characters_met": [],
    "obstacles_overcome": []
  }}
}}"""

        msg = self.client.messages.create(
            model=self.cfg.claude_model, max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )
        text   = msg.content[0].text.strip().replace("```json","").replace("```","").strip()
        script = json.loads(text)
        script["video_type"] = "short"

        # Advance story state
        self._advance_story(script, "short")

        logger.info(f"[ScriptAgent] Short script: {script['title_raw']}")
        return script

    # ── Long script ───────────────────────────────────────────────────────────

    def _generate_long(self, trend: dict) -> dict:
        is_merge = trend.get("source") == "weekly_merge"
        mode_note = (
            "This is a WEEKLY RECAP video — start with 'Previously on Whimble...' recapping the week's Shorts, "
            "then expand into a new extended adventure."
            if is_merge else
            "This is a STANDALONE ADVENTURE — self-contained, works for new viewers."
        )

        prompt = f"""You are writing a 10-minute episode of "Milo & Luna in Whimble" — a gentle animated cartoon for children aged 4-10.

{CHARACTERS}

{mode_note}

EPISODE PLAN:
Title: {trend['topic']}
Story: {trend['episode_beat']}
Ending: {trend['cliffhanger_or_ending']}

Write a full 10-minute narrated script. Warm storyteller voice.
Short sentences. Sound words. Magical and funny. Never scary.

Return ONLY valid JSON (no markdown):
{{
  "title_raw": "full episode title",
  "topic": "{trend['topic']}",
  "video_type": "long",
  "duration_sec": 600,
  "chapters": [
    {{
      "id": 1,
      "title": "Previously on Whimble / Opening Hook",
      "timestamp_sec": 0,
      "type": "recap_or_hook",
      "text": "full narration for this chapter",
      "duration_sec": 90,
      "broll_queries": ["cartoon adventure recap", "magical forest kids"],
      "key_points": ["recap point 1", "recap point 2"],
      "caption_overlays": ["PREVIOUSLY ON WHIMBLE... ✨"]
    }},
    {{
      "id": 2,
      "title": "The Adventure Begins",
      "timestamp_sec": 90,
      "type": "story",
      "text": "narration...",
      "duration_sec": 120,
      "broll_queries": ["cartoon kids explore forest"],
      "key_points": ["story point"],
      "caption_overlays": ["caption"]
    }},
    {{
      "id": 3,
      "title": "The Big Discovery",
      "timestamp_sec": 210,
      "type": "story",
      "text": "narration...",
      "duration_sec": 120,
      "broll_queries": ["cartoon magical discovery"],
      "key_points": ["discovery"],
      "caption_overlays": ["caption"]
    }},
    {{
      "id": 4,
      "title": "The Challenge",
      "timestamp_sec": 330,
      "type": "story",
      "text": "narration...",
      "duration_sec": 120,
      "broll_queries": ["cartoon kids puzzle adventure"],
      "key_points": ["challenge"],
      "caption_overlays": ["caption"]
    }},
    {{
      "id": 5,
      "title": "Resolution and Surprise",
      "timestamp_sec": 450,
      "type": "resolution",
      "text": "narration...",
      "duration_sec": 90,
      "broll_queries": ["cartoon happy ending"],
      "key_points": ["resolution"],
      "caption_overlays": ["caption"]
    }},
    {{
      "id": 6,
      "title": "Until Next Time...",
      "timestamp_sec": 540,
      "type": "outro",
      "text": "warm goodbye + tease of next week",
      "duration_sec": 60,
      "broll_queries": ["cartoon kids waving sunset"],
      "key_points": ["subscribe", "next week tease"],
      "caption_overlays": ["SEE YOU NEXT WEEK! 🦊✨"]
    }}
  ],
  "background_music_mood": "calm background",
  "color_theme": "warm golden forest tones",
  "thumbnail_text": "4-6 word episode title",
  "thumbnail_emoji": "🌟",
  "keywords": ["milo luna cartoon", "whimble cartoon series", "kids cartoon", "animated story"],
  "episode_summary": "3-4 sentence summary for story continuity",
  "updated_character_state": {{
    "Milo": {{"mood": "...", "location": "...", "last_action": "...", "items": [], "friends_met": [], "goal": "..."}},
    "Luna": {{"mood": "...", "location": "...", "last_action": "...", "items": [], "friends_met": [], "goal": "..."}},
    "Pip":  {{"mood": "...", "location": "...", "last_action": "...", "items": [], "friends_met": [], "goal": "..."}}
  }},
  "updated_world_state": {{
    "time_of_day": "...",
    "weather": "...",
    "discovered_locations": [],
    "unsolved_mysteries": [],
    "friendly_characters_met": [],
    "obstacles_overcome": []
  }},
  "new_arc_name": null
}}

Include all 6 chapters with full narration text."""

        msg = self.client.messages.create(
            model=self.cfg.claude_model, max_tokens=8000,
            messages=[{"role": "user", "content": prompt}],
        )
        text   = msg.content[0].text.strip().replace("```json","").replace("```","").strip()
        script = json.loads(text)
        script["video_type"] = "long"

        self._advance_story(script, "long", new_arc_name=trend.get("new_arc_name"))

        logger.info(f"[ScriptAgent] Long script: {script['title_raw']} ({len(script['chapters'])} chapters)")
        return script

    # ── Story state advancement ───────────────────────────────────────────────

    def _advance_story(self, script: dict, video_type: str, new_arc_name: str = None):
        """Update persistent story state after script generation."""
        try:
            from story_state import StoryManager
            sm = StoryManager()
            summary  = script.get("episode_summary", "")
            chars    = script.get("updated_character_state", {})
            world    = script.get("updated_world_state", {})

            # Merge — only update keys that exist (don't wipe unchanged data)
            current_chars = sm.state["character_state"]
            for name, updates in chars.items():
                if name in current_chars and updates:
                    current_chars[name].update({k: v for k, v in updates.items() if v})

            current_world = sm.state["world_state"]
            for key, val in world.items():
                if val:
                    if isinstance(val, list):
                        existing = current_world.get(key, [])
                        current_world[key] = list(set(existing + val))
                    else:
                        current_world[key] = val

            if video_type == "short":
                sm.advance_short(summary, current_chars, current_world)
            else:
                sm.advance_long(summary, current_chars, current_world, new_arc_name)

        except Exception as e:
            logger.warning(f"[ScriptAgent] Story state update failed (non-fatal): {e}")

    def get_full_narration(self, script: dict) -> str:
        if script["video_type"] == "short":
            return " ".join(seg["text"] for seg in script["segments"])
        else:
            return " ".join(ch["text"] for ch in script["chapters"])
