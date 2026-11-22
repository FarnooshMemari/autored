import { useMemo, useState } from "react";
import type { AutoRedClient } from "../api/client";
import type { AgentId, AgentInfo, AutoRedEvent, FindingPayload } from "../contracts/events";
import { SPECIALIST_IDS } from "../contracts/events";
import type { AgentView, MissionState } from "../state/missionReducer";
import { useAgentFrame } from "../state/useMission";
import { AgentCharacter } from "../components/AgentCharacter";
import { Pill, Section } from "../components/common";

const BUSY = new Set(["thinking", "browsing", "typing", "awaiting"]);
const DONE = new Set(["idle", "done", "error", "stopped", "waiting"]);
const SEV_ORDER = { critical: 0, high: 1, medium: 2, low: 3 } as const;
const POS: Record<string, { x: number; y: number }> = {
  commander: { x: 50, y: 50 },
  injection: { x: 16, y: 25 }, leakage: { x: 84, y: 25 },
  hierarchy: { x: 16, y: 79 }, tools: { x: 84, y: 79 },
};

const describe = (e: AutoRedEvent): string => {
  const p: any = e.payload;
  switch (e.type) {
    case "test.verdict": return `${p.probe_id} → ${p.verdict}`;
    case "test.started": return `${p.probe_id}: ${p.prompt.slice(0, 64)}`;
    case "finding.candidate": case "finding.updated": return `${p.status} ${p.probe_id}: ${p.title}`;
    case "task.assigned": return `→ ${p.to_agent}: ${p.title}`;
    case "browser.blocked": return `BLOCKED ${p.url}`;
    case "agent.status": return p.activity;
    case "mission.status": return `${p.phase}: ${p.message}`;
    case "mission.completed": return `${p.phase} — ${p.confirmed} confirmed`;
    case "commander.plan": return `plan: ${Object.values(p.assignments).flat().length} probes`;
    case "log": return `[${p.level}] ${p.message}`;
    default: return e.type;
  }
};

/** Authentic ATTACK → OBSERVED → VERDICT pipeline for the selected specialist. */
function EvidencePipeline({ client, missionId, agent, info, findings, live, onViewShot }:
  { client: AutoRedClient; missionId: string; agent: AgentView; info?: AgentInfo; findings: FindingPayload[]; live: boolean; onViewShot: (a: string) => void }) {
  const sorted = [...findings].sort((a, b) =>
    (a.status === "confirmed" ? 0 : 1) - (b.status === "confirmed" ? 0 : 1) || SEV_ORDER[a.severity] - SEV_ORDER[b.severity]);
  const [fid, setFid] = useState<string | null>(null);
  const f = sorted.find((x) => x.finding_id === fid) ?? sorted[0];
  const color = info?.color ?? "var(--accent)";

  const attack = f?.prompt || agent.lastPrompt || "—";
  const observed = f?.evidence.find((e) => e.kind === "response_excerpt")?.detail || agent.lastResponse || (agent.status === "idle" ? "—" : "…");
  const proof = [...new Map((f?.evidence.filter((e) => e.kind === "canary" || e.kind === "oracle") ?? [])
    .map((e) => [e.detail, e])).values()];
  const shot = f?.evidence.find((e) => e.kind === "screenshot" && e.artifact)?.artifact ?? undefined;
  const liveSrc = useAgentFrame(client, live ? missionId : null, agent.agent_id);
  const previewSrc = live ? liveSrc : (shot ? client.artifactUrl(missionId, shot) : null);
  const vstat = f ? f.status : "not observed";

  return (
    <div className="pipe">
      {sorted.length > 1 && <div className="pipe-switch">
        {sorted.map((x) => <button key={x.finding_id} className={`pipe-chip st-${x.status} ${x === f ? "on" : ""}`}
          onClick={() => setFid(x.finding_id)} title={x.title}><code>{x.probe_id}</code></button>)}
      </div>}

      <div className="pipe-stage" style={{ ["--ac" as any]: color }}>
        <div className="pipe-k" style={{ color }}>ATTACK</div>
        <div className="pipe-v">{attack}</div>
      </div>
      <div className="pipe-flow"><span /></div>
      <div className="pipe-stage">
        <div className="pipe-k">OBSERVED</div>
        <div className="pipe-v">{observed}</div>
        {proof.length > 0 && <div className="pipe-proof">{proof.map((e, i) =>
          <span key={i} className="proof-chip">{e.kind}: {e.detail}</span>)}</div>}
      </div>
      <div className="pipe-flow"><span /></div>
      <div className={`pipe-verdict v-${f ? f.status : "clear"}`}>
        <div className="verdict-badge">{vstat.replace("_", " ")}</div>
        <div className="verdict-body">
          <div className="verdict-title">{f ? f.title : "No vulnerability observed on this surface."}</div>
          <div className="verdict-meta">
            {f ? <>
              <span className={`sev-${f.severity}`} style={{ fontWeight: 700, textTransform: "uppercase" }}>{f.severity}</span>
              <span className="muted"> · {f.reproductions}/{f.attempts} reproduced</span>
              {f.trials > 0 && <span className="muted"> · {Math.round(f.confirmation_rate * 100)}% confirmed <span className="faint">(95% CI {Math.round(f.ci_low * 100)}–{Math.round(f.ci_high * 100)}%)</span></span>}
            </> : <span className="muted">{agent.probes_run} probes executed · controls passed</span>}
          </div>
        </div>
      </div>

      <div className="evidence-shot">
        <div className="shot-bar"><span className="dots"><i /><i /><i /></span>
          <code className="monitor-url">{agent.url ?? "about:blank"}</code>
          {previewSrc && <button className="btn sm ghost shot-expand" onClick={() => onViewShot(previewSrc)}>⤢ Full viewer</button>}</div>
        <div className="shot-preview" onClick={() => previewSrc && onViewShot(previewSrc)}>
          {previewSrc ? <img src={previewSrc} alt="browser evidence" />
            : <div className="monitor-empty">{live && agent.status !== "idle" ? <><span className="spinner" /> connecting…</> : "No browser capture for this agent."}</div>}
        </div>
      </div>
    </div>
  );
}

