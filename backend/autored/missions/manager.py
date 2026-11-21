from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from ..agents.commander import Commander
from ..browser.runtime import BrowserRuntime, FrameHub
from ..events.bus import MissionEventLog
from ..events.schema import SPECIALIST_IDS, MissionPhase
from ..safety.limits import EmergencyStop, RateLimiter
from ..safety.scope import ScopeError, ScopeRegistry
from .context import MissionContext
from .snapshot import MissionSnapshot

TERMINAL = {MissionPhase.completed, MissionPhase.aborted, MissionPhase.failed, MissionPhase.interrupted}


class MissionRejected(Exception):
    pass


@dataclass
class Mission:
    id: str
    ctx: MissionContext
    created_at: datetime
    task: asyncio.Task | None = None

    @property
    def snapshot(self) -> MissionSnapshot:
        return self.ctx.snapshot

    @property
    def active(self) -> bool:
        return self.task is not None and not self.task.done()


class MissionManager:
    def __init__(self, scopes: ScopeRegistry, runtime: BrowserRuntime, frames: FrameHub,
                 runs_dir: Path, max_active: int = 1, estop: EmergencyStop | None = None, store=None):
        self.scopes, self.runtime, self.frames = scopes, runtime, frames
        self.runs_dir, self.max_active = runs_dir, max_active
        self.estop = estop or EmergencyStop()
        self.missions: dict[str, Mission] = {}
        self.store = store   # optional MissionStore for durable persistence

    def active(self) -> list[Mission]:
        return [m for m in self.missions.values() if m.active]

    def reconcile(self) -> list[str]:
        """On startup, mark missions whose process died mid-run as 'interrupted'
        (partial findings preserved from the event log). Returns reconciled ids."""
        if self.store is None:
            return []
        from .recovery import reconcile_runs
        return reconcile_runs(self.runs_dir, self.store, {m.id for m in self.active()})

    def create(self, target_id: str, operator: str, acknowledged: bool,
               agents: list[str] | None = None, mode: str = "assess") -> Mission:
        if self.estop.engaged:
            raise MissionRejected(f"emergency stop engaged: {self.estop.reason}")
        try:
            target = self.scopes.authorize(target_id, operator, acknowledged)
        except ScopeError as e:
            raise MissionRejected(str(e)) from e
        if len(self.active()) >= self.max_active:
            raise MissionRejected("concurrency limit: another mission is running")
        if any(m.ctx.target.id == target_id for m in self.active()):
            raise MissionRejected("a mission is already running against this target")
        bad = [a for a in (agents or []) if a not in SPECIALIST_IDS]
        if bad:
            raise MissionRejected(f"unknown agents: {bad}")
        if mode not in ("assess", "connectivity", "adaptive", "hybrid"):
            raise MissionRejected(f"unknown mode: {mode}")
        if mode in ("assess", "adaptive", "hybrid") and not target.allows("security_probes"):
            raise MissionRejected(
                f"target '{target_id}' authorizes {target.authorized_methods}; security probes are not "
                "permitted. Run mode='connectivity' (discovery + one benign message) instead.")
        if mode == "connectivity" and not target.allows("connectivity"):
            raise MissionRejected(f"target '{target_id}' does not authorize connectivity checks")
        mid = f"M-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:4]}"
        run_dir = self.runs_dir / mid
        ctx = MissionContext(
            mission_id=mid, target=target, runtime=self.runtime, frames=self.frames,
            log=MissionEventLog(mid, run_dir), snapshot=MissionSnapshot.new(mid, target_id, operator),
            limiter=RateLimiter(target.limits.requests_per_second, target.limits.burst),
            artifacts_dir=run_dir / "artifacts", mode=mode)
        (run_dir / "authorization.txt").write_text(
            f"mission={mid}\noperator={operator}\ntarget={target.id} {target.base_url}\n"
            f"authorization={target.authorization.reference} approved_by={target.authorization.approved_by} "
            f"expires={target.authorization.expires}\nacknowledged_at={datetime.now(timezone.utc).isoformat()}\n")
        m = Mission(mid, ctx, datetime.now(timezone.utc))
        self.missions[mid] = m
        if self.store is not None:   # persist metadata now so a crash before completion is recoverable
            try:
                self.store.save_mission(m.snapshot, mode=mode, created_at=m.created_at)
            except Exception:
                pass
        m.task = asyncio.create_task(self._run(m, agents), name=mid)
        return m

    async def _run(self, m: Mission, agents: list[str] | None) -> None:
        if m.ctx.mode in ("adaptive", "hybrid"):
            from ..agents.adaptive import AdaptiveBudget, AdaptiveCommander
            from ..agents.llm import LLMClient, LLMConfig
            b = AdaptiveBudget(**(m.ctx.target.adaptive_budget or {}))
            cfg = LLMConfig(model=m.ctx.target.planner_model) if m.ctx.target.planner_model else LLMConfig()
            commander = AdaptiveCommander(m.ctx, agents, llm=LLMClient(cfg, max_calls=b.max_llm_calls),
                                          budget=b, hybrid=(m.ctx.mode == "hybrid"))
        else:
            commander = Commander(m.ctx, agents)
        inner = asyncio.create_task(commander.run())
        try:
            done, _ = await asyncio.wait({inner}, timeout=m.ctx.target.limits.mission_timeout_s)
            if not done:
                m.ctx.abort_reason = "mission timeout exceeded"
                inner.cancel()
                await asyncio.gather(inner, return_exceptions=True)
            elif inner.exception():
                raise inner.exception()
        except asyncio.CancelledError:
            inner.cancel()
            await asyncio.gather(inner, return_exceptions=True)
        finally:
            m.ctx.log.close()
            if self.store is not None:
                try:
                    self.store.save_mission(m.snapshot, mode=m.ctx.mode, created_at=m.created_at)
                except Exception as e:   # persistence must never crash a mission
                    import logging
                    logging.getLogger("autored").warning("store save failed: %s", e)

    async def stop(self, mission_id: str, reason: str = "stopped by operator") -> bool:
        m = self.missions.get(mission_id)
        if not m or not m.active:
            return False
        m.ctx.abort_reason = reason
        m.task.cancel()
        await asyncio.gather(m.task, return_exceptions=True)
        return True

    async def emergency_stop(self, reason: str) -> list[str]:
        self.estop.engage(reason)
        stopped = [m.id for m in self.active()]
        await asyncio.gather(*(self.stop(mid, f"EMERGENCY STOP: {reason}") for mid in stopped))
        return stopped
