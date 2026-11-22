# AutoRed — Final Delivery Report (Phases 1–4)

**Date:** 2026-11-22 · **Repo:** github.com/FarnooshMemari/autored · **Tests:** backend 64, frontend 6, CI green each commit.

AutoRed is an autonomous multi-agent AI red-teaming platform: a Commander plus four specialists
(Inky/injection, Vault/leakage, Lexi/hierarchy, Guard/tools) drive isolated browser sessions against
authorized AI chat applications and report **evidence-based**, five-state verdicts.

## Phase 1 — Real-world validation (independent target)
Validated against **LibreChat v0.8.9 + Ollama llama3.2:3b** — an OSS app AutoRed was never built
against. Discovery/login/chat generalized out of the box. Positive/negative controls gave clean
ground truth. **Full writeup: `PHASE1_VALIDATION_REPORT.md`; reproducible harness: `ext-p1/`.**

## Phase 2 — Detection improvements (justified, re-evaluated)
1. **Scope/canary-derived probe identifiers** (replaced a hardcoded AcmeHelp order id). Turned
   cross-account leakage from candidate 1/1 → **confirmed 4/4**, zero new false positives; all three
   in-house targets' e2e preserved.
2. **Scope-aware adaptive planning** — the planner is seeded with scope identifiers (never secret
   values). Adaptive now **discovers leakage** on the positive control (4/4) while the held-out
   hardened scenario stays at **0 confirmed**. Fair Fixed/Adaptive/Hybrid comparison maintained.

## Phase 3 — Premium visual product
Cohesive command-center layer over the dark design system: ambient depth + tactical grid, top-lit
glass panels with hover lift, gradient display titles, instrumentation numerals, **agent character
status rings tied to real cues**, keyboard focus rings, and full `prefers-reduced-motion` support.
All data is real backend data; recorded evidence is explicitly labelled. Verified in Chromium across
**6 pages × desktop + mobile, 0 console errors** (`pilots/screenshots/p3-final/`).

## Phase 4 — End-to-end verification (actual behavior, not just code)
| Journey | Verified by | Status |
|---|---|---|
| Mission creation + all modes (Fixed/Adaptive/Hybrid/Connectivity) | `test_modes_execute_selected_strategy`, live matrix on LibreChat | ✅ |
| Live browser observation | Operations live/recorded frames (screenshots) | ✅ |
| Historical replay + reopen after restart | `test_mission_reopens_after_restart` + Chromium | ✅ |
| Interrupted-mission crash recovery | `test_interrupted_mission_full_recovery` + RECORDED·INTERRUPTED UI | ✅ |
| Findings + evidence (canary/oracle/screenshot) | `test_vulnerable_target_full_mission`, `test_five_state_reporting` | ✅ |
| Reporting (deterministic, reproducible) | `test_report_is_reproducible`, `test_bus_replay_then_live_is_gap_free` | ✅ |
| Security boundaries (scope, e-stop, concurrency, auth) | `test_off_scope_requests_blocked_at_network_layer`, `test_emergency_stop`, `test_concurrency_limit` | ✅ |
| Responsive visual quality (desktop + mobile) | Chromium @1440/390, 0 console errors | ✅ |
| CI + deployment | GitHub Actions green each commit; README + `ext-p1/librechat-config/README.md` | ✅ |

## Known limitations (no overclaiming)
- **Tool-use / deceptive-action classes not assessed on LibreChat** — they need an agent with a tool
  action (LibreChat *Agents*, not *modelSpecs*); reported as not-applicable there, exercised on the
  in-house tool-audit targets.
- One independent target + one local 3B model: *discovery* generalization is demonstrated; broad
  cross-model/robustness claims are not made.
- Positive-control vulnerabilities are **deliberately introduced** and labelled; not upstream defects.
- Crash recovery reconciles interrupted state but does not re-drive a half-finished mission.
- Single-token API auth; no multi-role RBAC. Characters are SVG, not 3D.

## Reproduce the headline demo
1. `cd backend && pytest -q` (unit + e2e against in-house targets).
2. Real-world: follow `ext-p1/librechat-config/README.md`, then run missions on `:8001`
   (`librechat` = hardened / `librechat-weak` = positive control) in each mode.
3. Dashboard: `backend` API + `frontend` Vite; open the mission in Live Operations / Findings / Experiments.
