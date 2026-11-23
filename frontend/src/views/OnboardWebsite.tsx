import { useEffect, useState } from "react";
import type { AutoRedClient } from "../api/client";

type Resp = any;

/** "Test Your AI Website": enter a URL you are authorized to test, onboard it as a
 * mission-compatible target (SSRF-checked), verify authorization, then launch. */
export function OnboardWebsite({ client, onReady }:
  { client: AutoRedClient; onReady: (targetId: string) => void }) {
  const [cfg, setCfg] = useState<{ enabled: boolean; allow_private_targets: boolean; admin_approval_available: boolean } | null>(null);
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [operator, setOperator] = useState("");
  const [scope, setScope] = useState("");
  const [wantProbes, setWantProbes] = useState(true);
  const [chatPath, setChatPath] = useState("/");
  const [adv, setAdv] = useState(false);
  const [sel, setSel] = useState({ input: "", send: "", launcher: "", frame: "" });
  const [login, setLogin] = useState({ path: "", username_selector: "", password_selector: "", submit_selector: "" });

  const [target, setTarget] = useState<Resp | null>(null);
  const [adminToken, setAdminToken] = useState("");
  const [reference, setReference] = useState("");
  const [approvedBy, setApprovedBy] = useState("");
  const [expires, setExpires] = useState("2027-12-31");

  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => { if (!client.isDemo) client.onboardingConfig().then(setCfg).catch(() => setCfg(null)); }, [client]);

  if (client.isDemo) {
    return (
      <section className="card pad onboard demo-onboard">
        <div className="onboard-head"><span className="onboard-badge">New</span>
          <h3>Test your own AI website</h3></div>
        <p className="muted" style={{ maxWidth: 680 }}>
          In the live app you enter the URL of an AI-powered site you're <strong>authorized</strong> to test.
          AutoRed validates the target (SSRF/DNS checks), verifies your authorization (domain token or
          administrator approval), runs a non-destructive discovery check, then Commander delegates applicable
          probes to Inky, Vault, Lexi and Guard — reusing the same engine, evidence verification and Attack Tracker.
        </p>
        <p className="faint" style={{ fontSize: 12 }}>Disabled in this public read-only demo. Explore recorded
          missions in Live Operations, the Attack Tracker and Findings.</p>
      </section>
    );
  }
  if (cfg && !cfg.enabled) return null;

  const onboard = async () => {
    setErr(null); setMsg(null); setBusy(true); setTarget(null);
    try {
      const body: Record<string, unknown> = {
        url, name, operator, scope_description: scope, chat_path: chatPath || "/",
        methods: wantProbes ? ["connectivity", "security_probes"] : ["connectivity"],
      };
      const chat_selectors: Record<string, string> = {};
      for (const k of ["input", "send", "launcher", "frame"] as const) if (sel[k].trim()) chat_selectors[k] = sel[k].trim();
      if (Object.keys(chat_selectors).length) body.chat_selectors = chat_selectors;
      if (login.path.trim()) body.login = Object.fromEntries(Object.entries(login).filter(([, v]) => v.trim()));
      setTarget(await client.onboardTarget(body));
      setMsg("Target onboarded. It is connectivity-only until authorization is verified below.");
    } catch (e) { setErr(String(e)); } finally { setBusy(false); }
  };

  const verifyAdmin = async () => {
    if (!target) return;
    setErr(null); setMsg(null); setBusy(true);
    try {
      const t = await client.verifyTarget(target.id, { method: "admin", admin_token: adminToken, reference, approved_by: approvedBy, expires });
      setTarget(t); setMsg("Authorization verified — security probes enabled.");
    } catch (e) { setErr(String(e)); } finally { setBusy(false); }
  };
  const verifyDomain = async () => {
    if (!target) return;
    setErr(null); setMsg(null); setBusy(true);
    try {
      const t = await client.verifyTarget(target.id, { method: "domain" });
      setTarget(t); setMsg("Domain control verified — security probes enabled.");
    } catch (e) { setErr(String(e)); } finally { setBusy(false); }
  };

  const verified = target?.verification?.status === "verified";
  const canProbe = target?.authorized_methods?.includes("security_probes");

  return (
    <section className="card pad onboard">
      <div className="onboard-head"><span className="onboard-badge">New</span>
        <h3>Test your own AI website</h3>
        <span className="faint" style={{ fontSize: 12, marginLeft: "auto" }}>
          {cfg?.allow_private_targets ? "dev mode: private targets allowed" : "public targets only"}</span>
      </div>
      <p className="muted" style={{ maxWidth: 720, marginTop: 2 }}>
        Enter a URL you are authorized to test. AutoRed validates it (SSRF/DNS), you prove authorization, a
        non-destructive discovery check confirms the chat interface, then you launch a real mission.
      </p>

      <div className="onboard-grid">
        <label className="field">Target URL
          <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://chat.example.com" /></label>
        <label className="field">Display name <span className="faint">(optional)</span>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Example Support Bot" /></label>
        <label className="field">Operator
          <input value={operator} onChange={(e) => setOperator(e.target.value)} placeholder="your name / id" /></label>
        <label className="field">Chat path
          <input value={chatPath} onChange={(e) => setChatPath(e.target.value)} placeholder="/ or /chat" /></label>
      </div>
      <label className="field">Testing scope / rules of engagement
        <textarea value={scope} onChange={(e) => setScope(e.target.value)} rows={2}
          placeholder="e.g. Authorized by engagement ENG-123. Non-destructive prompt-injection, leakage, hierarchy and tool-permission probes against the support assistant only." /></label>
      <label className="ack" style={{ marginTop: 4 }}>
        <input type="checkbox" checked={wantProbes} onChange={(e) => setWantProbes(e.target.checked)} />
        <span>Request active security probes (requires verified authorization — a checkbox alone is not enough)</span>
      </label>

      <button type="button" className="btn sm ghost" style={{ marginTop: 8, width: "fit-content" }}
        onClick={() => setAdv((a) => !a)}>{adv ? "▾" : "▸"} Advanced: manual chat/login configuration</button>
      {adv && <div className="onboard-adv">
        <div className="faint" style={{ fontSize: 12 }}>Only needed if auto-discovery fails or the chat requires sign-in. Leave blank to auto-discover.</div>
        <div className="onboard-grid">
          {(["input", "send", "launcher", "frame"] as const).map((k) => (
            <label key={k} className="field">chat {k} selector
              <input value={sel[k]} onChange={(e) => setSel({ ...sel, [k]: e.target.value })} placeholder={k === "input" ? "textarea#msg" : ""} /></label>))}
          {(["path", "username_selector", "password_selector", "submit_selector"] as const).map((k) => (
            <label key={k} className="field">login {k.replace("_selector", "")}
              <input value={login[k]} onChange={(e) => setLogin({ ...login, [k]: e.target.value })} placeholder={k === "path" ? "/login" : ""} /></label>))}
        </div>
      </div>}

      <button className="btn primary" style={{ marginTop: 12, width: "fit-content" }}
        disabled={busy || !url || !operator || !scope} onClick={onboard}>
        {busy ? <span className="spinner" /> : "Validate & onboard target"}</button>

      {err && <div className="sev-high" style={{ fontSize: 13, marginTop: 8 }}>{err}</div>}
      {msg && <div className="st-confirmed" style={{ fontSize: 13, marginTop: 8 }}>{msg}</div>}

      {target && <div className="onboard-result">
        <div className="row between"><strong>{target.name}</strong>
          <span className={verified ? "chip st-confirmed" : "chip st-candidate"}>{verified ? "✓ authorized" : "unverified"}</span></div>
        <div className="onboard-kv"><span className="muted">Resolved origin</span><code>{target.origin}</code></div>
        <div className="onboard-kv"><span className="muted">Resolved IPs (pinned)</span><code>{(target.resolved_ips || []).join(", ")}</code>
          <span className="chip st-confirmed" title="passed SSRF / DNS validation">SSRF ✓</span></div>
        <div className="onboard-kv"><span className="muted">Authorized methods</span>
          <span>{(target.authorized_methods || []).map((m: string) => <span key={m} className="chip" style={{ marginRight: 5 }}>{m}</span>)}</span></div>

        {!verified && <div className="onboard-verify">
          <div className="eyebrow">Verify authorization</div>
          <div className="onboard-verify-cols">
            <div>
              <div className="muted" style={{ fontSize: 12.5, marginBottom: 4 }}><strong>Option A — domain control.</strong> Serve this token, then verify:</div>
              <code className="onboard-token">{target.verification?.well_known_url}</code>
              <code className="onboard-token">{target.verification?.token}</code>
              <button className="btn sm" style={{ marginTop: 6 }} disabled={busy} onClick={verifyDomain}>Verify domain</button>
            </div>
            {cfg?.admin_approval_available && <div>
              <div className="muted" style={{ fontSize: 12.5, marginBottom: 4 }}><strong>Option B — administrator approval</strong> (written authorization):</div>
              <input className="onb-in" value={adminToken} onChange={(e) => setAdminToken(e.target.value)} placeholder="admin token" />
              <input className="onb-in" value={reference} onChange={(e) => setReference(e.target.value)} placeholder="authorization reference / ticket" />
              <input className="onb-in" value={approvedBy} onChange={(e) => setApprovedBy(e.target.value)} placeholder="approved by" />
              <input className="onb-in" value={expires} onChange={(e) => setExpires(e.target.value)} placeholder="expires YYYY-MM-DD" />
              <button className="btn sm" style={{ marginTop: 6 }} disabled={busy || !adminToken || !reference || !approvedBy} onClick={verifyAdmin}>Verify (admin)</button>
            </div>}
          </div>
        </div>}

        {verified && <button className="btn primary" style={{ marginTop: 10, width: "fit-content" }}
          onClick={() => onReady(target.id)}>
          Use in launcher {canProbe ? "(security probes enabled)" : "(connectivity only)"} →</button>}
      </div>}
    </section>
  );
}
