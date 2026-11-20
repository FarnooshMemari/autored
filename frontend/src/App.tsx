import { useEffect, useMemo, useState } from "react";
import { AutoRedClient } from "./api/client";
import type { AgentInfo, TargetInfo } from "./contracts/events";
import { AutoRedUIProvider } from "./integration/slots";
import { MissionScreen } from "./MissionScreen";
import { useMission } from "./state/useMission";

export default function App() {
  const client = useMemo(() => new AutoRedClient({ token: import.meta.env.VITE_AUTORED_TOKEN }), []);
  const [targets, setTargets] = useState<TargetInfo[]>([]);
  const [agentInfo, setAgentInfo] = useState<AgentInfo[]>([]);
  const [targetId, setTargetId] = useState("");
  const [operator, setOperator] = useState("");
  const [ack, setAck] = useState(false);
  const [missionId, setMissionId] = useState<string | null>(new URLSearchParams(location.search).get("mission"));
  const [err, setErr] = useState<string | null>(null);
  const { state, error } = useMission(client, missionId);

  useEffect(() => {
    client.targets().then((t) => { setTargets(t); setTargetId(t[0]?.id ?? ""); }).catch((e) => setErr(String(e)));
    client.agents().then(setAgentInfo).catch(() => {});
  }, [client]);

  const target = targets.find((t) => t.id === targetId);
  const start = async () => {
    setErr(null);
    try {
      const snap = await client.createMission({ target_id: targetId, operator, authorization_acknowledged: ack });
      setMissionId(snap.mission_id);
      history.replaceState(null, "", `?mission=${snap.mission_id}`);
    } catch (e) { setErr(String(e)); }
  };
  const estop = async () => { await client.emergencyStop("operator pressed emergency stop").catch((e) => setErr(String(e))); };

  return (
    <AutoRedUIProvider>
      <header>
        <h1>AutoRed</h1>
        <button onClick={estop} aria-label="Emergency stop">EMERGENCY STOP</button>
        <button onClick={() => client.resetEmergencyStop()}>Reset e-stop</button>
      </header>
      <section className="slot">
        <label>Target <select value={targetId} onChange={(e) => setTargetId(e.target.value)}>
          {targets.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select></label>
        {target && <p>Authorization {target.authorization.reference}, approved by {target.authorization.approved_by}, expires {target.authorization.expires}. Origin: {target.base_url}</p>}
        <label>Operator <input value={operator} onChange={(e) => setOperator(e.target.value)} /></label>
        <label><input type="checkbox" checked={ack} onChange={(e) => setAck(e.target.checked)} /> I confirm written authorization to test this target</label>
        <button disabled={!ack || !operator || !targetId} onClick={start}>Start mission</button>
        {missionId && <button onClick={() => client.stopMission(missionId)}>Stop mission</button>}
        {(err || error) && <p role="alert">{err || error}</p>}
      </section>
      {missionId && state.mission_id && <MissionScreen client={client} state={state} agentInfo={agentInfo} />}
    </AutoRedUIProvider>
  );
}
