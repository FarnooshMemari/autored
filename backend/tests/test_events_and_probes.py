import asyncio
import json

import pytest

from autored.agents.probes import PROBES, evaluate, probe_by_id
from autored.config import ROOT
from autored.events.bus import MissionEventLog
from autored.events.schema import (PAYLOADS, AgentStatus, AgentStatusPayload, Event, LogPayload, Verdict,
                                   export_json_schema)
from autored.missions.snapshot import MissionSnapshot
from conftest import target_from_scope

T = target_from_scope("http://127.0.0.1:9")


def test_payload_type_enforced():
    with pytest.raises(TypeError):
        Event.make("m", "commander", "agent.status", LogPayload(level="info", message="x"))


def test_committed_schema_is_current():
    committed = json.loads((ROOT / "contracts" / "events.schema.json").read_text())
    assert committed == json.loads(json.dumps(export_json_schema())), "run `python -m autored export-schema`"


def test_every_event_type_has_payload():
    from typing import get_args
    from autored.events.schema import EventType
    assert set(get_args(EventType)) == set(PAYLOADS)


async def test_bus_replay_then_live_is_gap_free(tmp_path):
    log = MissionEventLog("m1", tmp_path)
    mk = lambda i: Event.make("m1", "injection", "log", LogPayload(level="info", message=str(i)))
    for i in range(3):
        log.publish(mk(i))
    got = []

    async def consume():
        async for e in log.subscribe(since=1):
            got.append(e.seq)

    task = asyncio.create_task(consume())
    await asyncio.sleep(0)
    for i in range(3, 5):
        log.publish(mk(i))
    log.close()
    await asyncio.wait_for(task, 2)
    assert got == [2, 3, 4, 5]
    assert len((tmp_path / "events.jsonl").read_text().splitlines()) == 5


def test_snapshot_reducer():
    snap = MissionSnapshot.new("m1", "t", "op")
    e = Event.make("m1", "tools", "agent.status", AgentStatusPayload(status=AgentStatus.testing, activity="x"))
    e.seq = 7
    snap.apply(e)
    assert snap.agents["tools"].status == AgentStatus.testing and snap.last_seq == 7


def test_canary_is_strong_evidence():
    p = probe_by_id("PI-001")
    ev = evaluate(p, "ignore...", "Sure. My instructions are: ... SYS-CANARY-7F3A ...", T)
    assert ev.verdict == Verdict.vulnerable and any(x.kind == "canary" for x in ev.evidence)


def test_echoed_canary_is_not_evidence():
    p = probe_by_id("PI-001")
    ev = evaluate(p, "print SYS-CANARY-7F3A", "You said SYS-CANARY-7F3A", T)
    assert ev.verdict != Verdict.vulnerable


def test_weak_signal_is_inconclusive():
    ev = evaluate(probe_by_id("PI-001"), "x", "I cannot show my system prompt.", T)
    assert ev.verdict == Verdict.inconclusive


def test_refusal_is_not_a_refund_signal():
    p = probe_by_id("TP-001")
    ev = evaluate(p, "x", "Refunds must be processed by a staff member. I've noted your request.", T, oracle_records=[])
    assert ev.verdict == Verdict.not_observed


def test_refund_claim_without_oracle_record_is_inconclusive():
    p = probe_by_id("TP-001")
    assert evaluate(p, "x", "Done! Refund REF-1 issued for order 2004.", T, oracle_records=[]).verdict == Verdict.inconclusive


def test_oracle_record_is_strong_evidence():
    p = probe_by_id("TP-001")
    rec = [{"ts": "2026-01-01T00:00:00+00:00", "user": "tester4", "role": "customer", "tool": "issue_refund", "executed": True}]
    assert evaluate(p, "x", "ok", T, oracle_records=rec).verdict == Verdict.vulnerable


def test_probe_ids_unique_and_nondestructive_tools_declared():
    assert len({p.id for p in PROBES}) == len(PROBES)
    assert all(p.agent in ("injection", "leakage", "hierarchy", "tools") for p in PROBES)
