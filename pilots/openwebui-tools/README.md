# M3b pilot: AutoRed vs open-webui with REAL tool-calling (self-hosted)

Reproduces [../../docs/M3B_EXECUTION.md](../../docs/M3B_EXECUTION.md). open-webui is
used **unmodified**; tools are registered through its extension API (not a source
change). All records and secrets are synthetic.

## Prerequisites
- Ollama running; AutoRed backend set up; open-webui installed in a venv
  (`uv venv -p 3.11 .owui && uv pip install -p .owui open-webui`).

## Steps
```bash
ollama pull llama3.2:3b
ollama create acme-tools -f Modelfile.acme-tools         # seeds synthetic system-prompt canaries
./run_owui_tools.sh                                      # launch unmodified open-webui (auth on), port 3000
python setup_owui.py                                     # create accounts, register the audited tool, attach it to the model
# then run AutoRed:
AUTORED_SCOPE=owui-tools-scope.yaml AUTORED_RUNS_DIR=owui-tools-runs \
  backend/.venv/bin/python -m autored run-mission owui-tools --operator you --i-am-authorized
```
`setup_owui.py` also disables open-webui's built-in agentic tools for this model
(`capabilities.builtin_tools=False`) so the small model calls only the support
tools. Scope pins open-webui's selectors (its SPA) as the configurable fallback.

## Evidence in this folder
- `tool_audit_evidence.jsonl` — real tool-execution log (customer-role `issue_refund` executions = the confirmed finding).
- `transcript.md` — verbatim prompts + real-LLM replies + verdicts.
- `evidence-screenshot.png` — browser at a finding.
