import type { AgentInfo, AutoRedEvent, FindingPayload, TargetInfo } from "../contracts/events";

export interface ClientOptions { baseUrl?: string; token?: string; demo?: boolean }

export class AutoRedClient {
  private base: string;
  private token?: string;
  /** Public read-only demo: all data comes from sanitized static JSON; no backend,
   * no token, and every mutating/control action is refused. */
  readonly isDemo: boolean;
  private demoBase: string;
  constructor(opts: ClientOptions = {}) {
    this.base = opts.baseUrl ?? "";
    this.token = opts.token;
    this.isDemo = !!opts.demo;
    this.demoBase = (import.meta.env.BASE_URL ?? "/") + "demo/";
  }

  /** Map a REST path to its static demo file (GET-only surface). */
  private demoFile(path: string): string | null {
    if (path === "/api/health") return "health";
    if (path === "/api/agents") return "agents";
    if (path === "/api/targets") return "targets";
    if (path === "/api/missions") return "missions";
    if (path === "/api/experiments") return "experiments";
    const m = path.match(/^\/api\/missions\/([^/]+)(?:\/(report|events|findings))?$/);
    if (m) return `missions/${m[1]}/${m[2] ?? "snapshot"}`;
    return null;
  }

  private async req<T>(path: string, init: RequestInit = {}): Promise<T> {
    if (this.isDemo) {
      if (init.method && init.method !== "GET")
        throw new Error("This action is disabled in the public read-only demo.");
      const f = this.demoFile(path);
      if (!f) throw new Error("Not available in the demo.");
      const r = await fetch(`${this.demoBase}${f}.json`);
      if (!r.ok) throw new Error(`demo data ${f} unavailable (HTTP ${r.status})`);
      return r.json();
    }
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (this.token) headers.Authorization = `Bearer ${this.token}`;
    const r = await fetch(this.base + path, { ...init, headers: { ...headers, ...(init.headers as object) } });
    if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail ?? `HTTP ${r.status}`);
    return r.json();
  }

  health = () => this.req<any>("/api/health");
  agents = () => this.req<AgentInfo[]>("/api/agents");
  targets = () => this.req<TargetInfo[]>("/api/targets");
  missions = () => this.req<any[]>("/api/missions");
  mission = (id: string) => this.req<any>(`/api/missions/${id}`);
  missionReport = (id: string) => this.req<any>(`/api/missions/${id}/report`);
  events = (id: string) => this.req<AutoRedEvent[]>(`/api/missions/${id}/events`);
  experiments = () => this.req<Record<string, any>>("/api/experiments");
  findings = (id: string) => this.req<FindingPayload[]>(`/api/missions/${id}/findings`);
  createMission = (body: { target_id: string; operator: string; authorization_acknowledged: boolean; agents?: string[] }) =>
    this.req<any>("/api/missions", { method: "POST", body: JSON.stringify(body) });
  stopMission = (id: string) => this.req<{ stopped: boolean }>(`/api/missions/${id}/stop`, { method: "POST" });

  // --- dynamic target onboarding ("test your AI website") ---
  onboardingConfig = () => this.req<{ enabled: boolean; allow_private_targets: boolean; admin_approval_available: boolean }>("/api/onboarding/config");
  onboardingTargets = () => this.req<any[]>("/api/onboarding/targets");
  onboardTarget = (body: Record<string, unknown>) =>
    this.req<any>("/api/onboarding/targets", { method: "POST", body: JSON.stringify(body) });
  verifyTarget = (id: string, body: Record<string, unknown>) =>
    this.req<any>(`/api/onboarding/targets/${id}/verify`, { method: "POST", body: JSON.stringify(body) });
  emergencyStop = (reason: string) => this.req<{ stopped: string[] }>("/api/emergency-stop", { method: "POST", body: JSON.stringify({ reason }) });
  resetEmergencyStop = () => this.req("/api/emergency-stop/reset", { method: "POST" });

  artifactUrl = (missionId: string, name: string) =>
    this.isDemo ? `${this.demoBase}missions/${missionId}/artifacts/${name}`
                : `${this.base}/api/missions/${missionId}/artifacts/${name}`;

  private wsUrl(path: string, params: Record<string, string | number> = {}) {
    const origin = this.base || window.location.origin;
    const u = new URL(path, origin.replace(/^http/, "ws"));
    if (this.token) u.searchParams.set("token", this.token);
    for (const [k, v] of Object.entries(params)) u.searchParams.set(k, String(v));
    return u.toString();
  }

  /** Event stream with automatic resume: reconnects with since=<last seq seen>. */
  streamEvents(missionId: string, since: number, onEvent: (e: AutoRedEvent) => void, onClose?: () => void): () => void {
    if (this.isDemo) { onClose?.(); return () => {}; } // demo missions are recorded, never streamed
    let last = since, stopped = false, ws: WebSocket | null = null, retry = 500;
    const open = () => {
      ws = new WebSocket(this.wsUrl(`/ws/missions/${missionId}`, { since: last }));
      ws.onmessage = (m) => { const e = JSON.parse(m.data) as AutoRedEvent; last = Math.max(last, e.seq); retry = 500; onEvent(e); };
      ws.onclose = (ev) => {
        if (stopped) return;
        if (ev.code === 1000) { onClose?.(); return; } // mission finished
        setTimeout(open, (retry = Math.min(retry * 2, 8000)));
      };
    };
    open();
    return () => { stopped = true; ws?.close(); };
  }

  /** Live browser frames (JPEG) as object URLs. Caller revokes previous URLs. */
  streamFrames(missionId: string, agentId: string, onFrame: (objectUrl: string) => void): () => void {
    if (this.isDemo) return () => {};
    const ws = new WebSocket(this.wsUrl(`/ws/missions/${missionId}/agents/${agentId}/frames`));
    ws.binaryType = "blob";
    ws.onmessage = (m) => onFrame(URL.createObjectURL(m.data as Blob));
    return () => ws.close();
  }
}
