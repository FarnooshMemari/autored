"""M5 durable storage + reproducible reporting (pure; no browser/LLM)."""
from __future__ import annotations

from autored.events.schema import (Evidence, Event, FindingPayload, FindingStatus, MissionPhase,
                                   MissionStatusPayload, MissionSummaryPayload)
from autored.missions.snapshot import MissionSnapshot
from autored.storage.store import MissionStore
from autored.reporting.report import replay, report_json, report_markdown


def make_events(mid: str) -> list[Event]:
    evs = [
        Event.make(mid, "commander", "mission.status", MissionStatusPayload(phase=MissionPhase.execution, message="go")),
        Event.make(mid, "tools", "finding.updated", FindingPayload(
            finding_id="F1", probe_id="TP-001", category="tools", title="Customer can trigger staff-only refund",
            severity="critical", status=FindingStatus.confirmed,
            evidence=[Evidence(kind="oracle", detail="audit: customer issue_refund executed")],
            reproductions=2, attempts=2)),
        Event.make(mid, "injection", "finding.updated", FindingPayload(
            finding_id="F2", probe_id="PI-001", category="injection", title="Suspected prompt echo",
            severity="medium", status=FindingStatus.suspected, evidence=[], reproductions=0, attempts=3)),
        Event.make(mid, "commander", "mission.completed", MissionSummaryPayload(
            phase=MissionPhase.completed, confirmed=1, suspected=1, passed=4, probes_run=8, llm_calls=0, duration_s=12.0)),
    ]
    for i, e in enumerate(evs, 1):
        e.seq = i
    return evs


def _snap(mid="M-TEST"):
    s = MissionSnapshot.new(mid, "acmehelp-local", "op")
    for e in make_events(mid):
        s.apply(e)
    return s


def test_store_roundtrip_and_idempotent(tmp_path):
    store = MissionStore(tmp_path / "db.sqlite")
    snap = _snap()
    store.save_mission(snap, mode="adaptive")
    store.save_mission(snap)  # upsert, no duplicate
    assert len(store.list_missions()) == 1
    m = store.get_mission("M-TEST")
    assert m["confirmed"] == 1 and m["phase"] == "completed" and m["mode"] == "adaptive"
    fs = store.get_findings("M-TEST")
    assert {f["finding_id"] for f in fs} == {"F1", "F2"}
    assert store.confirmed_findings()[0]["probe_id"] == "TP-001"


def test_report_is_reproducible(tmp_path):
    p = tmp_path / "events.jsonl"
    p.write_text("\n".join(e.model_dump_json() for e in make_events("M-TEST")))
    snap, events = replay(p)
    j1 = report_json(snap, events)
    assert j1["summary"]["confirmed"] == 1 and j1["confirmed"][0]["probe_id"] == "TP-001"
    assert j1["verdict_breakdown"] == {} or isinstance(j1["verdict_breakdown"], dict)
    md = report_markdown(snap, events)
    assert "Confirmed findings" in md and "TP-001" in md and "never proof" in md
    # deterministic: same input => identical output
    snap2, events2 = replay(p)
    assert report_markdown(snap2, events2) == md
