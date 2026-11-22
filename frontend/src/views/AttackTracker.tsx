import { useMemo, useState } from "react";
import type { AutoRedClient } from "../api/client";
import type { AgentId, AgentInfo } from "../contracts/events";
import type { MissionState } from "../state/missionReducer";
import { deriveAttacks, type Attack } from "../state/attacks";
import { AgentCharacter } from "../components/AgentCharacter";
import { Empty, Section } from "../components/common";

const EXEC_LABEL: Record<string, string> = { pending: "Pending", running: "Running", completed: "Completed", skipped: "Skipped", failed: "Failed" };
const VERDICT_LABEL: Record<string, string> = { confirmed: "Confirmed", not_confirmed: "Not confirmed", inconclusive: "Inconclusive", not_assessed: "Not assessed" };

function AttackRow({ client, missionId, a, info, open, onToggle }:
  { client: AutoRedClient; missionId: string; a: Attack; info?: AgentInfo; open: boolean; onToggle: () => void }) {
  const color = info?.color ?? "var(--accent)";
  const proof = a.finding ? [...new Map(a.finding.evidence.filter((e) => e.kind === "canary" || e.kind === "oracle").map((e) => [e.detail, e])).values()] : [];
  const shot = a.finding?.evidence.find((e) => e.kind === "screenshot" && e.artifact)?.artifact;
  return (
    <div className={`atk ${open ? "open" : ""}`} style={{ ["--ac" as any]: color }}>
      <button className="atk-head" onClick={onToggle}>
        <code className="atk-id">{a.probe_id}</code>
        <span className="atk-title">{a.title}</span>
        {!a.planned && <span className="atk-adaptive" title="Adaptively chosen (not in the fixed plan)">adaptive</span>}
        <span className={`exec-chip ex-${a.exec}`}>{EXEC_LABEL[a.exec]}</span>
        <span className={`vchip v-${a.verdict}`}>{VERDICT_LABEL[a.verdict]}</span>
        <span className="atk-chev">{open ? "▲" : "▾"}</span>
      </button>
      {open && <div className="atk-body">
        {a.exec === "skipped" && a.skipReason
          ? <div className="atk-skip"><strong>Skipped —</strong> {a.skipReason}</div>
          : a.exec === "pending"
            ? <div className="atk-skip">Planned but not yet executed.</div>
            : <>
                <div className="atk-stage"><div className="pipe-k" style={{ color }}>ATTACK</div><div className="pipe-v">{a.prompt || "—"}</div></div>
                <div className="atk-stage"><div className="pipe-k">OBSERVED</div><div className="pipe-v">{a.response || "—"}</div>
                  {proof.length > 0 && <div className="pipe-proof">{proof.map((e, i) => <span key={i} className="proof-chip">{e.kind}: {e.detail}</span>)}</div>}</div>
                <div className={`pipe-verdict v-${a.finding ? a.finding.status : a.verdict === "not_confirmed" ? "clear" : "inconclusive"}`}>
                  <div className="verdict-badge">{VERDICT_LABEL[a.verdict]}</div>
                  <div className="verdict-body">
                    <div className="verdict-meta">
                      <span className="muted">probe verdict: </span><strong>{a.rawVerdict ?? "—"}</strong>
                      {a.finding && <span className="muted"> · {a.finding.reproductions}/{a.finding.attempts} reproduced · {Math.round(a.finding.confirmation_rate * 100)}% (95% CI {Math.round(a.finding.ci_low * 100)}–{Math.round(a.finding.ci_high * 100)}%)</span>}
                    </div>
                  </div>
                </div>
                {shot && <a className="atk-shot" href={client.artifactUrl(missionId, shot)} target="_blank" rel="noreferrer">⤢ open browser evidence</a>}
              </>}
      </div>}
    </div>
  );
}

export function AttackTracker({ client, state, agents }: { client: AutoRedClient; state: MissionState; agents: AgentInfo[] }) {
  const [open, setOpen] = useState<string | null>(null);
  const info = useMemo(() => Object.fromEntries(agents.map((a) => [a.id, a])), [agents]);
  const { groups, totals } = useMemo(() => deriveAttacks(state), [state]);
  const pct = totals.planned ? Math.round((totals.executed / totals.planned) * 100) : 0;

  const hasAny = groups.some((g) => g.attacks.length > 0);
  return (
    <Section title="Attack Tracker" sub={`Every planned attack for mission ${state.mission_id || "—"}, grouped by specialist — execution status and security verdict from real mission data.`}>
      {!hasAny ? <div className="card"><Empty>No planned attacks recorded for this mission yet.</Empty></div> : <>
        <div className="atk-progress">
          <div className="atk-stats">
            {[{ l: "Planned", v: totals.planned }, { l: "Executed", v: totals.executed, c: "var(--accent)" },
              { l: "Pending", v: totals.pending, c: totals.pending ? "var(--warn)" : undefined },
              { l: "Skipped", v: totals.skipped }, { l: "Confirmed", v: totals.confirmed, c: "var(--crit)" }].map((s) => (
              <div key={s.l} className="stat-tile"><div className="stat-v" style={s.c ? { color: s.c } : undefined}>{s.v}</div><div className="stat-l">{s.l}</div></div>
            ))}
          </div>
          <div className="atk-bar" title={`${totals.executed} of ${totals.planned} planned attacks executed`}>
            <div className="atk-bar-fill" style={{ width: `${pct}%` }} /><span className="atk-bar-label">{pct}% executed</span>
          </div>
        </div>

        <div className="atk-groups">
          {groups.map((g) => {
            const i = info[g.agent];
            const conf = g.attacks.filter((a) => a.verdict === "confirmed").length;
            return (
              <div key={g.agent} className="atk-group" style={{ ["--ac" as any]: i?.color }}>
                <div className="atk-group-head">
                  <AgentCharacter color={i?.color ?? "#888"} cue={conf > 0 ? "confirmed" : "idle"} size={44} name={i?.name} agentId={g.agent as AgentId} />
                  <div className="atk-group-id">
                    <div className="atk-group-name">{i?.name ?? g.agent}</div>
                    <div className="atk-group-role" style={{ color: i?.color }}>{i?.role}</div>
                  </div>
                  <div className="atk-group-counts">
                    <span>{g.attacks.length} planned</span>
                    {conf > 0 && <span className="vchip v-confirmed sm">{conf} confirmed</span>}
                  </div>
                </div>
                {g.attacks.length === 0 ? <div className="faint" style={{ fontSize: 12.5, padding: "4px 14px 12px" }}>No attacks assigned.</div> :
                  <div className="atk-rows">
                    {g.attacks.map((a) => <AttackRow key={a.probe_id} client={client} missionId={state.mission_id}
                      a={a} info={i} open={open === a.probe_id} onToggle={() => setOpen(open === a.probe_id ? null : a.probe_id)} />)}
                  </div>}
              </div>
            );
          })}
        </div>
      </>}
    </Section>
  );
}
