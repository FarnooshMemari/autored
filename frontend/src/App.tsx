import { useEffect, useMemo, useState } from "react";
import { AutoRedClient } from "./api/client";
import type { AgentInfo, TargetInfo } from "./contracts/events";
import { useMission } from "./state/useMission";
import { MissionControl } from "./views/MissionControl";
import { Operations } from "./views/Operations";
import { Findings } from "./views/Findings";
import { Experiments } from "./views/Experiments";
import { History } from "./views/History";
import { SystemHealth } from "./views/SystemHealth";

type View = "control" | "ops" | "findings" | "experiments" | "history" | "health";
const NAV: { id: View; label: string; ic: string; sect: string }[] = [
  { id: "control", label: "Mission Control", ic: "◎", sect: "Operations" },
  { id: "ops", label: "Live Operations", ic: "⬡", sect: "Operations" },
  { id: "findings", label: "Findings", ic: "⚑", sect: "Operations" },
  { id: "experiments", label: "Experiments", ic: "📊", sect: "Analysis" },
  { id: "history", label: "History & Reports", ic: "🗄", sect: "Analysis" },
  { id: "health", label: "System Health", ic: "❤", sect: "System" },
];

export default function App() {
  const client = useMemo(() => new AutoRedClient({ token: import.meta.env.VITE_AUTORED_TOKEN }), []);
  const [view, setView] = useState<View>(new URLSearchParams(location.search).get("mission") ? "ops" : "control");
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [targets, setTargets] = useState<TargetInfo[]>([]);
  const [health, setHealth] = useState<any>(null);
  const [missionId, setMissionId] = useState<string | null>(new URLSearchParams(location.search).get("mission"));
  const { state } = useMission(client, missionId);

  useEffect(() => {
    client.agents().then(setAgents).catch(() => {});
    client.targets().then(setTargets).catch(() => {});
    const f = () => client.health().then(setHealth).catch(() => setHealth({ ok: false }));
    f(); const t = setInterval(f, 5000); return () => clearInterval(t);
  }, [client]);

  const openMission = (id: string) => { setMissionId(id); setView("ops"); history.replaceState(null, "", `?mission=${id}`); };
  const stop = () => missionId && client.stopMission(missionId).catch(() => {});
  const estop = () => client.emergencyStop("operator pressed emergency stop in dashboard").catch(() => {});

  const grouped = NAV.reduce<Record<string, typeof NAV>>((a, n) => ((a[n.sect] ??= []).push(n), a), {});

  return (
    <div className="app">
      <div className="brand"><span className="dot" /> AutoRed</div>
      <div className="topbar">
        <div className="row" style={{ gap: 12 }}>
          <span className="pill" style={{ color: health?.ok ? "var(--ok)" : "var(--bad)" }}>{health?.ok ? "Backend online" : "Backend offline"}</span>
          {missionId && <span className="pill" style={{ color: "var(--accent)" }}>mission {missionId}</span>}
        </div>
        <div className="row" style={{ gap: 8 }}>
          {health?.emergency_stop
            ? <button className="btn sm" onClick={() => client.resetEmergencyStop().catch(() => {})}>Reset E-Stop</button>
            : <button className="btn sm danger" onClick={estop}>■ EMERGENCY STOP</button>}
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
        {view === "control" && <MissionControl client={client} targets={targets} agents={agents} onOpen={openMission} />}
        {view === "ops" && (missionId && state.mission_id
          ? <Operations client={client} state={state} agents={agents} onStop={stop} />
          : <div className="card"><div className="empty">No mission open. Launch one from Mission Control.</div></div>)}
        {view === "findings" && (missionId && state.mission_id
          ? <Findings client={client} state={state} />
          : <div className="card"><div className="empty">Open a mission to see findings.</div></div>)}
        {view === "experiments" && <Experiments client={client} />}
        {view === "history" && <History client={client} onOpen={openMission} />}
        {view === "health" && <SystemHealth client={client} />}
      </main>
    </div>
  );
}
