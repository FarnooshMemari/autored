/** Minimal functional placeholders. Intentionally unstyled: replace via slots. */
import type { BrowserViewSlotProps, CommanderSlotProps, FindingsSlotProps, SpecialistSlotProps, TimelineSlotProps } from "../slots";
import { agentColorVar } from "../slots";
import type { AutoRedEvent } from "../../contracts/events";

export function DefaultCommander({ agent, phase, message, capabilities, plan, onSelect, selected }: CommanderSlotProps) {
  return (
    <section className="slot" data-agent="commander" data-cue={agent.cue} aria-selected={selected} onClick={onSelect}
      style={{ borderColor: agentColorVar("commander") }}>
      <strong>Commander</strong> · phase <code>{phase}</code> · <em>{agent.status}</em>
      <div>{agent.activity || message}</div>
      {capabilities && <div>Tools discovered: {capabilities.tools.join(", ") || "none"}</div>}
      {plan && Object.keys(plan.skipped).length > 0 && (
        <div>Skipped: {Object.entries(plan.skipped).map(([p, r]) => `${p} (${r})`).join("; ")}</div>)}
    </section>
  );
}

export function DefaultSpecialist({ agent, info, findings, selected, onSelect }: SpecialistSlotProps) {
  return (
    <section className="slot" data-agent={agent.agent_id} data-cue={agent.cue} aria-selected={selected} onClick={onSelect}
      style={{ borderColor: agentColorVar(agent.agent_id) }}>
      <strong>{info.slot}. {info.name}</strong> · <em>{agent.status}</em> · cue <code>{agent.cue}</code>
      <div>{agent.activity}</div>
      <div>probes run: {agent.probes_run} · findings: {findings.length}</div>
    </section>
  );
}

export function DefaultBrowserView({ agentId, frameSrc, url, contextId, expanded, onToggleExpand }: BrowserViewSlotProps) {
  return (
    <figure className="slot browser" data-agent={agentId} data-expanded={expanded} style={{ borderColor: agentColorVar(agentId) }}>
      <figcaption>
        <code>{agentId}</code> · {url ?? "no page yet"} {contextId && <small>({contextId})</small>}
        <button onClick={onToggleExpand}>{expanded ? "Collapse" : "Expand"}</button>
      </figcaption>
      {frameSrc ? <img src={frameSrc} alt={`Live browser for ${agentId}`} style={{ width: "100%" }} /> : <div>waiting for frames…</div>}
    </figure>
  );
}

function describe(e: AutoRedEvent): string {
  switch (e.type) {
    case "task.assigned": return `→ ${e.payload.to_agent}: ${e.payload.title} [${e.payload.probe_ids.join(", ")}]`;
    case "test.started": return `${e.payload.probe_id} › ${e.payload.prompt}`;
    case "test.response": return `${e.payload.probe_id} ‹ ${e.payload.response} (${e.payload.latency_ms} ms)`;
    case "test.verdict": return `${e.payload.probe_id} = ${e.payload.verdict} (${e.payload.rationale})`;
    case "finding.candidate": case "finding.updated": return `${e.payload.finding_id} ${e.payload.status}: ${e.payload.title}`;
    case "agent.status": return `${e.payload.status}: ${e.payload.activity}`;
    case "browser.navigated": return `navigated ${e.payload.url}`;
    case "browser.action": return `${e.payload.action} ${e.payload.selector} ${e.payload.value_preview}`;
    case "browser.blocked": return `BLOCKED ${e.payload.url}`;
    case "mission.status": return `phase ${e.payload.phase}: ${e.payload.message}`;
    case "mission.completed": return `mission ${e.payload.phase}: ${e.payload.confirmed} confirmed, ${e.payload.inconclusive} inconclusive`;
    case "commander.capabilities": return `capabilities: tools=${e.payload.tools.join(",")}`;
    case "commander.plan": return `plan: ${JSON.stringify(e.payload.assignments)}`;
    case "task.completed": return `task ${e.payload.task_id} ${e.payload.outcome} ${e.payload.detail}`;
    case "log": return `[${e.payload.level}] ${e.payload.message}`;
  }
}

export function DefaultTimeline({ events, selectedAgent, onSelectAgent }: TimelineSlotProps) {
  const shown = (selectedAgent ? events.filter((e) => e.agent_id === selectedAgent) : events).slice(-200).reverse();
  return (
    <ol className="slot timeline">
      {shown.map((e) => (
        <li key={e.id} data-agent={e.agent_id} style={{ color: agentColorVar(e.agent_id) }} onClick={() => onSelectAgent(e.agent_id)}>
          <code>#{e.seq} {new Date(e.ts).toLocaleTimeString()} {e.agent_id} {e.type}</code> {describe(e)}
        </li>
      ))}
    </ol>
  );
}

export function DefaultFindings({ findings, artifactUrl }: FindingsSlotProps) {
  if (!findings.length) return <section className="slot">No findings yet.</section>;
  return (
    <table className="slot findings">
      <thead><tr><th>Status</th><th>Severity</th><th>Agent</th><th>Probe</th><th>Title</th><th>Reproduced</th><th>Evidence</th></tr></thead>
      <tbody>
        {findings.map((f) => (
          <tr key={f.finding_id} data-status={f.status}>
            <td>{f.status}</td><td>{f.severity}</td><td>{f.category}</td><td>{f.probe_id}</td><td>{f.title}</td>
            <td>{f.reproductions}/{f.attempts}</td>
            <td>
              {f.evidence.map((ev, i) => ev.kind === "screenshot" && ev.artifact
                ? <a key={i} href={artifactUrl(ev.artifact)} target="_blank" rel="noreferrer">screenshot </a>
                : <div key={i}><code>{ev.kind}</code> {ev.detail.slice(0, 160)}</div>)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
