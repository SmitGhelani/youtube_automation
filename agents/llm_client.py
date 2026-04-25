"""
llm_client.py — Unified free LLM client
========================================
Uses Ollama (local, free, no API key) running on the same EC2.
Model: llama3.2:3b  (fast, fits t3.medium 4GB RAM — ~2GB model)
       gemma2:2b    (even lighter fallback)

Zero API calls. Zero cost. Zero quota limits. Runs forever.

Setup (one-time, already in setup_ec2.sh):
    curl -fsSL https://ollama.com/install.sh | sh
    ollama pull llama3.2:3b
    systemctl enable ollama
"""

import json
import logging
import time
import requests

logger = logging.getLogger("LLMClient")

OLLAMA_URL    = "http://localhost:11434/api/generate"
OLLAMA_HEALTH = "http://localhost:11434/api/tags"

# Model priority: try best first, fall back to lighter models
MODELS = [
    "llama3.2:3b",   # Best quality that fits t3.medium (4GB RAM)
    "gemma2:2b",     # Lighter fallback
    "tinyllama",     # Emergency fallback — very fast, lower quality
]


class LLMClient:
    def __init__(self):
        self._model = None

    def _get_model(self) -> str:
        """Find the best available Ollama model."""
        if self._model:
            return self._model
        try:
            resp = requests.get(OLLAMA_HEALTH, timeout=5)
            available = [m["name"] for m in resp.json().get("models", [])]
            logger.info(f"[LLM] Ollama models available: {available}")
            for preferred in MODELS:
                # Match by prefix (e.g. "llama3.2:3b" matches "llama3.2:3b")
                for avail in available:
                    if preferred.split(":")[0] in avail:
                        self._model = avail
                        logger.info(f"[LLM] Using model: {self._model}")
                        return self._model
            raise RuntimeError(f"No preferred model found. Available: {available}")
        except requests.ConnectionError:
            raise RuntimeError(
                "Ollama not running. Start it with: systemctl start ollama\n"
                "Install: curl -fsSL https://ollama.com/install.sh | sh && ollama pull llama3.2:3b"
            )

    def generate(self, prompt: str, max_tokens: int = 2048, temperature: float = 0.7) -> str:
        """
        Generate text using local Ollama.
        Returns plain text response.
        Retries once on failure.
        """
        model = self._get_model()

        for attempt in range(2):
            try:
                resp = requests.post(
                    OLLAMA_URL,
                    json={
                        "model":  model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature":   temperature,
                            "num_predict":   max_tokens,
                            "num_ctx":       4096,
                            "repeat_penalty": 1.1,
                        },
                    },
                    timeout=300,  # local inference can take up to 5 min for long scripts
                )
                resp.raise_for_status()
                text = resp.json().get("response", "").strip()
                if not text:
                    raise ValueError("Empty response from Ollama")
                logger.info(f"[LLM] Generated {len(text)} chars with {model}")
                return text

            except Exception as e:
                logger.warning(f"[LLM] Attempt {attempt+1} failed: {e}")
                if attempt == 0:
                    time.sleep(3)
                else:
                    raise

    def generate_json(self, prompt: str, max_tokens: int = 2048) -> dict:
        """
        Generate and parse JSON. Retries up to 3 times with error feedback.
        Strips markdown fences automatically.
        """
        json_prompt = prompt + "\n\nIMPORTANT: Return ONLY valid JSON. No explanation, no markdown fences, no ```json blocks. Start your response with { and end with }."

        last_err = None
        for attempt in range(3):
            try:
                text = self.generate(json_prompt, max_tokens=max_tokens, temperature=0.5)
                # Strip any markdown fences
                text = text.replace("```json", "").replace("```", "").strip()
                # Find JSON boundaries
                start = text.find("{")
                end   = text.rfind("}") + 1
                if start == -1 or end == 0:
                    raise ValueError("No JSON object found in response")
                return json.loads(text[start:end])
            except (json.JSONDecodeError, ValueError) as e:
                last_err = e
                logger.warning(f"[LLM] JSON parse attempt {attempt+1} failed: {e}")
                if attempt < 2:
                    # Give the model a hint about what went wrong
                    json_prompt = prompt + f"\n\nPrevious attempt failed with: {e}\nReturn ONLY a valid JSON object starting with {{ and ending with }}. No other text."
        raise ValueError(f"LLM failed to return valid JSON after 3 attempts: {last_err}")
