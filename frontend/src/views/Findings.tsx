import { useMemo, useState } from "react";
import type { AutoRedClient } from "../api/client";
import type { FindingPayload } from "../contracts/events";
import type { MissionState } from "../state/missionReducer";
import { Empty, Section } from "../components/common";

const SEV_ORDER = { critical: 0, high: 1, medium: 2, low: 3 } as const;
const AGENT_COLOR: Record<string, string> = {
  injection: "#a855f7", leakage: "#f97316", hierarchy: "#3b82f6", tools: "#22c55e", commander: "#9aa4b2",
};
const AGENT_NAME: Record<string, string> = {
  injection: "Inky", leakage: "Vault", hierarchy: "Lexi", tools: "Guard", commander: "Commander",
};

function Evidence({ client, missionId, f }: { client: AutoRedClient; missionId: string; f: FindingPayload }) {
  const shot = f.evidence.find((e) => e.kind === "screenshot" && e.artifact);
  const strong = [...new Map(f.evidence.filter((e) => e.kind === "canary" || e.kind === "oracle").map((e) => [e.detail, e])).values()];
  const reply = f.evidence.find((e) => e.kind === "response_excerpt");
  const color = AGENT_COLOR[f.category] ?? "var(--accent)";
  return (
    <div className="fc-body">
      <div className="fc-grid">
        <div className="fc-pipe">
          <div className="pipe-stage" style={{ ["--ac" as any]: color }}>
            <div className="pipe-k" style={{ color }}>ATTACK · {f.probe_id}</div>
            <div className="pipe-v">{f.prompt || "—"}</div>
          </div>
          <div className="pipe-flow"><span /></div>
          <div className="pipe-stage">
            <div className="pipe-k">OBSERVED</div>
            <div className="pipe-v">{reply?.detail || "—"}</div>
            {strong.length > 0 && <div className="pipe-proof">{strong.map((e, i) =>
              <span key={i} className="proof-chip">{e.kind}: {e.detail}</span>)}</div>}
          </div>
          <div className="pipe-flow"><span /></div>
          <div className={`pipe-verdict v-${f.status}`}>
            <div className="verdict-badge">{f.status}</div>
            <div className="verdict-body">
              <div className="verdict-title">{f.title}</div>
              <div className="verdict-meta">
                <span className={`sev-${f.severity}`} style={{ fontWeight: 700, textTransform: "uppercase" }}>{f.severity}</span>
                <span className="muted"> · {f.reproductions}/{f.attempts} reproduced</span>
                {f.trials > 0 && <span className="muted"> · {Math.round(f.confirmation_rate * 100)}% confirmed <span className="faint">(95% CI {Math.round(f.ci_low * 100)}–{Math.round(f.ci_high * 100)}%)</span></span>}
              </div>
            </div>
          </div>
        </div>
        <div className="fc-shot">
          <div className="pipe-k">Browser evidence</div>
          {shot?.artifact
            ? <a href={client.artifactUrl(missionId, shot.artifact)} target="_blank" rel="noreferrer" className="fc-shot-link">
                <img src={client.artifactUrl(missionId, shot.artifact)} alt="evidence" /><span>⤢ open original</span></a>
            : <div className="fc-shot-empty">No screenshot captured.</div>}
        </div>
      </div>
    </div>
  );
}

export function Findings({ client, state }: { client: AutoRedClient; state: MissionState }) {
  const [open, setOpen] = useState<string | null>(null);
  const findings = useMemo(() => Object.values(state.findings).sort(
    (a, b) => (a.status === "confirmed" ? 0 : 1) - (b.status === "confirmed" ? 0 : 1) ||
      SEV_ORDER[a.severity] - SEV_ORDER[b.severity]), [state.findings]);
  const count = (s: string) => findings.filter((f) => f.status === s).length;

  return (
    <Section title="Findings Explorer" sub={`Mission ${state.mission_id || "—"} — every finding traces attack → observed behaviour → adjudicated verdict.`}>
      {findings.length === 0 ? <div className="card"><Empty>No findings yet. Findings appear as agents gather evidence.</Empty></div> : <>
        <div className="findings-stats">
          {[{ l: "Confirmed", v: count("confirmed"), c: "var(--ok)" },
            { l: "Suspected", v: count("suspected"), c: "var(--warn)" },
            { l: "Inconclusive", v: count("inconclusive"), c: "var(--muted)" },
            { l: "Total findings", v: findings.length }].map((s) => (
            <div key={s.l} className="stat-tile"><div className="stat-v" style={s.c ? { color: s.c } : undefined}>{s.v}</div><div className="stat-l">{s.l}</div></div>
          ))}
        </div>
        <div className="findings-list">
          {findings.map((f) => {
            const color = AGENT_COLOR[f.category] ?? "var(--accent)";
            const isOpen = open === f.finding_id;
            return (
              <div key={f.finding_id} className={`finding-card ${isOpen ? "open" : ""}`} style={{ ["--ac" as any]: color }}>
                <button className="fc-head" onClick={() => setOpen(isOpen ? null : f.finding_id)}>
                  <span className={`status-chip s-${f.status}`}>{f.status}</span>
                  <span className={`sev-chip sev-${f.severity}`}>{f.severity}</span>
                  <span className="fc-title">{f.title}</span>
                  <span className="cat-pill" style={{ color }}><span className="d" />{AGENT_NAME[f.category] ?? f.category}</span>
                  <code className="fc-probe">{f.probe_id}</code>
                  <span className="fc-repro">{f.reproductions}/{f.attempts}{f.trials > 0 && <span className="faint"> · {Math.round(f.confirmation_rate * 100)}%</span>}</span>
                  <span className="fc-chev">{isOpen ? "▲" : "▾"}</span>
                </button>
                {isOpen && <Evidence client={client} missionId={state.mission_id} f={f} />}
              </div>
            );
          })}
        </div>
      </>}
    </Section>
  );
}
