"""
story_state/story_manager.py

Persistent story state for the animated cartoon series.
Tracks episode number, story arc, what happened last, and character state
so every new Short continues exactly where the last one left off.

State is saved as JSON on disk at story_state/state.json
"""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("StoryManager")

STATE_FILE = Path("story_state/state.json")

# ── Default initial state ─────────────────────────────────────────────────────
DEFAULT_STATE = {
    # Series tracking
    "short_episode":     1,       # increments every daily Short
    "long_episode":      1,       # increments every weekly Long
    "series_week":       1,       # which week of the season we're in (1-12)
    "season":            1,       # season number

    # Story arc tracking
    "current_arc":       "The Lost Map",   # name of current story arc
    "arc_episode":       1,                # episode within current arc
    "arc_total":         7,                # planned arc length before arc changes

    # What happened last (filled after each run)
    "last_short_summary":   "",    # 2-3 sentence summary of last Short
    "last_long_summary":    "",    # 2-3 sentence summary of last Long video
    "shorts_since_long":    0,     # how many Shorts since last Long (reset each Saturday)

    # Character state — updated by Claude after each episode
    "character_state": {
        "Milo": {
            "mood":         "curious",
            "location":     "the edge of Whimble Forest",
            "last_action":  "just arrived at the forest entrance",
            "items":        ["old map", "lantern", "small backpack"],
            "friends_met":  [],
            "goal":         "find the Crystal Cave hidden deep in Whimble Forest",
        },
        "Luna": {
            "mood":         "excited",
            "location":     "the edge of Whimble Forest",
            "last_action":  "convinced Milo to enter the forest",
            "items":        ["magic compass", "sketchbook"],
            "friends_met":  [],
            "goal":         "document every magical creature in the forest",
        },
        "Pip": {
            "mood":         "nervous",
            "location":     "hiding in Milo's backpack",
            "last_action":  "stowed away without telling anyone",
            "items":        ["acorn collection"],
            "friends_met":  [],
            "goal":         "find his missing family somewhere in the forest",
        },
    },

    # World state
    "world_state": {
        "time_of_day":    "early morning",
        "weather":        "misty and magical",
        "discovered_locations": ["forest entrance"],
        "unsolved_mysteries":   ["why the map glows at night", "the strange sound from the east"],
        "friendly_characters_met": [],
        "obstacles_overcome":  [],
    },

    # Long video weekly merge tracking
    "weekly_short_summaries": [],   # accumulates Short summaries Mon-Fri

    # Meta
    "created_at":    datetime.now().isoformat(),
    "last_updated":  datetime.now().isoformat(),
    "total_shorts_produced": 0,
    "total_longs_produced":  0,
}


class StoryManager:
    def __init__(self):
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load()

    def _load(self) -> dict:
        if STATE_FILE.exists():
            try:
                state = json.loads(STATE_FILE.read_text())
                logger.info(
                    f"[StoryManager] Loaded state: Short EP{state['short_episode']} | "
                    f"Arc: {state['current_arc']} EP{state['arc_episode']}"
                )
                return state
            except Exception as e:
                logger.warning(f"[StoryManager] State file corrupt ({e}), using default")
        logger.info("[StoryManager] No state file found — starting fresh (Episode 1)")
        return dict(DEFAULT_STATE)

    def save(self):
        self.state["last_updated"] = datetime.now().isoformat()
        STATE_FILE.write_text(json.dumps(self.state, indent=2))
        logger.info(f"[StoryManager] State saved: Short EP{self.state['short_episode']}")

    def get_context_for_short(self) -> dict:
        """Return everything the ScriptAgent needs to write the next Short."""
        s = self.state
        return {
            "episode_number":       s["short_episode"],
            "season":               s["season"],
            "current_arc":          s["current_arc"],
            "arc_episode":          s["arc_episode"],
            "arc_total":            s["arc_total"],
            "last_episode_summary": s["last_short_summary"],
            "character_state":      s["character_state"],
            "world_state":          s["world_state"],
            "is_arc_finale":        s["arc_episode"] >= s["arc_total"],
            "shorts_since_long":    s["shorts_since_long"],
        }

    def get_context_for_long(self) -> dict:
        """Return everything the ScriptAgent needs to write the Long video."""
        s = self.state
        return {
            "long_episode_number":    s["long_episode"],
            "season":                 s["season"],
            "series_week":            s["series_week"],
            "weekly_short_summaries": s["weekly_short_summaries"],
            "character_state":        s["character_state"],
            "world_state":            s["world_state"],
            "last_long_summary":      s["last_long_summary"],
            "current_arc":            s["current_arc"],
        }

    def advance_short(self, episode_summary: str, updated_character_state: dict,
                      updated_world_state: dict):
        """Call after a Short is successfully produced."""
        s = self.state
        s["last_short_summary"]  = episode_summary
        s["character_state"]     = updated_character_state
        s["world_state"]         = updated_world_state
        s["weekly_short_summaries"].append(
            f"EP{s['short_episode']}: {episode_summary}"
        )
        s["shorts_since_long"]         += 1
        s["short_episode"]             += 1
        s["arc_episode"]               += 1
        s["total_shorts_produced"]     += 1

        # Advance arc if complete
        if s["arc_episode"] > s["arc_total"]:
            s["arc_episode"] = 1
            s["season"]      += 1 if s["season"] % 3 == 0 else 0
            logger.info(f"[StoryManager] Arc '{s['current_arc']}' complete — new arc starts")
        self.save()

    def advance_long(self, episode_summary: str, updated_character_state: dict,
                     updated_world_state: dict, new_arc_name: str = None):
        """Call after a Long video is successfully produced."""
        s = self.state
        s["last_long_summary"]       = episode_summary
        s["character_state"]         = updated_character_state
        s["world_state"]             = updated_world_state
        s["weekly_short_summaries"]  = []   # reset for next week
        s["shorts_since_long"]       = 0
        s["long_episode"]           += 1
        s["series_week"]            += 1
        s["total_longs_produced"]   += 1
        if new_arc_name:
            s["current_arc"]  = new_arc_name
            s["arc_episode"]  = 1
        self.save()
