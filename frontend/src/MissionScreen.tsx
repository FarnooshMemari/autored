/** Composes slots from mission state. Layout here is a functional placeholder. */
import { useMemo, useState } from "react";
import type { AutoRedClient } from "./api/client";
import type { AgentId, AgentInfo } from "./contracts/events";
import { SPECIALIST_IDS } from "./contracts/events";
import { useSlots } from "./integration/slots";
import { useAgentFrame } from "./state/useMission";
import type { MissionState } from "./state/missionReducer";

function LiveBrowser({ client, state, agentId, expanded, onToggle }: { client: AutoRedClient; state: MissionState; agentId: AgentId; expanded: boolean; onToggle: () => void }) {
  const { BrowserView } = useSlots();
  const frameSrc = useAgentFrame(client, state.mission_id || null, agentId);
  const a = state.agents[agentId];
  return <BrowserView agentId={agentId} frameSrc={frameSrc} url={a.url} contextId={a.context_id} expanded={expanded} onToggleExpand={onToggle} />;
}

export function MissionScreen({ client, state, agentInfo }: { client: AutoRedClient; state: MissionState; agentInfo: AgentInfo[] }) {
  const { Commander, Specialist, Timeline, Findings } = useSlots();
  const [selected, setSelected] = useState<AgentId | null>(null);
  const [expanded, setExpanded] = useState<AgentId | null>(null);
  const findings = useMemo(() => Object.values(state.findings), [state.findings]);
  const toggle = (id: AgentId) => setSelected((s) => (s === id ? null : id));

  return (
    <>
      <Commander agent={state.agents.commander} phase={state.phase} message={state.message} capabilities={state.capabilities}
        plan={state.plan} selected={selected === "commander"} onSelect={() => toggle("commander")} />
      <div className="grid">
        {SPECIALIST_IDS.map((id) => (
          <Specialist key={id} agent={state.agents[id]} info={agentInfo.find((i) => i.id === id) ?? { id, name: id, kind: "specialist", slot: 0 }}
            findings={findings.filter((f) => f.category === id)} selected={selected === id} onSelect={() => toggle(id)} />
        ))}
      </div>
      <div className="grid">
        {(expanded ? [expanded] : SPECIALIST_IDS).map((id) => (
          <LiveBrowser key={id} client={client} state={state} agentId={id} expanded={expanded === id}
            onToggle={() => setExpanded((e) => (e === id ? null : id))} />
        ))}
      </div>
      <h3>Findings</h3>
      <Findings findings={findings} artifactUrl={(n) => client.artifactUrl(state.mission_id, n)} />
      <h3>Timeline {selected && <small>(filtered: {selected})</small>}</h3>
      <Timeline events={state.timeline} selectedAgent={selected} onSelectAgent={toggle} />
    </>
  );
}
