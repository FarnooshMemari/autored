import { useEffect, useState } from "react";
import type { AutoRedClient } from "../api/client";
import { Kpi, Section } from "../components/common";

export function SystemHealth({ client }: { client: AutoRedClient }) {
  const [h, setH] = useState<any | null>(null);
  useEffect(() => { const f = () => client.health().then(setH).catch(() => {}); f(); const t = setInterval(f, 3000); return () => clearInterval(t); }, [client]);
  if (!h) return <Section title="System Health"><div className="card pad">loading…</div></Section>;
  return (
    <Section title="System Health" sub="Live operational status from the backend.">
      <div className="grid" style={{ gridTemplateColumns: "repeat(4,1fr)", gap: 14, marginBottom: 14 }}>
        <Kpi value={h.ok ? "Online" : "Down"} label="Backend" color={h.ok ? "var(--ok)" : "var(--bad)"} small />
        <Kpi value={(h.active_missions ?? []).length} label="Active missions" small color="var(--accent)" />
        <Kpi value={h.total_missions ?? 0} label="Total missions" small />
        <Kpi value={h.emergency_stop ? "ENGAGED" : "Clear"} label="Emergency stop" color={h.emergency_stop ? "var(--bad)" : "var(--ok)"} small />
      </div>
      <div className="card pad" style={{ fontSize: 13 }}>
        <div className="row between"><span className="muted">Event schema version</span><code>v{h.schema_version}</code></div>
        <div className="row between" style={{ marginTop: 8 }}><span className="muted">Max concurrent missions</span><span>{h.max_active}</span></div>
        <div className="row between" style={{ marginTop: 8 }}><span className="muted">Headless browser</span><span>{String(h.headless)}</span></div>
        {h.emergency_stop && <div className="row between" style={{ marginTop: 8 }}><span className="muted">Stop reason</span><span className="sev-high">{h.emergency_stop_reason}</span></div>}
        {(h.active_missions ?? []).length > 0 && <div style={{ marginTop: 8 }}><span className="muted">Active:</span> {h.active_missions.map((m: string) => <code key={m} style={{ marginLeft: 6 }}>{m}</code>)}</div>}
      </div>
    </Section>
  );
}
