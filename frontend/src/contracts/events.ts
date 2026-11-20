/**
 * AutoRed event contract, schema v1. TypeScript mirror of
 * backend/autored/events/schema.py (canonical JSON Schema: contracts/events.schema.json).
 * Keep in sync; the parity test in state/missionReducer.test.ts replays a
 * real backend event log through this contract.
 */
export const SCHEMA_VERSION = 3;

export type AgentId = "commander" | "injection" | "leakage" | "hierarchy" | "tools";
export const SPECIALIST_IDS = ["injection", "leakage", "hierarchy", "tools"] as const;
export const ALL_AGENT_IDS: AgentId[] = ["commander", ...SPECIALIST_IDS];

export type AgentStatus =
  | "idle" | "starting" | "authenticating" | "discovering" | "planning" | "monitoring"
  | "navigating" | "testing" | "validating" | "waiting" | "done" | "error" | "stopped";

export type MissionPhase =
  | "created" | "discovery" | "planning" | "execution" | "consolidation"
  | "completed" | "aborted" | "failed";

export type Verdict = "vulnerable" | "suspected" | "not_observed" | "inconclusive" | "not_applicable" | "error";
export type FindingStatus = "candidate" | "confirmed" | "suspected" | "inconclusive";
export type Severity = "low" | "medium" | "high" | "critical";

export interface Box { x: number; y: number; width: number; height: number }

export interface Evidence {
  kind: "response_excerpt" | "canary" | "oracle" | "screenshot";
  detail: string;
  artifact: string | null;
}

export interface FindingPayload {
  finding_id: string;
  probe_id: string;
  category: string;
  title: string;
  severity: Severity;
  status: FindingStatus;
  evidence: Evidence[];
  attempts: number;
  reproductions: number;
  trials: number;
  successes: number;
  confirmation_rate: number;
  ci_low: number;
  ci_high: number;
  prompt: string;
}

export interface CapabilityPayload {
  assistant_detected: boolean;
  chat_url: string | null;
  tools: string[];
  selectors: Record<string, string>;
  raw_response: string;
}

export interface PlanPayload {
  assignments: Record<string, string[]>;
  skipped: Record<string, string>;
}

export interface MissionSummaryPayload {
  phase: MissionPhase;
  confirmed: number;
  suspected: number;
  inconclusive: number;
  passed: number;
  not_applicable: number;
  probes_run: number;
  llm_calls: number;
  agent_errors: number;
  duration_s: number;
  reason: string;
}

export interface PayloadByType {
  "mission.status": { phase: MissionPhase; message: string };
  "mission.completed": MissionSummaryPayload;
  "agent.status": { status: AgentStatus; activity: string; task_id: string | null };
  "task.assigned": { task_id: string; to_agent: AgentId; kind: "assess" | "validate"; title: string; probe_ids: string[]; reason: string };
  "task.completed": { task_id: string; kind: "assess" | "validate"; outcome: "completed" | "failed" | "cancelled" | "skipped"; detail: string };
  "commander.capabilities": CapabilityPayload;
  "commander.plan": PlanPayload;
  "browser.navigated": { url: string; title: string; context_id: string; viewport: { width: number; height: number } | null };
  "browser.action": { action: "click" | "fill" | "press" | "wait" | "read"; selector: string; value_preview: string; frame: string | null; box: Box | null };
  "browser.blocked": { url: string; reason: string };
  "test.started": { probe_id: string; probe_name: string; category: string; prompt: string; attempt: number };
  "test.response": { probe_id: string; response: string; latency_ms: number; attempt: number; box: Box | null };
  "test.verdict": { probe_id: string; verdict: Verdict; rationale: string; attempt: number };
  "finding.candidate": FindingPayload;
  "finding.updated": FindingPayload;
  log: { level: "debug" | "info" | "warning" | "error"; message: string };
}

export type EventType = keyof PayloadByType;

/** Discriminated union: narrowing on `type` narrows `payload`. */
export type AutoRedEvent = {
  [T in EventType]: {
    v: number;
    id: string;
    seq: number;
    mission_id: string;
    agent_id: AgentId;
    ts: string;
    type: T;
    payload: PayloadByType[T];
  };
}[EventType];

export interface AgentInfo { id: AgentId; name: string; role: string; color: string; kind: "commander" | "specialist"; slot: number }

export interface TargetInfo {
  id: string;
  name: string;
  base_url: string;
  authorization: { reference: string; approved_by: string; expires: string };
}
