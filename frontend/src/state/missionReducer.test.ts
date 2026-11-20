import { describe, expect, it } from "vitest";
import events from "../__fixtures__/mission.events.json";
import expected from "../__fixtures__/mission.expected.json";
import type { AutoRedEvent } from "../contracts/events";
import { ALL_AGENT_IDS } from "../contracts/events";
import { emptyMission, fromSnapshot, reduce } from "./missionReducer";

const evs = events as unknown as AutoRedEvent[];
const replay = (list: AutoRedEvent[], s = emptyMission(evs[0].mission_id)) => list.reduce(reduce, s);

describe("missionReducer parity with backend snapshot", () => {
  const s = replay(evs);

  it("matches phase, summary and sequence", () => {
    expect(s.phase).toBe(expected.phase);
    expect(s.last_seq).toBe(expected.last_seq);
    expect(s.summary).toEqual(expected.summary);
    expect(s.plan).toEqual(expected.plan);
  });

  it("matches every agent's state and task history", () => {
    for (const id of ALL_AGENT_IDS) {
      const { cue, lastPrompt, lastResponse, viewport, lastBox, ...core } = s.agents[id];
      void cue; void lastPrompt; void lastResponse; void viewport; void lastBox;
      expect(core).toEqual((expected.agents as any)[id]);
    }
  });

  it("matches findings", () => {
    expect(s.findings).toEqual(expected.findings);
  });
});

describe("missionReducer resume semantics", () => {
  it("is idempotent under replay overlap (reconnect with since=)", () => {
    const half = Math.floor(evs.length / 2);
    const a = replay(evs.slice(0, half));
    const b = replay(evs.slice(half - 10), a); // 10 duplicate events
    expect(b.findings).toEqual(replay(evs).findings);
    expect(b.timeline.length).toBe(evs.length);
  });

  it("continues correctly from a REST snapshot", () => {
    const s = replay(evs.slice(-5), fromSnapshot({ ...(expected as any), last_seq: evs.at(-6)!.seq }));
    expect(s.phase).toBe(expected.phase);
  });
});
