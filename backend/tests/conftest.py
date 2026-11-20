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
from target.acmehelp.app import create_app as create_target  # noqa: E402

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


def target_from_scope(base_url: str, **limit_overrides) -> Target:
    data = yaml.safe_load(SCOPE_FILE.read_text())["targets"][0]
    data["base_url"] = base_url
    data["allowed_origins"] = [base_url]
    data["limits"].update({"requests_per_second": 50, "burst": 10, **limit_overrides})
    return Target.model_validate(data)


def _target_server(mode: str):
    app = create_target(mode=mode, latency=(0.01, 0.05))
    with ServerThread(app, free_port()) as srv:
        srv.app = app
        yield srv


@pytest.fixture
def vulnerable_target():
    yield from _target_server("vulnerable")


@pytest.fixture
def hardened_target():
    yield from _target_server("hardened")


@pytest.fixture
def scopes_for():
    return lambda base_url, **kw: ScopeRegistry([target_from_scope(base_url, **kw)])


def chromium_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            return Path(p.chromium.executable_path).exists()
    except Exception:
        return False


requires_browser = pytest.mark.skipif(not chromium_available(), reason="run `playwright install chromium`")
