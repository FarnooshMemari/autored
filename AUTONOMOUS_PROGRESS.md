# AutoRed — Autonomous execution checkpoint (M6: product completion)

_Living checkpoint. Update after each increment so work resumes after interruption._

## Last successful commit
`2f6b79c` (CI green). Working tree clean at session start.

## Baseline that must be preserved (verified working)
Backend 46 tests + frontend 6 green; M1–M5 shipped: target-independent discovery,
4 isolated specialists, evidence-based eval (canary/oracle + reproduction), real
tool-calling assessment (confirmed tool-permission violations), adaptive LLM
Commander (honest negative vs baseline), durable SQLite store + reproducible reports,
full safety controls. Do NOT rebuild; extend.

## Plan (priority order; each increment: implement → test → commit → push → CI → inspect)
- [ ] M6.1 Agent identities: Inky(injection/purple) Vault(leakage/orange) Lexi(hierarchy/blue) Guard(tools/green) + Commander. Backend manifest + colors.
- [ ] M6.2 Statistical confirmation: confirmation rate + Wilson 95% CI + uncertainty surfaced in findings & reports (addresses the #1 reliability limitation).
- [ ] M6.3 Tester-controlled ground truth: runtime-planted unique markers for cross-account leakage, verified without owner audit (vulnerable/hardened).
- [ ] M6.4 Dashboard (major): polished dark-first React UI on real backend data — Mission Control, Live Agent Ops (characters + states), Browser Workspace (live frames + coordinate overlays), Findings Explorer, Evidence Inspector, Experiment Analytics, Mission History, Reporting. Inspect in a real browser.
- [ ] M6.5 Experiments A–F with honest reporting (incl. negatives, uncertainty).
- [ ] M6.6 Recovery/resume investigation + checkpoint discipline.
- [ ] M6.7 Final docs + PRODUCT_DELIVERY_REPORT.md + dashboard screenshots.

## Known failures / limits carried in
- Confirmation needs owner-instrumented ground truth (addressed by M6.2/M6.3).
- Non-determinism; small local planner; no authorized external target.

## Critical self-checks (apply at each milestone)
Is it actually working (not just code)? Simulated vs real success? False positive?
Generalizes beyond the dev target? Simpler/more reliable option? Evidence strong enough?

## Exact next action
Implement M6.1 (agent identities) then M6.2 (statistical confirmation).
