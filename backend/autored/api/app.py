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
    manager = MissionManager(scopes or ScopeRegistry.load(settings.scope_path), runtime, frames,
                             settings.runs_dir, settings.max_active_missions, store=MissionStore(settings.db_path))

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

    app = FastAPI(title="AutoRed", version="0.1.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins),
                       allow_methods=["*"], allow_headers=["*"])
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
                "max_active": manager.max_active, "headless": settings.headless}

    @app.get("/api/agents", response_model=list[AgentInfo], dependencies=[api])
    async def agents():
        return [AgentInfo(id=a, name=AGENT_IDENTITY[a]["name"], role=AGENT_IDENTITY[a]["role"],
                         color=AGENT_IDENTITY[a]["color"],
                         kind="commander" if a == "commander" else "specialist", slot=i)
                for i, a in enumerate(ALL_AGENT_IDS)]

    @app.get("/api/targets", dependencies=[api])
    async def targets():
        return [{"id": t.id, "name": t.name, "base_url": t.base_url,
                 "authorization": t.authorization.model_dump(mode="json"),
                 "limits": t.limits.model_dump()} for t in manager.scopes.list()]

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
