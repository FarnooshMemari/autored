from __future__ import annotations

import re
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from ..agents.specialist import AGENT_IDENTITY
from ..browser.runtime import BrowserRuntime, FrameHub
from ..config import Settings
from ..events.schema import ALL_AGENT_IDS, SCHEMA_VERSION, Event, FindingPayload
from ..missions.manager import MissionManager, MissionRejected
from ..missions.snapshot import MissionSnapshot
from ..onboarding import OnboardingError, OnboardingRegistry, SSRFError, validate_target_url
from ..onboarding.verify import verify_domain
from ..safety.scope import ScopeRegistry
from ..storage.store import MissionStore


class CreateMission(BaseModel):
    target_id: str
    operator: str = Field(min_length=1)
    authorization_acknowledged: bool = Field(description="Operator confirms written authorization for this target")
    agents: list[str] | None = Field(default=None, description="Subset of specialists; default all four")
    mode: str = Field(default="assess", description="assess | adaptive | hybrid | connectivity")


class EmergencyStopBody(BaseModel):
    reason: str = "operator emergency stop"


class OnboardTarget(BaseModel):
    url: str = Field(description="Target website URL (http/https) the operator is authorized to test")
    name: str = ""
    operator: str = Field(min_length=1)
    scope_description: str = Field(min_length=1, description="Written testing scope / rules of engagement")
    methods: list[str] = Field(default_factory=lambda: ["connectivity"],
                               description="Requested methods: connectivity and/or security_probes")
    chat_path: str = "/"
    chat_selectors: dict | None = None   # manual fallback: input/send/send_mode/assistant_message/frame/launcher
    login: dict | None = None            # optional LoginConfig fields
    # optional owner-supplied test material (enables deeper, evidence-based probes)
    canaries: list[dict] | None = None
    accounts: dict | None = None
    authorized_tools: list[str] | None = None
    oracle_audit_path: str | None = None


class VerifyTarget(BaseModel):
    method: str = Field(description="'domain' (well-known token) or 'admin' (admin-approved authorization)")
    admin_token: str | None = None
    reference: str | None = None
    approved_by: str | None = None
    expires: str | None = None           # ISO date for the admin authorization record


class AgentInfo(BaseModel):
    id: str
    name: str = Field(description="Character name, e.g. Inky")
    role: str
    color: str
    kind: str
    slot: int = Field(description="Stable UI slot: 0 = commander, 1-4 = specialists")


