"""Reproducible mission reports, derived deterministically from the event log.

Given the same runs/<mission>/events.jsonl, these functions always produce the
same report — the event log is the source of truth, replayed through the same
reducer the live UI uses. Emits structured JSON and human-readable Markdown.
"""
from __future__ import annotations

import json
from pathlib import Path

from ..events.schema import Event
from ..missions.snapshot import MissionSnapshot


def replay(events_path: Path | str) -> tuple[MissionSnapshot, list[Event]]:
    events = [Event.model_validate_json(l) for l in Path(events_path).read_text().splitlines() if l.strip()]
    if not events:
        raise ValueError("no events")
    snap = MissionSnapshot.new(events[0].mission_id, "", "")
    for e in events:
        snap.apply(e)
    return snap, events


def report_json(snap: MissionSnapshot, events: list[Event]) -> dict:
    verdicts: dict[str, int] = {}
    for e in events:
        if e.type == "test.verdict" and e.payload.get("attempt", 1) == 1:
            verdicts[e.payload["verdict"]] = verdicts.get(e.payload["verdict"], 0) + 1
    findings = [{
        "finding_id": f.finding_id, "status": f.status.value, "severity": f.severity,
        "category": f.category, "probe_id": f.probe_id, "title": f.title,
        "reproductions": f.reproductions, "attempts": f.attempts,
        "confirmation_rate": f.confirmation_rate, "ci95": [f.ci_low, f.ci_high], "trials": f.trials,
        "evidence": [{"kind": e.kind, "detail": e.detail[:300]} for e in f.evidence if e.kind in ("canary", "oracle")],
    } for f in sorted(snap.findings.values(), key=lambda x: (x.status.value != "confirmed", x.probe_id))]
    s = snap.summary
    return {
        "mission_id": snap.mission_id, "target_id": snap.target_id, "operator": snap.operator,
        "phase": snap.phase.value,
        "summary": s.model_dump(mode="json") if s else None,
        "verdict_breakdown": verdicts,
        "confirmed": [f for f in findings if f["status"] == "confirmed"],
        "all_findings": findings,
    }


def report_markdown(snap: MissionSnapshot, events: list[Event]) -> str:
    r = report_json(snap, events)
    s = r["summary"] or {}
    lines = [f"# AutoRed assessment report — `{r['mission_id']}`", ""]
    lines += [f"- **Target:** {r['target_id'] or '(see scope)'}",
              f"- **Operator:** {r['operator']}", f"- **Phase:** {r['phase']}",
              f"- **Duration:** {s.get('duration_s','?')} s · **probes:** {s.get('probes_run','?')} · **LLM calls:** {s.get('llm_calls',0)}",
              f"- **Confirmed:** {s.get('confirmed',0)} · suspected: {s.get('suspected',0)} · inconclusive: {s.get('inconclusive',0)} · passed: {s.get('passed',0)} · n/a: {s.get('not_applicable',0)}", ""]
    lines += ["## Verdict breakdown (first attempt)", ""]
    for v, n in sorted(r["verdict_breakdown"].items()):
        lines.append(f"- {v}: {n}")
    lines += ["", "## Confirmed findings (strong evidence, reproduced)", ""]
    if not r["confirmed"]:
        lines.append("_None confirmed._")
    for f in r["confirmed"]:
        rate = f.get("confirmation_rate", 0.0); ci = f.get("ci95", [0, 0])
        lines.append(f"### {f['probe_id']} — {f['title']} ({f['severity']})")
        lines.append(f"- **Reproduced:** {f['reproductions']}/{f['attempts']} fresh-context trials "
                     f"(rate {rate:.0%}, 95% CI [{ci[0]:.0%}, {ci[1]:.0%}])")
        for e in f["evidence"]:
            lines.append(f"- **{e['kind']}:** {e['detail']}")
        lines.append("")
    other = [f for f in r["all_findings"] if f["status"] != "confirmed"]
    if other:
        lines += ["## Other findings (not confirmed)", "", "| probe | status | title | reproduced |", "|---|---|---|---|"]
        for f in other:
            lines.append(f"| {f['probe_id']} | {f['status']} | {f['title']} | {f['reproductions']}/{f['attempts']} |")
    lines += ["", "> Evidence standard: a finding is `confirmed` only via a seeded synthetic canary or the tool-audit "
              "oracle, reproduced in fresh browser contexts. A model's claim is never proof.", ""]
    return "\n".join(lines)
