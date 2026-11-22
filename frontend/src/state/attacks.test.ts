import { describe, expect, it } from "vitest";
import events from "../__fixtures__/mission.events.json";
import type { AutoRedEvent } from "../contracts/events";
import { emptyMission, reduce } from "./missionReducer";
import { deriveAttacks } from "./attacks";

const evs = events as unknown as AutoRedEvent[];
const state = evs.reduce(reduce, emptyMission(evs[0].mission_id));

describe("deriveAttacks — real recorded mission (no invented data)", () => {
  const { groups, totals } = deriveAttacks(state);
  const byId = Object.fromEntries(groups.flatMap((g) => g.attacks).map((a) => [a.probe_id, a]));

  it("counts planned/executed/pending/skipped/confirmed from the event log", () => {
    expect(totals.planned).toBe(9);   // 8 assigned + 1 skipped
    expect(totals.executed).toBe(8);
    expect(totals.pending).toBe(0);   // recorded mission: nothing left pending
    expect(totals.skipped).toBe(1);
    expect(totals.confirmed).toBe(6);
  });

  it("groups every attack under its specialist", () => {
    expect(groups.map((g) => g.agent)).toEqual(["injection", "leakage", "hierarchy", "tools"]);
    expect(groups.find((g) => g.agent === "injection")!.attacks.map((a) => a.probe_id).sort()).toEqual(["PI-001", "PI-002", "PI-003"]);
    expect(groups.find((g) => g.agent === "tools")!.attacks.map((a) => a.probe_id).sort()).toEqual(["TP-001", "TP-002"]);
  });

  it("derives execution status truthfully", () => {
    expect(byId["PI-001"].exec).toBe("completed");
    expect(byId["IH-002"].exec).toBe("completed");
    expect(byId["TP-002"].exec).toBe("skipped");
    expect(byId["TP-002"].skipReason).toContain("not authorized");
    expect(byId["TP-002"].planned).toBe(true);
  });

  it("confirms a verdict only when a confirmed finding exists", () => {
    expect(byId["PI-001"].verdict).toBe("confirmed");
    expect(byId["IH-002"].verdict).toBe("not_confirmed");  // executed, not_observed
    expect(byId["PI-003"].verdict).toBe("not_confirmed");
    expect(byId["TP-002"].verdict).toBe("not_assessed");   // never executed
  });

  it("exposes the real prompt/response/finding for an executed attack", () => {
    expect(byId["PI-001"].prompt.length).toBeGreaterThan(0);
    expect(byId["PI-001"].response.length).toBeGreaterThan(0);
    expect(byId["PI-001"].finding?.status).toBe("confirmed");
    expect(byId["TP-002"].prompt).toBe("");                // nothing observed for a skipped probe
  });
});

describe("deriveAttacks — live mission distinguishes planned vs. executed", () => {
  it("marks a started probe running and an unstarted planned probe pending", () => {
    const s = emptyMission("M-LIVE");
    s.live = true;
    s.plan = { assignments: { injection: ["PI-001", "PI-009"] }, skipped: {} } as any;
    s.timeline = [{
      v: 1, id: "e1", seq: 1, mission_id: "M-LIVE", agent_id: "injection", ts: "",
      type: "test.started", payload: { probe_id: "PI-001", probe_name: "x", category: "injection", prompt: "p", attempt: 1 },
    } as AutoRedEvent];
    const { groups, totals } = deriveAttacks(s);
    const byId = Object.fromEntries(groups.flatMap((g) => g.attacks).map((a) => [a.probe_id, a]));
    expect(byId["PI-001"].exec).toBe("running");
    expect(byId["PI-009"].exec).toBe("pending");
    expect(byId["PI-009"].verdict).toBe("not_assessed");
    expect(totals.pending).toBe(2);
  });
});
