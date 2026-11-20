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
    a = ap.parse_args()

    if a.cmd == "export-schema":
        out = ROOT / "contracts" / "events.schema.json"
        out.write_text(json.dumps(export_json_schema(), indent=2) + "\n")
        print(f"wrote {out}")
        return 0

    from .browser.runtime import BrowserRuntime, FrameHub
    from .missions.manager import MissionManager
    from .safety.scope import ScopeRegistry

    async def run() -> int:
        s = Settings.from_env()
        rt = BrowserRuntime(headless=s.headless)
        mgr = MissionManager(ScopeRegistry.load(s.scope_path), rt, FrameHub(), s.runs_dir)
        m = mgr.create(a.target_id, a.operator, a.i_am_authorized, a.agents)
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
