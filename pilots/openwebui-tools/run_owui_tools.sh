#!/bin/zsh
export WEBUI_AUTH=True
export ENABLE_SIGNUP=True
export DEFAULT_USER_ROLE=user
export ENABLE_LOGIN_FORM=True
export DEFAULT_MODELS=acme-tools
export OLLAMA_BASE_URL=http://127.0.0.1:11434
export WEBUI_NAME="Acme Support"
export WEBUI_SECRET_KEY="autored-local-test-key"
export ANONYMIZED_TELEMETRY=False
export DO_NOT_TRACK=True
export SCARF_NO_ANALYTICS=True
export DATA_DIR="$HOME/autored/ext/owui-tools-data"
export GLOBAL_LOG_LEVEL=DEBUG
exec "$HOME/autored/ext/.owui/bin/open-webui" serve --port 3000
