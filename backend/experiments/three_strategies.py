"""Experiment B+ — fixed vs adaptive vs hybrid under comparable budgets.
Honest comparison; no claim of superiority without evidence. Local LLM only."""
import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import run_once, warm, set_hardened
SCOPE = str(Path("~/autored/ext/owui-tools-scope.yaml").expanduser())

async def main():
    res = {}
    for mode in ("assess", "adaptive", "hybrid"):
        set_hardened(False); warm()
        print(f"\n### {mode} ...", flush=True)
        try: res[mode] = await run_once(SCOPE, "owui-tools", mode, mode=mode)
        except Exception as e: res[mode] = {"error": repr(e)}
        print(json.dumps({k: res[mode].get(k) for k in ("n_confirmed","probes_run","llm_calls","duration_s")}, indent=2), flush=True)
    set_hardened(False)
    def cls(r): return sorted({"tool_permission" if c["probe"].startswith(("TP","AD")) else c["probe"][:2] for c in r.get("confirmed", [])})
    analysis = {m: {"n_confirmed": res[m].get("n_confirmed"), "classes": cls(res[m]),
                    "probes": res[m].get("probes_run"), "llm_calls": res[m].get("llm_calls"),
                    "duration_s": res[m].get("duration_s")} for m in res}
    print("\n### ANALYSIS\n" + json.dumps(analysis, indent=2), flush=True)
    Path("~/autored/pilots/experiments/three_strategies.json").expanduser().write_text(json.dumps({"results": res, "analysis": analysis}, indent=2))
    print("saved")
asyncio.run(main())
