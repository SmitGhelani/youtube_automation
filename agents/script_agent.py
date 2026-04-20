"""
agents/script_agent.py

Uses google-genai (NEW SDK — NOT deprecated google.generativeai).
Free tier: 1500 requests/day on gemini-2.0-flash.
Install: pip install google-genai
"""
import json
import logging
from google import genai
from google.genai import types

logger = logging.getLogger("ScriptAgent")

STYLE_GUIDE = """
NARRATION STYLE:
- Voice: deep, reverent, like a court poet reciting before a king
- Mix long epic lines with short dramatic punches
- Use Sanskrit words naturally: dharma, karma, kshatriya, yuddha
- Sound words: TWANG of bowstrings, CLASH of maces, THUNDER of chariots
- Never modern slang. Always timeless.
VISUAL STYLE: Cinematic ancient India — ochre palaces, vast battlefields, golden dusk.
"""


class ScriptAgent:
    def __init__(self, config):
        self.cfg = config
        self.client = genai.Client(api_key=config.gemini_api_key)

    def _call(self, prompt: str, max_tokens: int = 2048) -> str:
        resp = self.client.models.generate_content(
            model=self.cfg.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=0.85,
            ),
        )
        return resp.text.strip()

    def generate(self, trend: dict, video_type: str) -> dict:
        if video_type == "short":
            return self._generate_short(trend)
        else:
            return self._generate_long(trend)

    def _generate_short(self, trend: dict) -> dict:
        prompt = f"""You are writing a 60-second TEASER SHORT for the Mahabharat YouTube series.

{STYLE_GUIDE}

EPISODE PLAN:
Title: {trend['topic']}
Dramatic moment: {trend['angle']}
Opening hook: {trend['hook']}
What it shows: {trend['episode_beat']}
How it ends: {trend['cliffhanger_or_ending']}

Return ONLY valid JSON, no markdown fences:
{{
  "title_raw": "Teaser title",
  "topic": "{trend['topic']}",
  "video_type": "short",
  "duration_sec": 58,
  "segments": [
    {{"id":1,"type":"hook","text":"opening dramatic narration 7 seconds worth","duration_sec":7,"broll_query":"epic ancient india cinematic dramatic palace","caption":"dramatic on-screen text","emotion":"awe"}},
    {{"id":2,"type":"scene","text":"scene narration 12 seconds worth","duration_sec":12,"broll_query":"mahabharat warrior king ancient india epic","caption":"caption overlay","emotion":"tension"}},
    {{"id":3,"type":"scene","text":"rising tension narration 12 seconds worth","duration_sec":12,"broll_query":"ancient india battlefield kurukshetra dramatic","caption":"caption overlay","emotion":"dread"}},
    {{"id":4,"type":"scene","text":"peak dramatic moment 10 seconds worth","duration_sec":10,"broll_query":"mahabharat dramatic confrontation epic","caption":"key dialogue line","emotion":"climax"}},
    {{"id":5,"type":"cliffhanger","text":"hard cut cliffhanger 7 seconds worth","duration_sec":7,"broll_query":"ancient india dramatic silhouette sunset epic","caption":"FULL EPISODE THIS SATURDAY \u2694\ufe0f","emotion":"shock"}},
    {{"id":6,"type":"cta","text":"Subscribe for the full Mahabharat every Saturday.","duration_sec":5,"broll_query":"mahabharat title card epic","caption":"SUBSCRIBE \u2694\ufe0f EVERY SATURDAY","emotion":"epic"}}
  ],
  "background_music_mood": "cinematic inspiring",
  "color_theme": "deep ochre and crimson with gold",
  "thumbnail_text": "3-4 word dramatic title",
  "thumbnail_emoji": "\u2694\ufe0f",
  "keywords": ["mahabharat","mahabharat shorts","epic india","mahabharat series"],
  "episode_summary": "2-3 sentence summary for continuity tracking",
  "updated_character_state": {{
    "Yudhishthira":{{"location":"...","mood":"...","last_action":"..."}},
    "Arjuna":{{"location":"...","mood":"...","last_action":"..."}},
    "Bhima":{{"location":"...","mood":"...","last_action":"..."}},
    "Duryodhana":{{"location":"...","mood":"...","last_action":"..."}},
    "Krishna":{{"location":"...","mood":"...","last_action":"..."}},
    "Draupadi":{{"location":"...","mood":"...","last_action":"..."}},
    "Karna":{{"location":"...","mood":"...","last_action":"..."}},
    "Bhishma":{{"location":"...","mood":"...","last_action":"..."}}
  }},
  "updated_world_state": {{
    "era":"...","current_kingdom":"...","key_events_done":[],"tension_level":"...","upcoming_event":"..."
  }}
}}"""
        text = self._call(prompt, 2048).replace("```json","").replace("```","").strip()
        script = json.loads(text)
        script["video_type"] = "short"
        self._advance_story(script, "short")
        logger.info(f"[ScriptAgent] Short teaser: {script['title_raw']}")
        return script

    def _generate_long(self, trend: dict) -> dict:
        prompt = f"""You are writing a FULL 15-MINUTE SATURDAY EPISODE of the Mahabharat YouTube series.

{STYLE_GUIDE}

EPISODE PLAN:
Title: {trend['topic']}
Story arc: {trend['angle']}
Opening hook: {trend['hook']}
Full story: {trend['episode_beat']}
Ending: {trend['cliffhanger_or_ending']}

Write ALL 8 chapters with complete, full narration text (not placeholders).
Return ONLY valid JSON, no markdown fences:
{{
  "title_raw": "full episode title",
  "topic": "{trend['topic']}",
  "video_type": "long",
  "duration_sec": 900,
  "chapters": [
    {{"id":1,"title":"Previously — The Teasers Revealed","timestamp_sec":0,"type":"recap","text":"WRITE FULL 90-SECOND RECAP NARRATION HERE","duration_sec":90,"broll_queries":["mahabharat dramatic epic ancient india"],"key_points":["recap"],"caption_overlays":["PREVIOUSLY THIS WEEK..."]}},
    {{"id":2,"title":"The Scene Opens","timestamp_sec":90,"type":"scene","text":"WRITE FULL 120-SECOND OPENING NARRATION HERE","duration_sec":120,"broll_queries":["ancient india epic cinematic"],"key_points":["opening"],"caption_overlays":[""]}},
    {{"id":3,"title":"Rising Tension","timestamp_sec":210,"type":"scene","text":"WRITE FULL 120-SECOND NARRATION HERE","duration_sec":120,"broll_queries":["mahabharat dramatic confrontation"],"key_points":["tension"],"caption_overlays":[""]}},
    {{"id":4,"title":"The Turning Point","timestamp_sec":330,"type":"scene","text":"WRITE FULL 120-SECOND NARRATION HERE","duration_sec":120,"broll_queries":["ancient india warrior epic"],"key_points":["turning point"],"caption_overlays":[""]}},
    {{"id":5,"title":"The Climax","timestamp_sec":450,"type":"climax","text":"WRITE FULL 120-SECOND NARRATION HERE","duration_sec":120,"broll_queries":["mahabharat battle epic dramatic"],"key_points":["climax"],"caption_overlays":[""]}},
    {{"id":6,"title":"Aftermath","timestamp_sec":570,"type":"resolution","text":"WRITE FULL 120-SECOND NARRATION HERE","duration_sec":120,"broll_queries":["ancient india dramatic aftermath"],"key_points":["resolution"],"caption_overlays":[""]}},
    {{"id":7,"title":"The Vow","timestamp_sec":690,"type":"revelation","text":"WRITE FULL 90-SECOND NARRATION HERE","duration_sec":90,"broll_queries":["dramatic vow ancient india"],"key_points":["vow"],"caption_overlays":[""]}},
    {{"id":8,"title":"Next Week on Mahabharat","timestamp_sec":780,"type":"outro","text":"WRITE FULL 120-SECOND OUTRO AND NEXT WEEK TEASE HERE","duration_sec":120,"broll_queries":["mahabharat epic title dramatic"],"key_points":["subscribe","next week"],"caption_overlays":["NEXT SATURDAY \u2694\ufe0f"]}}
  ],
  "background_music_mood": "cinematic inspiring",
  "color_theme": "deep crimson, gold and ochre of ancient India",
  "thumbnail_text": "4-6 word episode title",
  "thumbnail_emoji": "\u2694\ufe0f",
  "keywords": ["mahabharat full episode","mahabharat saturday","epic mahabharat","mahabharat series"],
  "episode_summary": "3-4 sentence summary for story continuity",
  "updated_character_state": {{
    "Yudhishthira":{{"location":"...","mood":"...","last_action":"..."}},
    "Arjuna":{{"location":"...","mood":"...","last_action":"..."}},
    "Bhima":{{"location":"...","mood":"...","last_action":"..."}},
    "Duryodhana":{{"location":"...","mood":"...","last_action":"..."}},
    "Krishna":{{"location":"...","mood":"...","last_action":"..."}},
    "Draupadi":{{"location":"...","mood":"...","last_action":"..."}},
    "Karna":{{"location":"...","mood":"...","last_action":"..."}},
    "Bhishma":{{"location":"...","mood":"...","last_action":"..."}}
  }},
  "updated_world_state": {{
    "era":"...","current_kingdom":"...","key_events_done":[],"tension_level":"...","upcoming_event":"..."
  }}
}}"""
        text = self._call(prompt, 8192).replace("```json","").replace("```","").strip()
        script = json.loads(text)
        script["video_type"] = "long"
        self._advance_story(script, "long")
        logger.info(f"[ScriptAgent] Long EP: {script['title_raw']}")
        return script

    def _advance_story(self, script: dict, video_type: str):
        try:
            from story_state import StoryManager
            sm = StoryManager()
            chars     = script.get("updated_character_state", {})
            world     = script.get("updated_world_state", {})
            cur_chars = sm.state["character_state"]
            for name, updates in chars.items():
                if name in cur_chars and updates:
                    cur_chars[name].update({k: v for k, v in updates.items() if v})
            cur_world = sm.state["world_state"]
            for key, val in world.items():
                if val:
                    if isinstance(val, list):
                        cur_world[key] = list(set(cur_world.get(key, []) + val))
                    else:
                        cur_world[key] = val
            if video_type == "short":
                sm.advance_short(script.get("episode_summary", ""), cur_chars, cur_world)
            else:
                sm.advance_long(script.get("episode_summary", ""), cur_chars, cur_world)
        except Exception as e:
            logger.warning(f"[ScriptAgent] Story state update failed (non-fatal): {e}")

    def get_full_narration(self, script: dict) -> str:
        if script["video_type"] == "short":
            return " ".join(seg["text"] for seg in script["segments"])
        else:
            return " ".join(ch["text"] for ch in script["chapters"])
