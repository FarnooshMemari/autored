# Testing real, external AI assistants (authorization policy)

AutoRed's generalization goal is to assess *independently developed* AI
assistants, not only targets we build. This file records what is required
before pointing AutoRed at any target we do not own, and why we have **not**
run it against a third-party production service.

## Status: no external production target has been tested. This is deliberate.

### Why a public bug-bounty program is not sufficient authorization
- A bounty program authorizes good-faith **vulnerability research**; it typically
  coexists with a product **Terms of Use** that prohibits automated access, and
  with program **Rules of Engagement** that restrict automated tooling, request
  volume, and shared-account use. All three must be reconciled, in writing, for
  the *specific* methods we would run.
- Those terms change and cannot be verified from inside this project. Acting on a
  remembered or assumed scope is exactly how research becomes a violation.
- Driving a human's authenticated account through automation can trip anti-abuse
  systems and jeopardize that account. Vendor-provisioned test accounts/tenants
  are the correct path.
- Our "confirmed" bar needs seeded synthetic canaries or a test-only audit
  oracle. A real multi-tenant production service provides neither, so findings
  would be unverifiable (inconclusive at best) and data/tool probes could touch
  real user data. Security probes therefore stay off until the owner provides a
  controlled test tenant.

### Microsoft Copilot (first candidate) — not tested
We did not run AutoRed against `copilot.microsoft.com`. Even non-adversarial
automated browser interaction with a third-party production assistant needs the
current Rules of Engagement and automation terms confirmed first, which we could
not verify here. The reusable target adapter (`browser/discovery.py`) is the
transferable deliverable; it is validated on authorized targets instead.

## The authorized path (what unlocks a real external run)

1. **Pick a target with an explicit, automation-friendly scope.** Fastest option:
   **self-host an independently developed assistant** (e.g. an open-source chat
   assistant you deploy). You then own it, authorization is unambiguous, and you
   can seed canaries + an audit oracle so findings are confirmable. AutoRed drives
   it with zero code changes.
2. **Record the authorization artifact** in the scope file: `reference`,
   `approved_by`, `expires`, permitted methods, rate caps, test window, and the
   synthetic test accounts/canaries the owner provides.
3. **Encode the target's rules in scope limits:** `allowed_origins`,
   `requests_per_second`/`burst`, `max_concurrent_agents` (set to what the owner
   permits — concurrency is already per-target configurable), timeouts, and the
   authorized tool list.
4. **Phase the engagement.**
   - *Phase 0 — connectivity & discovery only:* `--agents` empty security set;
     normal browser interaction, 1 rps, 1 agent, no probes. Proves discovery +
     interaction on the real interface.
   - *Phase 1 — only after written sign-off on methods:* enable the agreed probe
     subset on the vendor's test tenant, with seeded evidence. Rate limits,
     concurrency caps, and emergency stop apply throughout.
5. **Model-initiated traffic policy:** the assistant building this system does not
   initiate automated traffic to third-party production sites. AutoRed runs under
   the operator's identity with the owner's written authorization.

A Phase-0 "connectivity & discovery only" mode is supported today: run a mission
with a scope entry whose `authorized_tools` is empty and no probes authorized, so
the Commander discovers and greets the assistant but no security probe executes.
