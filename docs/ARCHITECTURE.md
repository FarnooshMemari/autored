# Architecture and decisions

## Flow

```
Operator ──POST /api/missions (target_id, operator, ack)──► MissionManager
   │                                   scope check · expiry · e-stop latch · concurrency
   ▼
Commander (own context, account tester0)
   1 discover   log in, find chat UI by heuristics, verify with a real greeting, parse tools
   2 plan       per-agent probe lists; skip probes whose tools are not authorized/advertised
   3 delegate   task.assigned ──► 4 SpecialistAgents in parallel (semaphore = max_concurrent_agents)
   4 monitor    each candidate finding → commander assigns a `validate` task
   5 validate   specialist replays the probe N times, each in a FRESH context
   6 consolidate  mission.completed summary
Every step ──► MissionEventLog (ordered, persisted JSONL) ──► WebSocket / snapshot reducer
Each context ──► CDP screencast ──► FrameHub ──► /ws/.../frames (binary JPEG)
```

## Decisions (and why)

| Decision | Rationale | Reversible? |
|---|---|---|
| **One BrowserContext per agent**, never shared tabs | Tabs in a context share cookies/storage, so they are one server-side user. Contexts give separate cookie jars; **separate test accounts** give separate server sessions. | n/a (requirement) |
| **Fresh context per validation replay** | A reproduction must not depend on chat history or cookies from the first attempt. | yes |
| **Shared server-side state → named locks** (`Probe.shared_state`) | e.g. the refund ledger. Probes touching it are serialized across agents, and oracle reads are diffed before/after per account, so concurrent agents can't misattribute each other's effects. | yes |
| **Scope enforced twice**: at mission creation *and* at the network layer (`context.route`) | Redirects, injected `<img>`/`fetch` and model-produced links can't leave the allowlist. Blocked requests emit `browser.blocked`. | no: keep it |
| **Verdicts need machine-checkable evidence** | `vulnerable` = seeded synthetic canary in the reply (and not echoed from our prompt) or an audit-oracle record. Heuristic signals give only `inconclusive`. `confirmed` = ≥ `validation_required` of `validation_attempts` fresh replays. | thresholds per target |
| **Event log is the single source of truth** | REST snapshot and the UI reducer are both pure folds over the same events; a parity test replays a real run through both. Reconnects resume with `since=seq`; no gaps, no duplicates. | – |
| **Frames off the JSON stream** | Screencast JPEGs over a separate binary WS, latest-frame-wins with a 2-slot queue. Slow viewers can't backpressure agents or bloat the event log. | yes |
| **Plain asyncio orchestration (not LangGraph yet)** | Planning is deterministic in this slice; the hard problems are cancellation, timeouts and fan-out, which asyncio handles natively. Commander phases map 1:1 to graph nodes, so adopting LangGraph in M4 (LLM planner with adaptive follow-ups) is a refactor, not a rewrite. | yes |
| **Rule-based test target** | Deterministic, offline and free, so CI can assert exact outcomes, with a hardened twin for false-positive checks. AutoRed knows nothing target-specific beyond the scope file. | yes |
| **In-memory mission registry + JSONL persistence** | Enough for a single-node slice. Move to Postgres/Redis when multi-node is needed (M5). | yes |

## Safety controls

- Allowlist + written-authorization record (reference, approver, expiry) per target; operator must acknowledge; recorded in `runs/<id>/authorization.txt`.
- Network-layer origin guard on every agent context; APIRequestContext oracle reads are checked too.
- Probe library is non-destructive. Tools a probe would exercise must be listed in `authorized_tools`, otherwise the Commander skips it with a reason. Tool tests act only on the agent's **own** synthetic order.
- Only dedicated test accounts and synthetic canaries; the platform never asks for or stores real user data. Passwords are masked in events (`••••`).
- Global token-bucket rate limit per target (shared by all agents), per-probe and per-mission timeouts, `max_concurrent_agents`, `max_active_missions`, one mission per target.
- Emergency stop: `POST /api/emergency-stop` cancels every mission, closes all contexts and latches until reset.
- Optional bearer token for the API; binds to localhost by default.

## Assumptions to confirm

1. Targets expose the assistant via a web chat UI reachable after form login. SSO/MFA flows need a pluggable login step (M3).
2. Target owners can provide per-agent test accounts and seed synthetic canaries. Without canaries, almost everything is `inconclusive` by design.
3. Chromium-only (CDP screencast). Firefox/WebKit would fall back to periodic screenshots.
4. The visual team consumes `contracts/` and `frontend/src/integration/slots.tsx` and owns everything visual.
