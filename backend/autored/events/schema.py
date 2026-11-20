"""Shared event contract between the backend and any UI (including the
visualization team's animated interface).

Every event on the wire is an `Event` envelope. `type` selects the payload
model in `PAYLOADS`. Bump `SCHEMA_VERSION` on any breaking change.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

SCHEMA_VERSION = 4

AgentId = Literal["commander", "injection", "leakage", "hierarchy", "tools"]
SPECIALIST_IDS: tuple[AgentId, ...] = ("injection", "leakage", "hierarchy", "tools")
ALL_AGENT_IDS: tuple[AgentId, ...] = ("commander", *SPECIALIST_IDS)


class AgentStatus(str, Enum):
    idle = "idle"
    starting = "starting"          # launching browser context
    authenticating = "authenticating"
    discovering = "discovering"    # commander only
    planning = "planning"          # commander only
    monitoring = "monitoring"      # commander only: supervising specialists
    navigating = "navigating"
    testing = "testing"            # sending a probe / awaiting response
    validating = "validating"      # replaying a candidate finding
    waiting = "waiting"            # rate limit / shared-state lock
    done = "done"
    error = "error"
    stopped = "stopped"


class MissionPhase(str, Enum):
    created = "created"
    discovery = "discovery"
    planning = "planning"
    execution = "execution"
    consolidation = "consolidation"
    completed = "completed"
    aborted = "aborted"
    failed = "failed"
    interrupted = "interrupted"   # process died mid-mission; reconciled on restart


class Verdict(str, Enum):
    vulnerable = "vulnerable"        # strong evidence (synthetic canary / audit oracle)
    suspected = "suspected"          # weak signal, no strong evidence: needs a human
    not_observed = "not_observed"    # tested cleanly; the weakness was not observed (passed)
    inconclusive = "inconclusive"    # could not be evaluated reliably (e.g. oracle unavailable)
    not_applicable = "not_applicable"  # probe not runnable on this target (e.g. tool absent/unauthorized)
    error = "error"


class FindingStatus(str, Enum):
    candidate = "candidate"          # observed once, pending independent reproduction
    confirmed = "confirmed"          # strong evidence reproduced in fresh contexts
    suspected = "suspected"          # real signal, not reliably reproduced to the confirm bar
    inconclusive = "inconclusive"    # could not be verified (no strong evidence available)


# ---------------------------------------------------------------- payloads

class MissionStatusPayload(BaseModel):
    phase: MissionPhase
    message: str = ""


class MissionSummaryPayload(BaseModel):
    phase: MissionPhase
    confirmed: int
    suspected: int = 0
    inconclusive: int = 0
    passed: int = 0              # probes that tested cleanly (not_observed)
    not_applicable: int = 0     # probes skipped as not runnable on this target
    probes_run: int = 0
    llm_calls: int = 0           # adaptive planner calls (0 for the fixed-probe Commander)
    agent_errors: int = 0
    duration_s: float = 0.0
    reason: str = ""


class AgentStatusPayload(BaseModel):
    status: AgentStatus
    activity: str = Field(description="Human-readable current activity, e.g. 'Sending probe PI-001'")
    task_id: str | None = None


class TaskAssignedPayload(BaseModel):
    task_id: str
    to_agent: AgentId
    kind: Literal["assess", "validate"]
    title: str
    probe_ids: list[str]
    reason: str = ""


class TaskCompletedPayload(BaseModel):
    task_id: str
    kind: Literal["assess", "validate"]
    outcome: Literal["completed", "failed", "cancelled", "skipped"]
    detail: str = ""


class CapabilityPayload(BaseModel):
    assistant_detected: bool
    chat_url: str | None = None
    tools: list[str] = []
    selectors: dict[str, str] = {}
    raw_response: str = ""


class PlanPayload(BaseModel):
    assignments: dict[str, list[str]] = Field(description="agent_id -> probe ids")
    skipped: dict[str, str] = Field(default_factory=dict, description="probe_id -> reason")


class Box(BaseModel):
    x: float; y: float; width: float; height: float  # page coords, for element-following animations


class BrowserNavigatedPayload(BaseModel):
    url: str
    title: str = ""
    context_id: str = Field(description="Isolated BrowserContext id; changes on fresh-context replays")
    viewport: dict[str, int] | None = None  # {width, height}


class BrowserActionPayload(BaseModel):
    action: Literal["click", "fill", "press", "wait", "read"]
    selector: str
    value_preview: str = ""
    frame: str | None = None     # iframe selector when the element is inside an iframe
    box: Box | None = None       # bounding box of the target element, if known


class BrowserBlockedPayload(BaseModel):
    url: str
    reason: str


class TestStartedPayload(BaseModel):
    probe_id: str
    probe_name: str
    category: str
    prompt: str
    attempt: int = 1


class TestResponsePayload(BaseModel):
    probe_id: str
    response: str
    latency_ms: int
    attempt: int = 1
    box: Box | None = None       # bounding box of the reply element, for reaction animations


class TestVerdictPayload(BaseModel):
    probe_id: str
    verdict: Verdict
    rationale: str
    attempt: int = 1


class Evidence(BaseModel):
    kind: Literal["response_excerpt", "canary", "oracle", "screenshot"]
    detail: str
    artifact: str | None = Field(default=None, description="Relative artifact path, fetch via /api/missions/{id}/artifacts/{name}")


class FindingPayload(BaseModel):
    finding_id: str
    probe_id: str
    category: str
    title: str
    severity: Literal["low", "medium", "high", "critical"]
    status: FindingStatus
    evidence: list[Evidence]
    attempts: int = 1
    reproductions: int = 0
    # statistical confirmation: of `trials` independent fresh-context runs, `successes`
    # reproduced strong evidence. rate + 95% Wilson interval report the uncertainty.
    trials: int = 0
    successes: int = 0
    confirmation_rate: float = 0.0
    ci_low: float = 0.0
    ci_high: float = 0.0
    prompt: str = ""


class LogPayload(BaseModel):
    level: Literal["debug", "info", "warning", "error"]
    message: str


PAYLOADS: dict[str, type[BaseModel]] = {
    "mission.status": MissionStatusPayload,
    "mission.completed": MissionSummaryPayload,
    "agent.status": AgentStatusPayload,
    "task.assigned": TaskAssignedPayload,
    "task.completed": TaskCompletedPayload,
    "commander.capabilities": CapabilityPayload,
    "commander.plan": PlanPayload,
    "browser.navigated": BrowserNavigatedPayload,
    "browser.action": BrowserActionPayload,
    "browser.blocked": BrowserBlockedPayload,
    "test.started": TestStartedPayload,
    "test.response": TestResponsePayload,
    "test.verdict": TestVerdictPayload,
    "finding.candidate": FindingPayload,
    "finding.updated": FindingPayload,
    "log": LogPayload,
}

EventType = Literal[
    "mission.status", "mission.completed", "agent.status", "task.assigned",
    "task.completed", "commander.capabilities", "commander.plan",
    "browser.navigated", "browser.action", "browser.blocked", "test.started",
    "test.response", "test.verdict", "finding.candidate", "finding.updated", "log",
]


class Event(BaseModel):
    """Wire envelope. `seq` is per-mission, strictly increasing, gap-free."""
    v: int = SCHEMA_VERSION
    id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    seq: int = 0
    mission_id: str
    agent_id: AgentId
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    type: EventType
    payload: dict[str, Any]

    @classmethod
    def make(cls, mission_id: str, agent_id: AgentId, type_: str, payload: BaseModel) -> "Event":
        expected = PAYLOADS[type_]
        if not isinstance(payload, expected):
            raise TypeError(f"{type_} requires {expected.__name__}, got {type(payload).__name__}")
        return cls(mission_id=mission_id, agent_id=agent_id, type=type_, payload=payload.model_dump(mode="json"))


def export_json_schema() -> dict[str, Any]:
    """Single JSON Schema document describing the envelope and every payload."""
    defs: dict[str, Any] = {}
    for name, model in PAYLOADS.items():
        s = model.model_json_schema(ref_template="#/$defs/{model}")
        defs.update(s.pop("$defs", {}))
        defs[model.__name__] = s
    env = Event.model_json_schema(ref_template="#/$defs/{model}")
    defs.update(env.pop("$defs", {}))
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "AutoRed event stream",
        "schemaVersion": SCHEMA_VERSION,
        "envelope": env,
        "payloadByType": {t: {"$ref": f"#/$defs/{m.__name__}"} for t, m in PAYLOADS.items()},
        "$defs": defs,
    }
