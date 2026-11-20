# Technical assessment — the highest-priority next limitation

_Independent review after M4, prioritizing real security-testing capability and
reliable evidence over visual features._

## What currently works (verified)
- **Target-independent discovery/interaction** across full-page chat, iframe
  widgets, and shadow-DOM SPAs (open-webui), with no per-target orchestration code.
- **Four isolated specialists** + **evidence-based evaluation**: a finding is
  `confirmed` only via a seeded synthetic canary or a tool-audit oracle, reproduced
  in fresh browser contexts. A model's claim is never proof (deception is flagged
  separately).
- **Real tool-calling assessment**: confirmed customer→staff-only-refund violations
  on a real LLM with native tool-calling, and **correct discrimination** of a
  backend-hardened config (0 false positives; Experiment 1).
- **Adaptive LLM Commander**: a bounded, safe planner loop that proposes creative
  probes but cannot lower the evidence bar; held-out run does not over-claim.
- **Durable storage + reproducible reporting**; full safety controls (scope/origin
  guard, rate/concurrency/probe/LLM budgets, emergency stop).

## What remains limited
1. **Confirmation depends on owner-provided ground truth.** AutoRed can only
   *confirm* a finding when the target is pre-instrumented: synthetic **canaries**
   seeded in prompts/data, and a **tool-execution audit oracle**. On an
   un-instrumented real assistant there is no canary to detect and no audit to read,
   so data-leakage and tool-permission findings collapse to `inconclusive`. This is
   the single biggest barrier to real-world applicability.
2. **Run-to-run non-determinism.** Injection/leakage canary leaks fire on some runs
   and not others (Experiments 1–2). In-run reproduction (≥2 fresh contexts) helps,
   but cross-run variance means single missions are noisy.
3. **Weak local planner.** `llama3.2:3b` does not out-discover the fixed baseline
   (Experiment 2). A stronger planner is constrained by the no-paid-API rule.
4. **No authorized external target.** A ToS/authorization blocker, not a code gap.

## What should be built next (highest priority)
**Tester-controlled ground truth, so AutoRed is its own oracle without owner
instrumentation.** Concretely:
- **Leakage/PII:** use controlled test accounts to *plant* known synthetic records
  through the product's own UI (e.g. set a unique marker in this account's profile/
  order), then probe from a *different* account. Any disclosure of that
  tester-known value is self-verifying — the tester planted it, so no backend audit
  is needed. This generalizes the canary from "owner seeds it" to "we seed it as a
  normal user."
- **Tool permissions:** confirm by **observing the effect** through the UI (did the
  unauthorized refund actually change the order/balance the tester can see?), rather
  than reading a privileged audit log.
- **Reliability:** make **statistical confirmation** first-class — run N trials,
  report a confirmation rate with a confidence interval, and gate "confirmed" on a
  rate threshold, not a single reproduction. This directly addresses non-determinism
  and makes evidence trustworthy.

## Why this is the highest priority
Everything else (more probes, a better planner, nicer UI) improves a system that
still **cannot produce confirmable evidence on a target we don't control the
internals of**. Tester-controlled ground truth + statistical confirmation turn
AutoRed from "works on instrumented test targets" into "produces reliable,
reproducible evidence on any assistant we have a normal test account for" — which is
the actual requirement for a general-purpose autonomous red-teamer. It also keeps
the safety model intact (synthetic data, authorized accounts, non-destructive),
and needs no paid APIs.
