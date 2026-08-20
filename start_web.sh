#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB_DIR="$ROOT_DIR/web"

PORT="${PORT:-8080}"
EXTRA_ARGS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port)
      if [[ -z "${2:-}" || "${2:-}" == -* ]]; then
        echo "Error: --port requires a port number argument" >&2
        exit 1
      fi
      PORT="$2"
      shift 2
      ;;
    --port=*)
      PORT="${1#*=}"
      shift
      ;;
    -h|--help)
      echo "Usage: $0 [--port <port>] [options]"
      echo ""
      echo "Options:"
      echo "  --port <port>   Set the port to run the server on (default: 8080)"
      echo "  -h, --help          Show this help message"
      exit 0
      ;;
    *)
      EXTRA_ARGS+=("$1")
      shift
      ;;
  esac
done

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

echo "Starting Astro dev server with $JS_RUNNER at http://127.0.0.1:$PORT"
if [ "$JS_RUNNER" = "bun" ]; then
  (cd "$WEB_DIR" && exec bun run dev -- --host 127.0.0.1 --port "$PORT" ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"})
else
  exec npm --prefix "$WEB_DIR" run dev -- --host 127.0.0.1 --force --port "$PORT" ${EXTRA_ARGS[@]+"${EXTRA_ARGS[@]}"}
fi

