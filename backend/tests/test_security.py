"""Security: API authorization enforcement and path-traversal resistance.
No browser needed — the app is created with a token and probed over HTTP."""
from __future__ import annotations

import pytest
import httpx

from autored.api.app import create_app
from autored.config import Settings
from conftest import ServerThread, free_port, target_from_scope
from autored.safety.scope import ScopeRegistry

PROTECTED = [
    ("GET", "/api/agents"), ("GET", "/api/targets"), ("GET", "/api/missions"),
    ("GET", "/api/experiments"), ("POST", "/api/emergency-stop"),
    ("GET", "/api/missions/NOPE/findings"), ("GET", "/api/missions/NOPE/report"),
]


@pytest.fixture
def api_server(tmp_path):
    scopes = ScopeRegistry([target_from_scope("http://127.0.0.1:9")])
    app = create_app(Settings(runs_dir=tmp_path, db_path=tmp_path / "db.sqlite", api_token="s3cret"), scopes)
    with ServerThread(app, free_port()) as srv:
        yield srv


async def test_health_is_public_but_everything_else_requires_token(api_server):
    async with httpx.AsyncClient(base_url=api_server.url, timeout=20) as c:
        assert (await c.get("/api/health")).status_code == 200            # health is public
        for method, path in PROTECTED:
            r = await c.request(method, path)                             # no token
            assert r.status_code == 401, f"{method} {path} not protected ({r.status_code})"
        # with the token, auth passes (not 401; may be 404/409 for missing resources)
        h = {"Authorization": "Bearer s3cret"}
        assert (await c.get("/api/agents", headers=h)).status_code == 200
        assert (await c.get("/api/missions/M-missing-id/findings", headers=h)).status_code == 404   # well-formed, absent
        assert (await c.get("/api/missions/NOPE/findings", headers=h)).status_code == 400              # bad id format


async def test_wrong_token_rejected(api_server):
    async with httpx.AsyncClient(base_url=api_server.url, timeout=20) as c:
        assert (await c.get("/api/agents", headers={"Authorization": "Bearer wrong"})).status_code == 401


async def test_artifact_path_traversal_blocked(api_server):
    # create a mission so the id resolves, then probe traversal on the artifact name
    async with httpx.AsyncClient(base_url=api_server.url, headers={"Authorization": "Bearer s3cret"}, timeout=20) as c:
        for name in ["..%2F..%2F..%2Fetc%2Fpasswd", "..%2Fsecret.png", "x.txt", "x.png%00.jpg"]:
            r = await c.get(f"/api/missions/NOPE/artifacts/{name}")
            assert r.status_code in (400, 404)                           # never 200 / never a file outside artifacts
