/**
 * Attack Tracker derivation — PURE, real-data-only.
 *
 * Reconstructs every planned attack and its true execution status + security
 * verdict from authoritative mission state: the Commander's plan
 * (assignments + skipped), the durable event log (test.started/response/verdict),
 * and reconciled findings. Nothing is invented: a probe is only "executed" if the
 * log shows it ran, and a verdict is only "confirmed" if a confirmed finding
 * exists. Works identically for live missions and recorded/historical replay.
 */
import type { AgentId, FindingPayload } from "../contracts/events";
import type { MissionState } from "./missionReducer";

export type ExecStatus = "pending" | "running" | "completed" | "skipped" | "failed";
export type AttackVerdict = "confirmed" | "not_confirmed" | "inconclusive" | "not_assessed";

export interface Attack {
  probe_id: string;
  agent: AgentId;
  title: string;
  planned: boolean;        // true = in the Commander plan (vs. adaptively chosen)
  exec: ExecStatus;
  verdict: AttackVerdict;
  prompt: string;
  response: string;
  finding?: FindingPayload;
  skipReason?: string;
  rawVerdict?: string;     // underlying probe verdict (vulnerable / not_observed / …)
}

export interface AttackGroup { agent: AgentId; attacks: Attack[] }
export interface AttackTotals { planned: number; executed: number; pending: number; confirmed: number; skipped: number }
export interface AttackTrackerData { groups: AttackGroup[]; totals: AttackTotals }

const SPECIALISTS: AgentId[] = ["injection", "leakage", "hierarchy", "tools"];
const PREFIX_AGENT: Record<string, AgentId> = { PI: "injection", DL: "leakage", IH: "hierarchy", TP: "tools" };
const VERDICT_ORDER: Record<AttackVerdict, number> = { confirmed: 0, inconclusive: 1, not_confirmed: 2, not_assessed: 3 };

export function deriveAttacks(state: MissionState): AttackTrackerData {
  const assignments = (state.plan?.assignments ?? {}) as Record<string, string[]>;
  const skipped = (state.plan?.skipped ?? {}) as Record<string, string>;

  // probe_id -> representative finding (prefer confirmed)
  const findingByProbe: Record<string, FindingPayload> = {};
  for (const f of Object.values(state.findings)) {
    const cur = findingByProbe[f.probe_id];
    if (!cur || (f.status === "confirmed" && cur.status !== "confirmed")) findingByProbe[f.probe_id] = f;
  }

  // per-probe facts from the authoritative event log
  type Rec = { prompt?: string; response?: string; verdict?: string; started?: boolean; agent?: string; name?: string };
  const rec: Record<string, Rec> = {};
  const get = (id: string) => (rec[id] ??= {});
  for (const e of state.timeline) {
    const p: any = e.payload;
    if (e.type === "test.started") { const r = get(p.probe_id); if (r.prompt === undefined) r.prompt = p.prompt; r.started = true; r.agent ??= p.category; r.name ??= p.probe_name; }
    else if (e.type === "test.response") { get(p.probe_id).response = p.response; }
    else if (e.type === "test.verdict") { get(p.probe_id).verdict = p.verdict; }
  }

  const isPlanned = (id: string) => Object.values(assignments).some((arr) => arr.includes(id)) || id in skipped;
  const agentOf = (id: string): AgentId => {
    for (const a of SPECIALISTS) if ((assignments[a] ?? []).includes(id)) return a;
    const r = rec[id];
    if (r?.agent && (SPECIALISTS as string[]).includes(r.agent)) return r.agent as AgentId;
    const f = findingByProbe[id];
    if (f && (SPECIALISTS as string[]).includes(f.category)) return f.category as AgentId;
    return PREFIX_AGENT[id.split("-")[0]] ?? "injection";
  };

  const ids = new Set<string>();
  for (const a of SPECIALISTS) for (const id of assignments[a] ?? []) ids.add(id);
  for (const id of Object.keys(skipped)) ids.add(id);
  for (const id of Object.keys(rec)) ids.add(id);

  const attacks: Attack[] = [];
  for (const id of ids) {
    const r = rec[id] ?? {};
    const v = r.verdict;
    const f = findingByProbe[id];

    let exec: ExecStatus;
    if (v === "error") exec = "failed";
    else if (v === "not_applicable") exec = "skipped";
    else if (v) exec = "completed";
    else if (r.started) exec = "running";
    else exec = (id in skipped || !state.live) ? "skipped" : "pending";

    let verdict: AttackVerdict;
    if (exec !== "completed") verdict = "not_assessed";
    else if (f?.status === "confirmed") verdict = "confirmed";
    else if (v === "not_observed") verdict = "not_confirmed";
    else verdict = "inconclusive";

    attacks.push({
      probe_id: id, agent: agentOf(id),
      title: f?.title ?? r.name ?? id,
      planned: isPlanned(id), exec, verdict,
      prompt: f?.prompt || r.prompt || "",
      response: f?.evidence.find((e) => e.kind === "response_excerpt")?.detail || r.response || "",
      finding: f, skipReason: skipped[id], rawVerdict: v,
    });
  }

  const groups: AttackGroup[] = SPECIALISTS.map((agent) => ({
    agent,
    attacks: attacks.filter((a) => a.agent === agent)
      .sort((a, b) => VERDICT_ORDER[a.verdict] - VERDICT_ORDER[b.verdict] || a.probe_id.localeCompare(b.probe_id)),
  }));
  const totals: AttackTotals = {
    planned: attacks.length,
    executed: attacks.filter((a) => a.exec === "completed").length,
    pending: attacks.filter((a) => a.exec === "pending" || a.exec === "running").length,
    confirmed: attacks.filter((a) => a.verdict === "confirmed").length,
    skipped: attacks.filter((a) => a.exec === "skipped").length,
  };
  return { groups, totals };
}
