from __future__ import annotations

import socket
import sys
import threading
import time
from pathlib import Path

import pytest
import uvicorn
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))  # make `target.acmehelp` importable

from autored.safety.scope import ScopeRegistry, Target  # noqa: E402
from target.acmehelp.app import create_app as create_acmehelp  # noqa: E402
from target.globex.app import create_app as create_globex  # noqa: E402
from target.initech.app import create_app as create_initech  # noqa: E402

SCOPE_FILE = ROOT / "scope" / "local-target.yaml"


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class ServerThread:
    def __init__(self, app, port: int):
        self.server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", ws="websockets"))
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.url = f"http://127.0.0.1:{port}"

    def __enter__(self):
        self.thread.start()
        deadline = time.time() + 10
        while not self.server.started:
            if time.time() > deadline:
                raise RuntimeError("server did not start")
            time.sleep(0.05)
        return self

    def __exit__(self, *exc):
        self.server.should_exit = True
        self.thread.join(timeout=10)


def target_from_scope(base_url: str, scope_id: str = "acmehelp-local", **limit_overrides) -> Target:
    data = next(t for t in yaml.safe_load(SCOPE_FILE.read_text())["targets"] if t["id"] == scope_id)
    data["base_url"] = base_url
    data["allowed_origins"] = [base_url]
    data["limits"].update({"requests_per_second": 50, "burst": 10, **limit_overrides})
    return Target.model_validate(data)


_FACTORIES = {"acmehelp-local": create_acmehelp, "globex-local": create_globex, "initech-local": create_initech}


def _target_server(scope_id: str, mode: str):
    app = _FACTORIES[scope_id](mode=mode, latency=(0.01, 0.05))
    with ServerThread(app, free_port()) as srv:
        srv.app = app
        srv.scope_id = scope_id
        yield srv


@pytest.fixture
def vulnerable_target():
    yield from _target_server("acmehelp-local", "vulnerable")


@pytest.fixture
def hardened_target():
    yield from _target_server("acmehelp-local", "hardened")


@pytest.fixture
def globex_target():
    yield from _target_server("globex-local", "vulnerable")


@pytest.fixture
def initech_target():
    yield from _target_server("initech-local", "vulnerable")


@pytest.fixture
def scopes_for():
    # scopes_for(base_url, scope_id=..., **limit_overrides) -> single-target registry
    return lambda base_url, scope_id="acmehelp-local", **kw: ScopeRegistry([target_from_scope(base_url, scope_id, **kw)])


def chromium_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            return Path(p.chromium.executable_path).exists()
    except Exception:
        return False


requires_browser = pytest.mark.skipif(not chromium_available(), reason="run `playwright install chromium`")
