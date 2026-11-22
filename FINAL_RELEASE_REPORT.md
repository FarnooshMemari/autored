# AutoRed — Final Release Report

**Date:** 2026-11-22
**Status:** Shipped — committed, pushed, tested, visually complete, and publicly accessible.

AutoRed is a multi-agent AI-red-teaming command center: a Commander orchestrates
four specialist agents (prompt injection, data leakage, instruction hierarchy,
tool permissions) against an authorized chat-assistant target, with
evidence-based verdicts, statistical confirmation, durable missions, and a
premium operations dashboard.

---

## 1. Final GitHub commit

- **Repository (private):** https://github.com/FarnooshMemari/autored
- **Branch:** `main`
- **Release commit SHA:** `28a97d4` (`28a97d4d34dec7939dd7194739bf0b0ea82b6aee`) — carries the full product + this report; a one-line follow-up commit records the confirmed CI status below.
- Commit contains: the completed V3 visual system across all six dashboard
  pages, the public-demo client mode, sanitized demo data, deploy/export
  scripts, and this report. No AI co-author attribution trailers.

## 2. CI results

- **GitHub Actions:** **success** on release commit `28a97d4` (run 45050347618-successor; full suite incl. e2e).
- **Backend:** 46 fast tests pass locally (`pytest -m "not e2e"`); CI runs the
  full suite including the e2e browser missions and crash-recovery tests.
- **Frontend:** 6 Vitest suites pass; `tsc --noEmit` clean; production build clean.

## 3. Public dashboard

- **Public URL (no login):** https://farnooshmemari.github.io/autored-demo/
- **Hosting:** GitHub Pages (free tier), served from the **separate public repo**
  `FarnooshMemari/autored-demo`. The source repo `autored` stays **private**
  (GitHub Pages on a private repo requires a paid plan, so the sanitized static
  build is published from its own public repo instead).
- **Rebuild/redeploy:** `scripts/deploy-demo.sh` (build with `VITE_DEMO=1` +
  `--base=/autored-demo/`, push `dist/` to the public repo, enable Pages).
- **Regenerate demo data:** `scripts/export_demo_data.py` (pulls sanitized
  mission data + recorded evidence from the local backend into
  `frontend/public/demo/`).

## 4. Features available to public visitors

Everything is a **static, read-only** experience backed by sanitized synthetic
data and genuine recorded evidence:

- Open the dashboard with **no authentication**.
- **Mission Control** — the five agent characters with distinct silhouettes and
  live-state expressions; squad composition view.
- **Live Operations** — Commander→specialist coordination constellation with
  delegation probe-counts; selectable inspection workspace; authentic
  **ATTACK → OBSERVED → VERDICT** evidence pipeline; a full-size browser-evidence
  viewer; the Commander decision/delegation console; an activity timeline.
- **Findings Explorer** — every confirmed finding with severity, category,
  reproduction statistics (95% Wilson CI), canary/oracle proof, and the original
  browser screenshot.
- **Experiment Analytics** — Fixed vs Adaptive vs Hybrid comparisons, N=3
  reproducibility, vulnerable-vs-hardened controls, with honest-negative notes.
- **History & Reports** — four curated recorded missions (including an
  **interrupted** mission showing crash-recovery) with reproducible JSON reports.
- **System Health** — recorded operational snapshot.

Curated demo missions: `M-20261122-173200-e6a4` (showcase, 6 confirmed),
`M-INTERRUPTED-DEMO-01` (recovery), `M-20261120-125758-ba8f`,
`M-20261120-004519-e37c`.

## 5. Features intentionally restricted (to protect the system)

- **No backend / no token:** the public build has **no** connection to the
  private API; the bundle carries no bearer token. Verified at runtime — the
  live site issues **only same-origin static requests** (no `/api/`, no
  `127.0.0.1`, no WebSocket).
- **Mission creation disabled** — the Launch control is inert in demo mode.
- **No emergency-stop / admin controls** — replaced with an informational link.
- **No arbitrary target selection or test execution** — visitors cannot drive a
  browser or hit any external site.
