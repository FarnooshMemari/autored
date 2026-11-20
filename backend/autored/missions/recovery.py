"""Crash recovery: reconcile missions whose process died mid-run.

The event log (runs/<mission>/events.jsonl) is the durable source of truth and is
flushed per event. On restart we replay each run's log; any mission that never
emitted `mission.completed` and is not currently active was interrupted — we mark
it `interrupted` in the store with its partial findings preserved, so nothing is
left dangling and the partial evidence is queryable. We never silently resume a
half-finished browser session (its contexts are gone); we reconcile state honestly.
"""
from __future__ import annotations

from pathlib import Path

from ..reporting.report import replay
from ..storage.store import MissionStore


def reconcile_runs(runs_dir: Path, store: MissionStore, active_ids: set[str] | None = None) -> list[str]:
    active_ids = active_ids or set()
    reconciled: list[str] = []
    runs_dir = Path(runs_dir)
    if not runs_dir.is_dir():
        return reconciled
    for d in sorted(runs_dir.glob("M-*")):
        ev = d / "events.jsonl"
        if not ev.is_file() or d.name in active_ids:
            continue
        existing = store.get_mission(d.name)
        if existing and existing["phase"] in ("completed", "aborted", "failed", "interrupted"):
            continue
        try:
            snap, events = replay(ev)
        except Exception:
            continue
        if snap.summary is not None:
            # completed/aborted/failed but not yet in store -> persist as-is
            store.save_mission(snap)
            continue
        # no mission.completed -> interrupted. Mark it, keep partial findings.
        from ..events.schema import MissionPhase, MissionSummaryPayload
        snap.phase = MissionPhase.interrupted
        snap.summary = MissionSummaryPayload(
            phase=MissionPhase.interrupted, reason="process ended before the mission completed; reconciled on restart",
            confirmed=sum(f.status.value == "confirmed" for f in snap.findings.values()),
            probes_run=sum(v.probes_run for v in snap.agents.values()))
        store.save_mission(snap)
        reconciled.append(d.name)
    return reconciled
