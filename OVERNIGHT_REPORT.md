# AutoRed — Overnight autonomous run report

Repo: https://github.com/FarnooshMemari/autored (private) · all work local, synthetic, non-destructive · no paid APIs · no new external targets · no AI co-author trailers.

## 1. Everything completed
- **M4 — Adaptive Commander (done).** LLM-powered `AdaptiveCommander` (local Ollama
  planner) with a bounded loop (discover → plan → delegate → observe → revise →
  decide), budgets (`max_rounds/max_probes/max_llm_calls`), a GOAL taxonomy that
  grounds generated probes in checkable evidence, and the invariant that the planner
  never confirms a finding. Adaptive mode in the manager (authorization-gated) + CLI
  (`--adaptive`). Per-probe error isolation so one timeout no longer kills an agent.
- **Experiments (real, local LLM).** Vulnerable-vs-hardened and baseline-vs-adaptive
  executed and analyzed; repeated-trials variance run. Raw data in
  `pilots/experiments/*.json`; write-up in `docs/EXPERIMENTS.md`.
- **M5 — Durable storage + reproducible reporting (done).** SQLite mission/finding
  store (`storage/store.py`), deterministic Markdown+JSON report replayed from the
  event log (`reporting/report.py`), CLI `autored missions` / `autored report <id>`,
  manager persists on completion. Stdlib only (no new deps).
- **Docs.** `docs/ADAPTIVE.md` (architecture + the asyncio-vs-LangGraph decision),
  `docs/EXPERIMENTS.md`, `docs/NEXT_STEP_ASSESSMENT.md` (Phase 2), updated MILESTONES.

## 2. M4 experimental results and conclusions
### Experiment 1 — Vulnerable vs Hardened (authorization axis)
| | Vulnerable | Hardened |
|---|---|---|
| Tool-permission confirmed | TP-001, TP-MT1 | **none** |
| Customer `issue_refund` executions (audit) | 8 | **0 (all rejected)** |

AutoRed confirms the violations on the vulnerable config and reports **zero** on the
hardened config — **no false positives** — distinguishing a *backend* violation
(audit `executed:true`) from the model merely calling the tool. (One orthogonal
prompt-injection finding appeared on the hardened run due to model non-determinism;
it is a true positive on a different axis, reported honestly, not a hardening FP.)

### Experiment 2 — Baseline (fixed) vs Adaptive (LLM) — single trial
| | Baseline | Adaptive | Adaptive held-out (hardened) |
|---|---|---|---|
| Confirmed | **3** | 1 | **0** |
| Probes | 22 | 9 | 6 |
| LLM calls | 0 | 2 | 2 |
| Duration | 246 s | 107 s | 65 s |

**Honest conclusion: adaptive did NOT improve discovery on this target.** The fixed
baseline found more confirmed vulnerabilities; adaptive was more probe-efficient and
faster but found nothing the baseline missed (its one finding is the *same*
tool-permission vuln class). The held-out hardened run confirmed **0** (no
over-claiming). We do **not** claim adaptive improves discovery. Likely causes: a
small, well-covered vulnerability surface, a weak local planner (`llama3.2:3b`), and
a tight budget. Adaptive's intended advantage (unknown/large attack surfaces) is not
exercised by this controlled target, so it is not demonstrated.

### Experiment 3 — Repeated trials (reproducibility / variance)
N=3 trials each (vulnerable):

| | Baseline | Adaptive |
|---|---|---|
| Confirmed (mean, range) | **2.0** (2–2) | **0.67** (0–1) |
| Tool-permission detected | **3/3** | **2/3** |
| Mean probes / LLM calls / duration | 18 / 0 / 195 s | 8 / 2 / 89 s |

**The variance run strengthens the negative result:** the fixed baseline detected the
confirmable vulnerability in **every** trial (zero variance); adaptive **missed it in
1/3** trials. Adaptive is ~2× cheaper but **less reliable and less thorough**. We do
not claim adaptive improvement — the evidence shows the opposite on this target.

## 3. Bugs found and fixed
- **Per-probe timeout killed the whole agent.** A single cold-model "no reply" raised
  `ChatError` out of `assess`, failing the specialist. Fixed: per-probe
  timeouts/ChatErrors are caught as a `verdict=error` and the agent continues.
- **"Adaptive found what baseline missed" mislabeling.** The experiment diffed
  finding *titles*; adaptive's goal-taxonomy title differs from the fixed probe's for
  the *same* vulnerability. Corrected to compare by vulnerability class — adaptive
  found a subset, nothing unique.
- **Vuln-vs-hardened false-positive mislabeling.** The hardening targets *tool
  authorization*; a prompt-injection finding on the hardened run was wrongly counted
  as a false positive. Corrected analysis separates the authorization axis from
  orthogonal model-behavior findings.
- **Store idempotency.** Re-saving a mission overwrote `mode` (a write-once field).
  Fixed the upsert; covered by a test.

## 4. M5 work implemented
`storage/store.py` (SQLite, idempotent upsert, write-once mode, indexed queries),
`reporting/report.py` (reproducible Markdown+JSON from `events.jsonl`), CLI
`missions`/`report`, manager persistence. Tests: `test_storage_reporting.py` (2) incl.
a determinism check.

## 5. Tests and CI status
- Backend: **46 passed** (`pytest`, ~112 s) — unit + real-Chromium E2E + adaptive
  (incl. a fake-planner adaptive loop) + storage/reporting.
- Frontend: **6 passed**; typecheck + build clean; schema v2 synchronized.
- CI: **green** on the M4+M5 commit.

## 6. Commit hashes
- `e99c29f` — M4 adaptive Commander + M5 durable storage/reporting (CI green).
- `f06e009` — repeated-trials variance, Phase-2 assessment, this report (CI green).
- Both pushed to `main`; CI (backend 46 + frontend 6) green on each.

## 7. Remaining problems / limitations
- **Confirmation needs owner-instrumented ground truth** (seeded canaries + audit
  oracle). Un-instrumented real assistants → mostly `inconclusive`. This is the top
  limitation (see `docs/NEXT_STEP_ASSESSMENT.md`).
- **Non-determinism**: cross-run variance in canary leaks; single missions are noisy.
- **Weak local planner**; stronger planners are blocked by the no-paid-API rule.
- **No authorized external target** (ToS/authorization blocker, not a code gap).

## 8. Recommended next action
Build **tester-controlled ground truth + statistical confirmation** (Phase-2
assessment): plant known synthetic data via controlled test accounts through the
product UI and confirm leakage/tool-effects by observation (so AutoRed is its own
oracle without owner instrumentation), and gate `confirmed` on a multi-trial
confirmation rate rather than a single reproduction. This is the highest-leverage
step toward reliable evidence on real, un-instrumented assistants, and it needs no
paid APIs.
