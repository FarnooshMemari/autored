# AutoRed

Real-time multi-agent security assessment of AI assistants on websites, for
**explicitly authorized targets only**. A Commander agent discovers the target's
assistant, plans, and delegates to four specialists (Prompt Injection, Data
Leakage, Instruction Hierarchy, Tool Permission Boundaries). Each specialist
drives its own isolated Chromium context. Every step streams over WebSockets.

> **Status:** Working multi-agent product with a complete dashboard. Five agents
> (Commander + Inky/Vault/Lexi/Guard), evidence-based confirmation with statistical
> reproduction, real tool-calling assessment, adaptive planner, and a dark-first
> dashboard on live data. See [PRODUCT_DELIVERY_REPORT.md](PRODUCT_DELIVERY_REPORT.md)
> and [docs/MILESTONES.md](docs/MILESTONES.md).

```
backend/    FastAPI + Playwright + agents        (Python 3.11+)
frontend/   React/TS data layer + UI slot shell  (Node 18+)
target/     3 self-hosted synthetic targets (AcmeHelp, Globex, Initech) + shared brain
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

### Run the dashboard (full product)
```bash
# 1. a target (vulnerable test app)
backend/.venv/bin/uvicorn target.acmehelp.app:app --port 8100
# 2. the AutoRed API
cd backend && .venv/bin/uvicorn autored.main:app --port 8000
# 3. the dashboard  ->  http://localhost:5173
cd frontend && npm run dev
```
Open the dashboard, pick a target in **Mission Control**, confirm authorization, and
**Launch**. Watch the five agents operate over live browser frames in **Live
Operations**, inspect evidence in **Findings**, compare approaches in **Experiments**,
and generate reports in **History**.

**Connectivity-only (Phase 0) for an authorized external target** — discovery +
one benign message, **no security probes**:
`.venv/bin/python -m autored connectivity-check <target_id> --operator you --i-am-authorized`
Security probes require the target's scope `authorized_methods` to include
`security_probes`; otherwise the four-agent suite is refused. See
[docs/M3_PLAN.md](docs/M3_PLAN.md) and [docs/EXTERNAL_TARGETS.md](docs/EXTERNAL_TARGETS.md).

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

- **Target-independent discovery.** The Commander finds and drives a chat
  assistant across different layouts with no per-target code: full-page chat,
  widgets inside **iframes**, **open shadow DOM**, launcher buttons, dynamically
  rendered UIs, textarea / input / contenteditable composers, send-by-button or
  **Enter key**, and **streaming/async** replies. Selectors can be pinned in the
  scope file as a manual fallback when auto-discovery fails.
- **Four isolated specialists** run in parallel in separate Chromium contexts
  with separate synthetic accounts and their own conversation history; each
  reconstructs the discovered interface in its own context.
- **Evidence-based, five-state evaluation:** `confirmed` (strong evidence —
  seeded synthetic canary or audit-oracle record — reproduced in fresh contexts),
  `suspected` (a model claim, not proof), `inconclusive` (could not evaluate),
  `passed` (tested cleanly), `not_applicable` (not runnable here). A model's claim
  is never treated as proof.
- **Verified on 3 structurally different targets** (AcmeHelp full-page, Globex
  iframe widget, Initech shadow-DOM) with the same orchestration core — see
  [docs/TARGETS.md](docs/TARGETS.md).
- Ordered, persisted, resumable WebSocket event stream + live JPEG screencast per
  agent; **viewport + element bounding boxes** emitted so overlay animations can
  follow real page elements.
- Safety: allowlist + authorization records, network-layer origin guard, rate
  limits, timeouts, configurable concurrency caps, emergency stop. Assisted-login
  scaffold for operator-completed SSO/MFA (we never type credentials or bypass auth).

## Limitations

- **Executed against a real LLM with real tool-calling.** Unmodified open-webui +
  `llama3.2:3b` (native function calling) with an auditable tool-execution log and
  four isolated test accounts: AutoRed **confirmed 2 critical tool-permission
  violations** (a customer invoking a staff-only refund tool, incl. a multi-turn
  attack), reproduced 4/4 via the audit oracle — see
  [docs/M3B_EXECUTION.md](docs/M3B_EXECUTION.md) (earlier `llama3.2:1b` run:
  [docs/M3_EXECUTION.md](docs/M3_EXECUTION.md)). No **externally-hosted** third-party
  target has been tested; that needs verified authorization
  ([docs/EXTERNAL_TARGETS.md](docs/EXTERNAL_TARGETS.md)).
- Probe library is still small (2–3 probes per category) and mostly single-turn
  (multi-turn history is tracked; multi-turn *probes* are M2b).
- Assisted-login and streaming/async handling are implemented but exercised only
  on synthetic targets; real SSO flows are unverified in CI.
- In-memory mission registry; single node. Chromium only (live view uses CDP).
- Frontend is a deliberately unstyled shell; visuals come from the design team via
  `frontend/src/integration/slots.tsx`.

## Security notes

`scope/local-target.yaml` contains **synthetic** credentials for the local test target only.
Real target credentials must be supplied via `${ENV_VAR}` references or a git-ignored `scope/*.local.yaml`.
