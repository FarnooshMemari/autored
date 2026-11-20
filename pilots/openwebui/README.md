# Real-LLM pilot: AutoRed vs. open-webui (self-hosted)

Reproduces the M3 execution in [../../docs/M3_EXECUTION.md](../../docs/M3_EXECUTION.md).
open-webui is independently developed and used **unmodified**; only the LLM's
system prompt carries **synthetic** canaries. All secrets here are fake.

## Prerequisites
- [Ollama](https://ollama.com) installed; `ollama serve` running.
- AutoRed backend set up (`backend/`), Chromium installed for Playwright.
- open-webui installed in a venv: `uv venv -p 3.11 .owui && uv pip install -p .owui open-webui`

## Steps
```bash
# 1. real LLM + seeded synthetic system prompt (app stays unmodified)
ollama pull llama3.2:1b
ollama create acme-helpdesk -f Modelfile.acme

# 2. launch the unmodified open-webui app wired to the seeded model (port 3000)
./run_owui.sh        # WEBUI_AUTH=False, DEFAULT_MODELS=acme-helpdesk

# 3a. connectivity only (discover + one benign message, no probes)
AUTORED_SCOPE=owui-scope.yaml \
  backend/.venv/bin/python -m autored connectivity-check owui-local --operator you --i-am-authorized

# 3b. full four-agent assessment (authorized on our own instance)
AUTORED_SCOPE=owui-scope.yaml AUTORED_RUNS_DIR=owui-runs \
  backend/.venv/bin/python -m autored run-mission owui-local --operator you --i-am-authorized
```
`owui-scope.yaml` pins open-webui's selectors (its SPA) as the configurable
manual fallback; the discovery/orchestration core is unchanged.
