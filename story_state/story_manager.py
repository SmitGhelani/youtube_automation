"""
story_state/story_manager.py

Persistent story state for the Mahabharat series.
Tracks parva, episode, scene beat, and character states
so every Short continues from exactly where the last left off,
and every Saturday long video is a banger full episode.

State is saved as JSON on disk at story_state/state.json
"""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger("StoryManager")
STATE_FILE = Path("story_state/state.json")

# Full Mahabharat parva sequence — each parva is a "season"
MAHABHARAT_PARVAS = [
    "Adi Parva",          # Origins: Pandavas, Kauravas, birth stories
    "Sabha Parva",        # Dice game, Draupadi's humiliation
    "Vana Parva",         # Exile in the forest (longest parva)
    "Virata Parva",       # Year of disguise at King Virata's court
    "Udyoga Parva",       # War preparations, Krishna's diplomacy
    "Bhishma Parva",      # First 10 days of Kurukshetra (Bhishma commands)
    "Drona Parva",        # Days 11-15 (Drona commands, Abhimanyu's death)
    "Karna Parva",        # Days 16-17 (Karna commands)
    "Shalya Parva",       # Day 18, Duryodhana's fall
    "Sauptika Parva",     # Night massacre by Ashwatthama
    "Stri Parva",         # Grief of the women
    "Shanti Parva",       # Bhishma's wisdom on the arrow bed
    "Anushasana Parva",   # Final teachings of Bhishma
    "Ashvamedhika Parva", # Horse sacrifice and Arjuna's journey
    "Mausala Parva",      # Fall of the Yadavas
    "Mahaprasthanika Parva", # Final journey
    "Svargarohana Parva", # Arrival in heaven
]

DEFAULT_STATE = {
    # Series position
    "short_episode":      1,
    "long_episode":       1,
    "parva_index":        0,         # index into MAHABHARAT_PARVAS
    "parva_scene":        1,         # scene number within current parva
    "parva_total_scenes": 6,         # scenes planned for this parva (shorts)

    # Story continuity
    "last_short_summary":  "",
    "last_long_summary":   "",
    "shorts_since_long":   0,
    "weekly_short_summaries": [],

    # Character states (key characters, updated each episode)
    "character_state": {
        "Yudhishthira": {"location": "Hastinapura", "mood": "righteous", "last_action": "born as eldest Pandava"},
        "Arjuna":       {"location": "Hastinapura", "mood": "determined", "last_action": "learning archery from Drona"},
        "Bhima":        {"location": "Hastinapura", "mood": "fierce", "last_action": "showing his strength"},
        "Duryodhana":   {"location": "Hastinapura", "mood": "jealous", "last_action": "plotting against Pandavas"},
        "Krishna":      {"location": "Mathura", "mood": "calm and knowing", "last_action": "watching from afar"},
        "Draupadi":     {"location": "Panchala", "mood": "spirited", "last_action": "yet to be born"},
        "Karna":        {"location": "Unknown", "mood": "proud", "last_action": "abandoned at birth"},
        "Bhishma":      {"location": "Hastinapura", "mood": "dutiful", "last_action": "sworn to protect the throne"},
    },

    "world_state": {
        "era":              "Dvapara Yuga",
        "current_kingdom":  "Hastinapura",
        "key_events_done":  [],
        "tension_level":    "building",
        "upcoming_event":   "Drona's arrival and training of princes",
    },

    # Meta
    "created_at":   datetime.now().isoformat(),
    "last_updated": datetime.now().isoformat(),
    "total_shorts_produced": 0,
    "total_longs_produced":  0,
}


class StoryManager:
    def __init__(self):
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        self.state = self._load()
        self.parvas = MAHABHARAT_PARVAS

    def _load(self) -> dict:
        if STATE_FILE.exists():
            try:
                s = json.loads(STATE_FILE.read_text())
                logger.info(
                    f"[StoryManager] Loaded: Short EP{s['short_episode']} | "
                    f"Parva: {MAHABHARAT_PARVAS[min(s['parva_index'], len(MAHABHARAT_PARVAS)-1)]} "
                    f"Scene {s['parva_scene']}"
                )
                return s
            except Exception as e:
                logger.warning(f"[StoryManager] Corrupt state ({e}), starting fresh")
        logger.info("[StoryManager] Fresh start — Mahabharat begins from Adi Parva")
        return dict(DEFAULT_STATE)

    def save(self):
        self.state["last_updated"] = datetime.now().isoformat()
        STATE_FILE.write_text(json.dumps(self.state, indent=2))

    def current_parva(self) -> str:
        idx = min(self.state["parva_index"], len(self.parvas) - 1)
        return self.parvas[idx]

    def get_context_for_short(self) -> dict:
        s = self.state
        return {
            "short_episode":      s["short_episode"],
            "parva":              self.current_parva(),
            "parva_index":        s["parva_index"],
            "parva_scene":        s["parva_scene"],
            "parva_total_scenes": s["parva_total_scenes"],
            "is_parva_finale":    s["parva_scene"] >= s["parva_total_scenes"],
            "last_summary":       s["last_short_summary"] or "This is the very first episode.",
            "character_state":    s["character_state"],
            "world_state":        s["world_state"],
            "shorts_since_long":  s["shorts_since_long"],
        }

    def get_context_for_long(self) -> dict:
        s = self.state
        return {
            "long_episode":           s["long_episode"],
            "parva":                  self.current_parva(),
            "parva_index":            s["parva_index"],
            "weekly_short_summaries": s["weekly_short_summaries"],
            "character_state":        s["character_state"],
            "world_state":            s["world_state"],
            "last_long_summary":      s["last_long_summary"],
        }

    def advance_short(self, summary: str, char_state: dict, world_state: dict):
        s = self.state
        s["last_short_summary"] = summary
        s["character_state"]    = char_state
        s["world_state"]        = world_state
        s["weekly_short_summaries"].append(f"Short EP{s['short_episode']}: {summary}")
        s["shorts_since_long"]      += 1
        s["short_episode"]          += 1
        s["parva_scene"]            += 1
        s["total_shorts_produced"]  += 1
        # Advance parva if all scenes done
        if s["parva_scene"] > s["parva_total_scenes"]:
            s["parva_index"]  = min(s["parva_index"] + 1, len(self.parvas) - 1)
            s["parva_scene"]  = 1
            logger.info(f"[StoryManager] Parva advanced to: {self.current_parva()}")
        self.save()

    def advance_long(self, summary: str, char_state: dict, world_state: dict):
        s = self.state
        s["last_long_summary"]      = summary
        s["character_state"]        = char_state
        s["world_state"]            = world_state
        s["weekly_short_summaries"] = []
        s["shorts_since_long"]      = 0
        s["long_episode"]          += 1
        s["total_longs_produced"]  += 1
        self.save()
