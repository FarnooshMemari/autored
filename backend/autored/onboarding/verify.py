"""Authorization verification for onboarded targets.

Two ways to prove authorization to run active security probes (a checkbox is
never enough):

  * domain  — the operator serves the per-target token at
              <origin>/.well-known/autored-authorization.txt. Fetching it proves
              control of the web property. The fetch is SSRF-guarded (re-resolve
              + public-IP check) and bounded (size, redirects disabled, timeout).
  * admin   — an administrator supplies the AutoRed admin token plus a written
              authorization reference (ticket / engagement letter), approver and
              expiry. Used for self-hosted or contractually-authorized targets.
"""
from __future__ import annotations

import httpx

from .registry import OnboardingError, OnboardingRegistry
from .ssrf import SSRFError, assert_still_resolves_same

_MAX_BODY = 4096


def verify_domain(reg: OnboardingRegistry, target_id: str, *, allow_private: bool = False) -> str:
    """Fetch the well-known token file and confirm it carries the expected token.
    Returns a short detail string on success; raises OnboardingError otherwise."""
    ot = reg.get(target_id)
    if ot is None:
        raise OnboardingError(f"onboarded target '{target_id}' not found")
    expected = reg.expected_token(target_id)
    url = ot.verification["well_known_url"]
    try:
        assert_still_resolves_same(ot.resolved.host, ot.resolved.ips, allow_private=allow_private)
    except SSRFError as e:
        raise OnboardingError(str(e)) from e
    try:
        with httpx.Client(follow_redirects=False, timeout=8.0) as c:
            r = c.get(url, headers={"User-Agent": "AutoRed-verifier/1.0"})
    except httpx.HTTPError as e:
        raise OnboardingError(f"could not fetch {url}: {e}") from e
    if r.status_code != 200:
        raise OnboardingError(f"{url} returned HTTP {r.status_code}; expected 200 serving the token")
    body = r.text[:_MAX_BODY]
    if expected not in body:
        raise OnboardingError(f"token not found at {url}; the file must contain '{expected}'")
    return f"verified domain control via {url}"
