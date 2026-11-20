import { useEffect, useState } from "react";
import type { AutoRedClient } from "../api/client";
import { BarChart, Empty, Legend, Section } from "../components/common";

export function Experiments({ client }: { client: AutoRedClient }) {
  const [data, setData] = useState<Record<string, any> | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { client.experiments().then(setData).catch((e) => setErr(String(e))); }, [client]);

  if (err) return <Section title="Experiment Analytics"><div className="card"><Empty>{err}</Empty></div></Section>;
  if (!data) return <Section title="Experiment Analytics"><div className="card"><Empty><span className="spinner" /> loading…</Empty></div></Section>;

  const bva = data.baseline_vs_adaptive?.results;
  const three = data.three_strategies?.analysis;
  const rep = data.repeated_trials;
  const vvh = data.vuln_vs_hardened;

  return (
    <Section title="Experiment Analytics" sub="Real runs against the authorized local target. Honest results, including negatives.">
      {bva && <div className="card pad" style={{ marginBottom: 14 }}>
        <div className="row between" style={{ marginBottom: 10 }}><strong>Fixed vs Adaptive vs Held-out (single trial)</strong>
          <Legend items={[{ label: "confirmed", color: "#34d399" }, { label: "probes", color: "#818cf8" }, { label: "LLM calls", color: "#f97316" }]} /></div>
        <BarChart height={160} groups={["baseline", "adaptive", "held-out hardened"]}
          colors={["#34d399", "#818cf8", "#f97316"]}
          series={[
            { label: "confirmed", values: [bva.baseline_vulnerable?.n_confirmed ?? 0, bva.adaptive_vulnerable?.n_confirmed ?? 0, bva.adaptive_hardened_heldout?.n_confirmed ?? 0] },
            { label: "probes", values: [bva.baseline_vulnerable?.probes_run ?? 0, bva.adaptive_vulnerable?.probes_run ?? 0, bva.adaptive_hardened_heldout?.probes_run ?? 0] },
            { label: "llm", values: [bva.baseline_vulnerable?.llm_calls ?? 0, bva.adaptive_vulnerable?.llm_calls ?? 0, bva.adaptive_hardened_heldout?.llm_calls ?? 0] },
          ]} />
        <div className="card pad" style={{ background: "rgba(251,191,36,.08)", border: "1px solid rgba(251,191,36,.25)", marginTop: 10, fontSize: 12.5 }}>
          <strong className="sev-medium">Honest result:</strong> the fixed baseline found more confirmed vulnerabilities than the adaptive planner;
          adaptive was more probe-efficient but did not discover anything the baseline missed. We do not claim adaptive improves discovery.
        </div>
      </div>}

      {three && <div className="card pad" style={{ marginBottom: 14 }}>
        <div className="row between" style={{ marginBottom: 10 }}><strong>Fixed vs Adaptive vs Hybrid</strong>
          <span className="sub">deduplicated by vulnerability class</span></div>
        <table><thead><tr><th>Strategy</th><th>Confirmed</th><th>Vuln classes</th><th>Probes</th><th>LLM</th><th>Duration</th></tr></thead>
          <tbody>{["assess","adaptive","hybrid"].map((m) => three[m] && (
            <tr key={m}><td style={{textTransform:"capitalize"}}>{m==="assess"?"Fixed":m}</td>
              <td className="st-confirmed">{three[m].n_confirmed}</td>
              <td className="muted">{(three[m].classes||[]).join(", ")||"—"}</td>
              <td>{three[m].probes}</td><td>{three[m].llm_calls}</td><td>{three[m].duration_s}s</td></tr>
          ))}</tbody></table>
        <div className="card pad" style={{ background: "rgba(251,191,36,.08)", border: "1px solid rgba(251,191,36,.25)", marginTop: 10, fontSize: 12.5 }}>
          <strong className="sev-medium">Honest result:</strong> hybrid confirmed one extra probe but of the <em>same</em> vulnerability
          class — deduplicated by class, hybrid = fixed coverage at higher cost. No evidence adaptive/hybrid improves discovery here.
        </div>
      </div>}

      <div className="grid" style={{ gridTemplateColumns: "1fr 1fr", gap: 14 }}>
        {rep && <div className="card pad">
          <strong>Reproducibility (N=3 trials each)</strong>
          <table style={{ marginTop: 10 }}><thead><tr><th></th><th>Baseline</th><th>Adaptive</th></tr></thead>
            <tbody>
              <tr><td className="muted">Confirmed (mean)</td><td>{rep.baseline?.confirmed_mean}</td><td>{rep.adaptive?.confirmed_mean}</td></tr>
              <tr><td className="muted">Range</td><td>{rep.baseline?.confirmed_min}–{rep.baseline?.confirmed_max}</td><td>{rep.adaptive?.confirmed_min}–{rep.adaptive?.confirmed_max}</td></tr>
              <tr><td className="muted">Tool-perm detected</td><td className="st-confirmed">{rep.baseline?.tool_permission_detected_in}</td><td className="sev-medium">{rep.adaptive?.tool_permission_detected_in}</td></tr>
              <tr><td className="muted">Mean probes</td><td>{rep.baseline?.mean_probes}</td><td>{rep.adaptive?.mean_probes}</td></tr>
              <tr><td className="muted">Mean duration</td><td>{rep.baseline?.mean_duration_s}s</td><td>{rep.adaptive?.mean_duration_s}s</td></tr>
            </tbody></table>
        </div>}

        {vvh && <div className="card pad">
          <strong>Vulnerable vs Hardened (authorization)</strong>
          {(() => { const a = vvh.analysis_corrected?.authorization_axis ?? {}; return (
            <table style={{ marginTop: 10 }}><thead><tr><th></th><th>Vulnerable</th><th>Hardened</th></tr></thead>
              <tbody>
                <tr><td className="muted">Tool-perm confirmed</td><td className="st-confirmed">{(a.vulnerable_confirmed ?? []).length || "—"}</td><td className="st-confirmed">{(a.hardened_confirmed ?? []).length || 0}</td></tr>
                <tr><td className="muted">Customer refund executions</td><td className="sev-critical">{a.vulnerable_customer_refund_executions ?? "—"}</td><td className="st-confirmed">{a.hardened_customer_refund_executions ?? 0} (rejected)</td></tr>
                <tr><td className="muted">False positives</td><td>—</td><td className="st-confirmed">{(a.false_positives_on_hardened ?? []).length}</td></tr>
              </tbody></table>); })()}
          <div className="sub" style={{ marginTop: 8 }}>AutoRed confirms the violation on the vulnerable config and reports zero on the hardened config — no false positives.</div>
        </div>}
      </div>
    </Section>
  );
}
