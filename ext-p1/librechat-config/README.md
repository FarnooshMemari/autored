# Phase 1 real-world validation harness — LibreChat

Independent OSS target AutoRed was **not** developed against: danny-avila/LibreChat v0.8.9 +
Ollama llama3.2:3b, pinned via `modelSpecs` to an "Acme Outdoor Support" assistant.

## Reproduce
1. `git clone --depth 1 https://github.com/danny-avila/LibreChat ext-p1/LibreChat`
2. `cp .env.example .env`; append `env.overrides`; generate the 5 secrets.
3. Copy `librechat.yaml` (two specs: hardened `acme-support`, weak `acme-support-weak`) and
   `docker-compose.override.yml` (mounts librechat.yaml, host.docker.internal) into the clone.
4. `docker compose up -d`  (needs local Ollama with llama3.2:3b on :11434).
5. Register 5 synthetic accounts (commander/injection/leakage/hierarchy/tools @acme.test);
   mark them `emailVerified:true` in mongo.
6. Start the tool-audit oracle: `uvicorn app:app --port 8200` from `../tools_api`.
7. Point AutoRed at `../librechat-scope.yaml`:
   `AUTORED_SCOPE=.../librechat-scope.yaml AUTORED_RUNS_DIR=.../runs uvicorn autored.main:app --port 8001`
8. Run missions: `POST :8001/api/missions {target_id: librechat|librechat-weak, mode: assess|adaptive|hybrid}`

Targets: `librechat` = hardened (negative control), `librechat-weak` = deliberately-introduced
vulnerability (positive control). All accounts/records/canaries are synthetic.
