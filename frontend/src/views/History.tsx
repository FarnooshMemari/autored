import { useEffect, useState } from "react";
import type { AutoRedClient } from "../api/client";
import { Empty, Section, sevClass, stClass } from "../components/common";

export function History({ client, onOpen }: { client: AutoRedClient; onOpen: (id: string) => void }) {
  const [missions, setMissions] = useState<any[]>([]);
  const [report, setReport] = useState<any | null>(null);
  const [loadingReport, setLoadingReport] = useState(false);
  useEffect(() => { client.missions().then(setMissions).catch(() => {}); }, [client]);

  const openReport = async (id: string) => {
    setLoadingReport(true); setReport(null);
    try { setReport(await client.missionReport(id)); } catch (e) { setReport({ error: String(e) }); } finally { setLoadingReport(false); }
  };

  return (
    <Section title="Mission History & Reporting" sub="Reopen completed missions and generate reproducible reports.">
      <div className="grid" style={{ gridTemplateColumns: "1fr 1.1fr", gap: 14 }}>
        <div className="card">
          {missions.length === 0 ? <Empty>No missions.</Empty> :
            <table><thead><tr><th>Mission</th><th>Phase</th><th></th></tr></thead>
              <tbody>{missions.map((m) => (
                <tr key={m.mission_id}>
                  <td><code>{m.mission_id}</code><div className="faint" style={{ fontSize: 11 }}>{m.target_id}</div></td>
                  <td><span className={m.phase === "completed" ? "st-confirmed" : "muted"}>{m.phase}</span></td>
                  <td style={{ textAlign: "right", whiteSpace: "nowrap" }}>
                    <button className="btn sm ghost" onClick={() => onOpen(m.mission_id)}>Open</button>{" "}
                    <button className="btn sm" onClick={() => openReport(m.mission_id)}>Report</button>
                  </td>
                </tr>
              ))}</tbody></table>}
        </div>
        <div className="card pad">
          <div className="row between" style={{ marginBottom: 10 }}><strong>Report</strong>
            {report && !report.error && <button className="btn sm" onClick={() => {
              const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
              const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `${report.mission_id}.report.json`; a.click();
            }}>↓ Download JSON</button>}
          </div>
          {loadingReport ? <Empty><span className="spinner" /> generating…</Empty> :
            !report ? <Empty>Select a mission and click “Report”.</Empty> :
            report.error ? <Empty><span className="sev-high">{report.error}</span></Empty> :
            <div style={{ fontSize: 13 }}>
              <code className="faint">{report.mission_id}</code>
              <div className="row wrap" style={{ gap: 8, margin: "10px 0" }}>
                {Object.entries((report.summary ?? {})).filter(([k]) => ["confirmed", "suspected", "inconclusive", "passed", "not_applicable", "probes_run", "llm_calls"].includes(k))
                  .map(([k, v]) => <span key={k} className="pill">{k}: {String(v)}</span>)}
              </div>
              <div className="sub" style={{ margin: "10px 0 6px" }}>Confirmed findings</div>
              {(report.confirmed ?? []).length === 0 ? <div className="faint">None confirmed.</div> :
                report.confirmed.map((f: any) => <div key={f.finding_id} className="card pad" style={{ background: "var(--surface-2)", marginBottom: 6 }}>
                  <div className="row between"><strong className={sevClass(f.severity)}>{f.probe_id} — {f.title}</strong><span className={stClass("confirmed")}>{Math.round((f.confirmation_rate ?? 0) * 100)}%</span></div>
                  {(f.evidence ?? []).map((e: any, i: number) => <div key={i} className="mono faint" style={{ fontSize: 11, marginTop: 4 }}>{e.kind}: {e.detail?.slice(0, 120)}</div>)}
                </div>)}
            </div>}
        </div>
      </div>
    </Section>
  );
}
