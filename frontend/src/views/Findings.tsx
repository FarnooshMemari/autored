import { Fragment, useMemo, useState } from "react";
import type { AutoRedClient } from "../api/client";
import type { FindingPayload } from "../contracts/events";
import type { MissionState } from "../state/missionReducer";
import { Empty, Section, sevClass, stClass } from "../components/common";

const SEV_ORDER = { critical: 0, high: 1, medium: 2, low: 3 } as const;

function EvidenceInspector({ client, missionId, f }: { client: AutoRedClient; missionId: string; f: FindingPayload }) {
  const shot = f.evidence.find((e) => e.kind === "screenshot" && e.artifact);
  const strong = f.evidence.filter((e) => e.kind === "canary" || e.kind === "oracle");
  const reply = f.evidence.find((e) => e.kind === "response_excerpt");
  return (
    <div className="card pad" style={{ background: "var(--surface)", marginTop: -6, borderTop: 0, borderTopLeftRadius: 0, borderTopRightRadius: 0 }}>
      <div className="grid" style={{ gridTemplateColumns: "1.1fr 1fr", gap: 16 }}>
        <div>
          <div className="sub" style={{ marginBottom: 6 }}>Reproduction</div>
          <div className="card pad" style={{ background: "var(--surface-2)", marginBottom: 12 }}>
            <div className="row between"><span>Reproduced</span><strong>{f.reproductions}/{f.attempts} trials</strong></div>
            {f.trials > 0 && <div className="row between" style={{ marginTop: 6 }}><span className="muted">Confirmation rate</span>
              <strong>{Math.round(f.confirmation_rate * 100)}% <span className="faint" style={{ fontWeight: 400 }}>(95% CI {Math.round(f.ci_low * 100)}–{Math.round(f.ci_high * 100)}%)</span></strong></div>}
          </div>
          <div className="sub" style={{ marginBottom: 6 }}>Strong evidence</div>
          {strong.length === 0 ? <div className="faint">No strong evidence (not confirmed).</div> :
            strong.map((e, i) => <div key={i} className="card pad mono" style={{ fontSize: 11.5, marginBottom: 6, background: "var(--surface-2)" }}>
              <span className="st-confirmed">{e.kind}</span> — {e.detail}</div>)}
          <div className="sub" style={{ margin: "12px 0 6px" }}>Probe prompt</div>
          <div className="card pad mono" style={{ fontSize: 11.5, background: "var(--surface-2)" }}>{f.prompt || "—"}</div>
          {reply && <><div className="sub" style={{ margin: "12px 0 6px" }}>Assistant reply</div>
            <div className="card pad mono" style={{ fontSize: 11.5, background: "var(--surface-2)", maxHeight: 140, overflow: "auto" }}>{reply.detail}</div></>}
        </div>
        <div>
          <div className="sub" style={{ marginBottom: 6 }}>Screenshot evidence</div>
          {shot?.artifact ? <a href={client.artifactUrl(missionId, shot.artifact)} target="_blank" rel="noreferrer">
            <img src={client.artifactUrl(missionId, shot.artifact)} alt="evidence" style={{ width: "100%", borderRadius: 10, border: "1px solid var(--border)" }} />
          </a> : <div className="faint">No screenshot.</div>}
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
  const confirmed = findings.filter((f) => f.status === "confirmed");

  return (
    <Section title="Findings Explorer" sub={`Mission ${state.mission_id || "—"} · ${confirmed.length} confirmed of ${findings.length}`}>
      {findings.length === 0 ? <div className="card"><Empty>No findings yet. Findings appear as agents gather evidence.</Empty></div> :
        <div className="card">
          <table><thead><tr><th>Status</th><th>Severity</th><th>Category</th><th>Probe</th><th>Title</th><th>Reproduced</th><th></th></tr></thead>
            <tbody>{findings.map((f) => (
              <Fragment key={f.finding_id}>
                <tr style={{ cursor: "pointer" }} onClick={() => setOpen(open === f.finding_id ? null : f.finding_id)}>
                  <td><span className={stClass(f.status)} style={{ fontWeight: 700 }}>{f.status}</span></td>
                  <td><span className={sevClass(f.severity)} style={{ fontWeight: 600 }}>{f.severity}</span></td>
                  <td className="muted">{f.category}</td>
                  <td><code>{f.probe_id}</code></td>
                  <td>{f.title}</td>
                  <td>{f.reproductions}/{f.attempts}{f.trials > 0 && <span className="faint"> · {Math.round(f.confirmation_rate * 100)}%</span>}</td>
                  <td style={{ textAlign: "right" }}>{open === f.finding_id ? "▲" : "▾"}</td>
                </tr>
                {open === f.finding_id && <tr><td colSpan={7} style={{ padding: 0 }}><EvidenceInspector client={client} missionId={state.mission_id} f={f} /></td></tr>}
              </Fragment>
            ))}</tbody></table>
        </div>}
    </Section>
  );
}
