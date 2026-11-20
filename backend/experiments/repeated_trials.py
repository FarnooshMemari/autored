"""Repeated trials to quantify run-to-run variance (reproducibility metric).
N trials each of baseline (fixed) and adaptive against the vulnerable config."""
import asyncio, json, statistics as st, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import run_once, warm, set_hardened

SCOPE = str(Path("~/autored/ext/owui-tools-scope.yaml").expanduser())
N = int(sys.argv[1]) if len(sys.argv) > 1 else 3

# vulnerability CLASS of a confirmed probe (collapses probe-title noise)
def vclass(probe):
    if probe.startswith("TP") or probe == "AD-05" or "tool" in probe.lower(): return "tool_permission"
    if probe.startswith("PI"): return "prompt_injection"
    if probe.startswith("DL"): return "data_leakage"
    if probe.startswith("IH"): return "instruction_hierarchy"
    if probe.startswith("AD"): return "adaptive_goal"
    return probe

async def trials(mode, label):
    runs = []
    for i in range(N):
        set_hardened(False); warm()
        print(f"  {label} trial {i+1}/{N} ...", flush=True)
        r = await run_once(SCOPE, "owui-tools", f"{label}{i+1}", mode=mode)
        classes = sorted({vclass(c["probe"]) for c in r.get("confirmed", [])})
        runs.append({"n_confirmed": r["n_confirmed"], "classes": classes,
                     "probes_run": r["probes_run"], "llm_calls": r["llm_calls"], "duration_s": r["duration_s"]})
        print(f"    -> confirmed={r['n_confirmed']} classes={classes} probes={r['probes_run']} llm={r['llm_calls']}", flush=True)
    return runs

def agg(runs):
    nc = [r["n_confirmed"] for r in runs]
    tp = sum(1 for r in runs if "tool_permission" in r["classes"])
    allclasses = set().union(*[set(r["classes"]) for r in runs]) if runs else set()
    return {"trials": len(runs), "confirmed_mean": round(st.mean(nc),2), "confirmed_min": min(nc), "confirmed_max": max(nc),
            "tool_permission_detected_in": f"{tp}/{len(runs)} trials",
            "union_of_classes_found": sorted(allclasses),
            "mean_probes": round(st.mean(r["probes_run"] for r in runs),1),
            "mean_llm_calls": round(st.mean(r["llm_calls"] for r in runs),1),
            "mean_duration_s": round(st.mean(r["duration_s"] for r in runs),1), "runs": runs}

async def main():
    print(f"### Baseline x{N}", flush=True); base = await trials("assess", "base")
    print(f"### Adaptive x{N}", flush=True); adap = await trials("adaptive", "adap")
    set_hardened(False)
    out = {"baseline": agg(base), "adaptive": agg(adap)}
    print("\n### SUMMARY\n" + json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "runs"} for k, v in out.items()}, indent=2), flush=True)
    p = Path("~/autored/pilots/experiments/repeated_trials.json").expanduser()
    p.write_text(json.dumps(out, indent=2)); print(f"\nsaved {p}")

asyncio.run(main())
