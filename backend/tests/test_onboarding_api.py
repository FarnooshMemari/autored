"""End-to-end API behaviour of the onboarding endpoints (no browser)."""
from __future__ import annotations

import httpx
import pytest

from autored.api.app import create_app
from autored.config import Settings
from autored.safety.scope import ScopeRegistry
from conftest import ServerThread, free_port

H = {"Authorization": "Bearer s3cret"}


@pytest.fixture
def api_server(tmp_path):
    scopes = ScopeRegistry([])   # no static targets; everything comes from onboarding
    app = create_app(Settings(runs_dir=tmp_path, db_path=tmp_path / "db.sqlite", api_token="s3cret",
                              allow_private_targets=True, admin_token="admin-s3cret",
                              onboarding_store=tmp_path / "onboarded.json"), scopes)
    with ServerThread(app, free_port()) as srv:
        yield srv


async def test_onboard_verify_and_gate(api_server):
    async with httpx.AsyncClient(base_url=api_server.url, timeout=20) as c:
        # public SSRF rejection (allow_private is on, but metadata is always blocked)
        r = await c.post("/api/onboarding/targets", headers=H, json={
            "url": "http://169.254.169.254/", "operator": "far", "scope_description": "x"})
        assert r.status_code == 422

        # onboard a loopback test target (dev allow_private)
        r = await c.post("/api/onboarding/targets", headers=H, json={
            "url": "http://127.0.0.1:8100/chat", "name": "Local AcmeHelp", "operator": "far",
            "scope_description": "chat endpoint, non-destructive",
            "methods": ["connectivity", "security_probes"], "chat_path": "/chat"})
        assert r.status_code == 201, r.text
        ot = r.json()
        tid = ot["id"]
        assert ot["authorized_methods"] == ["connectivity"]           # connectivity-only until verified
        assert ot["verification"]["status"] == "unverified"
        assert ot["onboarded"] is True

        # it shows up in /api/targets, flagged
        tlist = (await c.get("/api/targets", headers=H)).json()
        assert any(t["id"] == tid and t["onboarded"] for t in tlist)

        # an assess mission must be REJECTED while unverified (connectivity only)
        r = await c.post("/api/missions", headers=H, json={
            "target_id": tid, "operator": "far", "authorization_acknowledged": True, "mode": "assess"})
        assert r.status_code == 409 and "security probes are not" in r.text.lower()

        # admin verification requires the admin token
        r = await c.post(f"/api/onboarding/targets/{tid}/verify", headers=H, json={"method": "admin"})
        assert r.status_code == 403

        # admin verification with full authorization record upgrades methods
        r = await c.post(f"/api/onboarding/targets/{tid}/verify", headers=H, json={
            "method": "admin", "admin_token": "admin-s3cret", "reference": "ENG-77",
            "approved_by": "ciso", "expires": "2027-12-31"})
        assert r.status_code == 200, r.text
        assert r.json()["authorized_methods"] == ["connectivity", "security_probes"]
        assert r.json()["verification"]["status"] == "verified"


async def test_onboarding_disabled(tmp_path):
    scopes = ScopeRegistry([])
    app = create_app(Settings(runs_dir=tmp_path, db_path=tmp_path / "db.sqlite", api_token="s3cret",
                              enable_onboarding=False), scopes)
    with ServerThread(app, free_port()) as srv:
        async with httpx.AsyncClient(base_url=srv.url, timeout=20) as c:
            r = await c.get("/api/onboarding/config", headers=H)
            assert r.json()["enabled"] is False
            r = await c.post("/api/onboarding/targets", headers=H, json={
                "url": "https://example.com/", "operator": "far", "scope_description": "x"})
            assert r.status_code == 404
