from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class Settings:
    scope_path: Path = ROOT / "scope" / "local-target.yaml"
    runs_dir: Path = ROOT / "runs"
    db_path: Path = ROOT / "runs" / "autored.db"
    headless: bool = True
    max_active_missions: int = 1
    api_token: str | None = None          # if set, required as Bearer / ?token=
    cors_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")
    # --- dynamic target onboarding ("enter a URL") ---
    enable_onboarding: bool = True        # expose /api/onboarding/* (off => feature hidden)
    allow_private_targets: bool = False   # DEV ONLY: permit loopback/RFC-1918 targets (SSRF guard relaxed)
    admin_token: str | None = None        # grants admin-approved authorization for onboarded targets
    onboarding_store: Path = ROOT / "runs" / "onboarded-targets.json"
    # --- public/hosted-demo safety lock ---
    public_mode: bool = False             # hosted-facing: hardens defaults and restricts onboarding
    demo_target_origins: tuple[str, ...] = ()  # if set, onboarding ONLY accepts these origins
                                               # (a bundled sandbox) — never arbitrary third-party URLs

    @classmethod
    def from_env(cls) -> "Settings":
        s = cls()
        if v := os.environ.get("AUTORED_SCOPE"):
            s.scope_path = Path(v)
        if v := os.environ.get("AUTORED_RUNS_DIR"):
            s.runs_dir = Path(v)
            s.db_path = s.runs_dir / "autored.db"
        if v := os.environ.get("AUTORED_DB"):
            s.db_path = Path(v)
        s.headless = os.environ.get("AUTORED_HEADLESS", "1") != "0"
        s.max_active_missions = int(os.environ.get("AUTORED_MAX_ACTIVE_MISSIONS", s.max_active_missions))
        s.api_token = os.environ.get("AUTORED_API_TOKEN") or None
        s.enable_onboarding = os.environ.get("AUTORED_ENABLE_ONBOARDING", "1") != "0"
        s.allow_private_targets = os.environ.get("AUTORED_ALLOW_PRIVATE_TARGETS", "0") == "1"
        s.admin_token = os.environ.get("AUTORED_ADMIN_TOKEN") or None
        if v := os.environ.get("AUTORED_ONBOARDING_STORE"):
            s.onboarding_store = Path(v)
        elif os.environ.get("AUTORED_RUNS_DIR"):
            s.onboarding_store = s.runs_dir / "onboarded-targets.json"
        s.public_mode = os.environ.get("AUTORED_PUBLIC_MODE", "0") == "1"
        if v := os.environ.get("AUTORED_DEMO_TARGET_ORIGINS"):
            s.demo_target_origins = tuple(o.strip().rstrip("/") for o in v.split(",") if o.strip())
        # In public mode, refuse to run wide open: a token is required and quotas tighten.
        if s.public_mode:
            s.max_active_missions = int(os.environ.get("AUTORED_MAX_ACTIVE_MISSIONS", 1))
            if v := os.environ.get("AUTORED_CORS_ORIGINS"):
                s.cors_origins = tuple(o.strip() for o in v.split(",") if o.strip())
        return s
