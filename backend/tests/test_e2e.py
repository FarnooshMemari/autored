"""End-to-end: real Chromium, real AcmeHelp target over HTTP, real agents."""
from __future__ import annotations

import asyncio
import json
from collections import defaultdict

import httpx
import pytest
import websockets

from autored.api.app import create_app
from autored.browser.runtime import AgentBrowser, BrowserRuntime, FrameHub
from autored.config import Settings
from autored.events.schema import SPECIALIST_IDS, AgentStatus, FindingStatus, MissionPhase, Verdict
from autored.missions.manager import MissionManager, MissionRejected
from conftest import ServerThread, free_port, requires_browser

pytestmark = [pytest.mark.e2e, requires_browser]


@pytest.fixture
async def runtime():
    rt = BrowserRuntime(headless=True)
    yield rt
    await rt.close()


def manager(scopes, runtime, tmp_path, **kw):
    return MissionManager(scopes, runtime, FrameHub(), tmp_path, **kw)


async def run_to_end(mgr, **kw):
    m = mgr.create("acmehelp-local", "pytest", True, **kw)
    await asyncio.wait_for(m.task, 120)
    return m


async def test_vulnerable_target_full_mission(vulnerable_target, scopes_for, runtime, tmp_path):
    mgr = manager(scopes_for(vulnerable_target.url), runtime, tmp_path)
    m = await run_to_end(mgr)
    s, events = m.snapshot, m.ctx.log.events

    assert s.phase == MissionPhase.completed, s.summary
    assert s.capabilities.assistant_detected and "issue_refund" in s.capabilities.tools
    assert "TP-002" in s.plan.skipped and "not authorized" in s.plan.skipped["TP-002"]

    confirmed = {f.probe_id for f in s.findings.values() if f.status == FindingStatus.confirmed}
    assert confirmed == {"PI-001", "PI-002", "DL-001", "DL-002", "IH-001", "TP-001"}
    for f in s.findings.values():
        assert f.reproductions >= 2 and any(e.kind in ("canary", "oracle") for e in f.evidence)
        assert any(e.kind == "screenshot" and (m.ctx.artifacts_dir / e.artifact).is_file() for e in f.evidence)

    verdicts = {e.payload["probe_id"]: e.payload["verdict"] for e in events
                if e.type == "test.verdict" and e.payload["attempt"] == 1}
    assert verdicts["PI-003"] == verdicts["IH-002"] == Verdict.not_observed.value

    # Real execution trail: gap-free sequence, every specialist navigated in its own context
    assert [e.seq for e in events] == list(range(1, len(events) + 1))
    contexts = defaultdict(set)
    for e in events:
        if e.type == "browser.navigated":
            contexts[e.agent_id].add(e.payload["context_id"])
    assert set(SPECIALIST_IDS) <= set(contexts)
    all_ctx = [c for cs in contexts.values() for c in cs]
    assert len(all_ctx) == len(set(all_ctx)), "agents must never share a browser context"

    # Each agent authenticated as its own test account
    users = {e.agent_id: e.payload["value_preview"] for e in events
             if e.type == "browser.action" and e.payload["selector"] == "#username"}
    assert len(set(users.values())) == 5

    # Commander assigned every task; validation tasks only follow candidates
    assigned = [e for e in events if e.type == "task.assigned"]
    assert all(e.agent_id == "commander" for e in assigned)
    assert sum(e.payload["kind"] == "validate" for e in assigned) == len(s.findings)
    assert all(a.status == AgentStatus.done for a in s.agents.values())
    assert (tmp_path / m.id / "events.jsonl").is_file() and (tmp_path / m.id / "authorization.txt").is_file()


async def test_hardened_target_has_no_findings(hardened_target, scopes_for, runtime, tmp_path):
    m = await run_to_end(manager(scopes_for(hardened_target.url), runtime, tmp_path))
    assert m.snapshot.phase == MissionPhase.completed
    assert m.snapshot.findings == {}
    assert m.snapshot.summary.probes_run == 8  # each in-scope probe ran once; nothing to replay


async def test_shared_state_oracle_attribution(vulnerable_target, scopes_for, runtime, tmp_path):
    """Refund ledger is server-side shared state; oracle reads are per-account."""
    m = await run_to_end(manager(scopes_for(vulnerable_target.url), runtime, tmp_path), agents=["tools"])
    audit = vulnerable_target.app.state.acme.audit
    refunds = [a for a in audit if a["tool"] == "issue_refund"]
    assert refunds and {a["user"] for a in refunds} == {"tester4"}
    assert {a["args"]["order"] for a in refunds} == {"2004"}  # only its own synthetic order


async def test_off_scope_requests_blocked_at_network_layer(scopes_for, runtime, tmp_path):
    events = []
    guard = scopes_for("http://127.0.0.1:9").list()[0].guard()
    b = AgentBrowser(runtime, FrameHub(), "m", "injection", guard, lambda t, p: events.append((t, p)))
    await b.open()
    await b.page.set_content('<img src="http://example.com/pixel.png"><script>fetch("http://example.org/x")</script>')
    await b.page.wait_for_timeout(500)
    with pytest.raises(PermissionError):
        await b.goto("http://example.com/")
    await b.close()
    blocked = {p.url for t, p in events if t == "browser.blocked"}
    assert "http://example.com/pixel.png" in blocked and "http://example.org/x" in blocked


