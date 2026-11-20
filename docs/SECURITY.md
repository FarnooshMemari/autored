# Security model

AutoRed is an authorized, non-destructive security-testing tool. Its own controls:

## Authorization & scope
- **Allowlist of targets** (`scope/*.yaml`); each needs a written authorization record
  (reference, approver, expiry) and an **explicit operator acknowledgement** at mission
  creation (recorded in `runs/<mission>/authorization.txt`).
- **Network-layer origin guard:** every agent browser context aborts any request outside
  the target's `allowed_origins` (enforced again below the mission check, so redirects /
  injected resources cannot leave scope). `ws://`/`wss://` to an allowed origin pass.
- **Method gate:** security probes run only when the scope authorizes `security_probes`;
  otherwise connectivity-only (discover + benign message).

## Credentials & data
- Only **synthetic** test accounts and **synthetic** canaries. Scope passwords support
  `${ENV_VAR}` expansion so real test credentials need not live in the file; the committed
  local scopes contain only throwaway test-instance passwords.
- Passwords are masked in the event stream (`••••`). No real user data is accessed; all
  tool side effects are sandboxed synthetic records.
- Browser session/auth state, local DBs, model files and run artifacts are git-ignored.

## API
- Optional **bearer token** (`AUTORED_API_TOKEN`): when set, every endpoint except
  `/api/health` requires it (REST `Authorization: Bearer`, WS `?token=`). Verified by
  `tests/test_security.py`.
- Binds to `127.0.0.1` by default; CORS is restricted to the configured dashboard origin
  (not `*`). Artifact downloads are name-validated (no path traversal).

## Operational safety
- Per-target rate limit, concurrency cap, per-probe & per-mission timeouts, **emergency
  stop** (cancels all missions, latches until reset), and crash **reconciliation** on
  restart (no dangling missions). Non-destructive probes only.

## Out of scope / not done
- No RBAC beyond the single bearer token; no external/public deployment; no external
  target tested. These require explicit authorization and are documented as limitations.
