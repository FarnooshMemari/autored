import { useMemo, useState } from "react";
import type { AutoRedClient } from "../api/client";
import type { AgentId, AgentInfo, AutoRedEvent } from "../contracts/events";
import { SPECIALIST_IDS } from "../contracts/events";
import type { AgentView, MissionState } from "../state/missionReducer";
import { useAgentFrame } from "../state/useMission";
import { AgentCharacter } from "../components/AgentCharacter";
import { Pill, Section } from "../components/common";

function LiveBrowser({ client, missionId, agent, info, live, recordedShot, expanded, onToggle }:
  { client: AutoRedClient; missionId: string; agent: AgentView; info?: AgentInfo; live: boolean; recordedShot?: string; expanded: boolean; onToggle: () => void }) {
  const liveSrc = useAgentFrame(client, live ? missionId : null, agent.agent_id);
  const src = live ? liveSrc : (recordedShot ? client.artifactUrl(missionId, recordedShot) : null);
  const vp = agent.viewport ?? { width: 1100, height: 720 };
  const box = agent.lastBox;
  return (
    <div className="card" data-expanded={expanded} style={{ overflow: "hidden", borderColor: info ? `${info.color}55` : undefined }}>
      <div className="row between pad" style={{ padding: "9px 12px", borderBottom: "1px solid var(--border)" }}>
        <div className="row" style={{ gap: 8, minWidth: 0 }}>
          <span style={{ color: info?.color }}>●</span>
          <strong>{info?.name ?? agent.agent_id}</strong>
          <code className="faint" style={{ fontSize: 11, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{agent.url ?? "—"}</code>
        </div>
        <button className="btn sm ghost" onClick={onToggle}>{expanded ? "⤢ Collapse" : "⤢ Expand"}</button>
      </div>
      <div style={{ position: "relative", aspectRatio: "3 / 2", background: "#05070b" }}>
        {!live && <span className="rec-badge">● RECORDED</span>}
        {src ? <img src={src} alt={`${live ? "Live" : "Recorded"} browser for ${agent.agent_id}`} style={{ width: "100%", height: "100%", objectFit: "contain", display: "block" }} />
          : <div className="row" style={{ height: "100%", justifyContent: "center", color: "var(--faint)", gap: 8, textAlign: "center", padding: 16 }}>
              {live ? (agent.status === "idle" ? "not started" : <><span className="spinner" /> connecting to browser…</>)
                    : "No recorded browser view for this agent."}</div>}
        {live && src && box && box.width > 0 && (
          <div style={{ position: "absolute", left: `${(box.x / vp.width) * 100}%`, top: `${(box.y / vp.height) * 100}%`,
            width: `${(box.width / vp.width) * 100}%`, height: `${(box.height / vp.height) * 100}%`,
            border: `2px solid ${info?.color ?? "#22d3ee"}`, borderRadius: 4, boxShadow: `0 0 0 9999px rgba(5,7,11,.35)`,
            transition: "all .3s", pointerEvents: "none" }}>
            <span style={{ position: "absolute", top: -18, left: 0, fontSize: 10, fontWeight: 700,
              background: info?.color, color: "#05070b", padding: "1px 6px", borderRadius: 4 }}>{agent.cue}</span>
          </div>
        )}
      </div>
      <div className="row between" style={{ padding: "8px 12px", fontSize: 12 }}>
        <span className="muted" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{agent.activity || "—"}</span>
        <span className="faint">{agent.probes_run} probes</span>
      </div>
    </div>
  );
}

const describe = (e: AutoRedEvent): string => {
  const p: any = e.payload;
  switch (e.type) {
    case "test.verdict": return `${p.probe_id} → ${p.verdict}`;
    case "test.started": return `${p.probe_id}: ${p.prompt.slice(0, 54)}`;
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

export function Operations({ client, state, agents, onStop }:
  { client: AutoRedClient; state: MissionState; agents: AgentInfo[]; onStop: () => void }) {
  const [expanded, setExpanded] = useState<AgentId | null>(null);
  const info = useMemo(() => Object.fromEntries(agents.map((a) => [a.id, a])), [agents]);

  const feed = state.timeline.filter((e) => !["browser.action"].includes(e.type)).slice(-80).reverse();
  const shownBrowsers = (expanded ? [expanded] : [...SPECIALIST_IDS]) as AgentId[];

  return (
    <>
      <Section title="Live Operations" sub={`Mission ${state.mission_id || "—"} · ${state.target_id}`}
        actions={<div className="row" style={{ gap: 10 }}>
          <Pill color={state.live ? "var(--accent)" : "var(--muted)"}>{state.live ? "● LIVE" : "recorded"} · {state.phase}</Pill>
          {state.live && <button className="btn sm danger" onClick={onStop}>■ Stop</button>}
        </div>}>
        {/* agent strip */}
        <div className="card pad" style={{ marginBottom: 14 }}>
          <div className="agent-strip">
            {["commander", ...SPECIALIST_IDS].map((id) => {
              const a = state.agents[id as AgentId]; const i = info[id];
              return (
                <div key={id} className="row" style={{ gap: 10, alignItems: "flex-start" }}>
                  <AgentCharacter color={i?.color ?? "#888"} cue={a.cue} size={58} name={i?.name} />
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontWeight: 700 }}>{i?.name ?? id}</div>
                    <div className="sub" style={{ whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{a.status}</div>
                    <div className="faint" style={{ fontSize: 11, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{a.activity || "—"}</div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </Section>

      <div className={`browser-grid ${expanded ? "one" : ""}`}>
        {shownBrowsers.map((id) => {
          const shot = Object.values(state.findings).find((f) => f.category === id && f.evidence.some((e) => e.kind === "screenshot" && e.artifact))?.evidence.find((e) => e.kind === "screenshot")?.artifact;
          return <LiveBrowser key={id} client={client} missionId={state.mission_id} agent={state.agents[id]} info={info[id]}
            live={state.live} recordedShot={shot ?? undefined}
            expanded={expanded === id} onToggle={() => setExpanded((x) => (x === id ? null : id))} />;
        })}
      </div>

      <Section title="Activity feed">
        <div className="card" style={{ maxHeight: 340, overflow: "auto" }}>
          {feed.length === 0 ? <div className="empty">No activity yet.</div> : feed.map((e) => (
            <div key={e.id} className="row" style={{ gap: 10, padding: "6px 14px", borderBottom: "1px solid var(--border)", fontSize: 12.5 }}>
              <code className="faint" style={{ fontSize: 11, minWidth: 64 }}>{new Date(e.ts).toLocaleTimeString()}</code>
              <span style={{ color: info[e.agent_id]?.color, minWidth: 74, fontWeight: 600 }}>{info[e.agent_id]?.name ?? e.agent_id}</span>
              <span className="mono" style={{ fontSize: 11.5 }}>{describe(e)}</span>
            </div>
          ))}
        </div>
      </Section>
    </>
  );
}