def create_app(settings: Settings | None = None, scopes: ScopeRegistry | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    runtime, frames = BrowserRuntime(headless=settings.headless), FrameHub()
    scope_reg = scopes or ScopeRegistry.load(settings.scope_path)
    manager = MissionManager(scope_reg, runtime, frames,
                             settings.runs_dir, settings.max_active_missions, store=MissionStore(settings.db_path))
    onboarding = OnboardingRegistry(scope_reg, settings.onboarding_store) if settings.enable_onboarding else None

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            rec = manager.reconcile()
            if rec:
                import logging; logging.getLogger("autored").warning("reconciled interrupted missions: %s", rec)
        except Exception as e:
            import logging; logging.getLogger("autored").warning("reconcile failed: %s", e)
        yield
        await manager.emergency_stop("server shutdown")
        await runtime.close()

    # A public-facing instance must not run wide open: require an access token.
    if settings.public_mode and not settings.api_token:
        raise RuntimeError("AUTORED_PUBLIC_MODE=1 requires AUTORED_API_TOKEN to be set "
                           "(a public instance must not accept unauthenticated requests)")

    app = FastAPI(title="AutoRed", version="0.1.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins),
                       allow_methods=["*"], allow_headers=["*"])

    # Registered AFTER CORS so it is the OUTERMOST middleware and can answer the
    # Private-Network-Access preflight before CORS does. Chrome blocks a public (https)
    # page from reaching a local/loopback backend unless the server opts in here.
    @app.middleware("http")
    async def _private_network_access(request: Request, call_next):
        if (request.method == "OPTIONS"
                and request.headers.get("access-control-request-private-network") == "true"):
            from starlette.responses import Response as _R
            origin = request.headers.get("origin", "")
            allowed = "*" in settings.cors_origins or origin in settings.cors_origins
            resp = _R(status_code=204)
            if allowed and origin:
                resp.headers["Access-Control-Allow-Origin"] = origin
                resp.headers["Access-Control-Allow-Private-Network"] = "true"
                resp.headers["Access-Control-Allow-Methods"] = "*"
                resp.headers["Access-Control-Allow-Headers"] = "*"
                resp.headers["Vary"] = "Origin"
            return resp
        return await call_next(request)

    app.state.manager = manager

    def auth(request: Request) -> None:
        if settings.api_token and request.headers.get("authorization") != f"Bearer {settings.api_token}":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "missing or invalid bearer token")

    async def ws_auth(ws: WebSocket) -> bool:
        if settings.api_token and ws.query_params.get("token") != settings.api_token:
            await ws.close(code=4401)
            return False
        return True

    def mission_or_404(mid: str):
        m = manager.missions.get(mid)
        if not m:
            raise HTTPException(404, "mission not found")
        return m

    def resolve(mid: str):
        """Return (snapshot, live). Live missions come from memory; completed/
        interrupted ones are rebuilt from the durable event log + store."""
        from ..missions.snapshot import MissionSnapshot
        from ..reporting.report import replay
        m = manager.missions.get(mid)
        if m is not None:
            return m.snapshot, m.active
        if not re.fullmatch(r"M-[\w-]+", mid):
            raise HTTPException(400, "bad mission id")
        row = manager.store.get_mission(mid) if manager.store else None
        ev_path = settings.runs_dir / mid / "events.jsonl"
        if ev_path.is_file():
            snap, _ = replay(ev_path)            # rebuilds findings/agents/timeline from the log
            if row:
                # authoritative metadata from the store row; the log (which for an interrupted
                # mission has no mission.completed) must NOT override the reconciled phase/summary.
                from ..events.schema import MissionPhase, MissionSummaryPayload
                snap.target_id, snap.operator = row["target_id"], row["operator"]
                snap.phase = MissionPhase(row["phase"])
                if row["summary"]:
                    snap.summary = MissionSummaryPayload.model_validate_json(row["summary"])
            return snap, False
        if row:   # store row but no event log: minimal reconstruction from stored findings
            from ..events.schema import FindingPayload, MissionPhase
            snap = MissionSnapshot.new(mid, row["target_id"], row["operator"])
            snap.phase = MissionPhase(row["phase"])
            for f in manager.store.get_findings(mid):
                fp = FindingPayload(finding_id=f["finding_id"], probe_id=f["probe_id"], category=f["category"],
                                    title=f["title"], severity=f["severity"], status=f["status"],
                                    reproductions=f["reproductions"], attempts=f["attempts"],
                                    prompt=f["prompt"] or "", evidence=f["evidence"])
                snap.findings[f["finding_id"]] = fp
            return snap, False
        raise HTTPException(404, "mission not found")

    api = Depends(auth)

    @app.get("/api/health")
    async def health():
        active = manager.active()
        return {"ok": True, "schema_version": SCHEMA_VERSION, "emergency_stop": manager.estop.engaged,
                "emergency_stop_reason": manager.estop.reason,
                "active_missions": [m.id for m in active], "total_missions": len(manager.missions),
                "max_active": manager.max_active, "headless": settings.headless,
                "public_mode": settings.public_mode, "live": True,
                "onboarding_enabled": onboarding is not None,
                "demo_locked": bool(settings.demo_target_origins)}

    @app.get("/api/agents", response_model=list[AgentInfo], dependencies=[api])
    async def agents():
        return [AgentInfo(id=a, name=AGENT_IDENTITY[a]["name"], role=AGENT_IDENTITY[a]["role"],
                         color=AGENT_IDENTITY[a]["color"],
                         kind="commander" if a == "commander" else "specialist", slot=i)
                for i, a in enumerate(ALL_AGENT_IDS)]

    @app.get("/api/targets", dependencies=[api])
    async def targets():
        onboarded_ids = {ot.target.id for ot in onboarding.list()} if onboarding else set()
        return [{"id": t.id, "name": t.name, "base_url": t.base_url,
                 "authorization": t.authorization.model_dump(mode="json"),
                 "authorized_methods": list(t.authorized_methods),
                 "onboarded": t.id in onboarded_ids,
                 "limits": t.limits.model_dump()} for t in manager.scopes.list()]

    def _onboarding_or_404() -> OnboardingRegistry:
        if onboarding is None:
            raise HTTPException(404, "target onboarding is disabled on this deployment")
        return onboarding

    @app.get("/api/onboarding/config", dependencies=[api])
    async def onboarding_config():
        return {"enabled": onboarding is not None,
                "allow_private_targets": settings.allow_private_targets,
                "admin_approval_available": bool(settings.admin_token),
                "public_mode": settings.public_mode,
                "demo_target_origins": list(settings.demo_target_origins)}

    @app.get("/api/onboarding/targets", dependencies=[api])
    async def onboarding_list():
        reg = _onboarding_or_404()
        return [ot.public_view() for ot in reg.list()]

    @app.post("/api/onboarding/targets", status_code=201, dependencies=[api])
    async def onboarding_create(body: OnboardTarget):
        reg = _onboarding_or_404()
        try:
            resolved = validate_target_url(body.url, allow_private=settings.allow_private_targets)
        except SSRFError as e:
            raise HTTPException(422, f"URL rejected: {e}")
        # Hosted-demo safety lock: when a bundled-sandbox allowlist is configured, this
        # instance is NOT an open scanner — it may only test the pre-authorized origin(s).
        if settings.demo_target_origins and resolved.origin not in settings.demo_target_origins:
            raise HTTPException(403, "this public instance only tests its bundled sandbox target; "
                                "arbitrary third-party URLs are not permitted here. Run AutoRed locally "
                                "to test a site you are authorized to assess.")
        try:
            ot = reg.onboard(
                resolved, name=body.name, scope_description=body.scope_description,
                requested_methods=body.methods, operator=body.operator,
                chat_path=body.chat_path, chat_selectors=body.chat_selectors, login=body.login,
                canaries=body.canaries, accounts=body.accounts,
                authorized_tools=body.authorized_tools, oracle_audit_path=body.oracle_audit_path)
        except OnboardingError as e:
            raise HTTPException(409, str(e))
        return ot.public_view()

    @app.post("/api/onboarding/targets/{tid}/verify", dependencies=[api])
    async def onboarding_verify(tid: str, body: VerifyTarget):
        from datetime import date as _date
        reg = _onboarding_or_404()
        if reg.get(tid) is None:
            raise HTTPException(404, "onboarded target not found")
        try:
            if body.method == "domain":
                detail = verify_domain(reg, tid, allow_private=settings.allow_private_targets)
                ot = reg.mark_verified(tid, method="domain", reference=f"domain-verified:{tid}",
                                       approved_by="domain-control", expires=_date.today().replace(year=_date.today().year + 1),
                                       detail=detail)
            elif body.method == "admin":
                if not settings.admin_token or body.admin_token != settings.admin_token:
                    raise HTTPException(403, "invalid or missing admin token")
                if not (body.reference and body.approved_by and body.expires):
                    raise HTTPException(422, "admin approval requires reference, approved_by and expires")
                try:
                    exp = _date.fromisoformat(body.expires)
                except ValueError:
                    raise HTTPException(422, "expires must be an ISO date (YYYY-MM-DD)")
                ot = reg.mark_verified(tid, method="admin", reference=body.reference,
                                       approved_by=body.approved_by, expires=exp,
                                       detail="administrator-approved written authorization")
            else:
                raise HTTPException(422, "method must be 'domain' or 'admin'")
        except OnboardingError as e:
            raise HTTPException(422, str(e))
        return ot.public_view()

    @app.post("/api/missions", status_code=201, response_model=MissionSnapshot, dependencies=[api])
    async def create(body: CreateMission):
        try:
            m = manager.create(body.target_id, body.operator, body.authorization_acknowledged, body.agents, mode=body.mode)
        except MissionRejected as e:
            raise HTTPException(409, str(e))
        return m.snapshot

    @app.get("/api/missions", dependencies=[api])
    async def list_missions():
        live = [{"mission_id": m.id, "target_id": m.ctx.target.id, "phase": m.snapshot.phase.value,
                 "created_at": m.created_at.isoformat(), "active": m.active, "source": "live"}
                for m in manager.missions.values()]
        live_ids = set(manager.missions)
        stored = []
        if manager.store is not None:
            for row in manager.store.list_missions(limit=200):
                if row["id"] not in live_ids:
                    stored.append({"mission_id": row["id"], "target_id": row["target_id"], "phase": row["phase"],
                                   "created_at": row["created_at"], "active": False, "mode": row["mode"],
                                   "confirmed": row["confirmed"], "source": "stored"})
        return sorted(live + stored, key=lambda m: m["created_at"], reverse=True)

    @app.get("/api/missions/{mid}", dependencies=[api])
    async def get_mission(mid: str):
        snap, live = resolve(mid)
        return {**snap.model_dump(mode="json"), "live": live}

    @app.get("/api/missions/{mid}/events", response_model=list[Event], dependencies=[api])
    async def events(mid: str, since: int = 0):
        m = manager.missions.get(mid)
        if m is not None:
            return [e for e in m.ctx.log.events if e.seq > since]
        if not re.fullmatch(r"M-[\w-]+", mid):
            raise HTTPException(400, "bad mission id")
        ev_path = settings.runs_dir / mid / "events.jsonl"
        if not ev_path.is_file():
            raise HTTPException(404, "no event log")
        return [e for e in (Event.model_validate_json(l) for l in ev_path.read_text().splitlines() if l.strip()) if e.seq > since]

    @app.get("/api/missions/{mid}/findings", response_model=list[FindingPayload], dependencies=[api])
    async def findings(mid: str):
        snap, _ = resolve(mid)
        return list(snap.findings.values())

    @app.get("/api/missions/{mid}/report", dependencies=[api])
    async def mission_report(mid: str):
        from ..reporting.report import report_json
        snap, _ = resolve(mid)   # authoritative phase/summary/metadata/findings (incl. interrupted + store-only)
        events: list[Event] = []
        m = manager.missions.get(mid)
        if m is not None:
            events = m.ctx.log.events
        else:
            ev_path = settings.runs_dir / mid / "events.jsonl"
            if ev_path.is_file():
                events = [Event.model_validate_json(l) for l in ev_path.read_text().splitlines() if l.strip()]
        return report_json(snap, events)

    @app.get("/api/experiments", dependencies=[api])
    async def experiments():
        import json as _json
        from ..config import ROOT
        out = {}
        d = ROOT / "pilots" / "experiments"
        if d.is_dir():
            for f in sorted(d.glob("*.json")):
                try:
                    out[f.stem] = _json.loads(f.read_text())
                except Exception:
                    pass
        return out

    @app.post("/api/missions/{mid}/stop", dependencies=[api])
    async def stop(mid: str):
        mission_or_404(mid)
        return {"stopped": await manager.stop(mid)}

    @app.post("/api/emergency-stop", dependencies=[api])
    async def estop(body: EmergencyStopBody):
        return {"engaged": True, "stopped": await manager.emergency_stop(body.reason)}

    @app.post("/api/emergency-stop/reset", dependencies=[api])
    async def estop_reset():
        manager.estop.reset()
        return {"engaged": False}

    @app.get("/api/missions/{mid}/agents/{agent}/frame.jpg", dependencies=[api])
    async def frame(mid: str, agent: str):
        f = frames.latest(mid, agent)   # live only; historical missions use recorded screenshots
        if f is None:
            raise HTTPException(404, "no live frame (mission not active, or not started)")
        return Response(f, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.get("/api/missions/{mid}/artifacts/{name}", dependencies=[api])
    async def artifact(mid: str, name: str):
        # evidence lives on disk under runs/<mid>/artifacts; served for live AND historical missions
        if not re.fullmatch(r"M-[\w-]+", mid) or not re.fullmatch(r"[\w.-]+\.png", name):
            raise HTTPException(400, "bad id or artifact name")
        p = settings.runs_dir / mid / "artifacts" / name
        if not p.is_file():
            raise HTTPException(404, "artifact not found")
        return FileResponse(p)

    @app.websocket("/ws/missions/{mid}")
    async def ws_events(ws: WebSocket, mid: str):
        if not await ws_auth(ws):
            return
        m = manager.missions.get(mid)
        if not m:
            await ws.close(code=4404)
            return
        await ws.accept()
        since = int(ws.query_params.get("since", 0))
        try:
            async for e in m.ctx.log.subscribe(since):
                await ws.send_text(e.model_dump_json())
            await ws.close(code=1000)
        except WebSocketDisconnect:
            pass

    @app.websocket("/ws/missions/{mid}/agents/{agent}/frames")
    async def ws_frames(ws: WebSocket, mid: str, agent: str):
        if not await ws_auth(ws):
            return
        if mid not in manager.missions or agent not in ALL_AGENT_IDS:
            await ws.close(code=4404)
            return
        await ws.accept()
        q = frames.subscribe(mid, agent)
        try:
            while True:
                await ws.send_bytes(await q.get())
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            frames.unsubscribe(mid, agent, q)

    return app
