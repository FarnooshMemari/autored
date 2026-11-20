from __future__ import annotations

import asyncio
import time


class RateLimiter:
    """Async token bucket. One instance per target is shared by all agents,
    because they all hit the same website."""

    def __init__(self, rate: float, burst: int = 1):
        if rate <= 0:
            raise ValueError("rate must be > 0")
        self.rate, self.capacity = rate, max(1, burst)
        self._tokens = float(self.capacity)
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self) -> float:
        """Returns seconds waited."""
        waited = 0.0
        async with self._lock:
            while True:
                now = time.monotonic()
                self._tokens = min(self.capacity, self._tokens + (now - self._last) * self.rate)
                self._last = now
                if self._tokens >= 1:
                    self._tokens -= 1
                    return waited
                delay = (1 - self._tokens) / self.rate
                waited += delay
                await asyncio.sleep(delay)


class EmergencyStop:
    """Process-wide latch. While engaged, no mission may start and every
    running mission is cancelled by the MissionManager."""

    def __init__(self) -> None:
        self.engaged = False
        self.reason = ""

    def engage(self, reason: str) -> None:
        self.engaged, self.reason = True, reason

    def reset(self) -> None:
        self.engaged, self.reason = False, ""
