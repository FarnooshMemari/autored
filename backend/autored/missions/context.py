from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

from ..browser.runtime import BrowserRuntime, FrameHub
from ..events.bus import MissionEventLog
from ..events.schema import Event
from ..safety.limits import RateLimiter
from ..safety.scope import ChatHints, Target
from .snapshot import MissionSnapshot


@dataclass
class MissionContext:
    """Everything shared by one mission's agents. Agents never share browser
    contexts; they share only the target-wide rate limiter, named locks
    for server-side shared state, and the commander's discovery results."""
    mission_id: str
    target: Target
    runtime: BrowserRuntime
    frames: FrameHub
    log: MissionEventLog
    snapshot: MissionSnapshot
    limiter: RateLimiter
    artifacts_dir: Path
    effective_hints: ChatHints | None = None   # discovered chat config, reused by specialists
    discovered_tools: list[str] = field(default_factory=list)
    abort_reason: str = ""
    _locks: dict[str, asyncio.Lock] = field(default_factory=lambda: defaultdict(asyncio.Lock))

    def emit(self, agent_id: str, type_: str, payload: BaseModel) -> Event:
        ev = self.log.publish(Event.make(self.mission_id, agent_id, type_, payload))
        self.snapshot.apply(ev)
        return ev

    def shared_state_lock(self, resource: str) -> asyncio.Lock:
        return self._locks[resource]
