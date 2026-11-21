"""P0 E2E: assessment modes actually execute, and missions reopen after restart.
Drives the real API + a real browser against the AcmeHelp target."""
from __future__ import annotations

import asyncio

import httpx
import pytest

from autored.api.app import create_app
from autored.config import Settings
from conftest import ServerThread, free_port, requires_browser

pytestmark = [pytest.mark.e2e, requires_browser]


async def _create(c, **body):
    r = await c.post("/api/missions", json={"authorization_acknowledged": True, **body})
    assert r.status_code == 201, r.text
    return r.json()["mission_id"]


async def _await_done(c, mid, timeout=150):
    for _ in range(timeout):
        snap = (await c.get(f"/api/missions/{mid}")).json()
        if snap["phase"] in ("completed", "aborted", "failed", "interrupted"):
            return snap
        await asyncio.sleep(1)
    raise AssertionError("mission did not finish")


@pytest.fixture
def app_env(vulnerable_target, scopes_for, tmp_path):
    settings = Settings(runs_dir=tmp_path, db_path=tmp_path / "db.sqlite")
    app = create_app(settings, scopes_for(vulnerable_target.url))
    return app, settings, scopes_for, vulnerable_target


async def test_modes_execute_selected_strategy(app_env):
    app, settings, scopes_for, target = app_env
    with ServerThread(app, free_port()) as srv:
        mgr = app.state.manager
        async with httpx.AsyncClient(base_url=srv.url, timeout=180) as c:
            # connectivity: NO security probes
            mid = await _create(c, target_id="acmehelp-local", operator="t", mode="connectivity")
            assert mgr.missions[mid].ctx.mode == "connectivity"      # mode forwarded (was dropped before)
            snap = await _await_done(c, mid)
            assert snap["phase"] == "completed" and snap["summary"]["probes_run"] == 0
            assert snap["capabilities"]["assistant_detected"]

            # assess: fixed suite confirms findings
            mid = await _create(c, target_id="acmehelp-local", operator="t", mode="assess")
            assert mgr.missions[mid].ctx.mode == "assess"
            snap = await _await_done(c, mid)
            assert snap["summary"]["confirmed"] >= 5

            # hybrid: fixed phase runs (planner may be offline in CI -> adaptive stops gracefully)
            mid = await _create(c, target_id="acmehelp-local", operator="t", mode="hybrid")
            assert mgr.missions[mid].ctx.mode == "hybrid"
            snap = await _await_done(c, mid)
            assert snap["phase"] == "completed" and snap["summary"]["confirmed"] >= 5

            # adaptive: completes without crashing even if the local planner is unavailable
            mid = await _create(c, target_id="acmehelp-local", operator="t", mode="adaptive")
            assert mgr.missions[mid].ctx.mode == "adaptive"
            snap = await _await_done(c, mid)
            assert snap["phase"] in ("completed", "failed")

            # unknown mode is rejected
            r = await c.post("/api/missions", json={"target_id": "acmehelp-local", "operator": "t",
                                                    "authorization_acknowledged": True, "mode": "bogus"})
            assert r.status_code == 409


async def test_mission_reopens_after_restart(app_env):
    app, settings, scopes_for, target = app_env
    # run + complete a mission on "server 1"
    with ServerThread(app, free_port()) as srv:
        async with httpx.AsyncClient(base_url=srv.url, timeout=180) as c:
            mid = await _create(c, target_id="acmehelp-local", operator="restart-test", mode="assess")
            await _await_done(c, mid)

    # "restart": a brand-new app/manager with the SAME runs_dir + db (no in-memory state)
    app2 = create_app(settings, scopes_for(target.url))
    with ServerThread(app2, free_port()) as srv2:
        assert mid not in app2.state.manager.missions          # not in memory after restart
        async with httpx.AsyncClient(base_url=srv2.url, timeout=60) as c:
            snap = (await c.get(f"/api/missions/{mid}")).json()
            assert snap["phase"] == "completed" and snap["live"] is False    # resolved from disk, marked recorded
            findings = (await c.get(f"/api/missions/{mid}/findings")).json()
            assert len(findings) >= 5 and any(f["status"] == "confirmed" for f in findings)
            events = (await c.get(f"/api/missions/{mid}/events")).json()
            assert len(events) > 10
            report = (await c.get(f"/api/missions/{mid}/report")).json()
            assert report["summary"]["confirmed"] >= 5
            # evidence screenshot still fetchable
            shot = next(e["artifact"] for f in findings if f["status"] == "confirmed"
                        for e in f["evidence"] if e["kind"] == "screenshot")
            assert (await c.get(f"/api/missions/{mid}/artifacts/{shot}")).status_code == 200


async def test_interrupted_mission_full_recovery(app_env):
    """Real crash artifact: run a mission to completion, take the event-log PREFIX
    before mission.completed (exactly what a kill -9 leaves), then boot a fresh
    backend on that runs dir + db and verify the interrupted state end-to-end."""
    import shutil
    app, settings, scopes_for, target = app_env
    with ServerThread(app, free_port()) as srv:
        async with httpx.AsyncClient(base_url=srv.url, timeout=180) as c:
            mid = await _create(c, target_id="acmehelp-local", operator="crash-victim", mode="assess")
            await _await_done(c, mid)

    full = (settings.runs_dir / mid / "events.jsonl").read_text().splitlines()
    prefix = [l for l in full if "mission.completed" not in l]
    assert any("finding.candidate" in l for l in prefix), "need a finding before the crash"
    assert len(prefix) < len(full)                       # we actually dropped the completion

    crash = settings.runs_dir.parent / "crash_runs"
    (crash / mid / "artifacts").mkdir(parents=True)
    (crash / mid / "events.jsonl").write_text("\n".join(prefix))
    for a in (settings.runs_dir / mid / "artifacts").glob("*.png"):
        shutil.copy(a, crash / mid / "artifacts" / a.name)

    settings2 = Settings(runs_dir=crash, db_path=crash / "db.sqlite")
    app2 = create_app(settings2, scopes_for(target.url))
    with ServerThread(app2, free_port()) as srv2:   # lifespan reconciles interrupted missions on boot
        assert mid not in app2.state.manager.missions
        async with httpx.AsyncClient(base_url=srv2.url, timeout=60) as c:
            snap = (await c.get(f"/api/missions/{mid}")).json()
            assert snap["phase"] == "interrupted", snap["phase"]        # authoritative, not "execution"
            assert snap["live"] is False                                 # no false LIVE
            assert snap["summary"] and snap["summary"]["phase"] == "interrupted"
            findings = (await c.get(f"/api/missions/{mid}/findings")).json()
            assert len(findings) >= 1                                     # partial findings preserved
            events = (await c.get(f"/api/missions/{mid}/events")).json()
            assert len(events) > 5                                        # activity timeline preserved
            report = (await c.get(f"/api/missions/{mid}/report")).json()
            assert report["phase"] == "interrupted" and report["summary"]["phase"] == "interrupted"
            lst = (await c.get("/api/missions")).json()
            assert any(m["mission_id"] == mid and m["phase"] == "interrupted" for m in lst)
