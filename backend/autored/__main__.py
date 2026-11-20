"""CLI: python -m autored export-schema | run-mission <target_id> --operator NAME --i-am-authorized"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys

from .config import ROOT, Settings
from .events.schema import export_json_schema


def main() -> int:
    ap = argparse.ArgumentParser(prog="autored")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("export-schema")
    r = sub.add_parser("run-mission")
    r.add_argument("target_id")
    r.add_argument("--operator", required=True)
    r.add_argument("--i-am-authorized", action="store_true", help="Confirm written authorization for this target")
    r.add_argument("--agents", nargs="*")
    r.add_argument("--adaptive", action="store_true", help="Use the LLM-powered adaptive Commander")
    c = sub.add_parser("connectivity-check", help="Phase-0: discover + one benign message, NO security probes")
    c.add_argument("target_id")
    c.add_argument("--operator", required=True)
    c.add_argument("--i-am-authorized", action="store_true")
    rep = sub.add_parser("report", help="Generate a reproducible report from a mission's event log")
    rep.add_argument("mission_id")
    sub.add_parser("missions", help="List stored missions")
    a = ap.parse_args()

    if a.cmd == "export-schema":
        out = ROOT / "contracts" / "events.schema.json"
        out.write_text(json.dumps(export_json_schema(), indent=2) + "\n")
        print(f"wrote {out}")
        return 0

    if a.cmd == "missions":
        from .config import Settings
        from .storage.store import MissionStore
        for m in MissionStore(Settings.from_env().db_path).list_missions():
            print(f"{m['id']}  {m['target_id']:<16} {m['mode']:<12} {m['phase']:<10} confirmed={m['confirmed']}  {m['created_at']}")
        return 0

    if a.cmd == "report":
        from .config import Settings
        from .reporting.report import replay, report_json, report_markdown
        run_dir = Settings.from_env().runs_dir / a.mission_id
        snap, events = replay(run_dir / "events.jsonl")
        md = report_markdown(snap, events)
        (run_dir / "report.md").write_text(md)
        (run_dir / "report.json").write_text(json.dumps(report_json(snap, events), indent=2))
        print(md)
        print(f"\n[wrote {run_dir}/report.md and report.json]")
        return 0

    from .browser.runtime import BrowserRuntime, FrameHub
    from .missions.manager import MissionManager
    from .safety.scope import ScopeRegistry

    async def run() -> int:
        s = Settings.from_env()
        rt = BrowserRuntime(headless=s.headless)
        from .storage.store import MissionStore
        mgr = MissionManager(ScopeRegistry.load(s.scope_path), rt, FrameHub(), s.runs_dir, store=MissionStore(s.db_path))
        mode = "connectivity" if a.cmd == "connectivity-check" else ("adaptive" if getattr(a, "adaptive", False) else "assess")
        agents = getattr(a, "agents", None)
        m = mgr.create(a.target_id, a.operator, a.i_am_authorized, agents, mode=mode)
        async for e in m.ctx.log.subscribe():
            if e.type in ("mission.status", "task.assigned", "test.verdict", "finding.updated", "mission.completed", "log"):
                print(f"[{e.seq:04}] {e.agent_id:<10} {e.type:<18} {json.dumps(e.payload)[:160]}")
        await m.task
        await rt.close()
        print(json.dumps(m.snapshot.summary.model_dump(mode="json") if m.snapshot.summary else {}, indent=2))
        return 0

    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
