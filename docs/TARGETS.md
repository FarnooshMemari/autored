# Test targets

AutoRed is validated against self-hosted synthetic targets. All data is
synthetic; canary values live in the scope file. Each target is independent;
the orchestration core contains no target-specific code.

| Target | Port | Chat delivery | Composer | Send | Replies | Proves |
|---|---|---|---|---|---|---|
| **AcmeHelp** (`target/acmehelp`) | 8100 | full-page chat after form login | `textarea` | Send button | synchronous | baseline; vulnerable + hardened modes (regression) |
| **Globex** (`target/globex`) | 8101 | widget inside an **iframe**, opened by a launcher button | `contenteditable` `[role=textbox]` | icon button (`aria-label`) | **streamed** word-by-word | iframe traversal, launcher, contenteditable, streaming, async |
| **Initech** (`target/initech`) | 8102 | **shadow-DOM** web component `<support-bot>` | `textarea` in open shadow root | Enter key or button | async after a `typing…` indicator | shadow-DOM piercing, Enter-to-send, async indicator |

Globex and Initech share a synthetic "assistant brain" (`target/common/`) so the
same probes and canaries evaluate across all three — the DOM and transport differ,
the evaluable behavior does not. AcmeHelp keeps its own copy and is never changed,
so it stays a stable regression target.

## Discovery result per target (auto-discovered, nothing pinned in scope)

| Target | input selector | send | frame |
|---|---|---|---|
| AcmeHelp | `textarea:not([readonly])` | `button:has-text("Send")` (click) | main document |
| Globex | `[contenteditable=true]` | `[aria-label*="send" i]` (click) | **iframe** |
| Initech | `textarea:not([readonly])` | `button:has-text("Send")` (click) | main document (shadow DOM) |

Latest verified run (vulnerable mode, each target): **6 confirmed, 2 passed,
1 not-applicable, 0 suspected, 0 inconclusive**; 26 probe executions; viewport +
26 reply bounding boxes captured for overlay animations.

## Run one

```bash
backend/.venv/bin/uvicorn target.globex.app:app  --port 8101   # or acmehelp:8100 / initech:8102
cd backend && .venv/bin/python -m autored run-mission globex-local --operator you --i-am-authorized
```

## Adding a target

Add a scope entry (allowlist origin, authorization record, synthetic accounts,
canaries, optional `oracle_audit_path`). Pin selectors under `chat:` only if
auto-discovery fails; otherwise leave them out and let the Commander discover
the interface. No core code changes are required to onboard a new interface.
