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
