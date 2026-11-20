# Milestones

| | Scope | Status |
|---|---|---|
| **M0** Contracts | Event schema v1, REST/WS API, slot interfaces, JSON Schema export | **done** |
| **M1** Vertical slice | Scope/authz, origin guard, rate limits, e-stop; isolated contexts; Commander discover/plan/delegate/validate; 4 specialists × 2–3 probes; evidence-based verdicts; live frames; UI shell; 33 backend + 6 frontend tests | **done** |
| **M2** Probe depth | Larger probe library per category (multi-turn, encoding/obfuscation, indirect injection via uploaded docs/URLs on the target); per-target probe config; severity rubric; dedup across agents | next |
| **M3** Real-target readiness | Pluggable login (SSO/MFA/test-token), chat adapters (iframe widgets, streaming replies, shadow DOM), robots/ToS & maintenance-window checks, per-target rate profiles, report export (Markdown/SARIF) | |
| **M4** LLM Commander | LangGraph state graph; LLM planner proposes follow-ups from evidence (bounded by scope and probe allowlist); LLM-assisted *inconclusive* triage; never auto-confirms without canary/oracle evidence | |
| **M5** Platform | Postgres for missions/findings, Redis pub/sub for multi-node streaming, RBAC + audit log, browser worker pool (separate processes), CI against hardened/vulnerable targets | |
| **M6** Viz integration | Design team's animated characters via slots; perf budget for 4 live streams | parallel with M2–M3 |

## Dependencies

Python: fastapi, uvicorn, pydantic v2, playwright (Chromium), pyyaml, python-multipart (target only), httpx/websockets/pytest (dev).
Frontend: react 18, vite 5, typescript 5, vitest. LangGraph and an LLM SDK are deliberately deferred to M4.
