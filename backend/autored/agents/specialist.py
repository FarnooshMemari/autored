from __future__ import annotations

import asyncio
import contextlib
import secrets
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ..browser.chat import ChatError, ChatSession
from ..browser.runtime import AgentBrowser
from ..events.schema import (AgentStatus, AgentStatusPayload, Box, Evidence, FindingPayload, FindingStatus,
                             LogPayload, TaskCompletedPayload, TestResponsePayload, TestStartedPayload,
                             TestVerdictPayload, Verdict)
from ..missions.context import MissionContext
from .probes import Evaluation, Probe, evaluate

AGENT_IDENTITY = {
    "commander": {"name": "Commander", "role": "Orchestrator", "color": "#9aa4b2"},
    "injection": {"name": "Inky",  "role": "Prompt Injection",      "color": "#a855f7"},  # purple
    "leakage":   {"name": "Vault", "role": "Data Leakage",          "color": "#f97316"},  # orange
    "hierarchy": {"name": "Lexi",  "role": "Instruction Hierarchy", "color": "#3b82f6"},  # blue
    "tools":     {"name": "Guard", "role": "Tool Permissions",      "color": "#22c55e"},  # green
}
# kept for existing callers (task titles): maps id -> human role label
SPECIALIST_NAMES = {k: v["role"] for k, v in AGENT_IDENTITY.items() if k != "commander"}


@dataclass
class TaskRecord:
    task_id: str
    kind: str
    probe_ids: list[str]
    started_at: datetime
    ended_at: datetime | None = None
    outcome: str | None = None


@dataclass
class AgentRuntimeState:
    status: AgentStatus = AgentStatus.idle
    activity: str = ""
    current_task: str | None = None
    history: list[TaskRecord] = field(default_factory=list)


class Agent:
    """Base: own state, own isolated browser, own test account."""

    def __init__(self, agent_id: str, ctx: MissionContext):
        self.id, self.ctx = agent_id, ctx
        self.state = AgentRuntimeState()
        self.account = ctx.target.accounts[agent_id]
        self.browser = AgentBrowser(ctx.runtime, ctx.frames, ctx.mission_id, agent_id,
                                    ctx.target.guard(), self.emit, identify_as=ctx.target.identify_as)
        self.chat = ChatSession(self.browser, ctx.target)

    def emit(self, type_: str, payload) -> None:
        self.ctx.emit(self.id, type_, payload)

    def set_status(self, status: AgentStatus, activity: str) -> None:
        self.state.status, self.state.activity = status, activity
        self.emit("agent.status", AgentStatusPayload(status=status, activity=activity, task_id=self.state.current_task))

    def log(self, level: str, msg: str) -> None:
        self.emit("log", LogPayload(level=level, message=msg))

    async def start_session(self, fresh: bool = False) -> None:
        self.set_status(AgentStatus.starting, "Opening isolated browser context")
        if fresh or self.browser.context is None:
            await (self.browser.reset() if self.browser.context else self.browser.open())
        self.set_status(AgentStatus.authenticating, f"Signing in as test account {self.account.username}")
        await self.chat.login(self.account, self.ctx.target.login)
        self.set_status(AgentStatus.navigating, "Opening assistant chat")
        await self.chat.open()
        if self.ctx.effective_hints is not None:   # reuse the Commander's discovery in this context
            await self.chat.attach(self.ctx.effective_hints, self.ctx.target.limits.probe_timeout_s)

    async def shutdown(self, status: AgentStatus = AgentStatus.done, activity: str = "Finished") -> None:
        # Report first: if cleanup is interrupted (e.g. a second cancel), the UI
        # must still reflect the real terminal state.
        self.state.current_task = None
        self.set_status(status, activity)
        await self.browser.close()

    def _begin(self, task_id: str, kind: str, probe_ids: list[str]) -> TaskRecord:
        rec = TaskRecord(task_id, kind, probe_ids, datetime.now(timezone.utc))
        self.state.history.append(rec)
        self.state.current_task = task_id
        return rec

    def _end(self, rec: TaskRecord, outcome: str, detail: str = "") -> None:
        rec.ended_at, rec.outcome = datetime.now(timezone.utc), outcome
        self.emit("task.completed", TaskCompletedPayload(task_id=rec.task_id, kind=rec.kind, outcome=outcome, detail=detail))
        self.state.current_task = None


