---
title: AutoRed Live Backend (Sandbox Demo)
emoji: 🛡️
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# AutoRed — hosted sandbox backend

A live AutoRed backend locked to a single **bundled sandbox chatbot** (AcmeHelp).
It runs real missions — Commander + four specialists in isolated Chromium contexts,
real evidence, real findings — but it is **not** an open scanner: onboarding only
accepts the bundled target origin (`AUTORED_DEMO_TARGET_ORIGINS`).

Connect to it from the public dashboard at
<https://farnooshmemari.github.io/autored-demo/> → **Run live assessment**.

## Required Space secrets
- `AUTORED_API_TOKEN` — bearer token the frontend must send.
- `AUTORED_ADMIN_TOKEN` — admin approval for the sandbox target.

Also set `AUTORED_CORS_ORIGINS` (variable) to include the dashboard origin, e.g.
`https://farnooshmemari.github.io`.

This Space uses only free CPU hardware. Adaptive/hybrid planning (Ollama) is
disabled here; the fixed `assess` suite runs with zero LLM calls.