- **No live polling** — System Health shows a static recorded snapshot.
- **Sanitized data only** — an export-time gate rejects any forbidden string;
  password field values are masked (`••••`); all canaries/accounts/emails are
  synthetic (`SYS-CANARY-7F3A`, `LEAK-CANARY-91C2`, `dana.synthetic@example.test`).

The private operational environment (local backend on :8000, targets, SQLite
store, event logs, real authentication state) is untouched and never published.

## 6. Public-deployment verification (actual, not just "build passed")

Verified in Chromium against the live URL `https://farnooshmemari.github.io/autored-demo/`:

- ✅ Opens without authentication.
- ✅ Mission Control, Live Operations, and Findings render correctly.
- ✅ Navigation between pages works.
- ✅ Recorded evidence loads (browser screenshots served from the public static
  origin, HTTP 200).
- ✅ No private credentials or sensitive endpoints exposed — network log shows
  only same-origin `*/demo/*.json` and `*/artifacts/*.png`; zero `/api/`,
  `127.0.0.1`, or WebSocket requests.
- ✅ No critical browser console errors.
- ✅ Desktop layout verified at normal zoom.
- ⚠️ Mobile: the responsive layout (breakpoints at 1100/980/760 px for every
  component) is implemented and was verified at device width during development;
  a fresh mobile capture on the deployed URL could not be taken this run because
  the automation window would not re-narrow. No code concern — the same CSS
  serves both environments.

Screenshots: `pilots/screenshots/release/public-*.jpg`,
`pilots/screenshots/p3-v2/v3-*.jpg`.

## 7. Screenshots

- `pilots/screenshots/release/public-mission-control.jpg`
- `pilots/screenshots/release/public-live-operations.jpg`
- `pilots/screenshots/release/public-findings.jpg`
- `pilots/screenshots/release/public-findings-evidence.jpg`
- `pilots/screenshots/p3-v2/v3-mission-control.jpg`
- `pilots/screenshots/p3-v2/v3-operations-specialist.jpg`
- `pilots/screenshots/p3-v2/v3-operations-commander.jpg`

## 8. Private local development environment — startup

```bash
# backend (API on :8000)
cd ~/autored/backend
.venv/bin/uvicorn autored.main:app --host 127.0.0.1 --port 8000

# a self-hosted synthetic target (e.g. AcmeHelp on :8100)
cd ~/autored
backend/.venv/bin/uvicorn target.acmehelp.app:app --port 8100

# dashboard (dev server on :5173, talks to the backend)
cd ~/autored/frontend
npm install && npx vite --port 5173
# open http://localhost:5173
```

- Local LLM planner/tool-calling uses Ollama (`llama3.2:3b`); no paid APIs.
- Tests: `cd backend && .venv/bin/python -m pytest -m "not e2e"` (fast) or without
  the marker for the full suite; `cd frontend && npx vitest run`.
- Rebuild the public demo: `scripts/export_demo_data.py` then `scripts/deploy-demo.sh`.

## 9. Remaining limitations (honest)

- The public demo is a **static snapshot** — no live missions; it reflects the
  curated recorded set only.
- Detection: the fixed probe suite remains the most reliable discoverer; the
  adaptive/hybrid LLM planner is more probe-efficient but does **not** discover
  vulnerability classes the fixed suite misses on these targets (reported as a
  genuine negative in Experiment Analytics).
- Confirming a *user-facing* leak still depends on the model surfacing data; the
  small local planner is weak.
- Crash recovery reconciles interrupted state faithfully but does **not** re-drive
  a half-finished browser mission (contexts are gone).
- No externally-hosted third-party target is included (authorization/ToS), only
  self-hosted synthetic targets and the independently-validated local LibreChat
  harness (see `PHASE1_VALIDATION_REPORT.md`).
- Mobile capture of the deployed URL pending (see §6); layout is responsive by design.
