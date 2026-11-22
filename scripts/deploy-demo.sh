#!/usr/bin/env bash
# Build and deploy the AutoRed PUBLIC READ-ONLY demo dashboard to GitHub Pages.
#
# The demo is a fully static site: no backend, no bearer token, every control
# action disabled (client.ts demo mode). Data is sanitized synthetic JSON +
# recorded synthetic evidence exported by scripts/export_demo_data.py into
# frontend/public/demo/. The private `autored` repo stays private; the demo is
# published from the separate PUBLIC repo `autored-demo` (GitHub Pages free tier).
set -euo pipefail
REPO=FarnooshMemari/autored-demo
BASE=/autored-demo/
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

echo "1/3  Building static demo (VITE_DEMO=1, base=$BASE)…"
cd "$ROOT/frontend"
VITE_DEMO=1 npx vite build --base="$BASE"
touch dist/.nojekyll   # serve folders that would otherwise be ignored by Jekyll

echo "2/3  Publishing dist/ to $REPO (main branch)…"
DEPLOY="$(mktemp -d)"
cp -R dist/. "$DEPLOY/"
cd "$DEPLOY"
git init -b main -q
git add -A
git -c user.name="FarnooshMemari" -c user.email="noreply@users.noreply.github.com" \
    commit -q -m "Deploy AutoRed public read-only demo dashboard"
git remote add origin "https://github.com/$REPO.git"
git push -f -u origin main

echo "3/3  Ensuring GitHub Pages is enabled (main / root)…"
echo '{"source":{"branch":"main","path":"/"}}' | gh api -X POST "repos/$REPO/pages" --input - 2>/dev/null \
  || echo '{"source":{"branch":"main","path":"/"}}' | gh api -X PUT "repos/$REPO/pages" --input - 2>/dev/null || true

echo "Done → https://farnooshmemari.github.io/autored-demo/"
