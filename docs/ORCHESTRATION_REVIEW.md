# Part 3 — Orchestration & dependency review

**Question:** before adding major dependencies, is the current asyncio
orchestration sufficient, or should we adopt LangGraph?

**Decision: keep plain asyncio for now. Do not add LangGraph in Milestone 2.**

## What the orchestration actually has to do today

1. Run a fixed, deterministic pipeline per agent: discover → plan → delegate →
   (assess → validate)×N → consolidate.
2. Fan out four agents with a concurrency cap, isolated browser contexts, a
   shared rate limiter, and named locks for server-side shared state.
3. Stream every step as ordered events and support hard cancellation
   (emergency stop, timeouts) at any point.

These are **control-flow and concurrency** problems. asyncio solves them
directly: `asyncio.gather` + `Semaphore` for fan-out, `wait_for` for timeouts,
`Task.cancel()` + `CancelledError` handlers for the stop path. The code is ~200
lines, fully tested, and has no hidden scheduler.

## What LangGraph would add — and why it isn't justified yet

LangGraph's value is **stateful graphs with cycles, conditional routing, and
checkpoint/resume driven by an LLM** — i.e. when the *plan itself* adapts at
runtime (an LLM reads evidence and decides the next node, with loops and
human-in-the-loop interrupts). Milestone 2's planning is deterministic rule
evaluation, so a graph engine would wrap existing straight-line code in nodes
without removing any real complexity, while adding a dependency, a second
execution model, and another failure surface over the browser/async layer.

| Need | asyncio today | LangGraph |
|---|---|---|
| Deterministic pipeline | ✅ direct | ⚠️ nodes around the same code |
| Parallel agents + concurrency cap | ✅ `gather`/`Semaphore` | ➖ not its job |
| Timeouts + emergency cancel | ✅ `wait_for`/`cancel` | ⚠️ cancel across a graph is harder |
| Ordered real-time events | ✅ event log | ➖ add emitters anyway |
| **Adaptive LLM-driven follow-ups, loops, resume** | ⚠️ hand-rolled | ✅ **its core strength** |

## When we *will* revisit it (Milestone 4)

When the Commander becomes an **LLM planner** that proposes follow-up probes
from observed evidence (bounded by scope and the probe allowlist), with cyclic
"triage → re-probe" loops and checkpoint/resume for long engagements, a graph
model earns its keep. The code is already shaped for that migration: the
Commander's phases (`discover`/`plan`/`_pipeline`/`_finish`) map one-to-one onto
graph nodes, and all state flows through `MissionContext` + the event log, which
is exactly what a LangGraph checkpointer would persist. Adopting it then is a
refactor of `commander.py`, not a rewrite of the system.

## Other dependency choices (unchanged, re-confirmed)

- **Playwright** over raw CDP: cross-frame + shadow-DOM piercing and robust
  waiting are exactly what target-independent discovery needs.
- **Pydantic v2** as the single contract source (JSON Schema + TS mirror).
- **In-memory mission registry + JSONL**: sufficient for one node; Postgres/Redis
  deferred to M5 (multi-node), not needed to prove generalization.
