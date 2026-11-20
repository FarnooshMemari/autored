import { expect, it } from "vitest";
import events from "../__fixtures__/mission.events.json";
import type { AutoRedEvent } from "../contracts/events";
import { emptyMission, reduce } from "./missionReducer";

it("derives cues from real events and ends idle-safe", () => {
  const evs = events as unknown as AutoRedEvent[];
  const seen = new Set<string>();
  let s = emptyMission(evs[0].mission_id);
  for (const e of evs) {
    s = reduce(s, e);
    seen.add(s.agents.injection.cue);
  }
  for (const cue of ["browsing", "typing", "awaiting", "alarmed", "done"]) expect(seen).toContain(cue);
  expect(s.agents.commander.cue).toBe("done");
});
