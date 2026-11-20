"""State derived purely from events. The frontend reducer
(frontend/src/state/missionReducer.ts) implements the same rules."""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..events.schema import (ALL_AGENT_IDS, AgentStatus, CapabilityPayload, Event, FindingPayload,
                             MissionPhase, MissionSummaryPayload, PlanPayload)


class TaskView(BaseModel):
    task_id: str
    kind: str
    title: str
    probe_ids: list[str]
    outcome: str | None = None
    detail: str = ""


class AgentView(BaseModel):
    agent_id: str
    status: AgentStatus = AgentStatus.idle
    activity: str = ""
    task_id: str | None = None
    url: str | None = None
    context_id: str | None = None
    probes_run: int = 0
    tasks: list[TaskView] = Field(default_factory=list)


class MissionSnapshot(BaseModel):
    mission_id: str
    target_id: str
    operator: str
    phase: MissionPhase = MissionPhase.created
    message: str = ""
    agents: dict[str, AgentView]
    findings: dict[str, FindingPayload] = Field(default_factory=dict)
    capabilities: CapabilityPayload | None = None
    plan: PlanPayload | None = None
    summary: MissionSummaryPayload | None = None
    last_seq: int = 0

    @classmethod
    def new(cls, mission_id: str, target_id: str, operator: str) -> "MissionSnapshot":
        return cls(mission_id=mission_id, target_id=target_id, operator=operator,
                   agents={a: AgentView(agent_id=a) for a in ALL_AGENT_IDS})

    def apply(self, e: Event) -> None:
        p, a = e.payload, self.agents[e.agent_id]
        self.last_seq = e.seq
        match e.type:
            case "mission.status":
                self.phase, self.message = MissionPhase(p["phase"]), p.get("message", "")
            case "mission.completed":
                self.summary = MissionSummaryPayload.model_validate(p)
                self.phase = self.summary.phase
            case "agent.status":
                a.status, a.activity, a.task_id = AgentStatus(p["status"]), p["activity"], p.get("task_id")
            case "task.assigned":
                self.agents[p["to_agent"]].tasks.append(TaskView(
                    task_id=p["task_id"], kind=p["kind"], title=p["title"], probe_ids=p["probe_ids"]))
            case "task.completed":
                for t in a.tasks:
                    if t.task_id == p["task_id"]:
                        t.outcome, t.detail = p["outcome"], p.get("detail", "")
            case "commander.capabilities":
                self.capabilities = CapabilityPayload.model_validate(p)
            case "commander.plan":
                self.plan = PlanPayload.model_validate(p)
            case "browser.navigated":
                a.url, a.context_id = p["url"], p["context_id"]
            case "test.verdict":
                if p["verdict"] not in ("not_applicable",):  # not executed
                    a.probes_run += 1
            case "finding.candidate" | "finding.updated":
                self.findings[p["finding_id"]] = FindingPayload.model_validate(p)
