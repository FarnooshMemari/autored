import { useEffect, useState } from "react";
import type { AutoRedClient } from "../api/client";
import type { AgentInfo, TargetInfo } from "../contracts/events";
import { SPECIALIST_IDS } from "../contracts/events";
import { AgentCharacter } from "../components/AgentCharacter";
import { Empty, Pill, Section } from "../components/common";

const MODES = [
  { id: "assess", name: "Fixed assessment", desc: "Full fixed-probe suite across all four categories." },
  { id: "adaptive", name: "Adaptive (LLM)", desc: "LLM planner proposes probes and revises on evidence." },
  { id: "connectivity", name: "Connectivity only", desc: "Discover + one benign message. No security probes." },
];

export function MissionControl({ client, targets, agents, onOpen }:
  { client: AutoRedClient; targets: TargetInfo[]; agents: AgentInfo[]; onOpen: (id: string) => void }) {
  const [targetId, setTargetId] = useState("");
  const [operator, setOperator] = useState("");
  const [ack, setAck] = useState(false);
  const [mode, setMode] = useState("assess");
  const [picked, setPicked] = useState<string[]>([...SPECIALIST_IDS]);
  const [missions, setMissions] = useState<any[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (targets[0] && !targetId) setTargetId(targets[0].id); }, [targets]);
  const refresh = () => client.missions().then(setMissions).catch(() => {});
  useEffect(() => { refresh(); const t = setInterval(refresh, 4000); return () => clearInterval(t); }, [client]);

  const target = targets.find((t) => t.id === targetId);
  const specialists = agents.filter((a) => a.kind === "specialist");

  const start = async () => {
    setErr(null); setBusy(true);
    try {
      const body: any = { target_id: targetId, operator, authorization_acknowledged: ack, mode };
      if (mode !== "connectivity") body.agents = picked;
      const snap = await client.createMission(body);
      onOpen(snap.mission_id);
    } catch (e) { setErr(String(e)); } finally { setBusy(false); }
  };

  const toggle = (id: string) => setPicked((p) => p.includes(id) ? p.filter((x) => x !== id) : [...p, id]);

  return (
    <>
      <Section title="Mission Control" sub="Configure, launch and manage authorized assessments.">
        <div className="grid" style={{ gridTemplateColumns: "1.3fr 1fr" }}>
          <div className="card pad grid" style={{ gap: 14 }}>
            <label className="field">Target
              <select value={targetId} onChange={(e) => setTargetId(e.target.value)}>
                {targets.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </label>
            {target && <div className="card pad" style={{ background: "var(--surface)", fontSize: 12.5 }}>
              <div className="row between"><span className="muted">Authorization</span><Pill color="var(--ok)">{target.authorization.reference}</Pill></div>
              <div className="row between" style={{ marginTop: 6 }}><span className="muted">Approved by</span><span>{target.authorization.approved_by}</span></div>
              <div className="row between" style={{ marginTop: 6 }}><span className="muted">Expires</span><span>{target.authorization.expires}</span></div>
              <div className="row between" style={{ marginTop: 6 }}><span className="muted">Origin</span><code>{target.base_url}</code></div>
            </div>}
            <label className="field">Operator
              <input value={operator} onChange={(e) => setOperator(e.target.value)} placeholder="your name / id" />
            </label>
            <div className="field">Mode
              <div className="grid" style={{ gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
                {MODES.map((m) => (
                  <button key={m.id} className={`btn sm ${mode === m.id ? "primary" : "ghost"}`} onClick={() => setMode(m.id)}
                    title={m.desc} style={{ textAlign: "left", padding: "10px 12px", height: "100%" }}>
                    <div style={{ fontWeight: 700 }}>{m.name}</div>
                    <div className="sub" style={{ fontSize: 11, color: mode === m.id ? "#0b0e14" : undefined }}>{m.desc}</div>
                  </button>
                ))}
              </div>
            </div>
            {mode !== "connectivity" && <div className="field">Specialists
              <div className="row wrap" style={{ gap: 8 }}>
                {specialists.map((a) => (
                  <button key={a.id} onClick={() => toggle(a.id)} className="btn sm"
                    style={{ borderColor: picked.includes(a.id) ? a.color : "var(--border)", opacity: picked.includes(a.id) ? 1 : .5 }}>
                    <span style={{ color: a.color }}>●</span> {a.name} <span className="faint">· {a.role}</span>
                  </button>
                ))}
              </div>
            </div>}
            <label className="row" style={{ gap: 9, fontSize: 13 }}>
              <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} style={{ width: 16 }} />
              I confirm written authorization to test this target.
            </label>
            <div className="row" style={{ gap: 10 }}>
              <button className="btn primary" disabled={!ack || !operator || !targetId || busy} onClick={start}>
                {busy ? <span className="spinner" /> : "▶ Launch assessment"}
              </button>
              {err && <span className="sev-high" style={{ fontSize: 13 }}>{err}</span>}
            </div>
          </div>

          <div className="card pad">
            <div className="sub" style={{ marginBottom: 10 }}>Agent roster</div>
            <div className="grid" style={{ gap: 10 }}>
              {agents.map((a) => (
                <div key={a.id} className="row" style={{ gap: 12 }}>
                  <AgentCharacter color={a.color} cue="idle" size={46} name={a.name} />
                  <div><div style={{ fontWeight: 700 }}>{a.name} <span className="faint" style={{ fontWeight: 400 }}>/ {a.id}</span></div>
                    <div className="sub">{a.role}</div></div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </Section>

      <Section title="Missions" actions={<button className="btn sm ghost" onClick={refresh}>↻ Refresh</button>}>
        <div className="card">
          {missions.length === 0 ? <Empty>No missions yet. Launch one above.</Empty> :
            <table><thead><tr><th>Mission</th><th>Target</th><th>Phase</th><th>Active</th><th></th></tr></thead>
              <tbody>{missions.map((m) => (
                <tr key={m.mission_id}>
                  <td><code>{m.mission_id}</code></td><td>{m.target_id}</td>
                  <td><span className={m.phase === "completed" ? "st-confirmed" : m.active ? "st-candidate" : "muted"}>{m.phase}</span></td>
                  <td>{m.active ? <Pill color="var(--accent)">live</Pill> : <span className="faint">—</span>}</td>
                  <td style={{ textAlign: "right" }}><button className="btn sm" onClick={() => onOpen(m.mission_id)}>Open →</button></td>
                </tr>
              ))}</tbody></table>}
        </div>
      </Section>
    </>
  );
}
