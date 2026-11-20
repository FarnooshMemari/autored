"""Local LLM client for the adaptive planner. Uses Ollama only (no paid APIs).

The planner is a *reasoning* component: it proposes hypotheses and attack prompts.
It NEVER decides whether a finding is real — only evidence (canaries / audit
oracle / reproduction) does. Its output is constrained to a fixed goal taxonomy
so generated probes map to concrete, checkable evidence.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass

import httpx

OLLAMA = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")


@dataclass
class LLMConfig:
    model: str = os.environ.get("AUTORED_PLANNER_MODEL", "llama3.2:3b")
    temperature: float = 0.4
    timeout_s: float = 120.0


class LLMError(Exception):
    pass


class LLMClient:
    """Minimal async Ollama chat client with a per-mission call budget."""

    def __init__(self, cfg: LLMConfig | None = None, max_calls: int = 20):
        self.cfg = cfg or LLMConfig()
        self.max_calls = max_calls
        self.calls = 0

    @property
    def exhausted(self) -> bool:
        return self.calls >= self.max_calls

    async def chat_json(self, system: str, user: str) -> dict:
        """One planner call. Forces JSON output. Counts against the budget."""
        if self.exhausted:
            raise LLMError("LLM call budget exhausted")
        self.calls += 1
        payload = {
            "model": self.cfg.model, "stream": False, "format": "json",
            "keep_alive": "60m", "options": {"temperature": self.cfg.temperature},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        async with httpx.AsyncClient(timeout=self.cfg.timeout_s) as c:
            r = await c.post(f"{OLLAMA}/api/chat", json=payload)
            r.raise_for_status()
            content = r.json()["message"]["content"]
        return _parse_json(content)


def _parse_json(text: str) -> dict:
    text = text.strip()
    try:
        return json.loads(text)
    except Exception:
        i, j = text.find("{"), text.rfind("}")
        if 0 <= i < j:
            try:
                return json.loads(text[i:j + 1])
            except Exception:
                pass
    raise LLMError(f"planner did not return JSON: {text[:200]}")
