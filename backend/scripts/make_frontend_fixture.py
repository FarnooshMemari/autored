"""Turn a real mission's events.jsonl into frontend parity fixtures.
Usage: python scripts/make_frontend_fixture.py runs/<mission>/events.jsonl"""
import json
import sys
from pathlib import Path

from autored.events.schema import Event
from autored.missions.snapshot import MissionSnapshot

src = Path(sys.argv[1])
events = [Event.model_validate_json(l) for l in src.read_text().splitlines() if l.strip()]
snap = MissionSnapshot.new(events[0].mission_id, "acmehelp-local", "dev")
for e in events:
    snap.apply(e)
out = Path(__file__).resolve().parents[2] / "frontend" / "src" / "__fixtures__"
out.mkdir(parents=True, exist_ok=True)
(out / "mission.events.json").write_text(json.dumps([e.model_dump(mode="json") for e in events], indent=1))
(out / "mission.expected.json").write_text(snap.model_dump_json(indent=1))
print(f"{len(events)} events -> {out}")