function CommanderConsole({ state, info }: { state: MissionState; info: Record<string, AgentInfo | undefined> }) {
  const assignments = (state.plan?.assignments ?? {}) as Record<string, string[]>;
  return (
    <div className="console">
      <div className="console-head">
        <div className="eyebrow">Commander decision</div>
        <div className="console-msg">{state.message || (state.summary ? "Mission complete — findings reconciled." : "Standing by.")}</div>
      </div>
      {state.capabilities && <div className="console-caps">
        <span className="console-lbl">Observed surface</span>
        <div className="row wrap" style={{ gap: 7 }}>
          {(state.capabilities.tools ?? []).slice(0, 10).map((t) => <span key={t} className="chip">{t}</span>)}
          {(!state.capabilities.tools || state.capabilities.tools.length === 0) && <span className="faint">no tools advertised</span>}
        </div>
      </div>}
      <div className="console-assign">
        <span className="console-lbl">Delegation</span>
        {SPECIALIST_IDS.map((id) => {
          const probes = assignments[id] ?? []; const a = state.agents[id];
          return (
            <div key={id} className="assign-row" style={{ ["--ac" as any]: info[id]?.color }}>
              <span className="assign-dot" />
              <span className="assign-name">{info[id]?.name ?? id}</span>
              <span className="assign-probes">{probes.length ? `${probes.length} assigned` : `${a.probes_run} probes`}</span>
              <span className={`assign-state st-${a.status === "done" ? "confirmed" : "candidate"}`}>{a.status}</span>
            </div>
          );
        })}
        {Object.keys(assignments).length === 0 && <div className="faint" style={{ fontSize: 12.5 }}>Plan not yet issued.</div>}
      </div>
    </div>
  );
}

