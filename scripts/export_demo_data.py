import json, os, shutil, urllib.request, sys

API = "http://127.0.0.1:8000"
RUNS = os.path.expanduser("~/autored/runs")
OUT = os.path.expanduser("~/autored/frontend/public/demo")
MISSIONS = [
    "M-20261122-173200-e6a4",   # showcase, completed, 6 confirmed (default)
    "M-INTERRUPTED-DEMO-01",     # interrupted — recovery
    "M-20261120-125758-ba8f",    # completed, 6 confirmed
    "M-20261120-004519-e37c",    # completed, 6 confirmed
]
# values that must never appear in published data
FORBIDDEN = ["mousavizadeh1365@gmail.com"]

def get(path):
    with urllib.request.urlopen(API + path) as r:
        return json.load(r)

def write(rel, obj):
    p = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        json.dump(obj, f)

if os.path.isdir(OUT):
    shutil.rmtree(OUT)
os.makedirs(OUT, exist_ok=True)

# --- global data ---
agents = get("/api/agents")
write("agents.json", agents)

# targets: keep only UI fields (id, name, base_url, authorization)
targets = get("/api/targets")
targets = [{"id": t["id"], "name": t["name"], "base_url": t.get("base_url"),
            "authorization": t.get("authorization")} for t in targets]
write("targets.json", targets)

# health: safe static snapshot (no live polling in demo)
write("health.json", {"ok": True, "schema_version": 4, "emergency_stop": False,
      "emergency_stop_reason": "", "active_missions": [], "total_missions": len(MISSIONS),
      "max_active": 1, "headless": True})

write("experiments.json", get("/api/experiments"))

# --- per-mission detail (curated + list) ---
all_missions = {m["mission_id"]: m for m in get("/api/missions")}
listing = []
for mid in MISSIONS:
    snap = get(f"/api/missions/{mid}")
    events = get(f"/api/missions/{mid}/events")
    report = get(f"/api/missions/{mid}/report")
    findings = get(f"/api/missions/{mid}/findings")
    write(f"missions/{mid}/snapshot.json", snap)
    write(f"missions/{mid}/events.json", events)
    write(f"missions/{mid}/report.json", report)
    write(f"missions/{mid}/findings.json", findings)
    # copy screenshot artifacts referenced by findings
    adir = os.path.join(RUNS, mid, "artifacts")
    names = {e["artifact"] for f in findings for e in f["evidence"]
             if e["kind"] == "screenshot" and e.get("artifact")}
    for n in names:
        src = os.path.join(adir, n)
        if os.path.isfile(src):
            dst = os.path.join(OUT, "missions", mid, "artifacts", n)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy(src, dst)
    row = all_missions.get(mid, {})
    listing.append({"mission_id": mid, "target_id": snap.get("target_id"),
        "phase": snap.get("phase"), "active": False, "mode": row.get("mode"),
        "confirmed": row.get("confirmed"), "source": row.get("source")})
write("missions.json", listing)

# --- sanitization gate ---
blob = ""
for root, _, files in os.walk(OUT):
    for fn in files:
        if fn.endswith(".json"):
            with open(os.path.join(root, fn)) as f:
                blob += f.read()
bad = [s for s in FORBIDDEN if s in blob]
if bad:
    print("ABORT: forbidden string(s) found in export:", bad); sys.exit(1)

# report size
total = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(OUT) for f in fs)
nfiles = sum(len(fs) for _, _, fs in os.walk(OUT))
print(f"OK: exported {len(MISSIONS)} missions, {nfiles} files, {total/1024:.0f} KB")
print("sanitization gate: no forbidden strings found")
