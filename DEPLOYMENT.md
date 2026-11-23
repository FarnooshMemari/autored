# AutoRed — Public Live Testing: Deployment Guide

This document covers how the "Launch a mission by entering a URL" feature is made
publicly usable **while keeping the existing public URL unchanged** and **without
spending money**.

**Public site (unchanged):** <https://farnooshmemari.github.io/autored-demo/>

---

## 1. Architecture

```
  GitHub Pages (static, FREE, URL unchanged)
    │   Explore Demo  ── recorded missions, works fully offline
    │   Run Live Assessment ── "⚡" connects to a backend YOU run
    ▼  (browser → HTTPS/WSS, CORS-gated)
  AutoRed API (FastAPI)  ── auth token, SSRF guard, per-origin lock, estop, quotas
    ▼
  Mission engine ── Playwright/Chromium (isolated context per agent), event stream
    ▼
  Target ── a site you are authorized to test (or the bundled sandbox)
  (Ollama only for adaptive/hybrid; fixed `assess` runs with 0 LLM calls)
```

The frontend is **already deployed** and static. Making live testing work means
**running the backend somewhere** and pointing the "Run live assessment" button at it.
GitHub Pages cannot run backend code — that is a hard fact, not a limitation we can code around.

---

## 2. The $0 / no-credit-card reality (read before provisioning)

The backend needs a long-running server **plus Chromium** (~1 GB RAM + system libs)
plus optionally an LLM. Here is the honest hosting matrix:

| Option | Runs FastAPI+Chromium? | Permanent free? | No credit card? | Network egress control? | Verdict |
|---|---|---|---|---|---|
| GitHub Pages | ❌ static only | ✅ | ✅ | — | Frontend only |
| Render free | ⚠️ 512 MB, spins down | ✅ | ✅ | ❌ | Too small for Chromium |
| Fly.io free allowance | ✅ | ⚠️ allowance | ❌ card required | ⚠️ limited | Needs a card |
| Railway / Cloud Run / Oracle | ✅ | ⚠️ trial/credits | ❌ card required | partial | Needs a card |
| **Hugging Face Spaces (Docker, 2 vCPU/16 GB)** | ✅ | ✅ | ✅ | ❌ (no egress firewall) | **Only true $0 host** |
| **Your own machine (self-host)** | ✅ | ✅ | ✅ | ✅ (your network) | **Safest $0 option** |

**Two blockers that no code can remove at $0:**

1. **Network-layer egress control is impossible on free shared hosts.** We enforce
   SSRF/DNS/metadata/private-range blocking at the application layer (tested), but a
   true egress firewall needs infrastructure you own. On a free host you only get
   app-layer defence.
2. **Letting the public scan arbitrary third-party sites from a shared host is
   abuse** (and against those hosts' ToS). So a *hosted* public instance is
   **locked to a bundled sandbox target** — it is a live demo, not an open scanner.

**Also:** a *public* HF Space exposes its source; a *private* Space isn't publicly
reachable. Keeping the `autored` repo private therefore conflicts with free public
hosting of the backend's source. (Self-hosting avoids this entirely.)

### Recommended $0 path
- **Primary — self-host + connect:** run `scripts/run-local.sh` (own-target mode) and
  connect from the public site. Genuinely free, safe (your own network + your own
  authorization), tests sites *you* authorize. Nothing to provision.
- **Optional — hosted sandbox demo:** deploy the sandbox-locked Docker image to a free
  HF Space so visitors can watch a *real* live mission against the bundled AcmeHelp
  chatbot (not arbitrary URLs). Requires **your** HF account (free, no card).

### Cost estimates
| Usage | Self-host | HF Space (free CPU) |
|---|---|---|
| Low (occasional demo) | **$0** (your machine) | **$0** (sleeps when idle) |
| Medium (classroom) | **$0** | **$0**, slower; one mission at a time |
| High (always-on, concurrent) | electricity only | needs paid HF hardware (**not $0** — ask first) |

No paid tier is used anywhere in this guide. Nothing here activates billing.

---

## 3. Option A — self-host and connect (no provisioning, do this first)

```bash
# one-time: install deps + browser (see README)
cd backend && uv pip install -p .venv -e '.[dev]' && .venv/bin/playwright install chromium && cd ..

# own-target mode: onboard public URLs you are authorized to test
scripts/run-local.sh
#   → prints a Backend URL (http://localhost:8000) and an access token
```
Then open <https://farnooshmemari.github.io/autored-demo/>, click **⚡ Run live
assessment**, paste the URL + token, and launch. For the bundled sandbox instead:
`scripts/run-local.sh --sandbox`.

---

## 4. Option B — hosted sandbox demo on a free HF Space (needs your approval + account)

> Requires a free Hugging Face account (no credit card). This is the provisioning
> gate — I will not create accounts or push source to a public host without you.

1. Create a **Docker** Space at huggingface.co (free CPU basic hardware).
2. Put the contents of `deploy/hf-space-README.md` as the Space's `README.md`,
   add this repo's `deploy/Dockerfile`, `backend/`, `scope/`, `target/`, `deploy/entrypoint.sh`.
3. Set Space **secrets**: `AUTORED_API_TOKEN`, `AUTORED_ADMIN_TOKEN`.
4. The Space boots the sandbox target + API, locked to `http://127.0.0.1:8100`.
5. Connect the public site's "Run live assessment" to the Space URL + token.

Local equivalent of the hosted image:
```bash
cp deploy/.env.example deploy/.env   # fill in tokens
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up --build
```

---

## 5. Security posture (what is enforced)

Implemented and tested:
- **Access token required** in public mode (app refuses to start without one).
- **SSRF/DNS/metadata/private-range** blocking at the application layer (`onboarding/ssrf.py`).
- **Sandbox lock** — hosted instance onboards only its bundled origin (`AUTORED_DEMO_TARGET_ORIGINS`).
- **Authorization before probes** — domain token or admin approval; a checkbox is not enough.
- **Origin-scoped navigation** — Playwright aborts off-allowlist requests per mission.
- **Rate limits / concurrency / mission timeouts / emergency stop** (existing).
- **CORS allowlist** — only configured origins may call the API from a browser.

Deferred (needs infrastructure you own or fund — not $0):
- Network-layer egress firewall; worker sandboxing between untrusted users;
  multi-tenant user accounts with per-user data partitioning; durable distributed
  queue. On a self-hosted single-operator instance these are not required.

---

## 6. What is NOT done (honest status)
- No backend is currently hosted anywhere. The public URL serves the **static
  two-mode frontend**; "Run live assessment" needs a backend you start (§3) or
  provision (§4).
- Arbitrary-URL public multi-tenant scanning is intentionally **not** shipped — it is
  unsafe at $0 and would make AutoRed an open scanner.
