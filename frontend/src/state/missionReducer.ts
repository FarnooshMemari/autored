/**
 * Pure reducer: (state, event) -> state. Same rules as
 * backend/autored/missions/snapshot.py, plus UI-only fields (timeline, live
 * test I/O, animation cues). Initialize from GET /api/missions/{id}, then
 * apply WebSocket events with seq > last_seq.
 */
import type {
  AgentId, AgentStatus, AutoRedEvent, CapabilityPayload, FindingPayload, MissionPhase,
  MissionSummaryPayload, PlanPayload,
} from "../contracts/events";
import { ALL_AGENT_IDS } from "../contracts/events";
import { cueFor, type AnimationCue } from "./animationCues";

export interface TaskView { task_id: string; kind: string; title: string; probe_ids: string[]; outcome: string | null; detail: string }

export interface AgentView {
  agent_id: AgentId;
  status: AgentStatus;
  activity: string;
  task_id: string | null;
  url: string | null;
  context_id: string | null;
  probes_run: number;
  tasks: TaskView[];
  /** UI-only: last probe prompt/response for speech bubbles etc. */
  lastPrompt?: string;
  lastResponse?: string;
  /** UI-only: semantic animation intent for the character layer. */
  cue: AnimationCue;
}

export interface MissionState {
  mission_id: string;
  target_id: string;
  operator: string;
  phase: MissionPhase;
  message: string;
  agents: Record<AgentId, AgentView>;
  findings: Record<string, FindingPayload>;
  capabilities: CapabilityPayload | null;
  plan: PlanPayload | null;
  summary: MissionSummaryPayload | null;
  last_seq: number;
  /** UI-only: bounded event history for the mission timeline. */
  timeline: AutoRedEvent[];
}

export const TIMELINE_LIMIT = 1000;

/** Accepts the REST snapshot (which lacks UI-only fields). */
export function fromSnapshot(snap: Omit<MissionState, "timeline" | "agents"> & { agents: Record<string, Omit<AgentView, "cue">> }): MissionState {
  const agents = {} as Record<AgentId, AgentView>;
  for (const id of ALL_AGENT_IDS) {
    const a = snap.agents[id];
    agents[id] = { ...a, agent_id: id, cue: cueFor(a.status) };
  }
  return { ...snap, agents, timeline: [] };
}

export function emptyMission(mission_id: string): MissionState {
  const agents = {} as Record<AgentId, AgentView>;
  for (const id of ALL_AGENT_IDS)
    agents[id] = { agent_id: id, status: "idle", activity: "", task_id: null, url: null, context_id: null, probes_run: 0, tasks: [], cue: "idle" };
  return { mission_id, target_id: "", operator: "", phase: "created", message: "", agents, findings: {},
           capabilities: null, plan: null, summary: null, last_seq: 0, timeline: [] };
}

export function reduce(s: MissionState, e: AutoRedEvent): MissionState {
  if (e.seq <= s.last_seq) return s; // replay overlap: idempotent
  const agents = { ...s.agents };
  const a = { ...agents[e.agent_id] };
  agents[e.agent_id] = a;
  let next: MissionState = { ...s, agents, last_seq: e.seq, timeline: [...s.timeline, e].slice(-TIMELINE_LIMIT) };

  switch (e.type) {
    case "mission.status":
      next = { ...next, phase: e.payload.phase, message: e.payload.message };
      break;
    case "mission.completed":
      next = { ...next, summary: e.payload, phase: e.payload.phase };
      break;
    case "agent.status":
      Object.assign(a, { status: e.payload.status, activity: e.payload.activity, task_id: e.payload.task_id, cue: cueFor(e.payload.status) });
      break;
    case "task.assigned": {
      const to = { ...agents[e.payload.to_agent] };
      to.tasks = [...to.tasks, { task_id: e.payload.task_id, kind: e.payload.kind, title: e.payload.title, probe_ids: e.payload.probe_ids, outcome: null, detail: "" }];
      agents[e.payload.to_agent] = to;
      break;
    }
    case "task.completed":
      a.tasks = a.tasks.map((t) => (t.task_id === e.payload.task_id ? { ...t, outcome: e.payload.outcome, detail: e.payload.detail } : t));
      break;
    case "commander.capabilities":
      next = { ...next, capabilities: e.payload };
      break;
    case "commander.plan":
      next = { ...next, plan: e.payload };
      break;
    case "browser.navigated":
      Object.assign(a, { url: e.payload.url, context_id: e.payload.context_id, cue: "browsing" });
      break;
    case "browser.action":
      a.cue = e.payload.action === "fill" ? "typing" : e.payload.action === "wait" ? "awaiting" : a.cue;
      break;
    case "browser.blocked":
      a.cue = "blocked";
      break;
    case "test.started":
      a.lastPrompt = e.payload.prompt;
      break;
    case "test.response":
      a.lastResponse = e.payload.response;
      break;
    case "test.verdict":
      if (e.payload.verdict !== "not_applicable") a.probes_run += 1; // not executed
      if (e.payload.verdict === "vulnerable") a.cue = "alarmed";
      else if (e.payload.verdict === "suspected") a.cue = "thinking";
      break;
    case "finding.candidate":
    case "finding.updated":
      next = { ...next, findings: { ...s.findings, [e.payload.finding_id]: e.payload } };
      if (e.payload.status === "confirmed") a.cue = "confirmed";
      break;
  }
  return next;
}
