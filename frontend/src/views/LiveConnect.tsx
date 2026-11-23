import { useState } from "react";
import { createPortal } from "react-dom";

export type LiveConn = { url: string; token: string };

/** Lets a visitor on the public (static) site connect to a REAL AutoRed backend
 * they run themselves (locally or self-hosted). No backend => graceful "not
 * connected" state; the demo keeps working offline. */
export function LiveConnect({ current, onConnect, onDisconnect }:
  { current: LiveConn | null; onConnect: (c: LiveConn) => void; onDisconnect: () => void }) {
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState(current?.url ?? (import.meta.env.VITE_LIVE_API as string) ?? "");
  const [token, setToken] = useState(current?.token ?? "");
  const [state, setState] = useState<"idle" | "connecting" | "error">("idle");
  const [msg, setMsg] = useState("");

  if (current) {
    let origin = current.url;
    try { origin = new URL(current.url).host; } catch { /* keep as-is */ }
    return (
      <span className="row" style={{ gap: 8 }}>
        <span className="pill" style={{ color: "var(--ok)" }} title={current.url}>● LIVE · {origin}</span>
        <button className="btn sm ghost" onClick={onDisconnect}>Disconnect</button>
      </span>
    );
  }

  const connect = async () => {
    const base = url.trim().replace(/\/$/, "");
    if (!base) return;
    setState("connecting"); setMsg("");
    try {
      const r = await fetch(`${base}/api/health`, token.trim() ? { headers: { Authorization: `Bearer ${token.trim()}` } } : {});
      if (!r.ok) throw new Error(r.status === 401 ? "backend requires a valid access token" : `backend returned HTTP ${r.status}`);
      const h = await r.json();
      if (!h?.ok) throw new Error("backend health check failed");
      onConnect({ url: base, token: token.trim() });
      setOpen(false); setState("idle");
    } catch (e) {
      setState("error");
      setMsg(e instanceof TypeError ? "could not reach the backend (is it running? is CORS allowing this site?)" : String(e instanceof Error ? e.message : e));
    }
  };

  return (
    <span className="live-connect">
      <button className="btn sm" onClick={() => setOpen((o) => !o)}>⚡ Run live assessment</button>
      {open && createPortal(<div className="live-pop">
        <div className="eyebrow">Connect your AutoRed backend</div>
        <p className="faint" style={{ fontSize: 11.5, margin: "2px 0 8px" }}>
          This public site is read-only on its own. To run real missions, start a backend you
          control and connect to it. A public <code>https</code> backend works best; browsers
          restrict a public site from reaching <code>localhost</code> (see README).</p>
        <label className="field">Backend URL
          <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://your-space.hf.space" /></label>
        <label className="field">Access token <span className="faint">(if the backend requires one)</span>
          <input value={token} onChange={(e) => setToken(e.target.value)} placeholder="AUTORED_API_TOKEN" type="password" /></label>
        <button className="btn sm primary" style={{ marginTop: 8 }} disabled={state === "connecting" || !url.trim()} onClick={connect}>
          {state === "connecting" ? <span className="spinner" /> : "Connect"}</button>
        {state === "error" && <div className="sev-high" style={{ fontSize: 12, marginTop: 6 }}>{msg}</div>}
        <div className="faint" style={{ fontSize: 11, marginTop: 8 }}>
          No backend yet? <code>git clone</code> the repo and run <code>scripts/run-local.sh</code> — see the README.</div>
      </div>, document.body)}
    </span>
  );
}
