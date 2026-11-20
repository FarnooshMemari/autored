# AutoRed — Product Delivery Report

AutoRed is an autonomous, multi-agent platform for evaluating the security,
trustworthiness, and behavioral integrity of AI applications. This report states
honestly what was built, what actually works (verified), what is experimentally
validated, and what remains limited.

Repo: https://github.com/FarnooshMemari/autored (private) · local-only, synthetic,
non-destructive · no paid APIs · no AI co-author trailers.

## What was built (and verified working)
- **Target-independent assessment engine.** Discovers and drives AI chat assistants
  across full-page chat, iframe widgets and shadow-DOM SPAs with no per-target code
  (verified on AcmeHelp, Globex, Initech, and unmodified open-webui).
- **Five agents.** Commander (orchestrator) + four specialists with distinct roles:
  **Inky** (prompt injection), **Vault** (data leakage), **Lexi** (instruction
  hierarchy), **Guard** (tool permissions). Each runs in an isolated browser context
  with its own test account; the Commander plans, delegates, validates, consolidates.
- **Evidence-based evaluation.** A finding is `confirmed` only via a seeded synthetic
  canary or a tool-audit oracle, **reproduced in fresh browser contexts**, with a
  **confirmation rate + 95% Wilson interval**. A model's claim is never proof;
  fabricated tool-action claims are flagged as deceptive (`suspected`), not confirmed.
- **Real tool-calling assessment.** Against open-webui + a real LLM (`llama3.2:3b`,
  native tool-calling) with an auditable tool-execution log, AutoRed confirmed
  customer→staff-only-refund violations (incl. a multi-turn attack), reproduced 4/4.
- **Adaptive LLM Commander.** A bounded local-Ollama planner loop (plan→delegate→
  observe→revise→decide) that proposes creative probes but never lowers the evidence bar.
- **Complete dark-first dashboard** (React/TS) on **real** backend data: Mission
  Control, Live Operations (five animated agent characters + **real live browser frames
  with coordinate overlays** + activity feed), Findings Explorer + Evidence Inspector
  (rate/CI, canary/oracle, prompt/reply, screenshot), Experiment Analytics, History &
  Reporting, System Health. Verified by driving the rendered app in Chromium
  (screenshots in `pilots/screenshots/`).
- **Durable persistence + reproducible reporting** (SQLite + deterministic report from
  the event log). Full safety controls: scope allowlist + network origin guard, rate
  limits, concurrency caps, probe/LLM budgets, timeouts, emergency stop, bearer-token API.

## What was experimentally validated (real runs; see docs/EXPERIMENTS.md)
- **Vulnerable vs Hardened (Exp A):** AutoRed confirms the tool-permission violation on
  the vulnerable config (8 customer refund executions) and reports **0** on the
  backend-hardened config (0 executions, all rejected) — **no false positives**.
- **Fixed vs Adaptive (Exp B) + repeated trials (N=3):** **honest negative result** —
  the fixed baseline was more reliable (tool-perm detected 3/3 trials, mean 2.0 confirmed)
  than adaptive (2/3 trials, mean 0.67); adaptive was ~2× cheaper but found nothing the
  baseline missed. We do **not** claim adaptive improves discovery.
- **Held-out (Exp C):** adaptive on the hardened config it was not designed against →
  0 confirmed, no over-claiming.
- **Cross-account, tester-controlled (Exp D):** AutoRed planted a runtime marker and verified cross-account access with no owner seeding; 0 false positives, latent over-permission surfaced via audit (see docs/EXPERIMENTS.md).
- **Deception (Exp E, partial):** tool-action claims with no matching audit record are
  reported as fabricated/deceptive, distinct from verified side effects.

## What remains limited (honest)
- **Tester-controlled ground truth is now implemented** (Experiment D): AutoRed plants a
  unique runtime marker via a controlled account and verifies cross-account access
  itself, with **no owner-seeded canary or audit**. It correctly reported no false
  positive and surfaced a latent backend over-permission via the audit. Remaining gap:
  confirming a *user-facing* disclosure still depends on the model surfacing the data
  (the small local model masked it), and the richer tool-audit oracle is still used where
  available for strong confirmation.
- **Experiment F (full
  failure/recovery)** are partial; mission *recovery after process restart* persists
  findings but does not yet resume an in-flight mission.
- **No externally-hosted third-party target** has been tested (authorization/ToS
  blocker, not a code gap).
- **Agent characters are SVG "3D-inspired", not real 3D.** Planner is a small local
  model. RBAC is a single bearer token, not multi-role.

## How to install and run
See [README.md](README.md). Summary: Python 3.11+ backend (`uv`/`pip -e '.[dev]'` +
`playwright install chromium`), Node 18+ frontend (`npm ci`). Run the backend API, a
target, and the Vite dev server; open the dashboard and launch an assessment.

## How to reproduce key results
- Fixed/adaptive/variance: `backend/experiments/*.py` (local Ollama). Raw JSON in
  `pilots/experiments/`. Vulnerable↔hardened toggled by a flag file (no app changes).
- Any mission: `python -m autored report <mission_id>` → deterministic Markdown+JSON.

## Tests & CI
Backend **47** (`pytest`, incl. real-Chromium E2E, adaptive loop, storage/reporting,
stats). Frontend **6** + typecheck + build. **CI green** on every pushed commit.

## Acceptance criteria (Section 13) — honest status
1 starts from docs ✓ · 2 FE+BE together ✓ · 3 five agents real workflow ✓ · 4 configure+run ✓ ·
5 browser observable ✓ · 6 reproducible evidence ✓ · 7 reports gen+reopen ✓ · 8 polished/responsive ✓ ·
9 honest experiments ✓ · 10 failure/recovery **partial** (e-stop/timeouts/per-probe tested; in-flight resume not) ·
11 tests+CI ✓ · 12 end-to-end demo ✓ · 13 limits documented ✓.

## Final commit
Latest pushed commit is at the tip of `main` (CI green). Dashboard: `6204cde`.
