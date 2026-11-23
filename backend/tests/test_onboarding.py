"""Onboarding: SSRF guard, dynamic Target creation, verification gating."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from autored.onboarding import OnboardingError, OnboardingRegistry, SSRFError, validate_target_url
from autored.safety.scope import ScopeRegistry


# --------------------------------------------------------------------- SSRF
@pytest.mark.parametrize("url", [
    "http://169.254.169.254/latest/meta-data/",   # cloud metadata
    "http://10.0.0.5/", "http://192.168.1.1/", "http://172.16.0.1/",  # RFC-1918
    "http://127.0.0.1:8100/", "http://localhost/",                    # loopback
    "http://100.64.0.1/",                                             # CGNAT
    "ftp://example.com/", "file:///etc/passwd", "gopher://x/",        # bad schemes
    "http://user:pw@example.com/",                                    # creds in URL
    "http://[::1]/",                                                  # IPv6 loopback
])
def test_ssrf_blocks_unsafe_urls(url):
    with pytest.raises(SSRFError):
        validate_target_url(url, allow_private=False)


def test_ssrf_allows_loopback_only_in_dev():
    r = validate_target_url("http://127.0.0.1:8100/chat", allow_private=True)
    assert r.origin == "http://127.0.0.1:8100"
    assert r.ips == ("127.0.0.1",)


def test_ssrf_resolves_public_host():
    # example.com is reserved for documentation but resolves to public IPs
    r = validate_target_url("https://example.com/")
    assert r.scheme == "https" and r.port == 443 and r.host == "example.com"
    assert all(not ip.startswith(("10.", "127.", "192.168.", "169.254.")) for ip in r.ips)


# -------------------------------------------------------------- registry
def _reg(tmp_path: Path) -> OnboardingRegistry:
    scopes = ScopeRegistry([])
    return OnboardingRegistry(scopes, tmp_path / "onboarded.json")


def test_onboard_is_connectivity_only_until_verified(tmp_path):
    reg = _reg(tmp_path)
    resolved = validate_target_url("http://127.0.0.1:8100/chat", allow_private=True)
    ot = reg.onboard(resolved, name="Local", scope_description="chat endpoint only",
                     requested_methods=["connectivity", "security_probes"], operator="far", chat_path="/chat")
    assert ot.target.authorized_methods == ["connectivity"]          # not yet allowed to probe
    assert ot.target.allows("connectivity") and not ot.target.allows("security_probes")
    assert reg.scopes.list()[0].id == ot.target.id                   # registered into live scope
    assert ot.verification["status"] == "unverified"
    assert ot.verification["token"].startswith("autored-verify-")


def test_admin_verification_upgrades_methods(tmp_path):
    reg = _reg(tmp_path)
    resolved = validate_target_url("http://127.0.0.1:8100/chat", allow_private=True)
    ot = reg.onboard(resolved, name="Local", scope_description="full suite",
                     requested_methods=["connectivity", "security_probes"], operator="far")
    exp = date.today() + timedelta(days=30)
    ot2 = reg.mark_verified(ot.target.id, method="admin", reference="ENG-2026-01",
                            approved_by="ciso", expires=exp)
    assert ot2.target.allows("security_probes")
    assert ot2.target.authorization.reference == "ENG-2026-01"
    assert ot2.verification["status"] == "verified"


def test_duplicate_origin_rejected(tmp_path):
    reg = _reg(tmp_path)
    resolved = validate_target_url("http://127.0.0.1:8100/chat", allow_private=True)
    reg.onboard(resolved, name="a", scope_description="x", requested_methods=["connectivity"], operator="far")
    with pytest.raises(OnboardingError):
        reg.onboard(resolved, name="b", scope_description="x", requested_methods=["connectivity"], operator="far")


def test_persistence_survives_reload(tmp_path):
    reg = _reg(tmp_path)
    resolved = validate_target_url("http://127.0.0.1:8100/chat", allow_private=True)
    ot = reg.onboard(resolved, name="Local", scope_description="x",
                     requested_methods=["connectivity"], operator="far")
    tid = ot.target.id
    # reload into a fresh registry + scope
    reg2 = OnboardingRegistry(ScopeRegistry([]), tmp_path / "onboarded.json")
    assert reg2.get(tid) is not None
    assert reg2.scopes.list()[0].id == tid
