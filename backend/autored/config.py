from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Settings:
    scope_path: Path = ROOT / "scope" / "local-target.yaml"
    runs_dir: Path = ROOT / "runs"
    headless: bool = True
    max_active_missions: int = 1
    api_token: str | None = None          # if set, required as Bearer / ?token=
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")

    @classmethod
    def from_env(cls) -> "Settings":
        s = cls()
        if v := os.environ.get("AUTORED_SCOPE"):
            s.scope_path = Path(v)
        if v := os.environ.get("AUTORED_RUNS_DIR"):
            s.runs_dir = Path(v)
        s.headless = os.environ.get("AUTORED_HEADLESS", "1") != "0"
        s.max_active_missions = int(os.environ.get("AUTORED_MAX_ACTIVE_MISSIONS", s.max_active_missions))
        s.api_token = os.environ.get("AUTORED_API_TOKEN") or None
        return s