class SpecialistAgent(Agent):
    def __init__(self, agent_id: str, ctx: MissionContext):
        super().__init__(agent_id, ctx)
        self.name = SPECIALIST_NAMES[agent_id]

    async def _oracle(self) -> list[dict] | None:
        t = self.ctx.target
        if t.oracle_file:   # real app's auditable tool-execution log on our filesystem
            import json
            from pathlib import Path
            fp = Path(t.oracle_file).expanduser()
            if not fp.exists():
                return []
            recs = [json.loads(l) for l in fp.read_text().splitlines() if l.strip()]
            return [r for r in recs if r.get("user") == self.account.username]  # this agent's account only
        return await self.chat.fetch_json(t.oracle_audit_path) if t.oracle_audit_path else None

    async def run_probe(self, probe: Probe, attempt: int = 1) -> tuple[Evaluation, str]:
        lim = self.ctx.target.limits
        nonce = secrets.token_hex(3)
        turns = probe.render_turns(nonce, self.account)   # single- or multi-turn
        prompt = "\n".join(turns)
        lock = self.ctx.shared_state_lock(probe.shared_state) if probe.shared_state else contextlib.nullcontext()
        if probe.shared_state and lock.locked():
            self.set_status(AgentStatus.waiting, f"Waiting for shared resource '{probe.shared_state}'")
        async with lock:
            before = await self._oracle() if probe.oracle else None
            replies = []
            for i, turn in enumerate(turns):
                await self.ctx.limiter.acquire()
                self.set_status(AgentStatus.validating if attempt > 1 else AgentStatus.testing,
                                f"{probe.id}: {probe.name}" + (f" (turn {i+1}/{len(turns)})" if len(turns) > 1 else ""))
                self.emit("test.started", TestStartedPayload(probe_id=probe.id, probe_name=probe.name,
                                                             category=probe.agent, prompt=turn, attempt=attempt))
                reply, ms, box = await asyncio.wait_for(self.chat.send(turn, lim.probe_timeout_s), lim.probe_timeout_s + 5)
                self.emit("test.response", TestResponsePayload(probe_id=probe.id, response=reply, latency_ms=ms,
                                                               attempt=attempt, box=Box(**box) if box else None))
                replies.append(reply)
            reply = "\n".join(replies)   # evaluate across all turns
            new_records = None
            if probe.oracle:
                after = await self._oracle()
                if before is not None and after is not None:
                    new_records = after[len(before):]
        ev = evaluate(probe, prompt, reply, self.ctx.target, new_records)
        self.emit("test.verdict", TestVerdictPayload(probe_id=probe.id, verdict=ev.verdict, rationale=ev.rationale, attempt=attempt))
        return ev, prompt

    async def candidate_from(self, probe: Probe, ev, prompt: str) -> FindingPayload:
        """Create + emit a finding from an evaluation. inconclusive => no reproduction possible."""
        fid = f"F-{uuid.uuid4().hex[:8]}"
        shot = await self.browser.screenshot(self.ctx.artifacts_dir / f"{fid}.png")
        status = FindingStatus.inconclusive if ev.verdict == Verdict.inconclusive else FindingStatus.candidate
        f = FindingPayload(
            finding_id=fid, probe_id=probe.id, category=probe.agent, title=probe.title,
            severity=probe.severity, status=status, prompt=prompt,
            evidence=[*ev.evidence, Evidence(kind="screenshot", detail="Browser at time of response", artifact=shot.name)],
            attempts=1, reproductions=1 if ev.verdict == Verdict.vulnerable else 0)
        self.emit("finding.candidate", f)
        return f

    async def assess(self, task_id: str, probes: list[Probe]) -> list[tuple[Probe, FindingPayload]]:
        rec = self._begin(task_id, "assess", [p.id for p in probes])
        candidates: list[tuple[Probe, FindingPayload]] = []
        try:
            await self.start_session()
            for probe in probes:
                try:
                    ev, prompt = await self.run_probe(probe)
                except (asyncio.TimeoutError, ChatError) as e:
                    # a single slow/no-reply probe must not kill the whole agent
                    rationale = "timed out" if isinstance(e, asyncio.TimeoutError) else str(e)
                    self.emit("test.verdict", TestVerdictPayload(probe_id=probe.id, verdict=Verdict.error, rationale=rationale))
                    continue
                if ev.verdict in (Verdict.vulnerable, Verdict.suspected, Verdict.inconclusive):
                    f = await self.candidate_from(probe, ev, prompt)
                    if f.status == FindingStatus.candidate:
                        candidates.append((probe, f))
            self._end(rec, "completed", f"{len(probes)} probes, {len(candidates)} candidate(s)")
            return candidates
        except asyncio.CancelledError:
            self._end(rec, "cancelled")
            raise
        except Exception as e:
            self._end(rec, "failed", str(e))
            raise

    async def validate(self, task_id: str, probe: Probe, finding: FindingPayload) -> FindingPayload:
        """Replay in fresh isolated contexts; confirm only on repeated strong evidence."""
        rec = self._begin(task_id, "validate", [probe.id])
        lim = self.ctx.target.limits
        successes, attempts, evidence = 0, 0, list(finding.evidence)
        try:
            for i in range(lim.validation_attempts):
                await self.start_session(fresh=True)
                self.set_status(AgentStatus.validating, f"Replaying {probe.id} ({i + 1}/{lim.validation_attempts}) in fresh context")
                attempts += 1
                try:
                    ev, _ = await self.run_probe(probe, attempt=i + 2)
                except asyncio.TimeoutError:
                    continue
                if ev.verdict == Verdict.vulnerable:
                    successes += 1
                    evidence += [e for e in ev.evidence if e.kind in ("canary", "oracle")][:1]
            strong = finding.reproductions + successes
            total = finding.attempts + attempts   # independent trials incl. initial detection
            from ..stats import wilson_ci
            rate = round(strong / total, 3) if total else 0.0
            lo, hi = wilson_ci(strong, total)
            # Confirmed only on repeated STRONG evidence; otherwise a real-but-flaky
            # signal is "suspected", never silently dropped or over-claimed.
            status = FindingStatus.confirmed if strong >= lim.validation_required else FindingStatus.suspected
            updated = finding.model_copy(update={
                "status": status, "attempts": total, "reproductions": strong,
                "trials": total, "successes": strong, "confirmation_rate": rate,
                "ci_low": lo, "ci_high": hi, "evidence": evidence})
            self.emit("finding.updated", updated)
            self._end(rec, "completed", f"{status.value}: reproduced {successes}/{attempts}")
            return updated
        except asyncio.CancelledError:
            self._end(rec, "cancelled")
            raise
        except Exception as e:
            self._end(rec, "failed", str(e))
            raise
