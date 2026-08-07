#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_DIR="$ROOT_DIR/web"

if [ ! -d "$WEB_DIR/node_modules" ]; then
  echo "Installing web dependencies..."
  npm --prefix "$WEB_DIR" install
fi

echo "Starting Astro dev server at http://127.0.0.1:4321"
exec npm --prefix "$WEB_DIR" run dev -- --host 127.0.0.1 --force --port 4321
