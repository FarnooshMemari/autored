"""Public/hosted-demo safety: token required, onboarding locked to a sandbox origin."""
from __future__ import annotations

import httpx
import pytest

from autored.api.app import create_app
from autored.config import Settings
from autored.safety.scope import ScopeRegistry
from conftest import ServerThread, free_port

H = {"Authorization": "Bearer s3cret"}


def test_public_mode_requires_token(tmp_path):
    with pytest.raises(RuntimeError, match="requires AUTORED_API_TOKEN"):
        create_app(Settings(runs_dir=tmp_path, db_path=tmp_path / "db.sqlite",
                            public_mode=True, api_token=None), ScopeRegistry([]))


@pytest.fixture
def locked_server(tmp_path):
    """Public instance locked to a single bundled sandbox origin."""
    app = create_app(Settings(
        runs_dir=tmp_path, db_path=tmp_path / "db.sqlite", api_token="s3cret",
        public_mode=True, allow_private_targets=True, admin_token="admin-s3cret",
        demo_target_origins=("http://127.0.0.1:8100",),
        cors_origins=("https://farnooshmemari.github.io", "http://localhost:5173"),
        onboarding_store=tmp_path / "onboarded.json"), ScopeRegistry([]))
    with ServerThread(app, free_port()) as srv:
        yield srv


async def test_health_reports_live_and_locked(locked_server):
    async with httpx.AsyncClient(base_url=locked_server.url, timeout=20) as c:
        h = (await c.get("/api/health")).json()
        assert h["live"] is True and h["public_mode"] is True and h["demo_locked"] is True


async def test_private_network_access_preflight(locked_server):
    async with httpx.AsyncClient(base_url=locked_server.url, timeout=20) as c:
        r = await c.request("OPTIONS", "/api/health", headers={
            "Origin": "https://farnooshmemari.github.io",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Private-Network": "true"})
        assert r.status_code == 204
        assert r.headers.get("Access-Control-Allow-Private-Network") == "true"
        assert r.headers.get("Access-Control-Allow-Origin") == "https://farnooshmemari.github.io"


async def test_onboarding_rejects_arbitrary_urls_when_locked(locked_server):
    async with httpx.AsyncClient(base_url=locked_server.url, timeout=20) as c:
        # an arbitrary (even public, even SSRF-valid) URL is refused in locked mode
        r = await c.post("/api/onboarding/targets", headers=H, json={
            "url": "https://example.com/", "operator": "far", "scope_description": "x"})
        assert r.status_code == 403 and "bundled sandbox" in r.text

        # the bundled sandbox origin IS accepted
        r = await c.post("/api/onboarding/targets", headers=H, json={
            "url": "http://127.0.0.1:8100/chat", "operator": "far",
            "scope_description": "sandbox demo", "methods": ["connectivity"]})
        assert r.status_code == 201, r.text
        assert r.json()["origin"] == "http://127.0.0.1:8100"
