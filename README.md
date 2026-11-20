# AutoRed

Real-time multi-agent security assessment of AI assistants on websites, for
**explicitly authorized targets only**. A Commander agent discovers the target's
assistant, plans, and delegates to four specialists (Prompt Injection, Data
Leakage, Instruction Hierarchy, Tool Permission Boundaries). Each specialist
drives its own isolated Chromium context. Every step streams over WebSockets.

> **Status:** Milestone 1 (foundation + vertical slice) complete. See [docs/MILESTONES.md](docs/MILESTONES.md).

```
backend/    FastAPI + Playwright + agents        (Python 3.11+)
frontend/   React/TS data layer + UI slot shell  (Node 18+)
target/     AcmeHelp: self-hosted, deliberately vulnerable test target
scope/      allowlist + authorization records (the only targets AutoRed may touch)
contracts/  events.schema.json, the generated event contract
docs/       ARCHITECTURE.md, EVENTS.md (for the visualization team), MILESTONES.md
runs/       per-mission audit trail: events.jsonl, authorization.txt, screenshots
```

## Setup

```bash
# backend
cd backend
uv venv -p 3.12 .venv && uv pip install -p .venv -e '.[dev]'   # or: python -m venv .venv && .venv/bin/pip install -e '.[dev]'
.venv/bin/playwright install chromium

# frontend
cd ../frontend && npm install
```

## Run the vertical slice

Three terminals, all from the repo root:

```bash
# 1. authorized test target (ACMEHELP_MODE=hardened for the safe variant)
backend/.venv/bin/uvicorn target.acmehelp.app:app --port 8100

# 2. AutoRed API (binds to localhost; set AUTORED_API_TOKEN before exposing it)
cd backend && .venv/bin/uvicorn autored.main:app --port 8000

# 3. UI shell -> http://localhost:5173
cd frontend && npm run dev
```

Or headless, from `backend/`:
`.venv/bin/python -m autored run-mission acmehelp-local --operator you --i-am-authorized`

Against the vulnerable target, expect 6 confirmed findings (each reproduced in
fresh contexts), 2 probes `not_observed`, and 1 probe skipped by the Commander
because its tool is not authorized in scope. Against the hardened target, expect 0 findings.

## Tests

```bash
cd backend && .venv/bin/pytest            # 33 tests; E2E ones drive real Chromium (~10 s)
cd frontend && npm test && npm run typecheck
```

After changing `backend/autored/events/schema.py`, run `python -m autored export-schema`
(a test fails if the committed contract is stale) and update `frontend/src/contracts/events.ts`.

## Configuration

| env var | default | |
|---|---|---|
| `AUTORED_SCOPE` | `scope/local-target.yaml` | allowlist + authorization file |
| `AUTORED_RUNS_DIR` | `runs/` | audit trail location |
| `AUTORED_HEADLESS` | `1` | `0` shows the browsers |
| `AUTORED_MAX_ACTIVE_MISSIONS` | `1` | |
| `AUTORED_API_TOKEN` | unset | require `Authorization: Bearer` / `?token=` |
| `VITE_AUTORED_TOKEN` | unset | frontend token |

## Adding a real target

Add an entry to a scope file with a real authorization reference, approver and
expiry; list its exact origins; create **dedicated test accounts** (one per
agent) with synthetic data; list the synthetic canaries seeded for the test. Point
`oracle_audit_path` at a test-only audit endpoint if the target owner provides one;
without it, tool-boundary results can only be `inconclusive`, never `confirmed`.

## Current capabilities

- Commander discovers a chat assistant on a logged-in page, verifies it with a real greeting, parses advertised tools, plans and delegates.
- Four specialists run in parallel in isolated Chromium contexts with separate test accounts; candidates are replayed in fresh contexts before confirmation.
- Evidence-based verdicts (synthetic canaries, test-oracle audit records); heuristics alone never confirm.
- Ordered, persisted, resumable WebSocket event stream + live JPEG screencast per agent.
- Safety: allowlist + authorization records, network-layer origin guard, rate limits, timeouts, concurrency caps, emergency stop.

## Limitations

- Validated only against the self-hosted AcmeHelp target (one UI layout, form login, synchronous replies).
- Probe library is small (2–3 probes per category) and single-turn.
- In-memory mission registry; single node.
- Chromium only. Live view uses CDP screencast.
- Frontend is a deliberately unstyled shell; visuals come from the design team via `frontend/src/integration/slots.tsx`.

## Security notes

`scope/local-target.yaml` contains **synthetic** credentials for the local test target only.
Real target credentials must be supplied via `${ENV_VAR}` references or a git-ignored `scope/*.local.yaml`.
