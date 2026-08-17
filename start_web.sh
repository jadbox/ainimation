#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_DIR="$ROOT_DIR/web"

if command -v bun >/dev/null 2>&1; then
  JS_RUNNER="bun"
else
  JS_RUNNER="npm"
fi

if [ ! -d "$WEB_DIR/node_modules" ]; then
  echo "Installing web dependencies using $JS_RUNNER..."
  if [ "$JS_RUNNER" = "bun" ]; then
    (cd "$WEB_DIR" && bun install)
  else
    npm --prefix "$WEB_DIR" install
  fi
fi

echo "Starting Astro dev server with $JS_RUNNER at http://127.0.0.1:4321"
if [ "$JS_RUNNER" = "bun" ]; then
  (cd "$WEB_DIR" && exec bun run dev -- --host 127.0.0.1 --port 4321)
else
  exec npm --prefix "$WEB_DIR" run dev -- --host 127.0.0.1 --force --port 4321
fi
