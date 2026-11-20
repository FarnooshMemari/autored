import asyncio
import time
from datetime import date

import pytest

from autored.safety.limits import RateLimiter
from autored.safety.scope import OriginGuard, ScopeError, ScopeRegistry
from conftest import SCOPE_FILE, target_from_scope


def test_scope_file_loads():
    reg = ScopeRegistry.load(SCOPE_FILE)
    assert [t.id for t in reg.list()] == ["acmehelp-local", "globex-local", "initech-local"]


def test_unknown_target_rejected():
    reg = ScopeRegistry([target_from_scope("http://127.0.0.1:9")])
    with pytest.raises(ScopeError, match="not in the allowlist"):
        reg.authorize("example-com", "op", True)


def test_requires_explicit_ack_and_operator():
    reg = ScopeRegistry([target_from_scope("http://127.0.0.1:9")])
    with pytest.raises(ScopeError, match="acknowledge"):
        reg.authorize("acmehelp-local", "op", False)
    with pytest.raises(ScopeError, match="operator"):
        reg.authorize("acmehelp-local", " ", True)


def test_expired_authorization_rejected():
    reg = ScopeRegistry([target_from_scope("http://127.0.0.1:9")])
    with pytest.raises(ScopeError, match="expired"):
        reg.authorize("acmehelp-local", "op", True, today=date(2099, 1, 1))


def test_base_url_must_be_inside_allowlist():
    t = target_from_scope("http://127.0.0.1:9")
    t.allowed_origins = ["http://127.0.0.1:10"]
    with pytest.raises(ScopeError):
        ScopeRegistry([t])


@pytest.mark.parametrize("url,ok", [
    ("http://127.0.0.1:8100/chat", True),
    ("http://127.0.0.1:8100", True),
    ("http://127.0.0.1:8101/chat", False),          # different port
    ("https://127.0.0.1:8100/chat", False),         # different scheme
    ("http://127.0.0.1.evil.test:8100/", False),    # suffix trick
    ("http://evil.test/?u=http://127.0.0.1:8100", False),
    ("data:text/html,hi", True),
    ("about:blank", True),
])
def test_origin_guard(url, ok):
    assert OriginGuard(["http://127.0.0.1:8100"]).is_allowed(url) is ok


async def test_rate_limiter_enforces_rate():
    rl = RateLimiter(rate=20, burst=1)
    t0 = time.monotonic()
    await asyncio.gather(*(rl.acquire() for _ in range(6)))
    assert time.monotonic() - t0 >= 5 / 20 * 0.9


def test_authorized_methods_gate():
    t = target_from_scope("http://127.0.0.1:9")
    assert t.allows("connectivity") and t.allows("security_probes")  # default
    t.authorized_methods = ["connectivity"]
    assert t.allows("connectivity") and not t.allows("security_probes")
