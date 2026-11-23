"""Runtime target onboarding registry.

Turns an SSRF-validated URL + operator-declared scope into a mission-compatible
`Target` and registers it into the live `ScopeRegistry`, so the existing mission
engine can run against it with no other change. Verification state is tracked
separately and gates `authorized_methods`:

    unverified            -> ["connectivity"]   (discovery + one benign message only)
    domain / admin verified -> ["connectivity", "security_probes"]

A checkbox is never sufficient: `security_probes` requires either proven domain
control (a token served at /.well-known/autored-authorization.txt) or an
administrator's written approval (admin token + reference). Onboarded targets
are persisted to JSON so they survive a restart.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from ..safety.scope import Authorization, Canary, ChatHints, LoginConfig, ScopeRegistry, Target
from .ssrf import ResolvedTarget

_SLUG = re.compile(r"[^a-z0-9]+")


class OnboardingError(Exception):
    pass


@dataclass
class OnboardedTarget:
    target: Target
    resolved: ResolvedTarget
    scope_description: str                       # operator's written testing scope
    requested_methods: list[str]                 # methods the operator asked for
    verification: dict = field(default_factory=dict)  # {status, method, token, ...}
    created_by: str = ""
    created_at: str = ""

    def public_view(self) -> dict:
        t = self.target
        return {
            "id": t.id, "name": t.name, "base_url": t.base_url,
            "origin": self.resolved.origin, "resolved_ips": list(self.resolved.ips),
            "scope_description": self.scope_description,
            "requested_methods": self.requested_methods,
            "authorized_methods": list(t.authorized_methods),
            "authorization": t.authorization.model_dump(mode="json"),
            "chat": t.chat.model_dump(exclude_none=True),
            "verification": {k: v for k, v in self.verification.items() if k != "secret"},
            "created_by": self.created_by, "created_at": self.created_at,
            "onboarded": True,
        }


def _slug(host: str) -> str:
    return _SLUG.sub("-", host.lower()).strip("-")[:40] or "target"


def _token(seed: str) -> str:
    return "autored-verify-" + hashlib.sha256(seed.encode()).hexdigest()[:24]


class OnboardingRegistry:
    def __init__(self, scopes: ScopeRegistry, store_path: Path | None = None):
        self.scopes = scopes
        self.store_path = store_path
        self._targets: dict[str, OnboardedTarget] = {}
        if store_path and store_path.is_file():
            self._load()

    # ------------------------------------------------------------------ public
    def list(self) -> list[OnboardedTarget]:
        return list(self._targets.values())

    def get(self, target_id: str) -> OnboardedTarget | None:
        return self._targets.get(target_id)

    def onboard(self, resolved: ResolvedTarget, *, name: str, scope_description: str,
                requested_methods: list[str], operator: str,
                chat_path: str = "/", chat_selectors: dict | None = None,
                login: dict | None = None, canaries: list[dict] | None = None,
                accounts: dict | None = None, authorized_tools: list[str] | None = None,
                oracle_audit_path: str | None = None) -> OnboardedTarget:
        if not scope_description.strip():
            raise OnboardingError("a written testing scope is required")
        if not operator.strip():
            raise OnboardingError("operator identity is required for the audit trail")
        tid = f"onboard-{_slug(resolved.host)}-{hashlib.sha256(resolved.origin.encode()).hexdigest()[:6]}"
        if tid in self._targets:
            raise OnboardingError(f"target for {resolved.origin} is already onboarded as '{tid}'")

        sel = chat_selectors or {}
        chat = ChatHints(path=chat_path or "/", input=sel.get("input"), send=sel.get("send"),
                         send_mode=sel.get("send_mode"), assistant_message=sel.get("assistant_message"),
                         frame=sel.get("frame"), launcher=sel.get("launcher"))
        # unverified targets start connectivity-only regardless of what was requested.
        target = Target(
            id=tid, name=name or resolved.host, base_url=resolved.origin,
            allowed_origins=[resolved.origin],
            authorization=Authorization(reference="PENDING-VERIFICATION", approved_by="(unverified)",
                                        expires=date.today() + timedelta(days=7)),
            login=LoginConfig(**login) if login else None,
            chat=chat,
            accounts={k: self._account(v) for k, v in (accounts or {}).items()},
            canaries=[Canary(**c) for c in (canaries or [])],
            authorized_tools=list(authorized_tools or []),
            oracle_audit_path=oracle_audit_path,
            authorized_methods=["connectivity"],
            identify_as="AutoRed/1.0 (authorized security assessment; +https://github.com/FarnooshMemari/autored)",
        )
        self.scopes.register(target)
        ot = OnboardedTarget(
            target=target, resolved=resolved, scope_description=scope_description.strip(),
            requested_methods=list(requested_methods or ["connectivity"]), created_by=operator.strip(),
            created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            verification={"status": "unverified", "token": _token(resolved.origin),
                          "well_known_url": resolved.origin + "/.well-known/autored-authorization.txt"})
        self._targets[tid] = ot
        self._save()
        return ot

    def mark_verified(self, target_id: str, *, method: str, reference: str, approved_by: str,
                      expires: date, detail: str = "") -> OnboardedTarget:
        ot = self._require(target_id)
        want = set(ot.requested_methods) or {"security_probes"}
        methods = ["connectivity"] + (["security_probes"] if "security_probes" in want else [])
        # Rebuild Target with real authorization + upgraded methods, re-register.
        t = ot.target
        ot.target = t.model_copy(update={
            "authorization": Authorization(reference=reference, approved_by=approved_by, expires=expires),
            "authorized_methods": methods,
        })
        self.scopes.register(ot.target)
        ot.verification = {**ot.verification, "status": "verified", "method": method,
                           "verified_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                           "detail": detail, "reference": reference}
        self._save()
        return ot

    def expected_token(self, target_id: str) -> str:
        return self._require(target_id).verification["token"]

    # ----------------------------------------------------------------- helpers
    def _account(self, v: dict):
        from ..safety.scope import Account
        return Account(**v)

    def _require(self, target_id: str) -> OnboardedTarget:
        ot = self._targets.get(target_id)
        if ot is None:
            raise OnboardingError(f"onboarded target '{target_id}' not found")
        return ot

    # ---------------------------------------------------------- persistence
    def _save(self) -> None:
        if not self.store_path:
            return
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        data = [{
            "resolved": {"url": ot.resolved.url, "scheme": ot.resolved.scheme, "host": ot.resolved.host,
                         "port": ot.resolved.port, "origin": ot.resolved.origin, "ips": list(ot.resolved.ips)},
            "target": ot.target.model_dump(mode="json"),
            "scope_description": ot.scope_description, "requested_methods": ot.requested_methods,
            "verification": ot.verification, "created_by": ot.created_by, "created_at": ot.created_at,
        } for ot in self._targets.values()]
        self.store_path.write_text(json.dumps(data, indent=2))

    def _load(self) -> None:
        try:
            data = json.loads(self.store_path.read_text())
        except Exception:
            return
        for row in data:
            try:
                r = row["resolved"]
                resolved = ResolvedTarget(url=r["url"], scheme=r["scheme"], host=r["host"], port=r["port"],
                                          origin=r["origin"], ips=tuple(r["ips"]))
                target = Target.model_validate(row["target"])
                self.scopes.register(target)
                self._targets[target.id] = OnboardedTarget(
                    target=target, resolved=resolved, scope_description=row.get("scope_description", ""),
                    requested_methods=row.get("requested_methods", ["connectivity"]),
                    verification=row.get("verification", {}), created_by=row.get("created_by", ""),
                    created_at=row.get("created_at", ""))
            except Exception:
                continue
