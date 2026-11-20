"""Idempotency guard: record completed experiments so a resumed run does not
repeat a finished (or expensive, or state-changing) experiment. Compliant and
non-destructive — it only reads/writes a small local ledger."""
from __future__ import annotations
import argparse, hashlib, json, sys, time
from pathlib import Path

LEDGER = Path("~/autored/pilots/experiments/.completed.json").expanduser()

def _load(): return json.loads(LEDGER.read_text()) if LEDGER.exists() else {}
def _save(d): LEDGER.parent.mkdir(parents=True, exist_ok=True); LEDGER.write_text(json.dumps(d, indent=2))

def key(name: str, inputs: str) -> str:
    return f"{name}:{hashlib.sha1(inputs.encode()).hexdigest()[:10]}"

def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("done"); d.add_argument("name"); d.add_argument("--inputs", default="")
    c = sub.add_parser("check"); c.add_argument("name"); c.add_argument("--inputs", default="")
    sub.add_parser("status")
    a = ap.parse_args()
    led = _load()
    if a.cmd == "status":
        for k, v in led.items(): print(f"✓ {k}  {v['at']}")
        return 0
    k = key(a.name, a.inputs)
    if a.cmd == "check":
        print("DONE" if k in led else "PENDING"); return 0 if k in led else 1
    led[k] = {"name": a.name, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}; _save(led)
    print(f"recorded {k}"); return 0

if __name__ == "__main__":
    sys.exit(main())
