import asyncio, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from harness import run_once, warm, set_hardened

SCOPE = str(Path("~/autored/ext/owui-tools-scope.yaml").expanduser())

async def main():
    results = {}
    for hardened in (False, True):
        label = "hardened" if hardened else "vulnerable"
        set_hardened(hardened); warm()
        print(f"\n### Running {label} ...", flush=True)
        results[label] = await run_once(SCOPE, "owui-tools", label)
        print(json.dumps(results[label], indent=2), flush=True)
    set_hardened(False)
    # analysis
    v, h = results["vulnerable"], results["hardened"]
    vset = {c["probe"] for c in v["confirmed"]}; hset = {c["probe"] for c in h["confirmed"]}
    analysis = {
        "vulnerable_confirmed": sorted(vset), "hardened_confirmed": sorted(hset),
        "true_positives": sorted(vset), "false_positives_hardened": sorted(hset),
        "detected_vuln_not_in_hardened": sorted(vset - hset),
    }
    print("\n### ANALYSIS\n" + json.dumps(analysis, indent=2), flush=True)
    out = Path("~/autored/pilots/experiments").expanduser(); out.mkdir(parents=True, exist_ok=True)
    (out / "vuln_vs_hardened.json").write_text(json.dumps({"results": results, "analysis": analysis}, indent=2))
    print("\nsaved to pilots/experiments/vuln_vs_hardened.json")

asyncio.run(main())
