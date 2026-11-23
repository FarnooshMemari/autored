#!/usr/bin/env bash
# Start the bundled sandbox chatbot (AcmeHelp) on 8100, then the AutoRed API on $PORT.
# In public mode the API refuses to start without AUTORED_API_TOKEN (see api/app.py),
# and onboarding is locked to AUTORED_DEMO_TARGET_ORIGINS (the sandbox only).
set -euo pipefail
cd /app

if [[ "${AUTORED_PUBLIC_MODE:-0}" == "1" && -z "${AUTORED_API_TOKEN:-}" ]]; then
  echo "FATAL: AUTORED_PUBLIC_MODE=1 requires AUTORED_API_TOKEN (set it as a secret)." >&2
  exit 1
fi

if [[ "${AUTORED_SANDBOX:-0}" == "1" ]]; then
  echo "[entrypoint] starting bundled sandbox target on :8100"
  python -m uvicorn target.acmehelp.app:app --host 127.0.0.1 --port 8100 --log-level warning &
  for i in $(seq 1 30); do
    if python - <<'PY' 2>/dev/null; then break; fi
import socket; s=socket.socket(); s.settimeout(0.5); s.connect(("127.0.0.1",8100)); s.close()
PY
    sleep 0.5
  done
  echo "[entrypoint] sandbox target ready"
fi

echo "[entrypoint] starting AutoRed API on :${PORT:-7860}"
exec python -m uvicorn autored.main:app --host 0.0.0.0 --port "${PORT:-7860}" --log-level warning
