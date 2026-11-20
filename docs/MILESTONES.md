# Milestones

| | Scope | Status |
|---|---|---|
| **M0** Contracts | Event schema v1, REST/WS API, slot interfaces, JSON Schema export | **done** |
| **M1** Vertical slice | Scope/authz, origin guard, rate limits, e-stop; isolated contexts; Commander discover/plan/delegate/validate; 4 specialists × 2–3 probes; evidence-based verdicts; live frames; UI shell; 33 backend + 6 frontend tests | **done** |
| **M2** Generalization | Target-independent discovery (iframes, shadow DOM, launchers, async/streaming, Enter-to-send, configurable selectors + manual fallback); 5-state evaluation (confirmed/suspected/inconclusive/passed/not-applicable); viewport+bounding-box events for overlays; assisted-login scaffold; 2 structurally different targets (Globex iframe widget, Initech shadow-DOM) verified with the same core; AcmeHelp kept as regression | **done** |
| **M2b** Probe depth | Larger probe library per category (multi-turn, encoding/obfuscation, indirect injection via uploaded docs/URLs); per-target probe config; severity rubric; dedup across agents | next |
| **M3** Real-world validation pilot | **Executed** against a real LLM: unmodified open-webui + `llama3.2:1b`, self-hosted. See [M3_EXECUTION.md](M3_EXECUTION.md). External candidates (Lakera, HTB) reviewed and **not** run (automation permission unverifiable). Built: authorization gate, connectivity harness, overlay dismissal. | **done (self-hosted)** |
| **M3b** Full multi-agent validation with real tool-calling | **Executed** against unmodified open-webui + `llama3.2:3b` with **real native tool-calling** and an **auditable tool-execution log**; four isolated test accounts; all four categories + **multi-turn** + indirect-injection + deception detection. **2 confirmed** critical tool-permission violations (incl. a multi-turn attack), reproduced 4/4 via the audit oracle; 7 passed, 1 n/a. See [M3B_EXECUTION.md](M3B_EXECUTION.md). Also: echo-guarded weak signals (PI-003 fix), per-probe error isolation, `oracle_file`, multi-turn probe support. | **done (self-hosted)** |
| **M4** LLM Commander | LangGraph state graph; LLM planner proposes follow-ups from evidence (bounded by scope and probe allowlist); LLM-assisted *inconclusive* triage; never auto-confirms without canary/oracle evidence | |
| **M5** Platform | Postgres for missions/findings, Redis pub/sub for multi-node streaming, RBAC + audit log, browser worker pool (separate processes), CI against hardened/vulnerable targets | |
| **M6** Viz integration | Design team's animated characters via slots; perf budget for 4 live streams | parallel with M2–M3 |

## Dependencies

Python: fastapi, uvicorn, pydantic v2, playwright (Chromium), pyyaml, python-multipart (target only), httpx/websockets/pytest (dev).
Frontend: react 18, vite 5, typescript 5, vitest. LangGraph and an LLM SDK are deliberately deferred to M4.
