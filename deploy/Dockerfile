# AutoRed hosted backend — sandbox-locked public demo OR self-hosted live backend.
#
# Base image already ships Chromium + all OS libraries Playwright needs, pinned to
# the same Playwright version as pyproject.toml (1.55.0).
FROM mcr.microsoft.com/playwright/python:v1.55.0-noble

# ---- app ----
WORKDIR /app
COPY backend/pyproject.toml backend/pyproject.toml
# install deps first (cache layer); the editable install needs the package tree, so
# copy it before `pip install -e`.
COPY backend/ backend/
COPY scope/ scope/
COPY target/ target/
RUN pip install --no-cache-dir -e ./backend

# Chromium is already in the base image; make sure the matching browser is present.
RUN python -m playwright install chromium

# ---- runtime ----
# HF Spaces inject PORT=7860; default to it. The API binds 0.0.0.0 so the platform
# can route to it. A token is REQUIRED in public mode (entrypoint enforces via app).
ENV PORT=7860 \
    AUTORED_HEADLESS=1 \
    AUTORED_RUNS_DIR=/app/runs \
    AUTORED_PUBLIC_MODE=1 \
    AUTORED_ALLOW_PRIVATE_TARGETS=1 \
    AUTORED_DEMO_TARGET_ORIGINS=http://127.0.0.1:8100 \
    AUTORED_SANDBOX=1
# AUTORED_API_TOKEN, AUTORED_ADMIN_TOKEN and AUTORED_CORS_ORIGINS come from secrets.

RUN mkdir -p /app/runs && chmod 777 /app/runs
COPY deploy/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

EXPOSE 7860
ENTRYPOINT ["/app/entrypoint.sh"]
