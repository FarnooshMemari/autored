import { useEffect, useState } from "react";
import type { AutoRedClient } from "../api/client";
import { Section } from "../components/common";

export function SystemHealth({ client }: { client: AutoRedClient }) {
  const [h, setH] = useState<any | null>(null);
  useEffect(() => {
    const f = () => client.health().then(setH).catch(() => setH({ ok: false }));
    f(); if (client.isDemo) return; const t = setInterval(f, 3000); return () => clearInterval(t);
  }, [client]);
  if (!h) return <Section title="System Health"><div className="card pad">loading…</div></Section>;

  const tiles = [
    { v: client.isDemo ? "Demo" : h.ok ? "Online" : "Down", l: "Environment", c: h.ok ? "var(--ok)" : "var(--bad)" },
    { v: (h.active_missions ?? []).length, l: "Active missions", c: "var(--accent)" },
    { v: h.total_missions ?? 0, l: "Total missions" },
    { v: h.emergency_stop ? "Engaged" : "Clear", l: "Emergency stop", c: h.emergency_stop ? "var(--bad)" : "var(--ok)" },
  ];
  return (
    <Section title="System Health" sub={client.isDemo ? "Recorded snapshot from the AutoRed backend (public demo — live polling disabled)." : "Live operational status from the backend."}>
      <div className="health-tiles">
        {tiles.map((t) => <div key={t.l} className="stat-tile"><div className="stat-v" style={t.c ? { color: t.c } : undefined}>{t.v}</div><div className="stat-l">{t.l}</div></div>)}
      </div>
      <div className="card pad health-detail">
        <div className="hd-row"><span className="muted">Event schema version</span><code>v{h.schema_version}</code></div>
        <div className="hd-row"><span className="muted">Max concurrent missions</span><span>{h.max_active ?? "—"}</span></div>
        <div className="hd-row"><span className="muted">Headless browser</span><span>{String(h.headless ?? "—")}</span></div>
        {h.emergency_stop && <div className="hd-row"><span className="muted">Stop reason</span><span className="sev-high">{h.emergency_stop_reason}</span></div>}
        {(h.active_missions ?? []).length > 0 && <div className="hd-row"><span className="muted">Active</span><span>{h.active_missions.map((m: string) => <code key={m} style={{ marginLeft: 6 }}>{m}</code>)}</span></div>}
      </div>
    </Section>
  );
}
