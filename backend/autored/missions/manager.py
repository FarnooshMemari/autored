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

TERMINAL = {MissionPhase.completed, MissionPhase.aborted, MissionPhase.failed}


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
                 runs_dir: Path, max_active: int = 1, estop: EmergencyStop | None = None):
        self.scopes, self.runtime, self.frames = scopes, runtime, frames
        self.runs_dir, self.max_active = runs_dir, max_active
        self.estop = estop or EmergencyStop()
        self.missions: dict[str, Mission] = {}

    def active(self) -> list[Mission]:
        return [m for m in self.missions.values() if m.active]

    def create(self, target_id: str, operator: str, acknowledged: bool,
               agents: list[str] | None = None) -> Mission:
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
        mid = f"M-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:4]}"
        run_dir = self.runs_dir / mid
        ctx = MissionContext(
            mission_id=mid, target=target, runtime=self.runtime, frames=self.frames,
            log=MissionEventLog(mid, run_dir), snapshot=MissionSnapshot.new(mid, target_id, operator),
            limiter=RateLimiter(target.limits.requests_per_second, target.limits.burst),
            artifacts_dir=run_dir / "artifacts")
        (run_dir / "authorization.txt").write_text(
            f"mission={mid}\noperator={operator}\ntarget={target.id} {target.base_url}\n"
            f"authorization={target.authorization.reference} approved_by={target.authorization.approved_by} "
            f"expires={target.authorization.expires}\nacknowledged_at={datetime.now(timezone.utc).isoformat()}\n")
        m = Mission(mid, ctx, datetime.now(timezone.utc))
        self.missions[mid] = m
        m.task = asyncio.create_task(self._run(m, agents), name=mid)
        return m

    async def _run(self, m: Mission, agents: list[str] | None) -> None:
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
