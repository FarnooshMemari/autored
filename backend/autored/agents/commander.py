"""Commander: discover -> plan -> delegate -> monitor/validate -> consolidate.

Orchestration is a plain asyncio state machine rather than LangGraph for this
slice: planning is deterministic, and the hard parts are cancellation,
concurrency and streaming, which asyncio handles directly. LangGraph comes in
when an LLM planner adds adaptive follow-up loops (milestone M4); the phase
methods below map 1:1 onto graph nodes.
"""
from __future__ import annotations

import asyncio
import time
import uuid

from ..events.schema import (SPECIALIST_IDS, AgentStatus, CapabilityPayload, FindingStatus, MissionPhase,
                             MissionStatusPayload, MissionSummaryPayload, PlanPayload, TaskAssignedPayload,
                             TestVerdictPayload, Verdict)
from ..missions.context import MissionContext
from .probes import Probe, probe_by_id, probes_for
from .specialist import SPECIALIST_NAMES, Agent, SpecialistAgent

GREETING = "Hi! What can you help me with, and which tools can you use?"


class Commander(Agent):
    def __init__(self, ctx: MissionContext, agent_ids: list[str] | None = None):
        super().__init__("commander", ctx)
        self.agent_ids = list(agent_ids or SPECIALIST_IDS)
        self.specialists: dict[str, SpecialistAgent] = {}
        self.findings: dict[str, object] = {}
        self.agent_errors = 0

    def phase(self, phase: MissionPhase, msg: str = "") -> None:
        self.emit("mission.status", MissionStatusPayload(phase=phase, message=msg))

    # ---------------------------------------------------------------- phases
    async def discover(self) -> CapabilityPayload:
        self.phase(MissionPhase.discovery, "Locating the AI assistant")
        await self.start_session()
        self.set_status(AgentStatus.discovering, "Probing chat UI and asking assistant about its capabilities")
        lim = self.ctx.target.limits
        await self.ctx.limiter.acquire()
        selectors, reply = await self.chat.discover(GREETING, lim.probe_timeout_s)
        self.ctx.effective_hints = self.chat.handle.to_hints(self.ctx.target.chat.path, self.ctx.target.chat.launcher)
        known = set(self.ctx.target.authorized_tools) | {t for p in self._all_probes() for t in p.tools}
        tools = sorted(t for t in known if t.lower() in reply.lower())
        self.ctx.discovered_tools = tools
        cap = CapabilityPayload(assistant_detected=True, chat_url=self.browser.page.url, tools=tools,
                                selectors=selectors, raw_response=reply)
        self.emit("commander.capabilities", cap)
        return cap

    def _all_probes(self) -> list[Probe]:
        opt = self.ctx.target.include_optional_probes
        return [p for a in self.agent_ids for p in probes_for(a, include_optional=opt)]

    def plan(self) -> dict[str, list[Probe]]:
        self.phase(MissionPhase.planning, "Selecting probes within scope")
        self.set_status(AgentStatus.planning, "Building assessment plan")
        authorized = set(self.ctx.target.authorized_tools)
        plan: dict[str, list[Probe]] = {}
        skipped: dict[str, str] = {}
        opt = self.ctx.target.include_optional_probes
        for a in self.agent_ids:
            for p in probes_for(a, include_optional=opt):
                unauth = [t for t in p.tools if t not in authorized]
                if unauth:
                    # not authorized in scope => not runnable here
                    skipped[p.id] = f"tool(s) {unauth} not authorized in scope"
                else:
                    # authorized_tools is the operator's assertion that the tool exists;
                    # we do not require the assistant to "advertise" it (real apps don't).
                    plan.setdefault(a, []).append(p)
        self.emit("commander.plan", PlanPayload(assignments={a: [p.id for p in ps] for a, ps in plan.items()}, skipped=skipped))
        for pid, reason in skipped.items():
            pr = probe_by_id(pid)
            self.ctx.emit(pr.agent, "test.verdict",
                          TestVerdictPayload(probe_id=pid, verdict=Verdict.not_applicable, rationale=reason))
        return plan

    async def _pipeline(self, agent_id: str, probes: list[Probe], sem: asyncio.Semaphore) -> None:
        async with sem:
            agent = self.specialists[agent_id] = SpecialistAgent(agent_id, self.ctx)
            tid = f"T-{uuid.uuid4().hex[:6]}"
            self.emit("task.assigned", TaskAssignedPayload(
                task_id=tid, to_agent=agent_id, kind="assess", title=f"{SPECIALIST_NAMES[agent_id]} assessment",
                probe_ids=[p.id for p in probes]))
            agent.state.current_task = tid
            try:
                candidates = await agent.assess(tid, probes)
                for probe, finding in candidates:
                    vid = f"T-{uuid.uuid4().hex[:6]}"
                    self.emit("task.assigned", TaskAssignedPayload(
                        task_id=vid, to_agent=agent_id, kind="validate", title=f"Reproduce {finding.finding_id}",
                        probe_ids=[probe.id], reason=f"candidate from {probe.id} needs independent reproduction"))
                    agent.state.current_task = vid
                    await agent.validate(vid, probe, finding)
                await agent.shutdown(AgentStatus.done, "Assignment complete")
            except asyncio.CancelledError:
                await agent.shutdown(AgentStatus.stopped, "Stopped by operator")
                raise
            except Exception as e:
                self.agent_errors += 1
                self.log("error", f"{agent_id} failed: {e!r}")
                await agent.shutdown(AgentStatus.error, f"Error: {e}")

    async def _connectivity(self, t0: float) -> MissionSummaryPayload:
        """Phase-0: prove discovery + one benign round-trip, then stop. No
        security probes run. Used for authorized external connectivity checks."""
        self.phase(MissionPhase.execution, "Connectivity check (no security probes)")
        lim = self.ctx.target.limits
        msg = self.ctx.target.connectivity_message
        try:
            await self.ctx.limiter.acquire()
            self.set_status(AgentStatus.testing, "Sending one benign message")
            reply, ms, _ = await self.chat.send(msg, lim.probe_timeout_s)
            self.log("info", f"connectivity reply ({ms} ms): {reply[:200]}")
            shot = await self.browser.screenshot(self.ctx.artifacts_dir / "connectivity.png")
            self.log("info", f"screenshot: {shot.name}")
            reason = "connectivity OK (discovery + benign message); security probes not authorized/requested"
            return self._finish(MissionPhase.completed, t0, reason)
        finally:
            await self.browser.close()

    async def run(self) -> MissionSummaryPayload:
        t0 = time.monotonic()
        try:
            await self.discover()
            if self.ctx.mode == "connectivity" or not self.ctx.target.allows("security_probes"):
                return await self._connectivity(t0)
            await self.browser.close()   # specialists use their own contexts
            plan = self.plan()
            self.phase(MissionPhase.execution, f"Delegating to {len(plan)} specialist(s)")
            self.set_status(AgentStatus.monitoring, f"Monitoring {len(plan)} specialists")
            sem = asyncio.Semaphore(self.ctx.target.limits.max_concurrent_agents)
            await asyncio.gather(*(self._pipeline(a, ps, sem) for a, ps in plan.items()))
            self.phase(MissionPhase.consolidation, "Consolidating findings")
            self.set_status(AgentStatus.planning, "Consolidating and validating findings")
            if plan and self.agent_errors == len(plan):
                return self._finish(MissionPhase.failed, t0, "every specialist failed; see log events")
            return self._finish(MissionPhase.completed, t0)
        except asyncio.CancelledError:
            await self._stop_all()
            self._finish(MissionPhase.aborted, t0, self.ctx.abort_reason or "stopped by operator")
            raise
        except Exception as e:
            self.log("error", f"mission failed: {e!r}")
            await self._stop_all()
            return self._finish(MissionPhase.failed, t0, str(e))
        finally:
            await self.browser.close()

    async def _stop_all(self) -> None:
        for a in self.specialists.values():
            await a.browser.close()

    def _finish(self, phase: MissionPhase, t0: float, reason: str = "") -> MissionSummaryPayload:
        fs = list(self.ctx.snapshot.findings.values())
        st = lambda s: sum(f.status == s for f in fs)
        verdicts = [e.payload["verdict"] for e in self.ctx.log.events if e.type == "test.verdict"]
        summary = MissionSummaryPayload(
            phase=phase, reason=reason, agent_errors=self.agent_errors, duration_s=round(time.monotonic() - t0, 2),
            confirmed=st(FindingStatus.confirmed), suspected=st(FindingStatus.suspected),
            inconclusive=st(FindingStatus.inconclusive),
            passed=verdicts.count(Verdict.not_observed.value),
            not_applicable=verdicts.count(Verdict.not_applicable.value),
            probes_run=sum(v.probes_run for v in self.ctx.snapshot.agents.values()),
            llm_calls=getattr(getattr(self, "llm", None), "calls", 0))
        self.state.current_task = None
        self.set_status(AgentStatus.done if phase == MissionPhase.completed else AgentStatus.stopped,
                        f"Mission {phase.value}")
        self.emit("mission.completed", summary)
        return summary
