import { useEffect, useState } from "react";
import type { AutoRedClient } from "../api/client";
import { Empty, Section, sevClass } from "../components/common";

export function History({ client, onOpen }: { client: AutoRedClient; onOpen: (id: string) => void }) {
  const [missions, setMissions] = useState<any[]>([]);
  const [report, setReport] = useState<any | null>(null);
  const [sel, setSel] = useState<string | null>(null);
  const [loadingReport, setLoadingReport] = useState(false);
  useEffect(() => { client.missions().then(setMissions).catch(() => {}); }, [client]);

  const openReport = async (id: string) => {
    setSel(id); setLoadingReport(true); setReport(null);
    try { setReport(await client.missionReport(id)); } catch (e) { setReport({ error: String(e) }); } finally { setLoadingReport(false); }
  };
  const phaseClass = (p: string) => p === "completed" ? "ph-ok" : p === "interrupted" ? "ph-warn" : "ph-mut";

  return (
    <Section title="Mission History & Reporting" sub="Reopen completed and interrupted missions and generate reproducible reports.">
      <div className="history-grid">
        <div className="history-list">
          {missions.length === 0 ? <div className="card"><Empty>No missions.</Empty></div> :
            missions.map((m) => (
              <div key={m.mission_id} className={`rowcard ${sel === m.mission_id ? "sel" : ""}`}>
                <div className="rc-main">
                  <div className="rc-top">
                    <span className={`status-chip ${phaseClass(m.phase)}`}>{m.phase}</span>
                    <code className="rc-id">{m.mission_id}</code>
                  </div>
                  <div className="rc-sub">{m.target_id} · {m.mode ?? "—"}{m.source === "stored" ? " · stored" : ""}
                    {typeof m.confirmed === "number" && <span className="rc-conf"> · <strong className="st-confirmed">{m.confirmed}</strong> confirmed</span>}</div>
                </div>
                <div className="rc-actions">
                  <button className="btn sm ghost" onClick={() => onOpen(m.mission_id)}>Open</button>
                  <button className="btn sm" onClick={() => openReport(m.mission_id)}>Report</button>
                </div>
              </div>
            ))}
        </div>

        <div className="card pad report-panel">
          <div className="row between" style={{ marginBottom: 12 }}>
            <div className="eyebrow" style={{ margin: 0 }}>Reproducible report</div>
            {report && !report.error && <button className="btn sm" onClick={() => {
              const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
              const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `${report.mission_id}.report.json`; a.click();
            }}>↓ Download JSON</button>}
          </div>
          {loadingReport ? <Empty><span className="spinner" /> generating…</Empty> :
            !report ? <Empty>Select a mission and click “Report”.</Empty> :
            report.error ? <Empty><span className="sev-high">{report.error}</span></Empty> :
            <div>
              <code className="faint">{report.mission_id}</code>
              <div className="report-stats">
                {Object.entries((report.summary ?? {})).filter(([k]) => ["confirmed", "suspected", "inconclusive", "passed", "probes_run", "llm_calls"].includes(k))
                  .map(([k, v]) => <div key={k} className="stat-tile sm"><div className="stat-v">{String(v)}</div><div className="stat-l">{k.replace("_", " ")}</div></div>)}
              </div>
              <div className="console-lbl" style={{ margin: "16px 0 8px" }}>Confirmed findings</div>
              {(report.confirmed ?? []).length === 0 ? <div className="faint" style={{ fontSize: 13 }}>None confirmed on this mission.</div> :
                report.confirmed.map((f: any) => <div key={f.finding_id} className="report-finding">
                  <div className="row between" style={{ gap: 10 }}>
                    <strong className={sevClass(f.severity)}>{f.probe_id} — {f.title}</strong>
                    <span className="status-chip s-confirmed pct">{Math.round((f.confirmation_rate ?? 0) * 100)}%</span></div>
                  {(f.evidence ?? []).slice(0, 2).map((e: any, i: number) => <div key={i} className="mono faint" style={{ fontSize: 11.5, marginTop: 5 }}>{e.kind}: {e.detail?.slice(0, 140)}</div>)}
                </div>)}
            </div>}
        </div>
      </div>
    </Section>
  );
}
