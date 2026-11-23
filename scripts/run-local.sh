#!/usr/bin/env bash
# One command to run a REAL AutoRed backend locally that the public demo site can
# drive. Tests ONLY targets you are authorized to assess.
#
#   scripts/run-local.sh            # your-own-target mode (public URLs, you authorize)
#   scripts/run-local.sh --sandbox  # bundled AcmeHelp sandbox demo (loopback only)
#
# After it prints "ready", open https://farnooshmemari.github.io/autored-demo/ ,
# click "Run live assessment", and connect to the URL + token shown below.
set -euo pipefail
cd "$(dirname "$0")/.."

TOKEN="${AUTORED_API_TOKEN:-$(python3 -c 'import secrets;print(secrets.token_urlsafe(24))')}"
PORT="${PORT:-8000}"
export AUTORED_API_TOKEN="$TOKEN"
export AUTORED_PUBLIC_MODE=1
export AUTORED_ADMIN_TOKEN="${AUTORED_ADMIN_TOKEN:-$(python3 -c 'import secrets;print(secrets.token_urlsafe(16))')}"
export AUTORED_CORS_ORIGINS="${AUTORED_CORS_ORIGINS:-https://farnooshmemari.github.io,http://localhost:5173}"
export AUTORED_HEADLESS="${AUTORED_HEADLESS:-1}"

if [[ "${1:-}" == "--sandbox" ]]; then
  export AUTORED_ALLOW_PRIVATE_TARGETS=1
  export AUTORED_DEMO_TARGET_ORIGINS="http://127.0.0.1:8100"
  echo "[run-local] starting bundled sandbox target on :8100"
  backend/.venv/bin/uvicorn target.acmehelp.app:app --port 8100 --log-level warning &
  sleep 2
else
  export AUTORED_ALLOW_PRIVATE_TARGETS=0
  export AUTORED_DEMO_TARGET_ORIGINS=""
  echo "[run-local] own-target mode: you may onboard public URLs you are authorized to test"
fi

cat <<EOF

  ──────────────────────────────────────────────────────────────
   AutoRed live backend starting on  http://localhost:${PORT}
   Connect from the public site with:
     Backend URL:  http://localhost:${PORT}
     Access token: ${TOKEN}
   (CORS allows: ${AUTORED_CORS_ORIGINS})
  ──────────────────────────────────────────────────────────────

EOF

exec backend/.venv/bin/uvicorn autored.main:app --host 127.0.0.1 --port "${PORT}" --log-level warning
