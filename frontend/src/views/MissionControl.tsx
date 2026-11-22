import { useEffect, useState } from "react";
import type { AutoRedClient } from "../api/client";
import type { AgentId, AgentInfo, TargetInfo } from "../contracts/events";
import { SPECIALIST_IDS } from "../contracts/events";
import { AgentCharacter } from "../components/AgentCharacter";
import { Empty, Pill, Section } from "../components/common";

const ABOUT: Record<string, string> = {
  commander: "Plans the assessment, delegates to specialists, interprets evidence and calls when enough is enough.",
  injection: "Direct, indirect and multi-turn prompt injection — making the assistant abandon its instructions.",
  leakage: "Unauthorized disclosure — cross-account access, privacy boundaries and synthetic canary leakage.",
  hierarchy: "System / developer / user instruction boundaries and privilege won by conversation.",
  tools: "Tool authorization, privilege escalation and real tool side-effects.",
};

const MODES = [
  { id: "assess", name: "Fixed", desc: "Full fixed-probe suite across all four categories.", ic: "▦" },
  { id: "adaptive", name: "Adaptive", desc: "LLM planner proposes probes and revises on evidence.", ic: "◇" },
  { id: "hybrid", name: "Hybrid", desc: "Fixed suite first, then adaptive follow-ups.", ic: "⬒" },
  { id: "connectivity", name: "Connectivity", desc: "Discover + one benign message. No security probes.", ic: "◌" },
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
  const byId = Object.fromEntries(agents.map((a) => [a.id, a]));
  const commander = byId["commander"];
  const specialists = SPECIALIST_IDS.map((id) => byId[id]).filter(Boolean);
  const activeSpecialists = mode === "connectivity" ? [] : picked;

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

  const member = (a: AgentInfo, lead: boolean) => {
    const sel = lead || picked.includes(a.id);
    const disabled = !lead && mode === "connectivity";
    return (
      <button key={a.id} type="button"
        className={`squad-member ${sel && !disabled ? "sel" : ""} ${disabled ? "off" : ""}`}
        style={{ ["--ac" as any]: a.color }}
        disabled={lead}
        aria-pressed={!lead ? sel : undefined}
        onClick={() => !lead && toggle(a.id)}
        title={lead ? "Commander leads every mission" : sel ? `${a.name} is on this mission — click to stand down` : `Click to deploy ${a.name}`}>
        <div className="squad-char">
          <AgentCharacter color={a.color} cue={sel && !disabled ? "browsing" : "idle"} size={lead ? 136 : 104} name={a.name} agentId={a.id as AgentId} />
        </div>
        <div className="squad-name">{a.name}</div>
        <div className="squad-role" style={{ color: a.color }}>{a.role}</div>
        <div className="squad-about">{ABOUT[a.id]}</div>
        {lead
          ? <span className="squad-tag lead">LEAD</span>
          : <span className={`squad-tag ${sel && !disabled ? "on" : ""}`}>{disabled ? "stood down" : sel ? "✓ deployed" : "stand by"}</span>}
      </button>
    );
  };

  return (
    <>
      <Section title="Mission Control" sub="Assemble the squad, authorize the target and launch an assessment.">
        {/* squad centerpiece — Commander feature + specialist formation */}
        <div className="card hero">
          <div className="hero-lead">
            <div className="hero-eyebrow">Central intelligence</div>
            {commander && member(commander, true)}
          </div>
          <div className="hero-right">
            <div className="hero-right-head"><span className="hero-right-label">The squad</span>
              <span className="hero-right-note">{activeSpecialists.length} of 4 deployed</span></div>
            <div className="hero-squad">{specialists.map((a) => member(a, false))}</div>
          </div>
        </div>

        {/* launch console */}
        <div className="launch-console">
          <div className="card pad grid" style={{ gap: 16 }}>
            <label className="field">Target
              <select value={targetId} onChange={(e) => setTargetId(e.target.value)}>
                {targets.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
            </label>
            {target && <div className="auth-card">
              <div className="row between"><span className="muted">Authorization</span><Pill color="var(--ok)">{target.authorization.reference}</Pill></div>
              <div className="row between"><span className="muted">Approved by</span><span>{target.authorization.approved_by}</span></div>
              <div className="row between"><span className="muted">Expires</span><span>{target.authorization.expires}</span></div>
              <div className="row between"><span className="muted">Origin</span><code>{target.base_url}</code></div>
            </div>}
            <label className="field">Operator
              <input value={operator} onChange={(e) => setOperator(e.target.value)} placeholder="your name / id" />
            </label>
            <div className="field">Assessment mode
              <div className="mode-grid">
                {MODES.map((m) => (
                  <button key={m.id} type="button" className={`mode-card ${mode === m.id ? "sel" : ""}`} onClick={() => setMode(m.id)}>
                    <span className="mode-ic">{m.ic}</span>
                    <span className="mode-name">{m.name}</span>
                    <span className="mode-desc">{m.desc}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="card pad brief">
            <div className="eyebrow">Mission briefing</div>
            <div className="brief-row"><span className="muted">Target</span><strong>{target?.name.split(" (")[0] ?? "—"}</strong></div>
            <div className="brief-row"><span className="muted">Mode</span><strong>{MODES.find((m) => m.id === mode)?.name}</strong></div>
            <div className="brief-row"><span className="muted">Squad</span>
              <span className="row" style={{ gap: 5 }}>
                {commander && <span className="brief-dot" style={{ background: commander.color }} title="Commander" />}
                {specialists.map((a) => <span key={a.id} className="brief-dot"
                  style={{ background: a.color, opacity: activeSpecialists.includes(a.id) ? 1 : .18 }} title={a.name} />)}
                <strong style={{ marginLeft: 6 }}>{1 + activeSpecialists.length}</strong>
              </span>
            </div>
            <div className="brief-sep" />
            <label className="ack">
              <input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} />
              <span>I confirm written authorization to test this target.</span>
            </label>
            <button className="btn primary launch-btn" disabled={client.isDemo || !ack || !operator || !targetId || busy} onClick={start}>
              {busy ? <span className="spinner" /> : client.isDemo ? "Launching disabled in demo" : "▶  Launch assessment"}
            </button>
            {err && <div className="sev-high" style={{ fontSize: 12.5 }}>{err}</div>}
            {client.isDemo
              ? <div className="faint" style={{ fontSize: 11.5 }}>Public read-only demo — explore recorded missions in Live Operations, Findings and History.</div>
              : (!operator || !ack) && !err && <div className="faint" style={{ fontSize: 11.5 }}>
                  {!operator ? "Enter an operator id" : "Confirm authorization"} to launch.</div>}
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
