"""
agents/compliance_agent.py — Checks content against YouTube policies
"""
import logging

logger = logging.getLogger("ComplianceAgent")


class ComplianceAgent:
    def __init__(self, config):
        self.cfg = config

    def check(self, script: dict, metadata: dict) -> tuple:
        issues = []
        all_text = self._extract_all_text(script, metadata)

        for term in self.cfg.banned_topics:
            if term.lower() in all_text.lower():
                issues.append(f"Potential policy issue: '{term}' detected")

        if len(metadata.get("title", "")) > 100:
            issues.append("Title exceeds 100 characters")

        dangerous = ["kill", "die", "hate", "terrorist", "bomb", "weapon"]
        for word in dangerous:
            if word in all_text.lower():
                issues.append(f"Flagged word: '{word}' — review context")

        severe = [i for i in issues if "policy" in i.lower()]
        if severe:
            return False, issues
        return True, issues

    def _extract_all_text(self, script: dict, metadata: dict) -> str:
        texts = [metadata.get("title",""), metadata.get("description","")]
        segments = script.get("segments") or script.get("chapters", [])
        for seg in segments:
            texts.append(seg.get("text",""))
        return " ".join(texts)