async def test_emergency_stop(vulnerable_target, scopes_for, runtime, tmp_path):
    mgr = manager(scopes_for(vulnerable_target.url, requests_per_second=2, burst=1), runtime, tmp_path)
    m = mgr.create("acmehelp-local", "pytest", True)
    for _ in range(200):
        if m.snapshot.phase == MissionPhase.execution:
            break
        await asyncio.sleep(0.05)
    stopped = await mgr.emergency_stop("test")
    assert stopped == [m.id] and not m.active
    s = m.snapshot
    assert s.phase == MissionPhase.aborted and "EMERGENCY STOP" in s.summary.reason
    assert all(a.status in (AgentStatus.stopped, AgentStatus.idle) for a in s.agents.values()), {k: (a.status, a.activity) for k, a in s.agents.items()}
    with pytest.raises(MissionRejected, match="emergency stop"):
        mgr.create("acmehelp-local", "pytest", True)
    mgr.estop.reset()


async def test_concurrency_limit(vulnerable_target, scopes_for, runtime, tmp_path):
    mgr = manager(scopes_for(vulnerable_target.url), runtime, tmp_path, max_active=1)
    m = mgr.create("acmehelp-local", "pytest", True)
    with pytest.raises(MissionRejected, match="concurrency"):
        mgr.create("acmehelp-local", "pytest", True)
    await mgr.stop(m.id)


async def test_http_and_websocket_api(vulnerable_target, scopes_for, tmp_path):
    settings = Settings(runs_dir=tmp_path, api_token="t0ken")
    app = create_app(settings, scopes_for(vulnerable_target.url))
    with ServerThread(app, free_port()) as api:
        h = {"Authorization": "Bearer t0ken"}
        ws_base = api.url.replace("http", "ws")
        async with httpx.AsyncClient(base_url=api.url, headers=h, timeout=30) as c:
            assert (await c.get("/api/agents", headers={"Authorization": ""})).status_code == 401
            assert len((await c.get("/api/agents")).json()) == 5
            r = await c.post("/api/missions", json={"target_id": "acmehelp-local", "operator": "pytest",
                                                    "authorization_acknowledged": False})
            assert r.status_code == 409 and "acknowledge" in r.json()["detail"]
            r = await c.post("/api/missions", json={"target_id": "other", "operator": "pytest",
                                                    "authorization_acknowledged": True})
            assert r.status_code == 409 and "allowlist" in r.json()["detail"]

            r = await c.post("/api/missions", json={"target_id": "acmehelp-local", "operator": "pytest",
                                                    "authorization_acknowledged": True, "agents": ["leakage"]})
            assert r.status_code == 201
            mid = r.json()["mission_id"]

            frame = None
            async with websockets.connect(f"{ws_base}/ws/missions/{mid}/agents/leakage/frames?token=t0ken") as fws:
                frame = await asyncio.wait_for(fws.recv(), 30)
            assert isinstance(frame, bytes) and frame[:2] == b"\xff\xd8"  # JPEG

            seqs = []
            async with websockets.connect(f"{ws_base}/ws/missions/{mid}?token=t0ken") as ws:
                async for msg in ws:  # server closes after mission.completed
                    e = json.loads(msg)
                    seqs.append(e["seq"])
                    last = e
            assert seqs == list(range(1, len(seqs) + 1)) and last["type"] == "mission.completed"

            async with websockets.connect(f"{ws_base}/ws/missions/{mid}?token=t0ken&since={seqs[-3]}") as ws:
                replay = [json.loads(x)["seq"] async for x in ws]
            assert replay == seqs[-2:]

            snap = (await c.get(f"/api/missions/{mid}")).json()
            assert snap["last_seq"] == seqs[-1] and snap["phase"] == "completed"
            findings = (await c.get(f"/api/missions/{mid}/findings")).json()
            assert {f["probe_id"] for f in findings} == {"DL-001", "DL-002"}
            shot = next(e["artifact"] for e in findings[0]["evidence"] if e["kind"] == "screenshot")
            assert (await c.get(f"/api/missions/{mid}/artifacts/{shot}")).headers["content-type"] == "image/png"
            assert (await c.get(f"/api/missions/{mid}/artifacts/..%2F..%2Fsecret.png")).status_code in (400, 404)


async def test_connectivity_mode_runs_no_probes(vulnerable_target, scopes_for, runtime, tmp_path):
    """A connectivity check discovers + sends one benign message and stops.
    No security probe runs, even against a vulnerable target."""
    scopes = scopes_for(vulnerable_target.url)
    scopes.list()[0].authorized_methods = ["connectivity"]  # external-target posture
    mgr = manager(scopes, runtime, tmp_path)

    # assess mode is refused when security probes are not authorized
    with pytest.raises(MissionRejected, match="not permitted|connectivity"):
        mgr.create("acmehelp-local", "pytest", True, mode="assess")

    m = mgr.create("acmehelp-local", "pytest", True, mode="connectivity")
    await asyncio.wait_for(m.task, 60)
    s = m.snapshot
    assert s.phase == MissionPhase.completed
    assert s.capabilities and s.capabilities.assistant_detected        # discovery worked
    assert s.summary.probes_run == 0 and s.findings == {}              # no probes, no findings
    types = {e.type for e in m.ctx.log.events}
    assert "test.started" not in types and "finding.candidate" not in types
    assert any(e.type == "browser.navigated" for e in m.ctx.log.events)  # real browser activity streamed
