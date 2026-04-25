"""
agents/script_agent.py — Generates Mahabharat scripts using local Ollama (FREE).
No API keys. No quotas. No cost. Runs on EC2 locally.
"""
import json
import logging
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from llm_client import LLMClient

logger = logging.getLogger("ScriptAgent")

STYLE_GUIDE = """Narration style: deep and reverent like a court poet reciting before a king.
Mix long epic lines with short dramatic punches.
Use Sanskrit words naturally: dharma, karma, kshatriya, yuddha, moksha.
Sound words: TWANG of bowstrings, CLASH of maces, THUNDER of chariots.
Never use modern slang. Always timeless and epic."""


class ScriptAgent:
    def __init__(self, config):
        self.cfg = config
        self.llm = LLMClient()

    def generate(self, trend: dict, video_type: str) -> dict:
        if video_type == "short":
            return self._generate_short(trend)
        else:
            return self._generate_long(trend)

    def _generate_short(self, trend: dict) -> dict:
        prompt = (
            f"You are writing a 60-second TEASER SHORT for the Mahabharat YouTube series.\n"
            f"{STYLE_GUIDE}\n\n"
            f"EPISODE PLAN:\n"
            f"Title: {trend['topic']}\n"
            f"Dramatic moment: {trend['angle']}\n"
            f"Opening hook: {trend['hook']}\n"
            f"What it shows: {trend['episode_beat']}\n"
            f"How it ends: {trend['cliffhanger_or_ending']}\n\n"
            f"Write a complete script. Return a JSON object with these exact keys:\n"
            '{\n'
            '  "title_raw": "teaser title here",\n'
            f'  "topic": "{trend["topic"]}",\n'
            '  "video_type": "short",\n'
            '  "duration_sec": 58,\n'
            '  "segments": [\n'
            '    {"id":1,"type":"hook","text":"Write dramatic opening narration for 7 seconds","duration_sec":7,"broll_query":"epic ancient india cinematic palace","caption":"DRAMATIC TEXT OVERLAY","emotion":"awe"},\n'
            '    {"id":2,"type":"scene","text":"Write scene narration for 12 seconds","duration_sec":12,"broll_query":"mahabharat warrior king ancient india","caption":"Caption here","emotion":"tension"},\n'
            '    {"id":3,"type":"scene","text":"Write rising tension narration for 12 seconds","duration_sec":12,"broll_query":"ancient india battlefield kurukshetra","caption":"Caption here","emotion":"dread"},\n'
            '    {"id":4,"type":"scene","text":"Write peak dramatic moment for 10 seconds","duration_sec":10,"broll_query":"mahabharat dramatic confrontation epic","caption":"Key dialogue line","emotion":"climax"},\n'
            '    {"id":5,"type":"cliffhanger","text":"Write hard cut cliffhanger for 7 seconds","duration_sec":7,"broll_query":"ancient india dramatic silhouette sunset","caption":"FULL EPISODE THIS SATURDAY","emotion":"shock"},\n'
            '    {"id":6,"type":"cta","text":"Subscribe for the full Mahabharat every Saturday.","duration_sec":5,"broll_query":"mahabharat title card epic","caption":"SUBSCRIBE EVERY SATURDAY","emotion":"epic"}\n'
            '  ],\n'
            '  "background_music_mood": "cinematic inspiring",\n'
            '  "color_theme": "deep ochre and crimson with gold",\n'
            '  "thumbnail_text": "3-4 word dramatic title",\n'
            '  "thumbnail_emoji": "sword",\n'
            '  "keywords": ["mahabharat","mahabharat shorts","epic india"],\n'
            '  "episode_summary": "Write 2-3 sentence summary for continuity tracking",\n'
            '  "updated_character_state": {"Yudhishthira":{"location":"...","mood":"...","last_action":"..."},"Arjuna":{"location":"...","mood":"...","last_action":"..."},"Bhima":{"location":"...","mood":"...","last_action":"..."},"Duryodhana":{"location":"...","mood":"...","last_action":"..."},"Krishna":{"location":"...","mood":"...","last_action":"..."},"Draupadi":{"location":"...","mood":"...","last_action":"..."},"Karna":{"location":"...","mood":"...","last_action":"..."},"Bhishma":{"location":"...","mood":"...","last_action":"..."}},\n'
            '  "updated_world_state": {"era":"Dvapara Yuga","current_kingdom":"...","key_events_done":[],"tension_level":"...","upcoming_event":"..."}\n'
            '}'
        )

        script = self.llm.generate_json(prompt, max_tokens=2048)
        script["video_type"] = "short"
        # Ensure thumbnail_emoji is a real emoji
        if script.get("thumbnail_emoji") in ("sword", "swords", ""):
            script["thumbnail_emoji"] = "\u2694\ufe0f"
        self._advance_story(script, "short")
        logger.info(f"[ScriptAgent] Short: {script.get('title_raw','')}")
        return script

    def _generate_long(self, trend: dict) -> dict:
        # For long videos, split into two calls to stay within Ollama context limit
        # Call 1: Plan + first 4 chapters
        # Call 2: Last 4 chapters
        prompt_part1 = (
            f"You are writing a FULL 15-MINUTE SATURDAY EPISODE of the Mahabharat YouTube series.\n"
            f"{STYLE_GUIDE}\n\n"
            f"EPISODE PLAN:\n"
            f"Title: {trend['topic']}\n"
            f"Story arc: {trend['angle']}\n"
            f"Opening hook: {trend['hook']}\n"
            f"Full story: {trend['episode_beat']}\n"
            f"Ending: {trend['cliffhanger_or_ending']}\n\n"
            f"Write chapters 1-4 with complete narration. Return a JSON object:\n"
            '{\n'
            '  "title_raw": "full episode title",\n'
            f'  "topic": "{trend["topic"]}",\n'
            '  "chapters_1_to_4": [\n'
            '    {"id":1,"title":"Previously This Week","timestamp_sec":0,"type":"recap","text":"Write FULL 90-second recap narration here","duration_sec":90,"broll_queries":["mahabharat dramatic epic ancient india"],"key_points":["recap"],"caption_overlays":["PREVIOUSLY THIS WEEK..."]},\n'
            '    {"id":2,"title":"The Scene Opens","timestamp_sec":90,"type":"scene","text":"Write FULL 120-second opening scene narration here","duration_sec":120,"broll_queries":["ancient india epic cinematic palace"],"key_points":["opening"],"caption_overlays":[""]},\n'
            '    {"id":3,"title":"Rising Tension","timestamp_sec":210,"type":"scene","text":"Write FULL 120-second rising tension narration here","duration_sec":120,"broll_queries":["mahabharat dramatic confrontation"],"key_points":["tension"],"caption_overlays":[""]},\n'
            '    {"id":4,"title":"The Turning Point","timestamp_sec":330,"type":"scene","text":"Write FULL 120-second turning point narration here","duration_sec":120,"broll_queries":["ancient india warrior epic"],"key_points":["turning point"],"caption_overlays":[""]}\n'
            '  ]\n'
            '}'
        )

        prompt_part2 = (
            f"Continue the Mahabharat episode '{trend['topic']}'. Write chapters 5-8.\n"
            f"Story arc: {trend['angle']}\n"
            f"Episode ending: {trend['cliffhanger_or_ending']}\n\n"
            f"Return a JSON object:\n"
            '{\n'
            '  "chapters_5_to_8": [\n'
            '    {"id":5,"title":"The Climax","timestamp_sec":450,"type":"climax","text":"Write FULL 120-second climax narration here","duration_sec":120,"broll_queries":["mahabharat battle epic dramatic"],"key_points":["climax"],"caption_overlays":[""]},\n'
            '    {"id":6,"title":"Aftermath","timestamp_sec":570,"type":"resolution","text":"Write FULL 120-second aftermath narration here","duration_sec":120,"broll_queries":["ancient india dramatic aftermath"],"key_points":["resolution"],"caption_overlays":[""]},\n'
            '    {"id":7,"title":"The Vow","timestamp_sec":690,"type":"revelation","text":"Write FULL 90-second revelation narration here","duration_sec":90,"broll_queries":["dramatic vow ancient india"],"key_points":["vow"],"caption_overlays":[""]},\n'
            '    {"id":8,"title":"Next Week on Mahabharat","timestamp_sec":780,"type":"outro","text":"Write FULL 120-second outro and next week tease here","duration_sec":120,"broll_queries":["mahabharat epic title dramatic"],"key_points":["subscribe","next week"],"caption_overlays":["NEXT SATURDAY"]}\n'
            '  ],\n'
            '  "episode_summary": "Write 3-4 sentence summary for story continuity",\n'
            '  "updated_character_state": {"Yudhishthira":{"location":"...","mood":"...","last_action":"..."},"Arjuna":{"location":"...","mood":"...","last_action":"..."},"Bhima":{"location":"...","mood":"...","last_action":"..."},"Duryodhana":{"location":"...","mood":"...","last_action":"..."},"Krishna":{"location":"...","mood":"...","last_action":"..."},"Draupadi":{"location":"...","mood":"...","last_action":"..."},"Karna":{"location":"...","mood":"...","last_action":"..."},"Bhishma":{"location":"...","mood":"...","last_action":"..."}},\n'
            '  "updated_world_state": {"era":"Dvapara Yuga","current_kingdom":"...","key_events_done":[],"tension_level":"...","upcoming_event":"..."}\n'
            '}'
        )

        logger.info("[ScriptAgent] Generating long episode part 1/2...")
        part1 = self.llm.generate_json(prompt_part1, max_tokens=3000)

        logger.info("[ScriptAgent] Generating long episode part 2/2...")
        part2 = self.llm.generate_json(prompt_part2, max_tokens=3000)

        # Merge into full script
        script = {
            "title_raw":    part1.get("title_raw", trend["topic"]),
            "topic":        trend["topic"],
            "video_type":   "long",
            "duration_sec": 900,
            "chapters":     part1.get("chapters_1_to_4", []) + part2.get("chapters_5_to_8", []),
            "background_music_mood": "cinematic inspiring",
            "color_theme":  "deep crimson, gold and ochre of ancient India",
            "thumbnail_text": part1.get("title_raw", trend["topic"])[:40],
            "thumbnail_emoji": "\u2694\ufe0f",
            "keywords":     ["mahabharat full episode", "mahabharat saturday", "epic mahabharat"],
            "episode_summary":          part2.get("episode_summary", ""),
            "updated_character_state":  part2.get("updated_character_state", {}),
            "updated_world_state":      part2.get("updated_world_state", {}),
        }

        self._advance_story(script, "long")
        logger.info(f"[ScriptAgent] Long EP: {script['title_raw']} ({len(script['chapters'])} chapters)")
        return script

    def _advance_story(self, script: dict, video_type: str):
        try:
            from story_state import StoryManager
            sm        = StoryManager()
            chars     = script.get("updated_character_state", {})
            world     = script.get("updated_world_state", {})
            cur_chars = sm.state["character_state"]
            for name, updates in chars.items():
                if name in cur_chars and updates:
                    cur_chars[name].update({k: v for k, v in updates.items() if v and v != "..."})
            cur_world = sm.state["world_state"]
            for key, val in world.items():
                if val and val != "...":
                    if isinstance(val, list):
                        cur_world[key] = list(set(cur_world.get(key, []) + val))
                    else:
                        cur_world[key] = val
            if video_type == "short":
                sm.advance_short(script.get("episode_summary", ""), cur_chars, cur_world)
            else:
                sm.advance_long(script.get("episode_summary", ""), cur_chars, cur_world)
        except Exception as e:
            logger.warning(f"[ScriptAgent] Story state update non-fatal: {e}")

    def get_full_narration(self, script: dict) -> str:
        if script["video_type"] == "short":
            return " ".join(seg["text"] for seg in script["segments"])
        else:
            return " ".join(ch["text"] for ch in script["chapters"])
