import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import run_once, warm, set_hardened

SCOPE = str(Path("~/autored/ext/owui-tools-scope.yaml").expanduser())

async def main():
    results = {}
    # Baseline (fixed probes) vs Adaptive (LLM planner), same vulnerable target.
    for label, mode, hardened in [("baseline_vulnerable", "assess", False),
                                  ("adaptive_vulnerable", "adaptive", False),
                                  ("adaptive_hardened_heldout", "adaptive", True)]:  # held-out: not used to design the planner
        set_hardened(hardened); warm()
        print(f"\n### {label} (mode={mode}, hardened={hardened}) ...", flush=True)
        try:
            results[label] = await run_once(SCOPE, "owui-tools", label, mode=mode)
        except Exception as e:
            results[label] = {"label": label, "error": repr(e)}
        print(json.dumps(results[label], indent=2), flush=True)
    set_hardened(False)

    def confset(r): return {c["probe"]: c for c in r.get("confirmed", [])}
    b, a, h = results["baseline_vulnerable"], results["adaptive_vulnerable"], results["adaptive_hardened_heldout"]
    analysis = {
        "baseline_confirmed_titles": sorted({c["title"] for c in b.get("confirmed", [])}),
        "adaptive_confirmed_titles": sorted({c["title"] for c in a.get("confirmed", [])}),
        "heldout_hardened_confirmed": [c["probe"] for c in h.get("confirmed", [])],  # expect [] (no false positives)
        "metrics": {k: {"n_confirmed": results[k].get("n_confirmed"), "probes_run": results[k].get("probes_run"),
                        "llm_calls": results[k].get("llm_calls"), "duration_s": results[k].get("duration_s"),
                        "suspected": results[k].get("n_suspected"), "passed": results[k].get("passed")} for k in results},
        "adaptive_found_titles_baseline_missed": sorted(
            {c["title"] for c in a.get("confirmed", [])} - {c["title"] for c in b.get("confirmed", [])}),
    }
    print("\n### ANALYSIS\n" + json.dumps(analysis, indent=2), flush=True)
    out = Path("~/autored/pilots/experiments").expanduser(); out.mkdir(parents=True, exist_ok=True)
    (out / "baseline_vs_adaptive.json").write_text(json.dumps({"results": results, "analysis": analysis}, indent=2))
    print("\nsaved to pilots/experiments/baseline_vs_adaptive.json")

asyncio.run(main())
