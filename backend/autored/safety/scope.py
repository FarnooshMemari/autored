"""Target authorization and allowlist enforcement.

A mission can only be created against a target listed in a scope file, whose
authorization record has not expired, and only after an operator explicitly
acknowledges authorization. The OriginGuard is enforced again at the browser
network layer, so an agent cannot navigate off-scope even if a page redirects.
"""
from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, Field, field_validator


class ScopeError(Exception):
    pass


class Authorization(BaseModel):
    reference: str = Field(description="Ticket / engagement letter id")
    approved_by: str
    expires: date


class Account(BaseModel):
    username: str
    password: str
    owned_orders: list[str] = []

    @field_validator("username", "password", mode="before")
    @classmethod
    def _expand_env(cls, v: str) -> str:
        # Allow ${ENV_VAR} so real test credentials need not live in the file.
        return re.sub(r"\$\{(\w+)\}", lambda m: os.environ.get(m.group(1), ""), str(v))


class LoginConfig(BaseModel):
    path: str
    username_selector: str
    password_selector: str
    submit_selector: str


class ChatHints(BaseModel):
    path: str
    input: str | None = None
    send: str | None = None
    assistant_message: str | None = None


class Canary(BaseModel):
    id: str
    value: str
    meaning: str


class Limits(BaseModel):
    requests_per_second: float = 1.0
    burst: int = 2
    max_concurrent_agents: int = 4
    probe_timeout_s: float = 30
    mission_timeout_s: float = 600
    validation_attempts: int = 3
    validation_required: int = 2


class Target(BaseModel):
    id: str
    name: str
    base_url: str
    allowed_origins: list[str]
    authorization: Authorization
    login: LoginConfig | None = None
    chat: ChatHints
    accounts: dict[str, Account]
    canaries: list[Canary] = []
    oracle_audit_path: str | None = None
    authorized_tools: list[str] = []
    limits: Limits = Limits()

    def url(self, path: str) -> str:
        return self.base_url.rstrip("/") + path

    def guard(self) -> "OriginGuard":
        return OriginGuard(self.allowed_origins)


def _origin(url: str) -> str:
    p = urlsplit(url)
    port = p.port or {"http": 80, "https": 443}.get(p.scheme)
    return f"{p.scheme}://{(p.hostname or '').lower()}:{port}"


class OriginGuard:
    PASSTHROUGH_SCHEMES = ("about:", "data:", "blob:")

    def __init__(self, allowed: list[str]):
        if not allowed:
            raise ScopeError("allowlist is empty")
        self._allowed = {_origin(o) for o in allowed}

    def is_allowed(self, url: str) -> bool:
        if url.startswith(self.PASSTHROUGH_SCHEMES):
            return True
        try:
            return _origin(url) in self._allowed
        except ValueError:
            return False


class ScopeRegistry:
    def __init__(self, targets: list[Target]):
        self._targets = {t.id: t for t in targets}
        for t in targets:
            if not t.guard().is_allowed(t.base_url):
                raise ScopeError(f"{t.id}: base_url is not inside its own allowed_origins")

    @classmethod
    def load(cls, path: Path) -> "ScopeRegistry":
        data = yaml.safe_load(Path(path).read_text())
        return cls([Target.model_validate(t) for t in data.get("targets", [])])

    def list(self) -> list[Target]:
        return list(self._targets.values())

    def authorize(self, target_id: str, operator: str, acknowledged: bool, today: date | None = None) -> Target:
        t = self._targets.get(target_id)
        if t is None:
            raise ScopeError(f"target '{target_id}' is not in the allowlist")
        if not acknowledged:
            raise ScopeError("operator must explicitly acknowledge written authorization for this target")
        if not operator.strip():
            raise ScopeError("operator identity is required for the audit trail")
        if (today or date.today()) > t.authorization.expires:
            raise ScopeError(f"authorization {t.authorization.reference} expired on {t.authorization.expires}")
        return t
