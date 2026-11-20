"""Per-mission ordered event log with live fan-out and replay.

Late WebSocket subscribers (or reconnecting UIs) call `subscribe(since=seq)`
and receive every event after `seq`, then live events, with no gaps.
Events are also appended to runs/<mission>/events.jsonl for reproducibility.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

from .schema import Event


class MissionEventLog:
    def __init__(self, mission_id: str, persist_dir: Path | None = None, max_queue: int = 5000):
        self.mission_id = mission_id
        self._events: list[Event] = []
        self._subscribers: set[asyncio.Queue[Event | None]] = set()
        self._closed = False
        self._max_queue = max_queue
        self._file = None
        if persist_dir is not None:
            persist_dir.mkdir(parents=True, exist_ok=True)
            self._file = open(persist_dir / "events.jsonl", "a", encoding="utf-8")

    @property
    def events(self) -> list[Event]:
        return list(self._events)

    @property
    def last_seq(self) -> int:
        return self._events[-1].seq if self._events else 0

    def publish(self, event: Event) -> Event:
        if event.mission_id != self.mission_id:
            raise ValueError("event mission_id mismatch")
        event.seq = self.last_seq + 1
        self._events.append(event)
        if self._file:
            self._file.write(event.model_dump_json() + "\n")
            self._file.flush()
        for q in list(self._subscribers):
            if q.qsize() >= self._max_queue:  # slow consumer: drop it, it can reconnect with since=
                self._subscribers.discard(q)
                q.put_nowait(None)
            else:
                q.put_nowait(event)
        return event

    def close(self) -> None:
        self._closed = True
        for q in self._subscribers:
            q.put_nowait(None)
        if self._file:
            self._file.close()
            self._file = None

    async def subscribe(self, since: int = 0) -> AsyncIterator[Event]:
        q: asyncio.Queue[Event | None] = asyncio.Queue()
        backlog = [e for e in self._events if e.seq > since]
        if not self._closed:
            self._subscribers.add(q)
        try:
            for e in backlog:
                yield e
            last = backlog[-1].seq if backlog else since
            if self._closed:
                return
            while True:
                e = await q.get()
                if e is None:
                    return
                if e.seq > last:
                    last = e.seq
                    yield e
        finally:
            self._subscribers.discard(q)
