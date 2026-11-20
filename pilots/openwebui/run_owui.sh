#!/bin/zsh
# Launch the UNMODIFIED open-webui app, wired to our local Ollama seeded model.
# WEBUI_AUTH=False => single-user instance under our control (no login).
export WEBUI_AUTH=False
export DEFAULT_MODELS=acme-helpdesk
export OLLAMA_BASE_URL=http://127.0.0.1:11434
export ENABLE_OLLAMA_API=True
export WEBUI_NAME="Acme Support"
export ANONYMIZED_TELEMETRY=False
export DO_NOT_TRACK=True
export SCARF_NO_ANALYTICS=True
export PORT=3000
export DATA_DIR="$HOME/autored/ext/owui-data"
exec "$HOME/autored/ext/.owui/bin/open-webui" serve --port 3000
