# AutoRed — Verification Matrix

Every capability, how it was verified, and its honest status. "Verified" = exercised
against real code/data (test, live experiment, or Chromium inspection), not asserted.

## Acceptance criteria (mandate §13)
| # | Criterion | Verified by | Status |
|---|---|---|---|
| 1 | Starts from documented instructions | README run guide; servers started this session | ✅ |
| 2 | Frontend + backend work together | Chromium drove the live dashboard against the API | ✅ |
| 3 | Five agents operate through real workflows | live missions; `test_e2e` full-mission | ✅ |
| 4 | Configure + run an assessment | `controls.py` (launch gating + real mission creation) | ✅ |
| 5 | Browser interaction observable | Operations view: real frames + coordinate overlays (screenshots) | ✅ |
| 6 | Findings backed by reproducible evidence | canary/oracle + fresh-context reproduction + Wilson CI | ✅ |
| 7 | Reports generated + reopened | `autored report`; durable History + `/api/.../report`; completed **and interrupted** missions reopen after restart | ✅ |
| 8 | Dashboard polished, responsive, functional | Chromium QA @1440/390px: 0 overflow, 0 console errors | ✅ |
| 9 | Experiments evaluate honestly | Experiments A–F, negatives reported | ✅ |
| 9b | Real-world validation on independent target | LibreChat+Ollama: pos/neg controls, Fixed/Adaptive/Hybrid, cross-target fix (PHASE1_VALIDATION_REPORT.md) | ✅ |
| 10 | Failure & recovery paths tested | e-stop, timeouts, per-probe, **kill -9 crash recovery**; interrupted missions reconciled (phase/summary/metadata preserved) — `test_recovery`, `test_interrupted_mission_full_recovery` | ✅ |
| 11 | Automated tests + CI pass | backend 64, frontend 6; CI green each commit | ✅ |
| 12 | End-to-end demonstration | live acmehelp mission → 6/6 confirmed in the dashboard | ✅ |
| 13 | Limitations documented without overstating | this file + PRODUCT_DELIVERY_REPORT + NEXT_STEP_ASSESSMENT | ✅ |

## Capabilities
| Capability | Verified by | Status |
|---|---|---|
| Target-independent discovery (iframe/shadow-DOM/SPA) | `test_generalization` (Globex/Initech) + open-webui | ✅ |
| Isolated specialists, per-account sessions | `test_e2e` (distinct contexts/accounts) | ✅ |
| Evidence-based evaluation (canary/oracle) | `test_events_and_probes` | ✅ |
| Reproduction + statistical confirmation (Wilson CI) | `test_wilson_ci`; shown in Findings/reports | ✅ |
| Real tool-calling + audit oracle | open-webui + llama3.2:3b (Exp A/B/D/E) | ✅ |
| Adaptive LLM Commander | `test_adaptive` + Exp B | ✅ |
| Hybrid (fixed + adaptive) | `test_hybrid_runs_fixed_then_adaptive` + Exp B+ | ✅ |
| Tester-controlled ground truth (no owner seeding) | Exp D (plant runtime marker, verify cross-account) | ✅ |
| Deception detection (positive + negative) | `test_deception_...` (controlled) + Exp E (real model) | ✅ |
| Crash recovery / reconciliation | `test_recovery` + live kill -9 | ✅ |
| Durable storage + reproducible reports | `test_storage_reporting`; History survives restart | ✅ |
| API authorization + path-traversal resistance | `test_security` (3) | ✅ |
| Safety: scope/origin guard/rate/concurrency/e-stop | `test_scope_and_limits`, `test_e2e` | ✅ |
| Dashboard: 6 views + 5 characters + mobile | Chromium screenshots (pilots/screenshots/final/, desktop+mobile) | ✅ |
| Assessment modes (Fixed/Adaptive/Hybrid/Connectivity) execute | `test_modes_persistence::test_modes_execute_selected_strategy` | ✅ |
| Mission reopening after server restart | `test_modes_persistence::test_mission_reopens_after_restart` + Chromium | ✅ |
| Recorded evidence vs live streams distinguished | Operations RECORDED badges + "recorded" header (screenshots) | ✅ |
| Loading / error / empty states | explicit states in App/useMission (no silent empty pages) | ✅ |

## Experiments (real runs; pilots/experiments/*.json)
| Exp | What | Result | Status |
|---|---|---|---|
| A | Vulnerable vs Hardened | 0 false positives on hardened (0 customer executions) | ✅ |
| B | Fixed vs Adaptive (+N=3 variance) | honest negative: fixed more reliable (3/3 vs 2/3) | ✅ |
| B+ | Fixed vs Adaptive vs Hybrid | see docs/EXPERIMENTS.md | ✅ |
| C | Held-out (hardened, undesigned) | adaptive 0 confirmed, no over-claiming | ✅ |
| D | Cross-account, tester-controlled | method works; latent over-permission surfaced | ✅ |
| E | Deception | 0 deceptive claims (real model) + controlled positive | ✅ |
| F | Reliability / crash recovery | kill -9 reconciled to interrupted, no data loss | ✅ |

## Outstanding limitations (honest)
- No **externally-hosted** third-party target tested (authorization/ToS; not a code gap).
- Confirming a *user-facing* leak still depends on the model surfacing data; the small
  local planner is weak and adaptive does not beat the fixed baseline.
- Characters are SVG "3D-inspired", not true 3D. RBAC is a single bearer token.
- Crash recovery reconciles state honestly but does not **re-drive** a half-finished
  browser mission (contexts are gone).
