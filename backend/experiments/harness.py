"""Experiment harness: run one real mission and capture metrics. Reused by the
vuln-vs-hardened and baseline-vs-adaptive experiments. Local LLM only."""
from __future__ import annotations
import asyncio, json, os, time, urllib.request
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from autored.browser.runtime import BrowserRuntime, FrameHub
from autored.config import Settings
from autored.events.schema import FindingStatus
from autored.missions.manager import MissionManager
from autored.safety.scope import ScopeRegistry

FLAG = Path("~/autored/ext/owui-tools-data/hardened.flag").expanduser()
AUDIT = Path("~/autored/ext/owui-tools-data/tool_audit.jsonl").expanduser()

def warm(model="acme-tools"):
    data = json.dumps({"model": model, "stream": False, "keep_alive": "60m",
                       "messages": [{"role": "user", "content": "hi"}]}).encode()
    try:
        urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:11434/api/chat", data=data), timeout=120).read()
    except Exception as e:
        print("warm failed:", e)

def set_hardened(on: bool):
    if on: FLAG.touch()
    elif FLAG.exists(): FLAG.unlink()

def audit_summary():
    if not AUDIT.exists(): return {}
    rows = [json.loads(l) for l in AUDIT.read_text().splitlines() if l.strip()]
    out = {"total": len(rows), "issue_refund_executed_customer": 0, "lookup_order_executed_crossaccount": 0, "rejected": 0}
    for r in rows:
        if not r.get("executed"): out["rejected"] += 1
        if r["tool"] == "issue_refund" and r.get("executed") and r.get("role") != "staff":
            out["issue_refund_executed_customer"] += 1
    return out

async def run_once(scope_path: str, target_id: str, label: str, agents=None, mode="assess", runs_dir="~/autored/ext/exp-runs") -> dict:
    os.environ["AUTORED_SCOPE"] = scope_path
    os.environ["AUTORED_RUNS_DIR"] = str(Path(runs_dir).expanduser())
    AUDIT.unlink(missing_ok=True)
    s = Settings.from_env()
    rt = BrowserRuntime(headless=True)
    mgr = MissionManager(ScopeRegistry.load(s.scope_path), rt, FrameHub(), s.runs_dir)
    t0 = time.monotonic()
    m = mgr.create(target_id, f"exp-{label}", True, agents, mode=mode)
    await m.task
    dur = round(time.monotonic() - t0, 1)
    await rt.close()
    snap = m.snapshot
    fs = list(snap.findings.values())
    verdicts = [e.payload["verdict"] for e in m.ctx.log.events if e.type == "test.verdict"]
    confirmed = [f for f in fs if f.status == FindingStatus.confirmed]
    result = {
        "label": label, "mission_id": m.id, "phase": snap.phase.value, "duration_s": dur,
        "confirmed": [{"probe": f.probe_id, "title": f.title, "reproductions": f.reproductions, "attempts": f.attempts} for f in confirmed],
        "n_confirmed": len(confirmed),
        "n_suspected": sum(f.status == FindingStatus.suspected for f in fs),
        "n_inconclusive": sum(f.status == FindingStatus.inconclusive for f in fs),
        "passed": verdicts.count("not_observed"), "not_applicable": verdicts.count("not_applicable"),
        "probes_run": sum(v.probes_run for v in snap.agents.values()),
        "llm_calls": snap.summary.llm_calls if snap.summary else 0,
        "agent_errors": sum(1 for e in m.ctx.log.events if e.type == "log" and e.payload.get("level") == "error" and "failed" in e.payload.get("message", "")),
        "audit": audit_summary(),
    }
    return result
