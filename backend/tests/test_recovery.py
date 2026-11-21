"""Experiment F — crash recovery / in-flight mission reconciliation."""
from __future__ import annotations

from autored.events.schema import (Evidence, Event, FindingPayload, FindingStatus, MissionPhase,
                                   MissionStatusPayload, MissionSummaryPayload)
from autored.missions.recovery import reconcile_runs
from autored.storage.store import MissionStore


def _write_run(runs_dir, mid, *, completed: bool):
    evs = [
        Event.make(mid, "commander", "mission.status", MissionStatusPayload(phase=MissionPhase.execution, message="go")),
        Event.make(mid, "tools", "finding.updated", FindingPayload(
            finding_id=f"F-{mid}", probe_id="TP-001", category="tools", title="Refund abuse", severity="critical",
            status=FindingStatus.confirmed, evidence=[Evidence(kind="oracle", detail="audit")], reproductions=2, attempts=2)),
    ]
    if completed:
        evs.append(Event.make(mid, "commander", "mission.completed",
                              MissionSummaryPayload(phase=MissionPhase.completed, confirmed=1, probes_run=8)))
    for i, e in enumerate(evs, 1):
        e.seq = i
    d = runs_dir / mid
    d.mkdir(parents=True)
    (d / "events.jsonl").write_text("\n".join(e.model_dump_json() for e in evs))


def test_interrupted_mission_is_reconciled(tmp_path):
    runs = tmp_path / "runs"
    _write_run(runs, "M-INTERRUPTED", completed=False)   # crashed mid-run (no mission.completed)
    _write_run(runs, "M-DONE", completed=True)           # finished but never saved to store
    store = MissionStore(tmp_path / "db.sqlite")

    rec = reconcile_runs(runs, store)
    assert rec == ["M-INTERRUPTED"]                       # only the interrupted one is reconciled

    m = store.get_mission("M-INTERRUPTED")
    assert m["phase"] == "interrupted" and m["confirmed"] == 1   # partial finding preserved
    assert "reconciled" in store.get_mission("M-INTERRUPTED")["summary"]
    done = store.get_mission("M-DONE")
    assert done["phase"] == "completed"                  # completed run persisted as-is
    # partial findings are queryable after recovery
    assert store.get_findings("M-INTERRUPTED")[0]["probe_id"] == "TP-001"


def test_reconcile_is_idempotent_and_skips_active(tmp_path):
    runs = tmp_path / "runs"
    _write_run(runs, "M-INTERRUPTED", completed=False)
    store = MissionStore(tmp_path / "db.sqlite")
    assert reconcile_runs(runs, store) == ["M-INTERRUPTED"]
    assert reconcile_runs(runs, store) == []             # already reconciled -> no-op
    # a still-active mission must NOT be reconciled
    _write_run(runs, "M-ACTIVE", completed=False)
    assert reconcile_runs(runs, store, active_ids={"M-ACTIVE"}) == []


def test_reconcile_preserves_creation_metadata(tmp_path):
    """A mission saved at creation (real target_id/operator/mode) that then crashes
    is reconciled to 'interrupted' WITHOUT losing that metadata (write-once fields)."""
    from autored.missions.snapshot import MissionSnapshot
    runs = tmp_path / "runs"
    store = MissionStore(tmp_path / "db.sqlite")
    # save-at-creation: a 'created' row with authoritative metadata
    store.save_mission(MissionSnapshot.new("M-META", "owui-tools", "alice"), mode="adaptive")
    assert store.get_mission("M-META")["phase"] == "created"
    # ran partially then crashed: a prefix log with a finding, no mission.completed
    _write_run(runs, "M-META", completed=False)
    assert reconcile_runs(runs, store) == ["M-META"]
    m = store.get_mission("M-META")
    assert m["phase"] == "interrupted"          # authoritative state
    assert m["target_id"] == "owui-tools" and m["operator"] == "alice" and m["mode"] == "adaptive"   # preserved
