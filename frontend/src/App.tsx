import { useEffect, useMemo, useState, type ReactNode } from "react";
import { AutoRedClient } from "./api/client";
import type { AgentInfo, TargetInfo } from "./contracts/events";
import { useMission } from "./state/useMission";
import { MissionControl } from "./views/MissionControl";
import { Operations } from "./views/Operations";
import { AttackTracker } from "./views/AttackTracker";
import { Findings } from "./views/Findings";
import { Experiments } from "./views/Experiments";
import { History } from "./views/History";
import { SystemHealth } from "./views/SystemHealth";
import { LiveConnect, type LiveConn } from "./views/LiveConnect";

type View = "control" | "ops" | "attacks" | "findings" | "experiments" | "history" | "health";
const NAV: { id: View; label: string; ic: string; sect: string }[] = [
  { id: "control", label: "Mission Control", ic: "◎", sect: "Operations" },
  { id: "ops", label: "Live Operations", ic: "⬡", sect: "Operations" },
  { id: "attacks", label: "Attack Tracker", ic: "◈", sect: "Operations" },
  { id: "findings", label: "Findings", ic: "⚑", sect: "Operations" },
  { id: "experiments", label: "Experiments", ic: "📊", sect: "Analysis" },
  { id: "history", label: "History & Reports", ic: "🗄", sect: "Analysis" },
  { id: "health", label: "System Health", ic: "❤", sect: "System" },
];

const DEMO = import.meta.env.VITE_DEMO === "1";
const DEMO_MISSION = "M-20261122-173200-e6a4";

const LIVE_KEY = "autored.live";
function loadLive(): LiveConn | null {
  try { const v = localStorage.getItem(LIVE_KEY); return v ? JSON.parse(v) : null; } catch { return null; }
}

export default function App() {
  // In a DEMO build the base client is read-only static; connecting a live backend
  // overrides it so the whole dashboard drives real missions against that backend.
  const [live, setLive] = useState<LiveConn | null>(() => loadLive());
  const client = useMemo(
    () => live ? new AutoRedClient({ baseUrl: live.url, token: live.token || undefined })
               : new AutoRedClient({ demo: DEMO, token: import.meta.env.VITE_AUTORED_TOKEN }),
    [live]);
  const urlMission = new URLSearchParams(location.search).get("mission");
  const [view, setView] = useState<View>(urlMission ? "ops" : "control");
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [targets, setTargets] = useState<TargetInfo[]>([]);
  const [health, setHealth] = useState<any>(null);
  const [missionId, setMissionId] = useState<string | null>(urlMission ?? (DEMO ? DEMO_MISSION : null));
  const { state, error: missionErr, loading: missionLoading } = useMission(client, missionId);

  useEffect(() => {
    client.agents().then(setAgents).catch(() => {});
    client.targets().then(setTargets).catch(() => {});
    const f = () => client.health().then(setHealth).catch(() => setHealth({ ok: false }));
    f(); const t = setInterval(f, 5000); return () => clearInterval(t);
  }, [client]);

  const connectLive = (c: LiveConn) => { try { localStorage.setItem(LIVE_KEY, JSON.stringify(c)); } catch { /* ignore */ }
    setLive(c); setMissionId(null); setView("control"); };
  const disconnectLive = () => { try { localStorage.removeItem(LIVE_KEY); } catch { /* ignore */ }
    setLive(null); setMissionId(DEMO ? DEMO_MISSION : null); setView("control"); };

  const openMission = (id: string) => { setMissionId(id); setView("ops"); history.replaceState(null, "", `?mission=${id}`); };
  const stop = () => missionId && client.stopMission(missionId).catch(() => {});
  const estop = () => client.emergencyStop("operator pressed emergency stop in dashboard").catch(() => {});

  const missionPane = (node: ReactNode) => {
    if (!missionId) return <div className="card"><div className="empty">No mission selected.<br /><span className="faint">Launch a new assessment or open one from Mission Control.</span></div></div>;
    if (missionLoading) return <div className="card"><div className="empty"><span className="spinner" /> Loading mission…</div></div>;
    if (missionErr) return <div className="card"><div className="empty"><span className="sev-high">Failed to load mission</span><br /><span className="faint">{missionErr}</span></div></div>;
    if (!state.mission_id) return <div className="card"><div className="empty">This mission has no recorded data.</div></div>;
    return node;
  };
  const grouped = NAV.reduce<Record<string, typeof NAV>>((a, n) => ((a[n.sect] ??= []).push(n), a), {});

  return (
    <div className="app">
      <div className="brand"><span className="dot" /> AutoRed</div>
      <div className="topbar">
        <div className="row" style={{ gap: 12 }}>
          {live
            ? <span className="pill" style={{ color: health?.ok ? "var(--ok)" : "var(--bad)" }}>{health?.ok ? "● Live backend connected" : "⚠ Live backend unavailable"}</span>
            : DEMO
              ? <span className="pill" style={{ color: "var(--accent)" }}>● Explore demo · read-only</span>
              : <span className="pill" style={{ color: health?.ok ? "var(--ok)" : "var(--bad)" }}>{health?.ok ? "Backend online" : "Backend offline"}</span>}
          {missionId && <span className="pill" style={{ color: "var(--accent)" }}>mission {missionId}</span>}
        </div>
        <div className="row" style={{ gap: 8 }}>
          <select className="mobile-nav" value={view} onChange={(e) => setView(e.target.value as View)}>
            {NAV.map((n) => <option key={n.id} value={n.id}>{n.label}</option>)}
          </select>
          {DEMO && <LiveConnect current={live} onConnect={connectLive} onDisconnect={disconnectLive} />}
          {(!DEMO || live)
            ? (health?.emergency_stop
                ? <button className="btn sm" onClick={() => client.resetEmergencyStop().catch(() => {})}>Reset E-Stop</button>
                : <button className="btn sm danger" onClick={estop}>■ EMERGENCY STOP</button>)
            : <a className="btn sm ghost" href="https://github.com/FarnooshMemari" target="_blank" rel="noreferrer">About AutoRed</a>}
        </div>
      </div>
      <nav className="nav">
        {Object.entries(grouped).map(([sect, items]) => (
          <div key={sect}>
            <div className="sect">{sect}</div>
            {items.map((n) => (
              <button key={n.id} className={view === n.id ? "active" : ""} onClick={() => setView(n.id)}>
                <span className="ic">{n.ic}</span> {n.label}
              </button>
            ))}
          </div>
        ))}
      </nav>
      <main className="main">
        {view === "control" && <MissionControl client={client} targets={targets} agents={agents} onOpen={openMission}
          reloadTargets={() => client.targets().then(setTargets).catch(() => {})} />}
        {view === "ops" && missionPane(<Operations client={client} state={state} agents={agents} onStop={stop} />)}
        {view === "attacks" && missionPane(<AttackTracker client={client} state={state} agents={agents} />)}
        {view === "findings" && missionPane(<Findings client={client} state={state} />)}
        {view === "experiments" && <Experiments client={client} />}
        {view === "history" && <History client={client} onOpen={openMission} />}
        {view === "health" && <SystemHealth client={client} />}
      </main>
    </div>
  );
}