export function Operations({ client, state, agents, onStop }:
  { client: AutoRedClient; state: MissionState; agents: AgentInfo[]; onStop: () => void }) {
  const [inspect, setInspect] = useState<AgentId>("injection");
  const [viewer, setViewer] = useState<string | null>(null);
  const info = useMemo(() => Object.fromEntries(agents.map((a) => [a.id, a])), [agents]);

  const fs = Object.values(state.findings);
  const nStatus = (st: string) => fs.filter((f) => f.status === st).length;
  const probes = Object.values(state.agents).reduce((a, x) => a + x.probes_run, 0);
  const feed = state.timeline.filter((e) => !["browser.action"].includes(e.type)).slice(-80).reverse();
  const ids = ["commander", ...SPECIALIST_IDS] as AgentId[];
  const activeFor = (id: AgentId) => BUSY.has(state.agents[id].cue) || !DONE.has(state.agents[id].status);

  return (
    <>
      <Section title="Live Operations" sub={`Mission ${state.mission_id || "—"} · ${state.target_id}`}
        actions={<div className="row" style={{ gap: 10 }}>
          <Pill color={state.live ? "var(--accent)" : state.phase === "interrupted" ? "var(--warn)" : "var(--muted)"}>
            {(state.live ? "● LIVE" : "RECORDED") + " · " + state.phase.toUpperCase()}</Pill>
          {state.live && <button className="btn sm danger" onClick={onStop}>■ Stop</button>}
        </div>}>

        <div className="card constellation">
          <div className="const-stage">
            <svg className="wires" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
              {SPECIALIST_IDS.map((id) => {
                const p = POS[id]; const c = info[id]?.color ?? "#888"; const on = activeFor(id);
                return <line key={id} x1="50" y1="50" x2={p.x} y2={p.y} stroke={c}
                  strokeOpacity={on ? 0.95 : 0.3} strokeWidth={on ? 0.8 : 0.5}
                  className={`wire ${on ? "live" : ""}`} />;
              })}
            </svg>
            {SPECIALIST_IDS.map((id) => {
              const p = POS[id]; const n = state.agents[id].probes_run; if (!n) return null;
              return <span key={id} className="wire-label" style={{ left: `${(50 + p.x) / 2}%`, top: `${(50 + p.y) / 2}%`, color: info[id]?.color }}>{n} probes</span>;
            })}
            {ids.map((id) => {
              const a = state.agents[id]; const i = info[id]; const p = POS[id]; const on = activeFor(id);
              const lead = id === "commander";
              return (
                <button key={id} type="button"
                  className={`node ${inspect === id ? "sel" : ""} ${lead ? "lead" : ""} ${on ? "on" : ""}`}
                  style={{ left: `${p.x}%`, top: `${p.y}%`, ["--ac" as any]: i?.color }}
                  onClick={() => setInspect(id)} title={`Inspect ${i?.name ?? id}`}>
                  <AgentCharacter color={i?.color ?? "#888"} cue={a.cue} size={lead ? 104 : 82} name={i?.name} agentId={id} />
                  <span className="node-name">{i?.name ?? id}</span>
                  <span className="node-status" style={{ color: on ? i?.color : "var(--faint)" }}>{lead ? "orchestrating" : a.status}</span>
                </button>
              );
            })}
          </div>
          <div className="const-stats">
            {[
              { label: "Confirmed", value: nStatus("confirmed"), color: "var(--ok)" },
              { label: "Suspected", value: nStatus("suspected"), color: "var(--warn)" },
              { label: "Inconclusive", value: nStatus("inconclusive"), color: "var(--muted)" },
              { label: "Probes", value: probes },
              { label: state.summary ? "Duration" : "Phase", value: state.summary ? `${state.summary.duration_s}s` : state.phase },
              { label: "LLM calls", value: state.summary?.llm_calls ?? 0 },
            ].map((s) => (
              <div key={s.label} className="cstat">
                <div className="cstat-v" style={s.color ? { color: s.color } : undefined}>{s.value}</div>
                <div className="cstat-l">{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </Section>

      <Section title="Inspection workspace" sub="Select an agent to inspect its real attack, the observed behaviour and the adjudicated verdict.">
        <div className="workspace">
          <div className="ws-rail">
            {ids.map((id) => {
              const a = state.agents[id]; const i = info[id];
              const af = fs.filter((f) => f.category === id);
              const conf = af.filter((f) => f.status === "confirmed").length;
              return (
                <button key={id} type="button" className={`ws-item ${inspect === id ? "sel" : ""}`}
                  style={{ ["--ac" as any]: i?.color }} onClick={() => setInspect(id)}>
                  <AgentCharacter color={i?.color ?? "#888"} cue={a.cue} size={46} name={i?.name} agentId={id} />
                  <div className="ws-item-main">
                    <div className="ws-item-top"><span className="ws-item-name">{i?.name ?? id}</span>
                      {conf > 0 && <span className="ws-badge">{conf}</span>}</div>
                    <div className="ws-item-sub">{a.activity || a.status}</div>
                  </div>
                  <span className="ws-count">{a.probes_run}</span>
                </button>
              );
            })}
          </div>
          <div className="ws-main">
            {inspect === "commander"
              ? <CommanderConsole state={state} info={info} />
              : <EvidencePipeline client={client} missionId={state.mission_id} agent={state.agents[inspect]}
                  info={info[inspect]} findings={fs.filter((f) => f.category === inspect)} live={state.live} onViewShot={setViewer} />}
          </div>
        </div>
      </Section>

      <Section title="Activity timeline">
        <div className="card timeline">
          {feed.length === 0 ? <div className="empty">No activity yet.</div> : feed.map((e) => (
            <div key={e.id} className="tl-row" style={{ ["--ac" as any]: info[e.agent_id]?.color ?? "var(--faint)" }}>
              <span className="tl-dot" />
              <code className="tl-time">{new Date(e.ts).toLocaleTimeString()}</code>
              <span className="tl-agent" style={{ color: info[e.agent_id]?.color }}>{info[e.agent_id]?.name ?? e.agent_id}</span>
              <span className="tl-text">{describe(e)}</span>
            </div>
          ))}
        </div>
      </Section>

      {viewer && <div className="viewer" onClick={() => setViewer(null)}>
        <div className="viewer-bar"><span className="muted">Browser evidence — original capture</span>
          <button className="btn sm" onClick={() => setViewer(null)}>✕ Close</button></div>
        <img src={viewer} alt="full browser evidence" onClick={(e) => e.stopPropagation()} />
      </div>}
    </>
  );
}
